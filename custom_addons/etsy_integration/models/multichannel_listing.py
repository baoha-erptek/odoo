"""P-LIST-CATEGORY (ADR-015 §3 / spec 012 §US4) — Etsy taxonomy extension.

mhc cannot depend on etsy_integration (ADR-003 keeps the dependency
graph one-way). Etsy-specific listing fields therefore live here, as
classic ``_inherit`` extensions of ``multichannel.listing``.
"""

from odoo import fields, models


class MultichannelListingEtsy(models.Model):
    _inherit = 'multichannel.listing'

    etsy_taxonomy_id = fields.Many2one(
        'etsy.taxonomy.node',
        string='Etsy Category',
        ondelete='set null',
        help='Per-listing Etsy taxonomy override. Empty → falls back to '
             'product.template.x_taxonomy_id → etsy.shop.default_taxonomy_id.',
    )

    # P-LIST-SHIPPING (ADR-015 §3 / spec 012 §US5)
    etsy_shipping_profile_id = fields.Many2one(
        'etsy.shipping.profile',
        string='Etsy Shipping Profile',
        ondelete='set null',
        help='Per-listing shipping profile override. Empty → falls back to '
             'etsy.shop.default_shipping_profile_id.',
    )
