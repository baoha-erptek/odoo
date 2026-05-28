"""Reference list of sales channels (Etsy, Amazon, website, ...).

Channel-agnostic surface. Channel-specific extensions live in per-channel
modules (etsy_integration, future amazon_channel, website_channel) and
reference rows here by code.

Spec 009 — P-HUB-PROD-MODEL. Data model: specs/009-product-hub/data-model.md §1.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MultichannelSalesChannel(models.Model):
    _name = 'multichannel.sales.channel'
    _description = 'Multichannel Sales Channel'
    _order = 'sequence, code'

    code = fields.Char(
        required=True,
        index=True,
        help="Stable channel identifier (lowercase ASCII): etsy / amazon / website / ...",
    )
    name = fields.Char(
        required=True,
        translate=True,
        help="Display label shown to operators",
    )
    sequence = fields.Integer(default=10, help="M2M picker ordering")
    active = fields.Boolean(default=True, help="Soft-disable flag")
    description = fields.Text(help="Operator help")

    def init(self):
        """Mirror C-CH-001 UNIQUE(code) in pg_constraint.

        Odoo 19 dropped declarative `_sql_constraints` enforcement
        (memory: project_sql_constraints_drift / feedback_odoo19_test_gotchas#135).
        The raw-SQL mirror is the sole enforcement path.
        """
        self.env.cr.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uniq_multichannel_sales_channel_code'
                ) THEN
                    ALTER TABLE multichannel_sales_channel
                        ADD CONSTRAINT uniq_multichannel_sales_channel_code
                        UNIQUE (code);
                END IF;
            END $$
        """)
