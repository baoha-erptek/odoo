"""multichannel.enquiry — Etsy-specific fields extension.

Per ADR-003, multichannel_hub_core cannot reference channel-specific models
(etsy.shop). Etsy fields and the partial UNIQUE on (etsy_shop_id,
etsy_conversation_id) live here.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MultichannelEnquiryEtsy(models.Model):
    _inherit = 'multichannel.enquiry'

    etsy_shop_id = fields.Many2one(
        'etsy.shop', string='Etsy Shop', ondelete='restrict',
        index=True, tracking=True,
    )
    etsy_conversation_id = fields.Char(
        string='Etsy Conversation ID', index=True, tracking=True,
        help='Etsy API conversation_id; UNIQUE per shop when set.',
    )

    def init(self):
        """Mirror the partial UNIQUE index for the Etsy conversation key.

        Drift template (project_sql_constraints_drift.md 6th confirmation):
        pg_indexes pre-check, not EXCEPTION clauses.
        PG normalizes WHERE clause to `((col)::text = 'v'::text)`-style on
        text comparisons; tests assert substring 'IS NOT NULL'.
        """
        super().init()
        self.env.cr.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname = 'public'
                    AND indexname = 'idx_mhe_etsy_conv'
                ) THEN
                    CREATE UNIQUE INDEX idx_mhe_etsy_conv
                    ON multichannel_enquiry (etsy_shop_id, etsy_conversation_id)
                    WHERE etsy_conversation_id IS NOT NULL;
                END IF;
            END $$;
        """)
