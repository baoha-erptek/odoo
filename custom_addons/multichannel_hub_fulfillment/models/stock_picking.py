"""stock.picking extension — advance the SO pipeline to 'shipped' when a
dropship picking transitions to done.

Per ADR-010 Amendment 2026-05-03 (P1-DROP-CALLSITE), the SO pipeline
follows the standard procurement lifecycle: PO confirm pushes to Gearment
(state=confirmed), and dropship picking validation marks the SO as
shipped. `_action_done` is the canonical hook — fires after a picking
transitions to `done` regardless of which UI/API path triggered it.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

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
