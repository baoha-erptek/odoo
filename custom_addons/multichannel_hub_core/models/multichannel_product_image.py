"""multichannel.product.image — extra-image gallery row for products.

Channel-agnostic mini-gallery (P-PUB-MULTI-IMAGE, MP006). Owner pivoted
away from website_sale.product.image (would pull website, portal,
payment, delivery, html_builder) — feedback_channel_agnostic_groups_in_mhc
+ Standard-Odoo-First escalation 2026-05-27.

Etsy publisher iterates main image_1920 first, then these rows sorted by
sequence, capped at Etsy's 10-image limit per listing. Amazon and future
channels reuse the same field without rename.
"""

from odoo import fields, models


class MultichannelProductImage(models.Model):
    _name = 'multichannel.product.image'
    _description = 'Product image gallery row for multichannel publishing'
    _order = 'sequence, id'

    name = fields.Char(help='Optional caption / alt text for the image')
    sequence = fields.Integer(default=10)
    image_1920 = fields.Image(max_width=1920, max_height=1920)
    product_tmpl_id = fields.Many2one(
        'product.template',
        required=True,
        ondelete='cascade',
        index=True,
    )
