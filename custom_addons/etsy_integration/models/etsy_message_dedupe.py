"""etsy.message.dedupe — first-seen ledger for Etsy buyer messages across channels.

Per spec 007 data-model.md §2. Deduplicates inbound messages between Etsy
conversation API (P1-MSG-API-PULL) and email-fallback parser
(P1-MSG-EMAIL-FALLBACK), buffers messages whose target order has not yet
ingested, and retains state for audit.

Deliberately does NOT inherit `mail.thread` — high-volume table, mirrors
`etsy.api.log` precedent (chatter would balloon storage).

Constraints:
- UNIQUE(etsy_shop_id, etsy_message_id): mirrored in `init()` per
  `project_sql_constraints_drift.md` (5th confirmation).
- C-EMD-001 XOR target: state='posted' requires exactly one of
  target_sale_order_id / target_enquiry_id / pending_target_receipt_id;
  state='buffered' requires only pending_target_receipt_id.

Retention (FR-035 hygiene):
- state='posted' rows older than 30 days → deleted by daily cron.
- state='buffered' rows older than 7 days → flipped to 'orphaned' (BA review).
- state='orphaned' rows are kept indefinitely.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Body excerpt is bounded by FR-015 audit policy: 256 chars is enough to
# hash-lookup or recognize the message; full body lives in mail.message.
_PAYLOAD_EXCERPT_MAX = 256

# Retention windows. Owner can adjust via ICPs in a follow-up slice if
# operational data shows pressure.
_POSTED_RETENTION_DAYS = 30
_BUFFERED_AGEOUT_DAYS = 7

_CHANNEL_SELECTION = [
    ('api', 'Etsy Conversations API'),
    ('email', 'Email Fallback Parser'),
]

_STATE_SELECTION = [
    ('posted', 'Posted'),
    ('buffered', 'Buffered'),
    ('orphaned', 'Orphaned'),
]


class EtsyMessageDedupe(models.Model):
    _name = 'etsy.message.dedupe'
    _description = 'Etsy Message Dedupe Ledger'
    _order = 'posted_at desc, id desc'

    etsy_shop_id = fields.Many2one(
        'etsy.shop', string='Etsy Shop',
        required=True, ondelete='cascade', index=True,
    )
    etsy_message_id = fields.Char(
        string='Message ID', required=True, index=True,
        help='Real Etsy conversation_id+message_id, or synthesized for email-fallback',
    )
    body_sha256_prefix = fields.Char(
        string='Body SHA-256 Prefix', size=16, index=True,
        help='First 16 hex chars of SHA-256(body). Used to reconcile API+email '
             'arrivals of the same logical message.',
    )
    channel = fields.Selection(
        _CHANNEL_SELECTION, string='Channel', required=True,
    )
    posted_at = fields.Datetime(
        string='Posted At', required=True,
        help='Buyer-side timestamp from API or email Date header (UTC).',
    )
    target_sale_order_id = fields.Many2one(
        'sale.order', string='Target Sale Order',
        ondelete='set null',
    )
    target_enquiry_id = fields.Many2one(
        'multichannel.enquiry', string='Target Enquiry',
        ondelete='set null',
    )
    pending_target_receipt_id = fields.Char(
        string='Pending Receipt ID', index=True,
        help='Etsy receipt_id when message arrived before order ingestion. '
             'Cleared when state flips to posted.',
    )
    state = fields.Selection(
        _STATE_SELECTION, string='State', required=True, default='posted',
    )
    payload_excerpt = fields.Char(
        string='Payload Excerpt', size=_PAYLOAD_EXCERPT_MAX,
        help='First 256 chars of the message body for audit debugging. '
             'Full body lives in mail.message.',
    )

    _sql_constraints = [
        (
            'uniq_emd_shop_message_id',
            'UNIQUE(etsy_shop_id, etsy_message_id)',
            'A message with this ID has already been recorded for this shop.',
        ),
    ]

    def init(self):
        """Create DB-level objects that Odoo's declarative path may miss.

        - UNIQUE(etsy_shop_id, etsy_message_id): mirrored from _sql_constraints
          per memory project_sql_constraints_drift.md (5th confirmation).
        - Partial index idx_emd_pending on (etsy_shop_id, pending_target_receipt_id)
          WHERE state='buffered': supports buffer-replay cron sweep cheaply.
        """
        cr = self.env.cr
        # ALTER TABLE ADD CONSTRAINT is not idempotent; pre-check pg_constraint
        # so re-runs (-u etsy_integration) silently no-op. Catching
        # duplicate_object alone is not enough — PG creates an index with
        # the constraint name and raises duplicate_table (42P07) on re-run.
        cr.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'etsy_message_dedupe_uniq_emd_shop_message_id'
                ) THEN
                    ALTER TABLE etsy_message_dedupe
                        ADD CONSTRAINT etsy_message_dedupe_uniq_emd_shop_message_id
                        UNIQUE (etsy_shop_id, etsy_message_id);
                END IF;
            END $$
        """)
        cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_emd_pending
                ON etsy_message_dedupe (etsy_shop_id, pending_target_receipt_id)
                WHERE state = 'buffered'
        """)

    @api.constrains(
        'state',
        'target_sale_order_id',
        'target_enquiry_id',
        'pending_target_receipt_id',
    )
    def _check_xor_target(self):
        """C-EMD-001: enforce XOR target semantics by state.

        - state='posted': exactly one of (target_sale_order_id,
          target_enquiry_id, pending_target_receipt_id) populated.
        - state='buffered': only pending_target_receipt_id allowed.
        - state='orphaned': no further constraint (was buffered, now stale).
        """
        for rec in self:
            order_set = bool(rec.target_sale_order_id)
            enquiry_set = bool(rec.target_enquiry_id)
            pending_set = bool(rec.pending_target_receipt_id)
            populated = sum((order_set, enquiry_set, pending_set))

            if rec.state == 'posted':
                if populated != 1:
                    raise ValidationError(
                        "C-EMD-001: state='posted' requires exactly one target "
                        f"(found {populated}). Set one of target_sale_order_id, "
                        "target_enquiry_id, or pending_target_receipt_id."
                    )
            elif rec.state == 'buffered':
                if order_set or enquiry_set:
                    raise ValidationError(
                        "C-EMD-001: state='buffered' may only set "
                        "pending_target_receipt_id; clear target_sale_order_id "
                        "and target_enquiry_id first."
                    )

    @api.model_create_multi
    def create(self, vals_list):
        """Truncate payload_excerpt to _PAYLOAD_EXCERPT_MAX before insert.

        Defense-in-depth — Char(size=256) already truncates at the ORM layer
        in Odoo 19, but explicit truncation here makes the audit-write
        contract obvious to readers and survives any future field redefinition.
        """
        for vals in vals_list:
            excerpt = vals.get('payload_excerpt')
            if excerpt and len(excerpt) > _PAYLOAD_EXCERPT_MAX:
                vals['payload_excerpt'] = excerpt[:_PAYLOAD_EXCERPT_MAX]
        return super().create(vals_list)

    def write(self, vals):
        """Re-validate C-EMD-001 on direct RPC writes.

        FR-017 defense-in-depth (10th confirmation): @api.constrains fires on
        ORM saves that touch tracked fields, but bare-bones recordset
        `record.write({...})` paths can race the framework. Re-running the
        check post-mutation closes the gap. See auto-memory
        feedback_fr017_write_defense_in_depth.md.
        """
        result = super().write(vals)
        guarded = {
            'state',
            'target_sale_order_id',
            'target_enquiry_id',
            'pending_target_receipt_id',
        }
        if guarded.intersection(vals):
            self._check_xor_target()
        return result

    def _cron_dedupe_retention(self):
        """Daily retention sweep — three-state lifecycle hygiene.

        - state='posted' AND posted_at < now-30d → unlink.
        - state='buffered' AND posted_at < now-7d → flip to 'orphaned'.
        - state='orphaned' → kept indefinitely (BA audit trail).

        Privilege context: runs as the cron's ir.cron.user_id (defaults
        to admin / base.group_system on first execution). The unlink and
        write paths require `etsy.message.dedupe` write+unlink ACL, which
        is granted only to base.group_system per ir.model.access.csv. No
        explicit sudo() — the cron user already carries the elevation.
        """
        now = fields.Datetime.now()
        posted_cutoff = now - timedelta(days=_POSTED_RETENTION_DAYS)
        buffered_cutoff = now - timedelta(days=_BUFFERED_AGEOUT_DAYS)

        old_posted = self.search([
            ('state', '=', 'posted'),
            ('posted_at', '<', posted_cutoff),
        ])
        if old_posted:
            _logger.debug(
                "etsy.message.dedupe retention: deleting %d posted rows older than %d days",
                len(old_posted), _POSTED_RETENTION_DAYS,
            )
            old_posted.unlink()

        aged_buffered = self.search([
            ('state', '=', 'buffered'),
            ('posted_at', '<', buffered_cutoff),
        ])
        if aged_buffered:
            _logger.debug(
                "etsy.message.dedupe retention: marking %d buffered rows orphaned (>%d days)",
                len(aged_buffered), _BUFFERED_AGEOUT_DAYS,
            )
            # state='orphaned' has no XOR enforcement; existing
            # pending_target_receipt_id is preserved for BA replay attempts.
            aged_buffered.write({'state': 'orphaned'})
