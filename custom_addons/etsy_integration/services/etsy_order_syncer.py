"""EtsyOrderSyncer — incremental receipts orchestrator (P0-16c).

Drives one shop's API sync cycle: read cursor → adapter pages → ingestor
writes → advance cursor per successful payload. Audit-mode short-circuit
(architect Q4) skips the ingestor and emits `_logger.warning` per
receipt; the future `etsy.api.log` model (P0-17) will retrofit a
durable audit trail behind the same call site.

Lifecycle: per cron tick. The cron calls `sync_shop_orders(shop)` for
each `sync_mode='api_only'` shop; per-shop exceptions are caught at
the cron level (see `etsy.shop._cron_sync_orders`) so one bad shop
does not poison the rest.

Cursor semantics (OQ3): per-payload advancement. After each successful
`ingestor.ingest`, the shop's `etsy_last_receipt_sync_at` is written
to that payload's `last_modified` (or `order_date` fallback). A
mid-iteration error leaves the cursor at the last successful payload's
timestamp — re-running the cron resumes from there. This trades extra
DB writes (one per ingest) for crash safety; at 5-minute cadence the
write volume is well within budget.
"""

import logging

from .etsy_api_adapter import EtsyApiAdapter
from .etsy_api_client import EtsyApiClient
from .etsy_order_ingestor import EtsyOrderIngestor

_logger = logging.getLogger(__name__)


class EtsyOrderSyncer:
    """One-shop sync orchestrator. Stateless; build per cron tick."""

    def __init__(self, env):
        self._env = env

    def sync_shop_orders(self, shop):
        """Run one sync pass for `shop`.

        - audit mode (`shop.sync_audit_mode=True`): fetch + log only
        - normal mode: fetch + ingest + advance cursor per-payload

        Returns a dict of `{ingested, audited, errors}` counts for
        operational visibility. The sync_audit_mode + sync_mode='api_only'
        combination is nonsensical (architect Q4 / OQ4) but allowed —
        we log a soft warning and proceed in audit mode.
        """
        if shop.sync_audit_mode and shop.sync_mode == 'api_only':
            _logger.warning(
                'Shop %s (id=%s): sync_audit_mode=True with '
                'sync_mode=api_only is nonsensical (audit is for '
                'pre-cutover validation, api_only means cutover already '
                'happened). Running audit anyway; consider setting '
                'sync_audit_mode=False.',
                shop.name, shop.id,
            )

        # Refuse to call Etsy without the real shop_id. Per
        # P1-11-RUNBOOK 2026-05-22 finding: the sandbox convention of
        # equating Odoo PK to Etsy shop_id breaks on real shops (Etsy
        # 403 "User does not own Shop {odoo_id}"). The bootstrap of
        # this field from /users/me is deferred to P1-11-SHOPID-BOOTSTRAP.
        api_shop_id = shop.sudo().etsy_api_shop_id
        if not api_shop_id:
            _logger.warning(
                'Etsy sync: shop %s (id=%s) has no etsy_api_shop_id; '
                'skipping. Set Etsy Shop ID in the shop form (admin) '
                'or re-Authorize Etsy once auto-bootstrap lands.',
                shop.name, shop.id,
            )
            return {'ingested': 0, 'audited': 0}

        adapter = self._build_adapter(shop)
        # Cursor is system-only (group_system ACL on the field). The
        # cron runs as `__system__`, so direct read works; explicit
        # sudo() removed when the field's ACL gate was tightened in
        # P0-16b1 and the cron never elevates.
        since = shop.etsy_last_receipt_sync_at or None
        ingestor = EtsyOrderIngestor(self._env) if not shop.sync_audit_mode else None

        ingested = 0
        audited = 0
        last_seen = since

        for payload in adapter.fetch_new_orders(api_shop_id, since):
            payload_ts = payload.last_modified or payload.order_date
            try:
                if shop.sync_audit_mode:
                    self._audit_log(shop, payload)
                    audited += 1
                else:
                    ingestor.ingest(payload, shop)
                    ingested += 1
            except Exception:
                _logger.exception(
                    'Etsy sync: shop %s receipt %s ingest failed; '
                    'cursor stays at %s.',
                    shop.name, payload.etsy_order_id, last_seen,
                )
                # OQ3: do NOT advance cursor on failure; bail so the
                # next cron tick re-fetches from the last good point.
                break

            if payload_ts and (last_seen is None or payload_ts > last_seen):
                last_seen = payload_ts
                shop.etsy_last_receipt_sync_at = payload_ts

        if last_seen and last_seen != since:
            _logger.info(
                'Etsy sync: shop %s — ingested=%d audited=%d cursor→%s',
                shop.name, ingested, audited, last_seen,
            )

        return {'ingested': ingested, 'audited': audited}

    def _build_adapter(self, shop):
        """Factory hook — overridable by tests via mock.patch."""
        client = EtsyApiClient(shop)
        return EtsyApiAdapter(client)

    def _audit_log(self, shop, payload):
        """Audit-mode receipt log. P0-17: writes one `etsy.api.log`
        row per receipt with `source='audit'`. PII (buyer_name,
        buyer_email, addresses) is intentionally absent from
        `response_summary` — receipt_id + amount + currency are
        sufficient for BA reconciliation against the GKE spreadsheet,
        and `etsy.api.log` itself carries `etsy_api_log_reader` ACL,
        not unrestricted operator read.
        """
        # sudo(): bypasses the etsy.api.log ACL gate (system-only
        # create per security/ir.model.access.csv). The cron context
        # is already __system__ so this is defensive redundancy — but
        # it also lets a future manual admin trigger of sync_shop_orders
        # write the audit row without elevating the caller's session.
        self._env['etsy.api.log'].sudo().create({
            'shop_id': shop.id,
            'endpoint': 'GET /v3/application/shops/%s/receipts (audit mode)' % (
                shop.sudo().etsy_api_shop_id or shop.id,
            ),
            'source': 'audit',
            'response_summary': (
                'audit: receipt %s amount=%s %s — '
                'no sale.order written (sync_audit_mode=True).'
                % (payload.etsy_order_id, payload.amount_total, payload.currency)
            ),
        })
