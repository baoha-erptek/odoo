"""product.category extension — fallback default pipeline.

Resolver chain: product.template → product.category → ICP system param.
"""
from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    x_default_pipeline_id = fields.Many2one(
        'order.pipeline',
        string='Default Pipeline',
        ondelete='set null',
        help="Fallback pipeline when individual products don't override. "
             "Used by services/pipeline_resolver.py.",
    )
