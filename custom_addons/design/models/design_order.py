"""design.order — the design document ("phiếu design").

ESTY-244: a first-class approval document per sale order, parallel to
sale.order / mrp.production. Owns the design workflow; the underlying files
stay as `design.file` rows (defined in multichannel_hub_core) linked via
`design_order_id`.

On approval ('Duyệt'):
  - the linked sale order advances to the `design_ready` pipeline stage
    (via the existing order.pipeline.state layer — ADR-018 / plan §3), and
  - every approved design file is attached to the linked mrp.production(s).
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

# Pipeline-state code seeded by data/design_pipeline_state_seed.xml on each
# production pipeline. Approval drives the SO to this stage.
DESIGN_READY_CODE = 'design_ready'


class DesignOrder(models.Model):
    _name = 'design.order'
    _description = 'Design Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date DESC, id DESC'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'), tracking=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order', string='Sale Order', required=True, index=True,
        ondelete='cascade', copy=False, tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner', string='Customer',
        related='sale_order_id.partner_id', store=True, readonly=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        [
            ('pending', 'Chờ duyệt'),
            ('proof_sent', 'Đã gửi proof'),
            ('approved', 'Duyệt'),
            ('rejected', 'Cần chỉnh lại'),
        ],
        string='Status', required=True, default='pending',
        tracking=True, index=True, copy=False,
    )
    design_file_ids = fields.One2many(
        'design.file', 'design_order_id', string='Design Files',
    )
    design_files_count = fields.Integer(
        string='Files', compute='_compute_design_files_count',
    )
    approved_files_count = fields.Integer(
        string='Approved Files', compute='_compute_design_files_count',
    )
    approved_by = fields.Many2one(
        'res.users', string='Approved By', readonly=True,
        ondelete='set null', copy=False,
    )
    approved_at = fields.Datetime(string='Approved At', readonly=True, copy=False)
    rejection_reason = fields.Text(string='Rejection Reason', tracking=True)

    _sql_constraints = [
        # P1 (owner default): one design.order per sale.order.
        # Declarative form kept for the error message; also enforced in init()
        # because _sql_constraints UNIQUE has been observed not to deploy on
        # this codebase (memory project_sql_constraints_drift.md).
        ('uniq_design_order_sale_order', 'UNIQUE(sale_order_id)',
         'A design order already exists for this sale order.'),
    ]

    def init(self):
        """Belt-and-braces UNIQUE(sale_order_id) — see _sql_constraints note."""
        self.env.cr.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'design_order_uniq_design_order_sale_order'
                ) THEN
                    ALTER TABLE design_order
                        ADD CONSTRAINT design_order_uniq_design_order_sale_order
                        UNIQUE (sale_order_id);
                END IF;
            END $$
        """)

    # ------------------------------------------------------------- compute
    @api.depends('design_file_ids', 'design_file_ids.state')
    def _compute_design_files_count(self):
        for rec in self:
            files = rec.design_file_ids
            rec.design_files_count = len(files)
            rec.approved_files_count = len(
                files.filtered(lambda f: f.state == 'approved'))

    # ------------------------------------------------------------- helpers
    def _check_production_team_or_raise(self):
        """Approval/rejection is production-team work (mirrors design.file gate)."""
        u = self.env.user
        if u.has_group('multichannel_hub_core.group_production_team') \
                or u.has_group('base.group_system'):
            return
        raise AccessError(_(
            "Only members of the Production Team may approve or reject a "
            "design order."))

    def _linked_productions(self):
        """Manufacturing order(s) for this design order's sale order.

        Resolved the same way the existing MO<->pipeline sync does
        (mrp.production.origin == sale order name). May be empty (MO not yet
        created for MTO/dropship — attachment then no-ops).
        """
        self.ensure_one()
        so = self.sale_order_id
        if not so or not so.name:
            return self.env['mrp.production']
        return self.env['mrp.production'].search([('origin', '=', so.name)])

    def _advance_pipeline_to_design_ready(self):
        """Move the linked SO to the `design_ready` pipeline stage (automatic).

        No-op (logged) when the order has no pipeline, or its pipeline lacks a
        `design_ready` code — mirrors the graceful skip in the MO-boundary sync.
        """
        self.ensure_one()
        so = self.sale_order_id
        if not so or not so.x_pipeline_id:
            return
        target = so.x_pipeline_id.state_ids.filtered(
            lambda s: s.code == DESIGN_READY_CODE)[:1]
        if not target:
            _logger.info(
                "design.order %s: pipeline '%s' has no state code='%s'; "
                "skipping pipeline advance.",
                self.name, so.x_pipeline_id.name, DESIGN_READY_CODE)
            return
        if so.x_pipeline_state_id == target:
            return
        # change_type='automatic': this is a system-driven sync (same contract
        # as the MO-boundary sync in mhc). design_ready is a non-terminal stage
        # (seq 15, no is_terminal in the seed), so bypassing the terminal-stage
        # guard is correct — using 'manual' would wrongly trip that guard.
        so._write_pipeline_state(
            target, note=_("Design order %s approved") % self.name,
            change_type='automatic')

    def _attach_approved_files_to_productions(self):
        """Attach approved design files to the linked MO(s) as ir.attachment.

        Handles all storage modes: 'small' copies the binary; 'url'/'gdrive'
        create a link-style attachment (URL in name/description) since there is
        no binary to store. Idempotent per (file, production): skips if an
        attachment already tags that file onto that MO.
        """
        self.ensure_one()
        productions = self._linked_productions()
        if not productions:
            return 0
        approved = self.design_file_ids.filtered(lambda f: f.state == 'approved')
        if not approved:
            return 0
        # sudo: production-team users may not hold generic ir.attachment write
        # scope on mrp.production. Bounded to internal writes here — the payload
        # is a validated design.file (URL scheme + gdrive-id already enforced by
        # design.file constraints in mhc) plus an internal dedup marker.
        Attachment = self.env['ir.attachment'].sudo()
        created = 0
        for mo in productions:
            for f in approved:
                marker = 'design.file:%s' % f.id
                exists = Attachment.search([
                    ('res_model', '=', 'mrp.production'),
                    ('res_id', '=', mo.id),
                    ('description', '=', marker),
                ], limit=1)
                if exists:
                    continue
                vals = {
                    'name': _("Design %s — %s") % (self.name, f.name or f.id),
                    'res_model': 'mrp.production',
                    'res_id': mo.id,
                    'description': marker,
                }
                if f.storage_mode == 'small' and f.design_file:
                    vals.update({'type': 'binary', 'datas': f.design_file,
                                 'name': f.file_name or vals['name']})
                else:
                    url = f.file_url or f.gdrive_preview_url or ''
                    vals.update({'type': 'url', 'url': url})
                Attachment.create(vals)
                created += 1
        return created

    # ------------------------------------------------------------- CRUD
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'design.order') or _('New')
        return super().create(vals_list)

    # ------------------------------------------------------------- actions
    def action_approve(self):
        """Production team approves the design order → 'Duyệt' + side-effects."""
        self._check_production_team_or_raise()
        for rec in self:
            if rec.state == 'approved':
                continue
            rec.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_at': fields.Datetime.now(),
            })
            rec._advance_pipeline_to_design_ready()
            rec._attach_approved_files_to_productions()

    def action_reject(self):
        """Production team rejects the design order (requires a reason)."""
        self._check_production_team_or_raise()
        for rec in self:
            if not rec.rejection_reason or not rec.rejection_reason.strip():
                raise ValidationError(_(
                    "Cannot reject design order '%(name)s' without a "
                    "rejection reason.", name=rec.name))
            rec.write({'state': 'rejected'})

    def action_reset_to_pending(self):
        self._check_production_team_or_raise()
        self.write({'state': 'pending'})

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
        }
