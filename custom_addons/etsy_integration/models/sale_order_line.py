from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    etsy_transaction_id = fields.Char(
        string='Etsy Transaction ID', index=True, copy=False)
    etsy_personalisation = fields.Text(string='Personalisation')
    etsy_sku = fields.Char(string='Etsy SKU')
    etsy_option = fields.Char(string='Option')
    etsy_color = fields.Char(string='Color')
    etsy_size = fields.Char(string='Size')
    etsy_side = fields.Char(string='Side')
    etsy_face_mask_size = fields.Char(string='Face Mask Size')
    etsy_image_url = fields.Char(string='Image URL')
    etsy_design_link_front = fields.Char(string='Design Link (Front)')
    etsy_design_link_back = fields.Char(string='Design Link (Back)')
    etsy_gift_message = fields.Text(
        string='Gift Message',
        related='order_id.etsy_gift_message',
        readonly=True,
    )

    _sql_constraints = [
        ('etsy_transaction_id_unique',
         'UNIQUE(etsy_transaction_id)',
         'Etsy Transaction ID must be unique!'),
    ]
