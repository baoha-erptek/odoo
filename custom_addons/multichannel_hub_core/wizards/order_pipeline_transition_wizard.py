"""Phase D#3 — operator wizard to move an order to a new pipeline state.

Flow 3a #3 / Flow 4 #3 ("Pipeline" tab + transition). Direct writes to
`sale.order.x_pipeline_state_id` are blocked by the FR-017 write guard; the
only sanctioned path is `sale.order._write_pipeline_state(...)`, which records
an `order.pipeline.transition.log` row in the same transaction. This wizard is
the UI for that helper.
"""

from odoo import _, fields, models


class OrderPipelineTransitionWizard(models.TransientModel):
    _name = 'order.pipeline.transition.wizard'
    _description = 'Pipeline State Transition Wizard'

    order_id = fields.Many2one(
        'sale.order', string='Order', required=True, ondelete='cascade',
    )
    pipeline_id = fields.Many2one(
        related='order_id.x_pipeline_id', string='Pipeline', readonly=True,
    )
    current_state_id = fields.Many2one(
        related='order_id.x_pipeline_state_id', string='Current State',
        readonly=True,
    )
    new_state_id = fields.Many2one(
        'order.pipeline.state', string='New State', required=True,
        domain="[('pipeline_id', '=', pipeline_id)]",
        help='Target stage on this order\'s pipeline.',
    )
    note = fields.Text(
        string='Note', help='Optional reason recorded in the transition log.',
    )

    def action_confirm(self):
        self.ensure_one()
        # _write_pipeline_state validates the state belongs to the order's
        # pipeline and writes the audit-log row in the same transaction.
        self.order_id._write_pipeline_state(
            self.new_state_id, note=self.note or None, change_type='manual',
        )
        return {'type': 'ir.actions.act_window_close'}
