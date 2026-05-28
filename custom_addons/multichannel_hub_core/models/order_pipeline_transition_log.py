"""order.pipeline.transition.log — append-only audit of pipeline state changes.

Per ADR-010 §1 + data-model.md §12. Written in the same transaction as the
state change via `sale.order._write_pipeline_state`.
"""
from odoo import fields, models


class OrderPipelineTransitionLog(models.Model):
    _name = 'order.pipeline.transition.log'
    _description = 'Order pipeline transition audit log'
    _order = 'timestamp desc, id desc'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        ondelete='cascade',
        index=True,
    )
    pipeline_id = fields.Many2one(
        'order.pipeline',
        string='Pipeline',
        required=True,
        ondelete='restrict',
    )
    from_state_id = fields.Many2one(
        'order.pipeline.state',
        string='From State',
        ondelete='set null',
        help="Null for initial state on order create.",
    )
    to_state_id = fields.Many2one(
        'order.pipeline.state',
        string='To State',
        required=True,
        ondelete='restrict',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Performed By',
        default=lambda self: self.env.user.id,
        required=True,
        ondelete='restrict',
    )
    timestamp = fields.Datetime(
        string='Timestamp',
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    change_type = fields.Selection(
        [
            ('initial', 'Initial Assignment'),
            ('manual', 'Manual Transition'),
            ('automatic', 'Automatic'),
            ('rollback', 'Rollback'),
            ('migration', 'Migration / Backfill'),
        ],
        string='Change Type',
        required=True,
        default='manual',
    )
    note = fields.Text(string='Note')

    def init(self):
        """Composite index for hot-path 'recent transitions per order'."""
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS order_pipeline_transition_log_order_ts_idx
            ON order_pipeline_transition_log (sale_order_id, timestamp DESC)
        """)
