"""product.template extension — Gearment SKU mapping (POD route).

Per ADR-003: Gearment-specific data lives in mhf, not mhc. mhf depends
on mhc which is a one-directional dependency, so extending product.template
here is correct.
"""
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_gearment_sku = fields.Char(
        string='Gearment SKU',
        index=True,
        tracking=True,
        help="Maps the product to a Gearment catalog SKU; required for "
             "any product that flows through the gearment_pod pipeline.",
    )
