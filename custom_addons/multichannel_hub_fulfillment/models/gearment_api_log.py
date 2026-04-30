"""Gearment API Log model (gearment.api.log) for P0-18b1.

Tracks all API calls to Gearment service with request/response summaries,
status, timing, and automatic retention cleanup.

Composite index on (sale_order_id, request_started_at DESC) for efficient
log queries by order.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class GearmentApiLog(models.Model):
    """API call audit log for Gearment fulfillment service.

    Fields:
    - sale_order_id: optional link to sale.order (many-to-one)
    - endpoint: HTTP method + path (e.g., 'POST /api/v3/orders')
    - http_status: response status code (200, 429, 500, etc.)
    - request_started_at: timestamp when request was initiated
    - duration_ms: elapsed time in milliseconds
    - request_payload_summary: JSON string (PII scrubbed per FR-017)
    - response_summary: JSON string of response (no PII)
    - error_message: exception text if call failed
    - rate_limit_remaining: advisory rate limit remaining (from header)
    - source: 'probe' | 'draft' | 'quote' | 'confirm' | 'callback' | 'health_check'

    Cleanup:
    - ir.cron _cron_cleanup_old_logs runs daily
    - Deletes rows older than ir.config_parameter 'multichannel_hub_fulfillment.api_log_retention_days' (default 30)
    """

    _name = 'gearment.api.log'
    _description = 'Gearment API Call Log'
    _order = 'request_started_at DESC, id DESC'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        ondelete='set null',
        index=True,
    )
    endpoint = fields.Char(
        string='Endpoint',
        required=True,
        size=255,
    )
    http_status = fields.Integer(
        string='HTTP Status',
        required=True,
    )
    request_started_at = fields.Datetime(
        string='Request Started',
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    duration_ms = fields.Integer(
        string='Duration (ms)',
        default=0,
    )
    request_payload_summary = fields.Text(
        string='Request Payload Summary',
        help='JSON string with PII scrubbed',
    )
    response_summary = fields.Text(
        string='Response Summary',
        help='JSON string of essential response fields',
    )
    error_message = fields.Text(
        string='Error Message',
        help='Exception text if request failed',
    )
    rate_limit_remaining = fields.Integer(
        string='Rate Limit Remaining',
        help='Advisory header value from Gearment',
    )
    source = fields.Selection(
        [
            ('probe', 'Probe'),
            ('draft', 'Draft Order'),
            ('quote', 'Quote Request'),
            ('confirm', 'Confirm'),
            ('callback', 'Callback'),
            ('health_check', 'Health Check'),
        ],
        string='Source',
        required=True,
        default='draft',
        index=True,
    )

    def init(self):
        """Create composite index on (sale_order_id, request_started_at DESC).

        Uses raw SQL with IF NOT EXISTS per drift-template (ADR-001).
        Must pre-check pg_constraint to avoid duplicate_table error on re-run.

        Also ensures ir.config_parameter for retention_days is seeded.
        Also creates ACL rows and daily cleanup cron (idempotent).
        """
        super().init()

        # Verify table exists before attempting index creation
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'gearment_api_log'
            )
        """)
        if not self.env.cr.fetchone()[0]:
            return

        # Create composite index (IF NOT EXISTS is safe on re-run)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS gearment_api_log_order_started_idx
            ON gearment_api_log (sale_order_id, request_started_at DESC)
        """)

        # Seed default retention days ICP (idempotent)
        icp_key = 'multichannel_hub_fulfillment.api_log_retention_days'
        try:
            existing = self.env['ir.config_parameter'].get_param(icp_key)
            if not existing:
                self.env['ir.config_parameter'].set_param(icp_key, '30')
        except Exception as e:
            _logger.debug(f"Could not seed ICP {icp_key}: {e}")

        # Create ACL and cron records (idempotent, runs after registry complete)
        try:
            from odoo import api
            # Use a fresh environment to ensure ORM can access ir.model
            env = api.Environment(self.env.cr, 1, {})

            ir_model_access = env['ir.model.access']
            ir_model = env['ir.model']
            ir_cron = env['ir.cron']

            # Get the ir.model record for gearment.api.log
            model_id = ir_model.search([('model', '=', 'gearment.api.log')])
            if not model_id:
                _logger.debug("ir.model record not found for gearment.api.log during init()")
                return

            # System admin group — full permissions
            system_group = env.ref('base.group_system')
            existing_system = ir_model_access.search([
                ('model_id', '=', model_id.id),
                ('group_id', '=', system_group.id),
            ])
            if not existing_system:
                ir_model_access.create({
                    'name': 'gearment.api.log system',
                    'model_id': model_id.id,
                    'group_id': system_group.id,
                    'perm_read': True,
                    'perm_write': True,
                    'perm_create': True,
                    'perm_unlink': True,
                })

            # Sales manager group — read-only
            sale_manager_group = env.ref('sales_team.group_sale_manager')
            existing_sale_mgr = ir_model_access.search([
                ('model_id', '=', model_id.id),
                ('group_id', '=', sale_manager_group.id),
            ])
            if not existing_sale_mgr:
                ir_model_access.create({
                    'name': 'gearment.api.log sale manager',
                    'model_id': model_id.id,
                    'group_id': sale_manager_group.id,
                    'perm_read': True,
                    'perm_write': False,
                    'perm_create': False,
                    'perm_unlink': False,
                })

            # Daily cleanup cron (idempotent)
            existing_cron = ir_cron.search([
                ('name', '=', 'Cleanup old Gearment API logs'),
            ])
            if not existing_cron:
                ir_cron.create({
                    'name': 'Cleanup old Gearment API logs',
                    'model_id': model_id.id,
                    'state': 'code',
                    'code': 'model._cron_cleanup_old_logs()',
                    'user_id': env.ref('base.user_root').id,
                    'interval_number': 1,
                    'interval_type': 'days',
                    'active': True,
                })
        except Exception as e:
            _logger.debug(f"Could not create ACL/cron for gearment.api.log in init(): {e}")


    def _cron_cleanup_old_logs(self):
        """Delete API logs older than retention period.

        Respects ir.config_parameter 'multichannel_hub_fulfillment.api_log_retention_days'.
        Called daily by ir.cron. Idempotent (safe to call multiple times).
        """
        from datetime import datetime, timedelta

        retention_days_str = self.env['ir.config_parameter'].get_param(
            'multichannel_hub_fulfillment.api_log_retention_days',
            default='30'
        )

        try:
            retention_days = int(retention_days_str)
        except (ValueError, TypeError):
            _logger.warning(
                f"Invalid retention days '{retention_days_str}'; using default 30"
            )
            retention_days = 30

        cutoff_date = datetime.now() - timedelta(days=retention_days)

        old_logs = self.search([
            ('request_started_at', '<', cutoff_date)
        ])

        if old_logs:
            count = len(old_logs)
            old_logs.unlink()
            _logger.debug(
                f"Cleaned up {count} old Gearment API logs (before {cutoff_date.date()})"
            )
