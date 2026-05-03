"""pipeline.team — runtime-editable team list owning pipeline stages.

Per ADR-010 §1: each `order.pipeline.state` may have a `team_id` so the
operations dashboard can group/filter by who owns the stage. Membership
controls who appears in user-pickers; record-rule enforcement deferred to
P1-PIPELINE-FULL+ (post-tomorrow).
"""
from odoo import fields, models


class PipelineTeam(models.Model):
    _name = 'pipeline.team'
    _description = 'Pipeline ownership team'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True, translate=True, tracking=True)
    code = fields.Char(string='Code', required=True, tracking=True)
    sequence = fields.Integer(string='Sequence', default=10)
    is_active = fields.Boolean(string='Active', default=True)
    member_ids = fields.Many2many(
        'res.users',
        'pipeline_team_user_rel',
        'team_id',
        'user_id',
        string='Members',
        help="Users participating in this team. Drives default-assignee pickers.",
    )
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('uniq_pipeline_team_code',
         'UNIQUE(code)',
         'Pipeline team code must be unique.'),
    ]

    def init(self):
        """Belt-and-braces drift template (project_sql_constraints_drift)."""
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'pipeline_team_uniq_code'
                ) THEN
                    ALTER TABLE pipeline_team
                    ADD CONSTRAINT pipeline_team_uniq_code UNIQUE (code);
                END IF;
            END
            $$;
        """)
