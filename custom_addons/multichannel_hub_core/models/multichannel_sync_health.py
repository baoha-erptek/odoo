"""Per-channel sync health snapshot (P0-11, ADR-008 §7).

One row per (`multichannel.sales.channel`, source-kind) combination. Updated
by per-channel sync services (e.g. EtsyOrderSyncer, EtsyListingAdapter,
gearment poller) to surface "is the sync chain healthy?" at a glance.

Dashboard tile (operations dashboard) is a follow-up slice (P0-11-TILE).
"""

from odoo import fields, models


STATUS_VALUES = [
    ('ok', 'OK'),
    ('warning', 'Warning'),
    ('error', 'Error'),
    ('paused', 'Paused'),
]


class MultichannelSyncHealth(models.Model):
    _name = 'multichannel.sync.health'
    _description = 'Multichannel Sync Health'
    _order = 'channel_id, metric_key'

    channel_id = fields.Many2one(
        'multichannel.sales.channel',
        required=True, ondelete='cascade', index=True,
    )
    metric_key = fields.Char(
        required=True, index=True,
        help="Stable identifier for the metric — e.g. 'etsy_order_sync', "
             "'etsy_listing_sync', 'parser_template_drift', "
             "'gearment_tracking_pull'.",
    )
    status = fields.Selection(
        STATUS_VALUES, required=True, default='ok', index=True,
    )
    last_run_at = fields.Datetime(help="Most recent sync run timestamp")
    last_success_at = fields.Datetime(help="Most recent successful sync run")
    last_error_at = fields.Datetime(help="Most recent failed sync run")
    last_error_message = fields.Text()
    rows_processed = fields.Integer(default=0)
    rows_failed = fields.Integer(default=0)

    def init(self):
        cr = self.env.cr
        cr.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uniq_multichannel_sync_health_channel_metric'
                ) THEN
                    ALTER TABLE multichannel_sync_health
                        ADD CONSTRAINT uniq_multichannel_sync_health_channel_metric
                        UNIQUE (channel_id, metric_key);
                END IF;
            END $$
        """)

    @classmethod
    def record(cls, env, channel_code, metric_key, status='ok',
               message='', delta_rows=0, delta_failed=0):
        """Upsert a health snapshot. Helper for syncers to call without
        having to recreate the upsert dance in every service.
        """
        Channel = env['multichannel.sales.channel'].with_context(active_test=False)
        channel = Channel.search([('code', '=', channel_code)], limit=1)
        if not channel:
            return env['multichannel.sync.health']
        Health = env['multichannel.sync.health'].sudo()
        row = Health.search([
            ('channel_id', '=', channel.id),
            ('metric_key', '=', metric_key),
        ], limit=1)
        now = fields.Datetime.now()
        vals = {
            'status': status,
            'last_run_at': now,
            'last_error_message': message[:4000] if message else '',
            'rows_processed': (row.rows_processed or 0) + (delta_rows or 0),
            'rows_failed': (row.rows_failed or 0) + (delta_failed or 0),
        }
        if status == 'ok':
            vals['last_success_at'] = now
        elif status in ('error', 'warning'):
            vals['last_error_at'] = now
        if row:
            row.write(vals)
            return row
        vals.update({'channel_id': channel.id, 'metric_key': metric_key})
        return Health.create(vals)
