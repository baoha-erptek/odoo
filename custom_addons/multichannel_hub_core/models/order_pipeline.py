"""order.pipeline — minimal master-data table for fulfillment routing.

P1-PIPELINE-MIN slice (2026-04-30): runtime-editable pipeline list used by
pipeline_resolver to assign each sale.order a fulfillment route based on
product.template / product.category configuration.

Full state machine + transition log + auto-versioning deferred to
P1-PIPELINE-FULL (post-tomorrow E2E).
"""
from odoo import _, api, fields, models


class OrderPipeline(models.Model):
    _name = 'order.pipeline'
    _description = 'Order fulfillment pipeline (master data)'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(
        string='Code',
        required=True,
        help="Stable machine code (e.g., 'vn_internal_production'). "
             "Used by ICP fallback + Gearment routing.",
    )
    sequence = fields.Integer(string='Sequence', default=10)
    is_active = fields.Boolean(string='Active', default=True)
    description = fields.Text(string='Description')

    channel_hint = fields.Selection(
        [
            ('internal', 'Internal Production'),
            ('gearment', 'Gearment Drop-Ship'),
            ('hybrid', 'Multi-Technique Hybrid'),
            ('other', 'Other / Manual'),
        ],
        string='Channel Hint',
        default='internal',
        required=True,
        help="Coarse-grained categorization to drive dashboard filters and "
             "downstream adapter selection. Not a state machine.",
    )

    _sql_constraints = [
        ('uniq_order_pipeline_code',
         'UNIQUE(code)',
         'Pipeline code must be unique.'),
    ]

    def init(self):
        """Belt-and-braces UNIQUE mirror per project_sql_constraints_drift memory."""
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'order_pipeline_uniq_code'
                ) THEN
                    ALTER TABLE order_pipeline
                    ADD CONSTRAINT order_pipeline_uniq_code UNIQUE (code);
                END IF;
            END
            $$;
        """)
