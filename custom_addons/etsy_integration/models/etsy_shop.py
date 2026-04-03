import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class EtsyShop(models.Model):
    _name = 'etsy.shop'
    _description = 'Etsy Shop'
    _order = 'name'

    name = fields.Char(string='Shop Name', required=True, index=True)
    active = fields.Boolean(default=True)
    order_ids = fields.One2many('sale.order', 'etsy_shop_id', string='Orders')
    order_count = fields.Integer(
        string='Order Count', compute='_compute_order_count')
    revenue_total = fields.Float(
        string='Total Revenue', compute='_compute_order_count')

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Shop name must be unique!'),
    ]

    @api.depends('order_ids')
    def _compute_order_count(self):
        for shop in self:
            orders = shop.order_ids
            shop.order_count = len(orders)
            shop.revenue_total = sum(orders.mapped('amount_total'))

    def action_view_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Orders - {self.name}',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('etsy_shop_id', '=', self.id)],
            'context': {'default_etsy_shop_id': self.id},
        }
