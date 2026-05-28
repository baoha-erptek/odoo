"""Etsy-channel extensions to product.attribute (Spec 011 P-PUB-VARIANT-PROPERTIES).

Two channel-specific fields gate and identify variant attribute axes for
Etsy push_inventory products[].property_values[].

`x_etsy_property_id` is Char (varchar) — Etsy attribute taxonomy IDs are
large integers and Char avoids XML-RPC int32 overflow trap (see memory
feedback_odoo19_test_gotchas entry 144). The service helper casts to int
when the string is numeric; otherwise it passes through unchanged.
"""

from odoo import fields, models


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    x_etsy_property_id = fields.Char(
        string="Etsy Property ID",
        help=(
            "Etsy attribute taxonomy ID for this axis. Stored as text to "
            "preserve large IDs. Discover via the Etsy taxonomy "
            "properties endpoint for the listing's taxonomy_id."
        ),
    )
    x_etsy_property_name = fields.Char(
        string="Etsy Property Name",
        help=(
            "Etsy property display name sent with the property ID in "
            "push_inventory property_values[]. Etsy REQUIRES a non-null "
            "property_name (the inventory PUT 400s 'Expected string value "
            "for property_name' without it). For standard properties match "
            "Etsy's canonical name (e.g. 200 -> 'Primary color'); for custom "
            "properties (513/514) it is a free label."
        ),
    )
    x_publish_as_property = fields.Boolean(
        string="Publish as Etsy property",
        default=False,
        help=(
            "When enabled, this attribute axis is included in Etsy "
            "push_inventory products[].property_values[]. Defaults to "
            "False (opt-in) so that new attributes never leak to Etsy "
            "without an admin explicitly enabling them. The shipped seed "
            "flips this True for the known publishable axes (Material, "
            "Color, Size, Shape, Fluid oz, Apparel Size)."
        ),
    )
