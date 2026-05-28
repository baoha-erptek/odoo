"""Per-(product_template, channel) state — channel-side mirror.

Created when a product is first added to a channel; updated by the
publisher service (Spec 011). Channel-agnostic surface.

Spec 009 — P-HUB-PROD-MODEL. Data model: specs/009-product-hub/data-model.md §2.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


STATE_VALUES = [
    ('draft', 'Draft'),
    ('published', 'Published'),
    ('archived', 'Archived'),
    ('error', 'Error'),
]


class ProductChannelStatus(models.Model):
    _name = 'product.channel.status'
    _description = 'Product Channel Status'
    _order = 'product_tmpl_id, channel_id'

    product_tmpl_id = fields.Many2one(
        'product.template',
        required=True,
        ondelete='cascade',
        index=True,
    )
    channel_id = fields.Many2one(
        'multichannel.sales.channel',
        required=True,
        ondelete='restrict',
        index=True,
    )
    state = fields.Selection(STATE_VALUES, required=True, default='draft', index=True)
    external_ref = fields.Char(
        index=True,
        help="Channel-side identifier (e.g. Etsy listing ID)",
    )
    last_sync_at = fields.Datetime(help="Last successful write/read to channel")
    last_sync_error = fields.Text(help="Last publisher error message (truncated 4 KB)")

    def init(self):
        """Mirror C-PCS-001 UNIQUE(product_tmpl_id, channel_id) + composite index."""
        cr = self.env.cr
        cr.execute("""
            CREATE INDEX IF NOT EXISTS product_channel_status_channel_state_idx
                ON product_channel_status (channel_id, state)
        """)
        cr.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uniq_product_channel_status_product_channel'
                ) THEN
                    ALTER TABLE product_channel_status
                        ADD CONSTRAINT uniq_product_channel_status_product_channel
                        UNIQUE (product_tmpl_id, channel_id);
                END IF;
            END $$
        """)
