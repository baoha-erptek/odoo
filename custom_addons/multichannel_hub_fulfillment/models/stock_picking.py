"""stock.picking extension — advance the SO pipeline to 'shipped' when a
dropship picking transitions to done.

Per ADR-010 Amendment 2026-05-03 (P1-DROP-CALLSITE), the SO pipeline
follows the standard procurement lifecycle: PO confirm pushes to Gearment
(state=confirmed), and dropship picking validation marks the SO as
shipped. `_action_done` is the canonical hook — fires after a picking
transitions to `done` regardless of which UI/API path triggered it.

ESTY-248 — surface the linked sale order's Gearment fulfillment status on
the picking form. `tracking_state`/`production_blocked`/`block_reason` are
the fields genuinely kept live by the Gearment webhook dispatcher (see
`services/gearment_webhook_dispatcher.py`); `x_gearment_status` was
considered but is only ever stamped once at push time and never updated
by any webhook handler, so it would be misleading here.

Security note: related fields do NOT inherit the source model's read ACL —
a user with `stock.picking` read access (gated by `stock.group_stock_user`,
i.e. any warehouse/stock operator) but no `sale.order.fulfillment` read
access could otherwise read `block_reason` (internal BA/production notes)
through this related field, bypassing the fulfillment model's own ACL
(`sales_team.group_salesman` / `group_production_team` /
`sales_team.group_sale_manager` in multichannel_hub_core's
ir.model.access.csv). `x_gearment_block_reason` mirrors those same groups
to close that gap; `tracking_state` and `production_blocked` are plain
operational status a warehouse operator legitimately needs, so they stay
ungated.
"""
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

_FULFILLMENT_NOTE_GROUPS = (
    'sales_team.group_sale_salesman,'
    'multichannel_hub_core.group_production_team,'
    'sales_team.group_sale_manager'
)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    x_gearment_tracking_state = fields.Selection(
        related='sale_id.tracking_state',
        string='Gearment Tracking Status',
        readonly=True,
        help="Shipment/fulfillment state as last reported by Gearment webhooks.",
    )
    x_gearment_production_blocked = fields.Boolean(
        related='sale_id.production_blocked',
        string='Gearment Production Blocked',
        readonly=True,
    )
    x_gearment_block_reason = fields.Text(
        related='sale_id.block_reason',
        string='Gearment Block Reason',
        readonly=True,
        groups=_FULFILLMENT_NOTE_GROUPS,
    )

    def _action_done(self):
        """Override to advance linked SO pipelines to 'shipped' for
        completed dropship pickings.
        """
        result = super()._action_done()
        for picking in self:
            if picking.picking_type_id.code != 'dropship':
                continue
            if not picking.sale_id:
                continue
            picking.sale_id._advance_pipeline_to('shipped')
        return result
