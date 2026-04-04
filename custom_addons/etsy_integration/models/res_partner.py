from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_etsy_customer = fields.Boolean(
        string='Is Etsy Customer', default=False, index=True)
    etsy_buyer_name = fields.Char(
        string='Etsy Buyer Name',
        help='Original buyer name from Etsy (may differ from shipping name)')
    etsy_order_count = fields.Integer(
        string='Etsy Order Count', compute='_compute_etsy_order_count')

    @api.depends('sale_order_ids')
    def _compute_etsy_order_count(self):
        for partner in self:
            partner.etsy_order_count = self.env['sale.order'].search_count([
                ('partner_id', '=', partner.id),
                ('is_etsy_order', '=', True),
            ])

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
