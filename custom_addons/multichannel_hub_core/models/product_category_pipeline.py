"""product.category extension — fallback default pipeline + SKU family chain.

Resolver chain: product.template → product.category → ICP system param.

SKU family inheritance: product.category.x_sku_family_id (M2O → mhc.sku.family)
with parent-chain inheritance via parent_id.
"""
from odoo import api, fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    x_default_pipeline_id = fields.Many2one(
        'order.pipeline',
        string='Default Pipeline',
        ondelete='set null',
        help="Fallback pipeline when individual products don't override. "
             "Used by services/pipeline_resolver.py.",
    )
    x_sku_family_id = fields.Many2one(
        'mhc.sku.family',
        string='SKU Family',
        ondelete='set null',
        index=True,
        help="SKU family for auto-derivation. Child categories inherit via parent_id chain.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override to ensure x_sku_family_id index is used."""
        return super().create(vals_list)

    def _get_sku_family_chain(self):
        """Return the SKU family for this category, walking parent_id chain if needed.

        Returns: mhc.sku.family record if found, else False.
        """
        if self.x_sku_family_id:
            return self.x_sku_family_id
        if self.parent_id:
            return self.parent_id._get_sku_family_chain()
        return False
