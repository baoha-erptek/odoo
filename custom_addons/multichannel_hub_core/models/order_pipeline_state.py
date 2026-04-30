"""order.pipeline.state — stage of an order.pipeline.

Per ADR-010 §1: stages form a directed graph via `next_state_ids` (M2M self).
The transition helper `sale.order._write_pipeline_state(new)` writes
`order.pipeline.transition.log` row in the same transaction.

Constraints (per spec):
- C-PS-001: exactly one `is_initial=True` per pipeline
- C-PS-002: at least one `is_terminal=True` per pipeline (deferred — runtime
  editor can leave a pipeline mid-construction)
- C-PS-003: `(pipeline_id, code)` UNIQUE
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class OrderPipelineState(models.Model):
    _name = 'order.pipeline.state'
    _description = 'Order pipeline stage'
    _order = 'pipeline_id, sequence, name'

    pipeline_id = fields.Many2one(
        'order.pipeline',
        string='Pipeline',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(
        string='Code',
        required=True,
        help="Stable per-pipeline machine code (e.g., 'pending_file').",
    )
    sequence = fields.Integer(string='Sequence', default=10)
    is_initial = fields.Boolean(
        string='Initial State',
        default=False,
        help="The state assigned to a new order on this pipeline. "
             "Exactly one per pipeline.",
    )
    is_terminal = fields.Boolean(
        string='Terminal State',
        default=False,
        help="True for done/cancelled-style end states. May be more than one.",
    )
    color = fields.Integer(
        string='Color Index',
        default=0,
        help="Kanban color (0-11) for badge rendering on dashboards.",
    )
    next_state_ids = fields.Many2many(
        'order.pipeline.state',
        'order_pipeline_state_next_rel',
        'state_id',
        'next_state_id',
        string='Next States',
        help="Allowed transitions from this state. Empty = no enforcement "
             "(any state on the same pipeline reachable).",
    )
    team_id = fields.Many2one(
        'pipeline.team',
        string='Owning Team',
        ondelete='set null',
        help="Who owns this stage. Drives default-assignee + dashboard filters.",
    )
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('uniq_pipeline_state_code',
         'UNIQUE(pipeline_id, code)',
         'State code must be unique within a pipeline.'),
    ]

    def init(self):
        """Belt-and-braces drift template (project_sql_constraints_drift)."""
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'order_pipeline_state_uniq_pipeline_code'
                ) THEN
                    ALTER TABLE order_pipeline_state
                    ADD CONSTRAINT order_pipeline_state_uniq_pipeline_code
                    UNIQUE (pipeline_id, code);
                END IF;
            END
            $$;
        """)

    @api.constrains('is_initial', 'pipeline_id')
    def _check_one_initial_per_pipeline(self):
        """C-PS-001: exactly one initial state per pipeline."""
        for state in self:
            if not state.is_initial:
                continue
            others = self.search([
                ('pipeline_id', '=', state.pipeline_id.id),
                ('is_initial', '=', True),
                ('id', '!=', state.id),
            ])
            if others:
                raise ValidationError(_(
                    "Pipeline %(name)s already has an initial state (%(other)s). "
                    "Only one is allowed.",
                    name=state.pipeline_id.name,
                    other=others[0].name,
                ))
