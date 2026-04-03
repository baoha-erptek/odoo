from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_etsy_customer = fields.Boolean(
        string='Is Etsy Customer', default=False, index=True)
    etsy_buyer_name = fields.Char(
        string='Etsy Buyer Name',
        help='Original buyer name from Etsy (may differ from shipping name)')

    def action_view_etsy_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Etsy Orders - {self.name}',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('is_etsy_order', '=', True),
            ],
        }
