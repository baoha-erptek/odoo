"""Extend product.attribute.value with SKU-grammar metadata.

Spec 009 §2.5 P-HUB-SKU-BUILDER T039. Additive `_inherit` — no override
of stock methods. Reuses Odoo's variant-attribute machinery for
Material / Shape / Size / Fluid oz / Apparel size / Color per
SKU_GRAMMAR §8.

- `x_code`: the 2-6 character code used in v2.1 SKUs (e.g. CE, F11, R30X18).
- `x_namespace`: SIZE-only — disambiguates shape vs dim vs rect vs fluid_oz
  vs apparel per §4 namespace table.
- `x_applicable_family_ids`: SIZE-only — family-gating so the builder
  wizard's size dropdown only shows codes valid for the chosen family.

Empty / NULL for non-SKU attributes (e.g. plain marketing tags) — no
constraint, no validation; SKU-grammar only inspects rows with x_code set.
"""

from odoo import fields, models


_NAMESPACE_SELECTION = [
    ('shape', 'Shape-class (SQ/HT/OV/...)'),
    ('dim', 'Dimensional square (S35/S41/...)'),
    ('rect', 'Rectangular (R30X18/...)'),
    ('fluid_oz', 'Fluid ounce (F11/F15/...)'),
    ('apparel', 'Apparel size (AS/AM/AL/...)'),
]


class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    x_code = fields.Char(
        size=6,
        index=True,
        help="SKU-grammar v2.1 code (e.g. CE, F11, R30X18, BK). "
             "Empty for non-SKU attribute values.",
    )
    x_namespace = fields.Selection(
        _NAMESPACE_SELECTION,
        help="SIZE attribute only — selects which §4 SIZE namespace this "
             "value belongs to. Empty for non-size attributes.",
    )
    x_applicable_family_ids = fields.Many2many(
        'mhc.sku.family',
        'product_attribute_value_mhc_sku_family_rel',
        'value_id',
        'family_id',
        string='Applicable Families',
        help="SIZE attribute only — restricts which families may use this "
             "size code in the builder wizard. Empty = applies to all.",
    )
