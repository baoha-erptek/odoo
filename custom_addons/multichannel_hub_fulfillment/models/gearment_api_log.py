"""gearment.api.log — per-call audit log for Gearment API interactions.

Mirrors etsy.api.log (Spec 005 P0-17): high-volume audit table without
mail.thread, daily retention cron, ACL gated to system + sale_manager-read.
"""
import logging
from datetime import datetime, timedelta, timezone

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class GearmentApiLog(models.Model):
    _name = 'gearment.api.log'
    _description = 'Gearment API call and webhook audit log'
    _order = 'request_started_at desc, id desc'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        ondelete='set null',
        index=True,
        help="Null for catalog/system probes; set for order-specific calls.",
    )
    endpoint = fields.Char(
        string='Endpoint',
        required=True,
        help="HTTP method + path, e.g. 'POST /api/v3/orders'.",
    )
    http_status = fields.Integer(string='HTTP Status')
    request_started_at = fields.Datetime(
        string='Request Started At',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    duration_ms = fields.Integer(string='Duration (ms)')
    request_payload_summary = fields.Text(
        string='Request Payload Summary',
        help="JSON body sent (PII + Authorization scrubbed).",
    )
    response_summary = fields.Text(
        string='Response Summary',
        help="JSON response truncated to ~4 KB.",
    )
    error_message = fields.Text(string='Error Message')
    rate_limit_remaining = fields.Integer(
        string='Rate Limit Remaining',
        help="From X-RateLimit-Remaining header if Gearment provides one.",
    )
    source = fields.Selection(
        [
            ('probe', 'Probe'),
            ('draft', 'Draft Order'),
            ('quote', 'Quote'),
            ('confirm', 'Confirm'),
            ('callback', 'Callback'),
            ('health_check', 'Health Check'),
            ('inbound_webhook', 'Inbound Webhook'),
        ],
        string='Source',
        required=True,
        default='probe',
    )
    direction = fields.Selection(
        [
            ('outbound', 'Outbound API Call'),
            ('inbound', 'Inbound Webhook'),
        ],
        string='Direction',
        help="Outbound = Odoo→Gearment API call. Inbound = Gearment→Odoo webhook callback. "
             "Nullable for backward compat with rows created before P0-18b2a.",
    )
    request_headers = fields.Text(
        string='Request Headers',
        help="JSON dict of inbound HTTP headers; Authorization/Cookie/secret-* keys scrubbed.",
    )
    request_body = fields.Text(
        string='Request Body',
        help="Inbound webhook body; truncated to 4096 chars.",
    )
    signature_header_seen = fields.Char(
        string='Signature Header Seen',
        help="Heuristic capture of the first incoming header whose name contains 'signature'. "
             "Empty in discovery mode if Gearment did not send one.",
    )
    topic_seen = fields.Char(
        string='Topic Seen',
        help="Webhook topic/event extracted from body['event'], body['topic'], "
             "or X-Topic header; empty if not detectable.",
    )

    def init(self):
        """Create composite index for hot-path filter (recent activity per order).

        IF NOT EXISTS pre-check follows the canonical drift-template
        (memory project_sql_constraints_drift) — declarative paths have
        been observed to miss this in our codebase.
        """
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS gearment_api_log_order_request_started_at_idx
            ON gearment_api_log (sale_order_id, request_started_at DESC)
        """)

    @api.model
    def _cron_cleanup_old_logs(self):
        """Daily retention cron — deletes rows older than the configured cutoff.

        Default 30 days; override via ICP `multichannel_hub_fulfillment.api_log_retention_days`.
        Raw DELETE for performance (4-byte integer comparison, no ORM overhead;
        cron runs as superuser so ACL bypass is intentional and documented).
        """
        param = self.env['ir.config_parameter'].sudo().get_param(
            'multichannel_hub_fulfillment.api_log_retention_days', '30',
        )
        try:
            retention_days = int(param)
        except (TypeError, ValueError):
            _logger.warning(
                "Invalid api_log_retention_days=%r; falling back to 30", param,
            )
            retention_days = 30
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)
        # Raw SQL: cron runs trusted; ORM unlink would scale O(n) on tens of
        # thousands of rows. Justified per common/security.md raw-SQL exception.
        self.env.cr.execute(
            "DELETE FROM gearment_api_log WHERE request_started_at < %s",
            (cutoff,),
        )
        deleted = self.env.cr.rowcount
        _logger.debug("gearment.api.log retention deleted %s rows older than %s",
                      deleted, cutoff)
        return deleted
