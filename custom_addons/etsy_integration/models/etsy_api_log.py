"""etsy.api.log — per-call audit trail for Etsy API + audit-mode runs.

Per data-model.md §3. Deliberately does NOT inherit `mail.thread` —
the model is intended for high-volume writes (one row per HTTP
call once P0-17b lands) and chatter would balloon storage. ACL
gates read access to `base.group_system` + the dedicated
`etsy_api_log_reader` group.

Retention: `_cron_cleanup_old_logs` deletes rows whose
`request_started_at` is older than
`ir.config_parameter.etsy_integration.api_log_retention_days`
(default 30). Implements FR-035.

Index: `(shop_id, request_started_at DESC)` to support the most
common query — "recent activity for this shop". The other two
indexes documented in data-model.md §3 (`(source,
request_started_at DESC)` and `http_status`) are deferred to a
P1 perf-tuning slice (P0-13 active-prioritization deferral).
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# 30 days default — matches FR-035 unless overridden by
# `ir.config_parameter.etsy_integration.api_log_retention_days`.
_DEFAULT_RETENTION_DAYS = 30

_SOURCE_SELECTION = [
    ('audit', 'Audit'),
    ('sync', 'Order Sync'),
    ('tracking_push', 'Tracking Push'),
    ('webhook_register', 'Webhook Register'),
    ('listing_push', 'Listing Push'),
    ('listing_pull', 'Listing Pull'),
    ('buyer_message_sync', 'Buyer Message Sync'),
    ('health_check', 'Health Check'),
    ('conversation_sync', 'Conversation Sync'),
    ('message_send', 'Outbound Message Send'),
    # P1-10: scope-assertion failures on the OAuth callback. The audit
    # row is written from a fresh cursor + commit so it survives the
    # 400 response that rolls back the outer controller transaction.
    ('scope_validation', 'OAuth Scope Validation'),
    # Spec 011 P-PUB-CLIENT T002 — outbound publish + write surface
    ('listing_create', 'Listing Create (Draft)'),
    ('listing_image_upload', 'Listing Image Upload'),
    ('listing_image_delete', 'Listing Image Delete'),
    ('listing_inventory_push', 'Listing Inventory Push'),
    ('listing_publish', 'Listing Publish'),
    # Spec 010 P-HUB-XLS-* — catalog import surface (co-located here so a single migration carries both)
    ('catalog_import_run', 'Catalog Import Run'),
    ('catalog_image_download', 'Catalog Image Download'),
]


class EtsyApiLog(models.Model):
    _name = 'etsy.api.log'
    _description = 'Etsy API Audit Log'
    _order = 'request_started_at desc, id desc'
    _rec_name = 'endpoint'

    shop_id = fields.Many2one(
        'etsy.shop', string='Etsy Shop',
        required=True, ondelete='cascade', index=True,
    )
    endpoint = fields.Char(
        string='Endpoint', required=True,
        help='HTTP method + path, e.g. GET /v3/application/shops/{shop_id}/receipts',
    )
    http_status = fields.Integer(
        string='HTTP Status',
        help='Last HTTP status seen. NULL on connection failures (no '
             'response). Audit-mode order-sync rows record 200 because '
             'the audit fires only after a successful page fetch '
             '(P-UAT-FIX-API-LOG-HTTP-STATUS).',
    )
    request_started_at = fields.Datetime(
        string='Request Started At', required=True,
        default=fields.Datetime.now, index=True,
    )
    duration_ms = fields.Integer(string='Duration (ms)')
    request_payload_summary = fields.Text(
        string='Request Summary',
        help='Body summary; Authorization header scrubbed.',
    )
    response_summary = fields.Text(
        string='Response Summary',
        help='Body summary, truncated to ~4 KB. PII (buyer_name, '
             'buyer_email, addresses) is scrubbed before write.',
    )
    error_message = fields.Text(string='Error Message')
    quota_used_today = fields.Integer(
        string='Quota Used Today',
        help='From X-RateLimit-Limit-Daily header (FR-027).',
    )
    quota_remaining_today = fields.Integer(string='Quota Remaining Today')
    source = fields.Selection(
        selection=_SOURCE_SELECTION,
        string='Source', required=True, index=True,
        help='Subsystem that generated this log entry.',
    )

    def init(self):
        """Composite index `(shop_id, request_started_at DESC)` —
        backs the most common query path (recent activity per shop).
        Odoo's column-level `index=True` does not produce composite
        indexes; we declare it manually here.
        """
        super().init()
        # Raw SQL is the only way to declare a composite DESC index
        # in Odoo. Idempotent via IF NOT EXISTS; the cron and the
        # audit-retrofit both rely on this index for sub-second
        # lookups.
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS etsy_api_log_shop_started_idx
            ON etsy_api_log (shop_id, request_started_at DESC)
        """)

    @api.model
    def _cron_cleanup_old_logs(self):
        """FR-035: delete rows older than the configured retention
        threshold. Raw SQL is intentional — at 30-day rolloff with
        per-call writes (post P0-17b) this table will hold tens of
        thousands of rows and ORM `unlink` would be O(N) ACL-checked
        and slow. Cron runs as `__system__` so the SQL bypass is
        already inside the trust boundary.
        """
        retention_days = self._get_retention_days()
        # Parameterized query — no string interpolation of the
        # day count. Postgres `now() - interval` is computed in
        # the DB so timezone is consistent.
        self.env.cr.execute("""
            DELETE FROM etsy_api_log
            WHERE request_started_at < (now() at time zone 'UTC') - (%s || ' days')::interval
        """, (retention_days,))
        deleted = self.env.cr.rowcount
        if deleted:
            _logger.info(
                'etsy.api.log retention sweep: deleted %d rows older than %d days',
                deleted, retention_days,
            )

    @api.model
    def _get_retention_days(self):
        """Read the retention threshold from ir.config_parameter,
        falling back to the module default."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'etsy_integration.api_log_retention_days',
            str(_DEFAULT_RETENTION_DAYS),
        )
        try:
            value = int(raw)
        except (TypeError, ValueError):
            _logger.warning(
                'Invalid api_log_retention_days param %r; falling back to %d',
                raw, _DEFAULT_RETENTION_DAYS,
            )
            return _DEFAULT_RETENTION_DAYS
        if value < 1:
            return _DEFAULT_RETENTION_DAYS
        return value
