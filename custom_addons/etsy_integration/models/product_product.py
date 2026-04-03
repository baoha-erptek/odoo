from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    etsy_image_url = fields.Char(string='Etsy Image URL')
    is_etsy_product = fields.Boolean(
        string='Is Etsy Product', default=False, index=True)
