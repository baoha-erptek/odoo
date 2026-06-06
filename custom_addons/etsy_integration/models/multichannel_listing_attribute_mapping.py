"""Per-listing attribute mapping override (P-LIST-ATTRIBUTES / ADR-015).

Spec 012 §US6: per-listing override of the Odoo product.attribute →
Etsy property_id mapping. Resolution order in the publisher:

    1. multichannel.listing.attribute_mapping_ids   (per-listing override)
    2. etsy.shop.default_attribute_mapping_ids      (shop default — slice P-LIST-ATTR-CONFIG)
    3. product.attribute.x_etsy_property_id         (global, ships today)

The mapping row carries an optional `etsy_property_id_override` Char.
When empty, the resolver falls through to the next tier.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MultichannelListingAttributeMapping(models.Model):
    _name = 'multichannel.listing.attribute.mapping'
    _description = 'Multichannel Listing — Per-listing Attribute Mapping'
    _order = 'listing_id, sequence, id'

    listing_id = fields.Many2one(
        'multichannel.listing',
        string='Listing',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_attribute_id = fields.Many2one(
        'product.attribute',
        string='Product Attribute',
        required=True,
        ondelete='restrict',
        help='Odoo product attribute (e.g. Size, Color, Material).',
    )
    etsy_property_id_override = fields.Char(
        string='Etsy Property ID Override',
        help='Numeric Etsy property_id to use FOR THIS LISTING. Empty → '
             'falls back to shop default → product.attribute.x_etsy_property_id.',
    )
    etsy_property_name_override = fields.Char(
        string='Etsy Property Name Override',
        help='Optional override for the Etsy property_name string. Empty → '
             'falls back to product.attribute.x_etsy_property_name.',
    )
    sequence = fields.Integer(default=10)

    def init(self):
        """UNIQUE (listing_id, product_attribute_id) — one mapping per
        attribute per listing."""
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                uniq_mhc_listing_attribute_mapping_pair
            ON multichannel_listing_attribute_mapping (
                listing_id, product_attribute_id
            )
        """)
