"""product.template extension — x_default_pipeline_id master-data field.

Operators set this per-product to override the category-level / system-wide
default. Read by services/pipeline_resolver.py during sale.order creation.
"""
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_default_pipeline_id = fields.Many2one(
        'order.pipeline',
        string='Default Pipeline',
        ondelete='set null',
        help="Default fulfillment pipeline for orders containing this product. "
             "Falls back to product.categ_id.x_default_pipeline_id, then to the "
             "ICP `multichannel_hub.default_pipeline_code`.",
    )
