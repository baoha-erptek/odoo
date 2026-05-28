"""tracking.import.log — audit envelope for one GKE Excel import.

Per Spec 004a §1 + ADR. One log → many `tracking.import.line`.

Constraints:
- C-TIL-001: file_size_bytes ≤ ICP `multichannel_hub.large_file_threshold_bytes`
- C-TIL-002: terminal state {ok, warning, error} requires finish_at ≥ start_at

Indexes via init() drift-template (project_sql_constraints_drift):
- composite (state, create_date DESC) — Tracking Dashboard recent-imports
- schema_hash via field index=True
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_TERMINAL_STATES = ('ok', 'warning', 'error')


class TrackingImportLog(models.Model):
    _name = 'tracking.import.log'
    _description = 'GKE tracking import — audit log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'tracking.import.log.seq') or '/',
    )
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('ok', 'OK'),
            ('warning', 'Warning'),
            ('error', 'Error'),
        ],
        string='State',
        required=True,
        default='pending',
        tracking=True,
        index=True,
    )
    source = fields.Selection(
        [('manual', 'Manual upload'), ('gdrive', 'GDrive poll')],
        string='Source',
        required=True,
        default='manual',
    )
    source_gdrive_file_id = fields.Char(
        string='GDrive File ID',
        copy=False,
        help='Set when source=gdrive (P2-06).',
    )
    filename = fields.Char(string='Filename', required=True)
    file_size_bytes = fields.Integer(string='File Size (bytes)', default=0)
    schema_hash = fields.Char(
        string='Schema Hash',
        size=64,
        required=True,
        index=True,
        help='SHA-256 of normalized header sequence.',
    )
    header_columns = fields.Text(
        string='Header Columns (JSON)',
        required=True,
        help='Original header sequence as JSON array (forensic).',
    )
    is_new_schema = fields.Boolean(
        string='New Schema',
        default=False,
        tracking=True,
        help='True if schema_hash not in approved set at upload time.',
    )

    total_rows = fields.Integer(string='Total Rows', default=0)
    matched_count = fields.Integer(string='Matched', default=0)
    unmatched_count = fields.Integer(string='Unmatched', default=0)
    conflict_count = fields.Integer(string='Conflict', default=0)
    error_count = fields.Integer(string='Errors', default=0)
    imported_count = fields.Integer(string='Imported', default=0)
    address_change_flagged_count = fields.Integer(
        string='Address-Change Flagged', default=0)

    line_ids = fields.One2many(
        'tracking.import.line', 'log_id', string='Lines')

    start_at = fields.Datetime(string='Started At')
    finish_at = fields.Datetime(string='Finished At')
    triggered_by_user_id = fields.Many2one(
        'res.users', string='Triggered By',
        required=True, default=lambda self: self.env.user.id, ondelete='restrict')
    notes = fields.Html(string='Notes')

    _sql_constraints = [
        ('tracking_import_log_name_uniq', 'UNIQUE(name)',
         'Tracking import log reference must be unique.'),
    ]

    def init(self):
        """Composite index + UNIQUE drift mirror (project_sql_constraints_drift)."""
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS tracking_import_log_state_create_date_idx
            ON tracking_import_log (state, create_date DESC)
        """)
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'tracking_import_log_name_uniq'
                ) THEN
                    ALTER TABLE tracking_import_log
                    ADD CONSTRAINT tracking_import_log_name_uniq UNIQUE (name);
                END IF;
            END
            $$;
        """)

    @api.constrains('file_size_bytes')
    def _check_file_size_under_cap(self):
        """C-TIL-001: enforce file size ≤ ICP threshold."""
        cap_str = self.env['ir.config_parameter'].sudo().get_param(
            'multichannel_hub.large_file_threshold_bytes', '10485760')
        try:
            cap = int(cap_str)
        except (TypeError, ValueError):
            cap = 10 * 1024 * 1024
        for log in self:
            if log.file_size_bytes and log.file_size_bytes > cap:
                raise ValidationError(_(
                    "Tracking import file (%(size)s bytes) exceeds the "
                    "configured cap of %(cap)s bytes.",
                    size=log.file_size_bytes, cap=cap,
                ))

    @api.constrains('state', 'finish_at', 'start_at')
    def _check_terminal_finish_at(self):
        """C-TIL-002: terminal state requires finish_at; if start_at set,
        finish_at >= start_at."""
        for log in self:
            if log.state in _TERMINAL_STATES:
                if not log.finish_at:
                    raise ValidationError(_(
                        "Tracking import %(name)s in terminal state '%(state)s' "
                        "requires finish_at.",
                        name=log.name, state=log.state,
                    ))
                if log.start_at and log.finish_at < log.start_at:
                    raise ValidationError(_(
                        "finish_at must be >= start_at on %(name)s.",
                        name=log.name,
                    ))

    # ------------------------------------------------------------------
    # P2-04 — replay support + smart-button.
    # ------------------------------------------------------------------
    def _recount_summary(self):
        """Recompute summary counts from child line state distribution.

        Called after `action_replay_line` mutates a line's state. Uses
        `read_group` for DB-side aggregation (acceptable up to ~5K lines).
        """
        Line = self.env['tracking.import.line']
        for log in self:
            groups = Line.read_group(
                [('log_id', '=', log.id)],
                ['state'],
                ['state'],
            )
            counts = {g['state']: g['state_count'] for g in groups}
            log.write({
                'matched_count': counts.get('matched', 0),
                'unmatched_count': counts.get('unmatched', 0),
                'conflict_count': counts.get('conflict', 0),
                'error_count': counts.get('error', 0),
                'imported_count': counts.get('imported', 0),
            })

    def action_view_today_imports(self):
        """Smart-button: open Imports list filtered to today's create_date.

        Domain is built in Python to avoid XML serialization of `timedelta`.
        Returns an `ir.actions.act_window` dict.
        """
        today_str = fields.Datetime.now().strftime('%Y-%m-%d 00:00:00')
        return {
            'type': 'ir.actions.act_window',
            'name': _("Today's GKE Imports"),
            'res_model': 'tracking.import.log',
            'view_mode': 'list,form',
            'domain': [('create_date', '>=', today_str)],
        }
