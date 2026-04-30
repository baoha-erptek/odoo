"""design.file — file record for design assets attached to orders.

P1-02a MVP scope (URL-mode focus, no GDrive upload, no routing):
  - Storage modes: 'url' (default — paste a GDrive / CDN link)
                   'small' (≤10 MB binary in filestore)
  - 3-state approval: pending → approved / rejected
  - Production-team RPC gate on state writes (kanban drag-drop safe)
  - Immutable history via parent_file_id + version
  - Historical seed from sale.order.line.etsy_design_link_front/back

Deferred (subsequent slices):
  - storage_mode='gdrive' + GDrive upload wizard (P1-02c)
  - design.file.route (P1-02b)
  - design.print.batch + bulk PDF (P1-02d)

References: ADR-006 §3, ADR-009 §1, data-model.md §6, FR-018..023.
"""
import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

_DEFAULT_LARGE_FILE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10 MB per ADR-006 §2


class DesignFile(models.Model):
    _name = 'design.file'
    _description = 'Design File'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date DESC, id DESC'

    name = fields.Char(string='Name', required=True, tracking=True)

    order_id = fields.Many2one(
        'sale.order',
        string='Order',
        ondelete='cascade',
        index=True,
        help="Set for order-level files (mockups). Mutually exclusive with order_line_id (C-DF-001).",
    )
    order_line_id = fields.Many2one(
        'sale.order.line',
        string='Order Line',
        ondelete='cascade',
        index=True,
        help="Set for line-level files (per-product designs). Mutually exclusive with order_id (C-DF-001).",
    )

    parent_file_id = fields.Many2one(
        'design.file',
        string='Previous Version',
        ondelete='set null',
        index=True,
        help="Points to the design.file record this one supersedes. Set when re-uploading after rejection (C-DF-005).",
    )
    version = fields.Integer(string='Version', default=1, required=True)

    storage_mode = fields.Selection(
        [('small', 'Small (filestore ≤10 MB)'), ('url', 'URL')],
        string='Storage Mode',
        required=True,
        default='url',
        tracking=True,
    )
    design_file = fields.Binary(
        string='Design File',
        attachment=True,
        help="Used when storage_mode='small'. Hard-capped via ir.attachment override + @api.constrains.",
    )
    preview_file = fields.Binary(string='Preview', attachment=True, help="Local thumbnail (≤2 MB).")
    file_url = fields.Char(string='File URL', help="Used when storage_mode='url'. GDrive shareable URL or external CDN.")
    file_name = fields.Char(string='File Name')
    file_size = fields.Integer(string='File Size (bytes)')
    file_checksum = fields.Char(string='SHA-256 Checksum')

    state = fields.Selection(
        [
            ('pending', 'Chờ duyệt'),
            ('approved', 'Duyệt'),
            ('rejected', 'Cần chỉnh lại'),
        ],
        string='Status',
        required=True,
        default='pending',
        tracking=True,
        index=True,
    )
    rejection_reason = fields.Text(string='Rejection Reason', tracking=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True, ondelete='set null')
    approved_at = fields.Datetime(string='Approved At', readonly=True)

    is_seed = fields.Boolean(
        string='Historical Seed',
        default=False,
        help="True for rows backfilled from historical etsy_design_link_* columns (T078).",
    )

    # P1-02b — Design file routing
    route_ids = fields.One2many(
        'design.file.route',
        'design_file_id',
        string='Routes',
        help="Delivery routes for this design file (P1-02b routing).",
    )

    _sql_constraints = [
        # Declarative form — also enforced via init() raw SQL because
        # _sql_constraints UNIQUE has been observed to silently fail to
        # deploy on this codebase (see memory project_sql_constraints_drift.md
        # and 002 etsy.email.log incident). init() is the belt-and-braces
        # guarantee that the DB-level constraint exists.
        (
            'uniq_design_file_order_line_url',
            'UNIQUE(order_line_id, file_url)',
            'A design file with the same URL already exists on this order line.',
        ),
    ]

    def init(self):
        """Create DB-level objects that Odoo's declarative path may miss.

        - Composite indexes on (order_id, state) and (order_line_id, state)
          for the dashboard hot-path filters; index=True on a single field
          can't express composites.
        - UNIQUE(order_line_id, file_url) constraint as a belt-and-braces
          mirror of _sql_constraints (see memory project_sql_constraints_drift.md).
        """
        cr = self.env.cr
        cr.execute("""
            CREATE INDEX IF NOT EXISTS design_file_order_id_state_idx
                ON design_file (order_id, state)
        """)
        cr.execute("""
            CREATE INDEX IF NOT EXISTS design_file_order_line_id_state_idx
                ON design_file (order_line_id, state)
        """)
        # ALTER TABLE ADD CONSTRAINT is not idempotent; pre-check pg_constraint
        # so re-runs (-u) silently no-op. Catching duplicate_object alone is not
        # enough — PG creates an index with the constraint name, which raises
        # duplicate_table (42P07), not duplicate_object (42710), on re-run.
        cr.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uniq_design_file_order_line_url'
                ) THEN
                    ALTER TABLE design_file
                        ADD CONSTRAINT uniq_design_file_order_line_url
                        UNIQUE (order_line_id, file_url);
                END IF;
            END $$
        """)

    # --------------------------------------------------------------- constraints

    @api.constrains('order_id', 'order_line_id')
    def _check_xor_order_link(self):
        """C-DF-001: exactly one of order_id / order_line_id must be set."""
        for rec in self:
            if bool(rec.order_id) == bool(rec.order_line_id):
                raise ValidationError(
                    _("Design file '%(name)s' must be linked to exactly one of: "
                      "an order or an order line (not both, not neither).",
                      name=rec.name or '?')
                )

    @api.constrains('storage_mode', 'design_file')
    def _check_storage_mode_small_size_cap(self):
        """C-DF-002: storage_mode='small' enforces threshold (default 10 MB)."""
        threshold = self._get_size_threshold()
        for rec in self:
            if rec.storage_mode != 'small':
                continue
            if not rec.design_file:
                continue
            actual_size = self._actual_binary_size(rec.design_file)
            if actual_size > threshold:
                raise ValidationError(_(
                    "Design file '%(name)s' (%(size).1f MB) exceeds the "
                    "%(threshold).1f MB limit. Use URL mode or upload to "
                    "Drive/S3 and paste the link instead.",
                    name=rec.name or '?',
                    size=actual_size / 1024 / 1024,
                    threshold=threshold / 1024 / 1024,
                ))

    @api.constrains('storage_mode', 'file_url')
    def _check_storage_mode_url_requires_file_url(self):
        """C-DF-003: storage_mode='url' requires a non-empty file_url."""
        for rec in self:
            if rec.storage_mode == 'url' and not rec.file_url:
                raise ValidationError(_(
                    "Design file '%(name)s' uses URL storage mode but has no "
                    "file_url. Paste a GDrive / CDN link or switch to small "
                    "storage mode.",
                    name=rec.name or '?',
                ))

    # ------------------------------------------------------------- helpers

    @api.model
    def _get_size_threshold(self):
        """Read the configurable threshold (bytes) for the small-mode size cap."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'multichannel_hub.large_file_threshold_bytes',
            str(_DEFAULT_LARGE_FILE_THRESHOLD_BYTES),
        )
        try:
            return int(param)
        except (TypeError, ValueError):
            _logger.warning(
                "multichannel_hub.large_file_threshold_bytes=%r is not an int; "
                "falling back to default %s",
                param, _DEFAULT_LARGE_FILE_THRESHOLD_BYTES,
            )
            return _DEFAULT_LARGE_FILE_THRESHOLD_BYTES

    @staticmethod
    def _actual_binary_size(value):
        """Best-effort decoded length for a Binary field value (base64 bytes/str)."""
        if not value:
            return 0
        try:
            return len(base64.b64decode(value))
        except (TypeError, ValueError, base64.binascii.Error):
            return len(value)

    def _check_production_team_or_raise(self):
        """RPC-level gate per P1-04 finding (view groups alone are XML-RPC-bypassable)."""
        if self.env.user.has_group('multichannel_hub_core.group_production_team'):
            return
        if self.env.user.has_group('base.group_system'):
            return
        raise AccessError(_(
            "Only members of the Production Team may change the approval state "
            "of a design file."
        ))

    # ------------------------------------------------------------- CRUD overrides

    def write(self, vals):
        """Gate state writes (covers kanban drag-drop, which calls write under the hood)."""
        if 'state' in vals:
            self._check_production_team_or_raise()
        return super().write(vals)

    # ------------------------------------------------------------- actions

    def action_approve(self):
        """Production team approves a pending design file."""
        self._check_production_team_or_raise()
        for rec in self:
            rec.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_at': fields.Datetime.now(),
            })

    def action_reject(self, reason=None):
        """Production team rejects a pending design file (requires rejection_reason)."""
        self._check_production_team_or_raise()
        for rec in self:
            effective_reason = reason if reason is not None else rec.rejection_reason
            if not effective_reason or not str(effective_reason).strip():
                raise ValidationError(_(
                    "Cannot reject design file '%(name)s' without a rejection reason.",
                    name=rec.name or '?',
                ))
            rec.write({
                'state': 'rejected',
                'rejection_reason': effective_reason,
            })

    # ------------------------------------------------------------- T078 historical seed

    @api.model
    def _seed_from_historical_lines(self, batch_size=500):
        """Backfill design.file rows from sale.order.line.etsy_design_link_*.

        Idempotent — safe to call multiple times. Matches existing rows on
        (order_line_id, file_url) and skips them. Empty / null URLs are
        skipped.

        Seed rows are marked is_seed=True with state='approved' (proof-of-record;
        historical orders were already shipped). See findings.md
        2026-04-29 (P1-02a, D3) for the rationale.

        Returns the count of newly created rows (excluding skipped duplicates).
        """
        SaleOrderLine = self.env['sale.order.line']

        # The columns only exist if etsy_integration is installed against the
        # same DB. Probe before touching them.
        if 'etsy_design_link_front' not in SaleOrderLine._fields:
            _logger.info(
                "design.file._seed_from_historical_lines: "
                "sale.order.line has no etsy_design_link_front field — "
                "etsy_integration not installed; skipping seed.",
            )
            return 0

        candidates = SaleOrderLine.search([
            '|',
            ('etsy_design_link_front', '!=', False),
            ('etsy_design_link_back', '!=', False),
        ])

        created = 0
        roles = (
            ('etsy_design_link_front', 'Front'),
            ('etsy_design_link_back', 'Back'),
        )

        for offset in range(0, len(candidates), batch_size):
            batch = candidates[offset:offset + batch_size]
            for line in batch:
                for field_name, role_label in roles:
                    url = (getattr(line, field_name) or '').strip()
                    if not url:
                        continue
                    existing = self.search([
                        ('order_line_id', '=', line.id),
                        ('file_url', '=', url),
                    ], limit=1)
                    if existing:
                        continue
                    order_ref = line.order_id.name or line.order_id.id or '?'
                    self.create({
                        'name': f"[Historical] {order_ref} — {role_label} design",
                        'order_line_id': line.id,
                        'storage_mode': 'url',
                        'file_url': url,
                        'state': 'approved',
                        'is_seed': True,
                    })
                    created += 1

        _logger.info(
            "design.file._seed_from_historical_lines: seeded %s rows "
            "from %s candidate lines.",
            created, len(candidates),
        )
        return created
