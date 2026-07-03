"""sale.order extension — auto-create a design.order on confirmation.

ESTY-244: gated by ir.config_parameter `design.auto_create_on_confirm`
(default True). Idempotent — the UNIQUE(sale_order_id) constraint on
design.order plus a pre-check prevent duplicates.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

AUTO_CREATE_PARAM = 'design.auto_create_on_confirm'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    design_order_ids = fields.One2many(
        'design.order', 'sale_order_id', string='Design Orders')
    design_order_count = fields.Integer(
        string='Design Orders', compute='_compute_design_order_count')

    @api.depends('design_order_ids')
    def _compute_design_order_count(self):
        for order in self:
            order.design_order_count = len(order.design_order_ids)

    def _design_auto_create_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            AUTO_CREATE_PARAM, 'True') == 'True'

    def _collect_design_files(self):
        """design.file rows belonging to this order (header- or line-level)."""
        self.ensure_one()
        return self.env['design.file'].search([
            '|',
            ('order_id', '=', self.id),
            ('order_line_id.order_id', '=', self.id),
        ])

    def _ensure_design_order(self):
        """Create the design.order for this SO if missing; link its files."""
        self.ensure_one()
        order = self.design_order_ids[:1]
        if not order:
            order = self.env['design.order'].create({'sale_order_id': self.id})
            _logger.info(
                "design.order %s auto-created for sale.order %s.",
                order.name, self.name)
        # Adopt any existing design files not yet linked to a design order.
        orphans = self._collect_design_files().filtered(
            lambda f: not f.design_order_id)
        if orphans:
            orphans.write({'design_order_id': order.id})
        return order

    def action_confirm(self):
        res = super().action_confirm()
        if self._design_auto_create_enabled():
            for order in self:
                order._ensure_design_order()
        return res

    def action_view_design_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'design.order',
            'name': 'Design Orders',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id},
        }
