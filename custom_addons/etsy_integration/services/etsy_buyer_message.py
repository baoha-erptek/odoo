"""Etsy buyer-message email fallback (Spec 003 P1-MSG-EMAIL-FALLBACK scaffold).

Pure-function detection + ingestion of Etsy "buyer messaged you"
notification emails. Standalone module — does NOT modify the existing
order-receipt parser (`email_parser.py`). The Gmail/email cron wiring
that calls `ingest_buyer_message_email` per fetched email is a follow-up.

Dedupes via `etsy.message.dedupe` (already shipped by P3-LEAD-DEDUPE)
so the future API path (P1-MSG-API-PULL) and this email path can run
concurrently without double-posting the same message.

Routes the message body to `sale.order.message_post` when the receipt
id in the email body matches an existing Odoo order. Falls back
gracefully (logs + audits) when the order is not found.
"""

import hashlib
import logging
import re

_logger = logging.getLogger(__name__)


# Etsy buyer-message notification subjects observed in production:
#   "<Shop> Owner — New message from <buyer>"
#   "You have a new message from <buyer> on Etsy"
#   "<buyer> sent you a message about <listing>"
_SUBJECT_PATTERNS = [
    re.compile(r'\bnew\s+message\s+from\b', re.IGNORECASE),
    re.compile(r'\bsent\s+you\s+a\s+message\b', re.IGNORECASE),
    re.compile(r'\bmessaged\s+you\b', re.IGNORECASE),
    re.compile(r'\bbuyer\s+message\b', re.IGNORECASE),
]

# Receipt-id pattern in the email body — Etsy embeds the receipt id as
# part of the "view your order" link or in the body text itself.
_RECEIPT_ID_PATTERN = re.compile(
    r'(?:receipt[_\s-]?id|order[_\s-]?id|/your/orders/sold/[^/]+/(\d+))[^0-9]*(\d{6,})',
    re.IGNORECASE,
)


def is_buyer_message_email(subject):
    """Return True if the email subject matches a buyer-message notification."""
    if not subject:
        return False
    text = subject.strip()
    return any(p.search(text) for p in _SUBJECT_PATTERNS)


def parse_buyer_message_email(subject, body):
    """Extract structured fields from a buyer-message notification email.

    Returns a dict with keys:
      - is_buyer_message: bool (False → caller skips)
      - etsy_order_id: str | None (receipt id from body, if found)
      - message_id: str (stable hash for dedupe — sha256(subject+date+body[:200]))
      - message_excerpt: str (first 4000 chars of body, for posting)

    The message_id hash is deterministic across re-fetches so a re-delivered
    email doesn't create a second `etsy.message.dedupe` row.
    """
    if not is_buyer_message_email(subject):
        return {'is_buyer_message': False}
    body = body or ''
    receipt_match = _RECEIPT_ID_PATTERN.search(body)
    receipt_id = None
    if receipt_match:
        # The pattern has two capture groups; take whichever is non-empty.
        receipt_id = receipt_match.group(1) or receipt_match.group(2)
    digest_input = (subject or '') + '|' + (body[:200] or '')
    message_id = 'email-' + hashlib.sha256(digest_input.encode('utf-8')).hexdigest()[:32]
    return {
        'is_buyer_message': True,
        'etsy_order_id': receipt_id,
        'message_id': message_id,
        'message_excerpt': body[:4000],
    }


def ingest_buyer_message_email(env, shop, parsed):
    """Post the message to the matched sale.order; dedupe via etsy.message.dedupe.

    Returns one of:
      - 'posted' — message landed on a matched order
      - 'duplicate' — already seen via etsy.message.dedupe
      - 'no_order' — receipt id missing or unmatched (logged + audited)
      - 'skipped' — not a buyer-message email

    All branches are safe to call from a swallowing cron.
    """
    if not parsed.get('is_buyer_message'):
        return 'skipped'
    Dedupe = env['etsy.message.dedupe'].sudo()
    if Dedupe.search_count([
        ('etsy_shop_id', '=', shop.id),
        ('etsy_message_id', '=', parsed['message_id']),
    ]):
        return 'duplicate'
    receipt_id = parsed.get('etsy_order_id')
    order = env['sale.order'].sudo().search([
        ('etsy_shop_id', '=', shop.id),
        ('etsy_order_id', '=', receipt_id),
    ], limit=1) if receipt_id else env['sale.order']
    from odoo import fields as ofields
    body = parsed.get('message_excerpt') or ''
    body_hash = (
        hashlib.sha256(body.encode('utf-8')).hexdigest()[:16] if body else ''
    )
    target_kwargs = {
        'channel': 'email',
        'posted_at': ofields.Datetime.now(),
        'body_sha256_prefix': body_hash,
        'payload_excerpt': body[:256],
    }
    if order:
        target_kwargs['target_sale_order_id'] = order.id
        target_kwargs['state'] = 'posted'
    else:
        target_kwargs['pending_target_receipt_id'] = receipt_id or ''
        target_kwargs['state'] = 'buffered'
    Dedupe.create({
        'etsy_shop_id': shop.id,
        'etsy_message_id': parsed['message_id'],
        **target_kwargs,
    })
    if not order:
        _logger.info(
            "Etsy buyer message buffered: shop=%s receipt=%r message_id=%s",
            shop.name, receipt_id, parsed['message_id'],
        )
        return 'no_order'
    body = parsed.get('message_excerpt') or ''
    order.with_user(env.ref('base.user_root')).message_post(
        body=body, subtype_xmlid='mail.mt_comment',
    )
    return 'posted'
