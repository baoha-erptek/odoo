"""mrp.production extension — surface design-order readiness on the MO (ESTY-249).

Production staff open a manufacturing order (đơn sản xuất) and need to know the
design file has been approved before they start. The literal ticket ("a state
before Draft") does not fit Odoo 19 — mrp.production.state is computed + readonly
(addons/mrp/models/mrp_production.py) and the project tracks granular workflow on
the sale.order pipeline, not the MO's fixed 6-state model. So this adds an
*informational* computed indicator (badge/banner + smart button), not a new state.

The MO<->design.order link reuses the established `MO.origin == sale_order.name`
resolution (design/models/design_order.py, mhc/models/mrp_production.py). Both
fields are non-stored: `design_ready` keys off the linked design.order's approval
state, which is not a declarable @api.depends path from the MO, so it recomputes
on read (a fresh form load is always current).
ponytail: non-stored + recompute-on-read is enough for a read-only badge; storing
it would need an inverse trigger on design.order.write for no user-visible gain.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    design_order_id = fields.Many2one(
        'design.order', string='Design Order',
        compute='_compute_design_readiness',
        help="Design order linked to this MO's sale order (via origin).")
    design_ready = fields.Boolean(
        string='Design Ready', compute='_compute_design_readiness',
        help="True once the linked design order has been approved (Duyệt).")

    @api.depends('origin', 'company_id')
    def _compute_design_readiness(self):
        DesignOrder = self.env['design.order']
        origins = [mo.origin for mo in self if mo.origin]
        # sudo: mrp/stock users need not hold design.order read access
        # (salesman-read is scoped to sale groups). Read-only lookup; batched
        # to one query. Keyed by (SO name, company) so the sudo does NOT bypass
        # multi-company isolation — SO names collide across companies.
        by_key = {}
        if origins:
            for order in DesignOrder.sudo().search(
                    [('sale_order_id.name', 'in', origins)]):
                by_key.setdefault(
                    (order.sale_order_id.name, order.company_id.id), order)
        for mo in self:
            order = by_key.get((mo.origin, mo.company_id.id), DesignOrder)
            mo.design_order_id = order
            mo.design_ready = order.state == 'approved'

    def action_view_design_order(self):
        self.ensure_one()
        if not self.design_order_id:
            raise UserError(_("No design order is linked to this "
                              "manufacturing order."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'design.order',
            'res_id': self.design_order_id.id,
            'view_mode': 'form',
        }
