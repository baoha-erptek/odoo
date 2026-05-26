"""SKU Family taxonomy — DB-managed replacement for the frozen Python tuple.

Spec 009 §2.5 P-HUB-SKU-BUILDER T038. Owner / BA can CRUD families
without a code release. `services/sku_grammar_v2.evaluate(name, env)`
reads this model ordered by priority and falls back to MSC.

UNIQUE(code) is enforced via init() raw-SQL mirror (C-SKU-FAM-001) per
memory `project_sql_constraints_drift` — Odoo 19 dropped declarative
`_sql_constraints` enforcement.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MhcSkuFamily(models.Model):
    _name = 'mhc.sku.family'
    _description = 'SKU Family (taxonomy row)'
    _order = 'priority, code'

    code = fields.Char(
        size=3,
        required=True,
        index=True,
        help="3-letter family code used as the FAM3 segment of v2.1 SKUs "
             "(e.g. MUG, APR, RDS).",
    )
    name = fields.Char(
        required=True,
        translate=True,
        help="Human-readable family name (e.g. 'Mug', 'Apron').",
    )
    priority = fields.Integer(
        default=100,
        required=True,
        help="Lower value = matched first. Mirrors SKU_GRAMMAR.md §2 priority "
             "column. evaluate() iterates families in (priority, code) order; "
             "first regex match wins.",
    )
    regex_pattern = fields.Char(
        required=True,
        help="Python regex matched case-insensitively against the product "
             "name. Anchor with \\b word boundaries to avoid false positives. "
             "Malformed patterns fall back to MSC with a WARNING log. "
             "Avoid nested quantifiers (e.g. (a+)+) — catastrophic-backtracking "
             "patterns can slow the classifier; BA edits land directly so keep "
             "patterns short and well-anchored.",
    )
    default_route = fields.Selection(
        [
            ('in_house', 'In-house MO'),
            ('gearment', 'Gearment POD'),
            ('tbd', 'To Be Determined'),
        ],
        default='tbd',
        help="Default fulfillment route per SKU_GRAMMAR §6. "
             "Overridden per-product via x_gearment_sku (ADR-010).",
    )
    default_material_id = fields.Many2one(
        'product.attribute.value',
        string='Default Material',
        ondelete='set null',
        help="Pre-fills the Material step in the SKU builder wizard. "
             "Should reference a product.attribute.value under the "
             "'Material' attribute.",
    )
    active = fields.Boolean(default=True, help="Soft-disable flag.")

    def init(self):
        """Mirror C-SKU-FAM-001 UNIQUE(code) in pg_constraint.

        Odoo 19 dropped declarative `_sql_constraints` enforcement
        (memory: project_sql_constraints_drift — 9 prior confirmations).
        The raw-SQL mirror is the sole enforcement path. Pre-check
        pg_constraint to keep ALTER TABLE idempotent across re-installs.
        """
        self.env.cr.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uniq_mhc_sku_family_code'
                ) THEN
                    ALTER TABLE mhc_sku_family
                        ADD CONSTRAINT uniq_mhc_sku_family_code
                        UNIQUE (code);
                END IF;
            END $$
        """)
