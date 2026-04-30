"""gearment.api.log — API audit trail for Gearment fulfillment integration (P0-18b1).

Per data-model.md § Gearment API Log (P0-18b1). Records every API call
(orders, quotes, webhooks, health checks) with timing, status, request/response
summaries, and error details. Designed for high-volume writes (one row per HTTP
call) without mail.thread overhead.

Schema (11 fields + ORM base):
  - sale_order_id: M2O sale.order (nullable, for demand-side tracing)
  - endpoint: str 'METHOD /path'
  - http_status: int (NULL on connection errors)
  - request_started_at: datetime (indexed DESC for per-shop queries)
  - duration_ms: int milliseconds
  - request_payload_summary: text (PII scrubbed, <2 KB)
  - response_summary: text (PII scrubbed, <4 KB)
  - error_message: text
  - rate_limit_remaining: int (from Gearment response header, if present)
  - source: selection (6 values: probe, draft, quote, confirm, callback, health_check)

Retention: _cron_cleanup_old_logs deletes rows older than
ir.config_parameter.multichannel_hub_fulfillment.api_log_retention_days (default 30).
Uses raw SQL DELETE for O(1) performance on tens of thousands of rows.

Index: Composite (sale_order_id, request_started_at DESC) created in init()
via raw SQL with IF NOT EXISTS to back the most common query: "recent activity
for this SO".

ACL:
  - base.group_system: full (create, read, write, unlink)
  - sales_team.group_sale_manager: read-only

NOT mail.thread: See etsy.api.log rationale (data volume, no chatter needed).
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

_DEFAULT_RETENTION_DAYS = 30

_SOURCE_SELECTION = [
    ('probe', 'Probe'),
    ('draft', 'Draft Order'),
    ('quote', 'Quote'),
    ('confirm', 'Confirm'),
    ('callback', 'Callback'),
    ('health_check', 'Health Check'),
]


class GearmentApiLog(models.Model):
    _name = 'gearment.api.log'
    _description = 'Gearment API call audit log'
    _order = 'request_started_at desc, id desc'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        ondelete='set null',
        help='Reference to the SO that triggered this API call (if applicable).',
    )
    endpoint = fields.Char(
        string='Endpoint',
        required=True,
        help='HTTP method + path, e.g. POST /api/v3/orders',
    )
    http_status = fields.Integer(
        string='HTTP Status',
        help='HTTP response code. NULL on connection failures.',
    )
    request_started_at = fields.Datetime(
        string='Request Started At',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    duration_ms = fields.Integer(
        string='Duration (ms)',
        help='Round-trip time in milliseconds.',
    )
    request_payload_summary = fields.Text(
        string='Request Summary',
        help='Request body summary; Authorization header and PII scrubbed.',
    )
    response_summary = fields.Text(
        string='Response Summary',
        help='Response body summary, truncated to ~4 KB. PII scrubbed.',
    )
    error_message = fields.Text(
        string='Error Message',
        help='Exception or HTTP error details.',
    )
    rate_limit_remaining = fields.Integer(
        string='Rate Limit Remaining',
        help='From Gearment Retry-After or rate limit header (if present).',
    )
    source = fields.Selection(
        selection=_SOURCE_SELECTION,
        string='Source',
        required=True,
        index=True,
        help='Subsystem that generated this log entry.',
    )

    def init(self):
        """Create composite index (sale_order_id, request_started_at DESC).

        Backs the most common query: "recent API calls for this SO".
        Raw SQL required for DESC ordering.
        Idempotent via IF NOT EXISTS to support both init and re-runs.
        """
        super().init()
        # Raw SQL justified: performance on high-volume table (tens of thousands
        # of rows after P0-18b lands). Composite DESC index not expressible via
        # ORM field-level index=True. IF NOT EXISTS ensures the cron and any
        # re-runs do not fail on duplicate index name.
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS gearment_api_log_sale_order_started_idx
            ON gearment_api_log (sale_order_id, request_started_at DESC)
        """)

    @api.model
    def _cron_cleanup_old_logs(self):
        """Delete rows older than the configured retention threshold.

        FR-035 pattern: raw SQL bypass for performance. At 30-day rolloff with
        per-call writes (post P0-18b) this table will hold tens of thousands
        of rows. ORM unlink would be O(N) ACL-checked and slow. Cron runs as
        __system__ so the SQL bypass is inside the trust boundary.

        Parameterized query: no string interpolation. Postgres now() - interval
        is computed at DB, so timezone is consistent.
        """
        retention_days = self._get_retention_days()
        self.env.cr.execute("""
            DELETE FROM gearment_api_log
            WHERE request_started_at < (now() at time zone 'UTC') - (%s || ' days')::interval
        """, (retention_days,))
        deleted = self.env.cr.rowcount
        if deleted:
            _logger.warning(
                'gearment.api.log retention sweep: deleted %d rows older than %d days',
                deleted, retention_days,
            )

    @api.model
    def _get_retention_days(self) -> int:
        """Read retention threshold from ir.config_parameter.

        Falls back to module default (30) if not configured or invalid.
        """
        raw = self.env['ir.config_parameter'].sudo().get_param(
            'multichannel_hub_fulfillment.api_log_retention_days',
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
