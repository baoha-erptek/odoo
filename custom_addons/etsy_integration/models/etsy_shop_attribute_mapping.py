"""Shop-level default attribute mapping (P-LIST-ATTR-CONFIG / ADR-015).

Tier 2 of the publisher's 3-tier property-id fallback chain (spec 012
§US6, UX review HIGH #4). Listing override wins over this; this wins
over the product.attribute global.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class EtsyShopAttributeMapping(models.Model):
    _name = 'etsy.shop.attribute.mapping'
    _description = 'Etsy Shop — Default Attribute Mapping'
    _order = 'shop_id, sequence, id'

    shop_id = fields.Many2one(
        'etsy.shop',
        string='Shop',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_attribute_id = fields.Many2one(
        'product.attribute',
        string='Product Attribute',
        required=True,
        ondelete='restrict',
    )
    etsy_property_id_override = fields.Char(
        string='Etsy Property ID Override',
        help='Shop-wide default Etsy property_id. Listings can still '
             'override per-row.',
    )
    etsy_property_name_override = fields.Char(
        string='Etsy Property Name Override',
    )
    sequence = fields.Integer(default=10)

    def init(self):
        """UNIQUE (shop_id, product_attribute_id) — one default per
        attribute per shop."""
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                uniq_etsy_shop_attribute_mapping_pair
            ON etsy_shop_attribute_mapping (
                shop_id, product_attribute_id
            )
        """)
