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
import re
from html import escape

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

_DEFAULT_LARGE_FILE_THRESHOLD_BYTES = 10 * 1024 * 1024  # 10 MB per ADR-006 §2

# P1-DESIGN-URL-VALIDATION: Drive file IDs are alphanumeric + `_-`.
# Real IDs are 33+ chars; the regex stays permissive on length to
# survive Drive id-format changes but strict on the character set so
# the computed `gdrive_preview_url` cannot be hijacked.
_GDRIVE_FILE_ID_RE = re.compile(r'^[A-Za-z0-9_-]+$')


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
        [
            ('small', 'Small (filestore ≤10 MB)'),
            ('url', 'URL'),
            ('gdrive', 'Google Drive'),
        ],
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

    # GDrive storage fields (P1-09)
    gdrive_file_id = fields.Char(string='GDrive File ID')
    gdrive_folder_id = fields.Char(string='GDrive Folder ID')
    gdrive_preview_url = fields.Char(
        string='GDrive Preview URL',
        compute='_compute_gdrive_preview_url',
        store=True,
    )
    gdrive_thumbnail = fields.Binary(
        string='GDrive Thumbnail',
        attachment=True,
        help='Cached thumbnail generated from GDrive file.',
    )

    # P1-DESIGN-AUTO-ARCHIVE — soft-archive sibling files when one is
    # approved (per slice spec). Approved row keeps active=True; siblings
    # in non-approved states (pending/rejected) flip to active=False.
    # Pre-existing rejected rows are not retroactively archived
    # (preserves audit trail per slice notes).
    active = fields.Boolean(default=True, tracking=True)

    state = fields.Selection(
        [
            ('pending', 'Chờ duyệt'),
            ('proof_sent', 'Đã gửi proof'),
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
    # P1-DESIGN+GEARMENT — buyer-preview audit (D2 §2.1 row 3 + 5).
    proof_sent_at = fields.Datetime(string='Proof Sent At', readonly=True, tracking=True)
    proof_sent_by = fields.Many2one(
        'res.users', string='Proof Sent By',
        readonly=True, ondelete='set null', tracking=True)
    # P1-DESIGN-AUTO-GDRIVE — stamped when the cron promotes
    # storage_mode small → gdrive. Drives the local-blob retention
    # cleanup pass (deferred to a later slice).
    synced_to_gdrive_at = fields.Datetime(
        string='Synced to GDrive At',
        readonly=True,
        help="Stamped when cron promoted storage_mode 'small' to 'gdrive'.")

    is_seed = fields.Boolean(
        string='Historical Seed',
        default=False,
        help="True for rows backfilled from historical etsy_design_link_* columns (T078).",
    )

    # P1-DESIGN-AUTO-CREATE-FROM-EMAIL (ADR-009 amendment).
    # Audit provenance: distinguishes auto-seeded rows (email/API ingest) from
    # operator-uploaded rows. Existing rows are backfilled to 'migration_seed'
    # by migrations/19.0.1.0.35/post-migrate-backfill-created-via.py.
    created_via = fields.Selection(
        [
            ('migration_seed', 'Migration seed'),
            ('email_ingest', 'Email ingest'),
            ('api_ingest', 'API ingest'),
            ('operator_wizard', 'Operator wizard'),
        ],
        string='Created Via',
        default='operator_wizard',
        required=True,
        index=True,
        tracking=True,
        help="Audit provenance — how this design.file was created. "
             "Auto-seeded rows from email/API ingest start at state='pending' "
             "and require operator approval before Gearment push.",
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

    # --------------------------------------------------------------- compute

    @api.depends('gdrive_file_id')
    def _compute_gdrive_preview_url(self):
        """Compute GDrive preview URL from file_id."""
        for rec in self:
            if rec.gdrive_file_id:
                rec.gdrive_preview_url = (
                    f"https://drive.google.com/file/d/{rec.gdrive_file_id}/view"
                )
            else:
                rec.gdrive_preview_url = ''

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

    @api.constrains('storage_mode', 'gdrive_file_id', 'gdrive_folder_id')
    def _check_storage_mode_gdrive_requires_ids(self):
        """C-DF-006: storage_mode='gdrive' requires both gdrive_file_id and gdrive_folder_id."""
        for rec in self:
            if rec.storage_mode != 'gdrive':
                continue
            if not rec.gdrive_file_id or not rec.gdrive_folder_id:
                raise ValidationError(_(
                    "Design file '%(name)s' uses GDrive storage mode but is missing "
                    "file ID and/or folder ID. Both are required.",
                    name=rec.name or '?',
                ))

    @api.constrains('file_url')
    def _check_file_url_scheme(self):
        """P1-DESIGN-URL-VALIDATION: reject non-http(s) schemes on file_url.

        Defense-in-depth above the production-team write-ACL. The field
        feeds into outbound payloads to Gearment (printing_options[].url)
        AND into chatter rendering. Allow `http(s)://` only — reject
        `javascript:`, `data:`, `file:`, and relative paths so a malicious
        operator cannot smuggle XSS / SSRF / file-disclosure URLs into
        downstream consumers.
        """
        for rec in self:
            if not rec.file_url:
                continue
            url = rec.file_url.strip()
            if not (url.lower().startswith('https://') or
                    url.lower().startswith('http://')):
                raise ValidationError(_(
                    "Design file '%(name)s' has an invalid file_url. "
                    "Only http:// and https:// URLs are accepted; got %(scheme)s.",
                    name=rec.name or '?',
                    scheme=url.split(':', 1)[0] if ':' in url else url[:30],
                ))

    @api.constrains('gdrive_file_id')
    def _check_gdrive_file_id_format(self):
        """P1-DESIGN-URL-VALIDATION: enforce Drive id format `[A-Za-z0-9_-]+`.

        Real Drive file IDs are 33+ alphanumeric chars + `_` and `-`.
        Anything else (path separators, whitespace, URL query chars, HTML
        tags) lets an attacker control the computed `gdrive_preview_url`
        and exfiltrate cookies on user click.
        """
        for rec in self:
            if not rec.gdrive_file_id:
                continue
            if not _GDRIVE_FILE_ID_RE.match(rec.gdrive_file_id):
                raise ValidationError(_(
                    "Design file '%(name)s' has an invalid gdrive_file_id. "
                    "Only alphanumeric, underscore, and hyphen characters "
                    "are accepted (Drive id format).",
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
            "Only members of the Production Team may approve or reject "
            "a design file."
        ))

    def _check_ba_or_production_or_raise(self):
        """P1-DESIGN+GEARMENT — BA may send proofs; MP/system may also.

        BA cannot approve (that gate stays via `_check_production_team_or_raise`).
        """
        u = self.env.user
        if (u.has_group('multichannel_hub_fulfillment.group_ba_shipping')
                or u.has_group('multichannel_hub_core.group_production_team')
                or u.has_group('base.group_system')):
            return
        raise AccessError(_(
            "Only BA Shipping or Production Team members may send a "
            "design proof to the buyer."
        ))

    # ------------------------------------------------------------- CRUD overrides

    # State transitions allowed for the proof-cycle.
    _ALLOWED_STATE_TRANSITIONS = {
        'pending': {'proof_sent', 'approved', 'rejected'},
        'proof_sent': {'approved', 'rejected', 'pending'},
        'approved': set(),
        'rejected': {'pending', 'proof_sent'},
    }

    # State-machine enforcement happens in write() before super(); a
    # @api.constrains can't see the OLD state once the write has applied
    # (Odoo's _origin == self for stored writes).

    @staticmethod
    def _generate_preview_blob(design_blob):
        """Return raw JPEG thumbnail bytes for `design_blob` or None.

        Lazy-import keeps the test mock target stable
        (`...services.design_thumbnail_generator.ThumbnailGenerator`) and
        avoids loading PIL at registry-build time. Best-effort: any
        exception is swallowed and a WARNING is logged so a corrupt
        upload never blocks design.file creation.
        """
        if not design_blob:
            return None
        try:
            raw = base64.b64decode(design_blob) if isinstance(design_blob, (bytes, str)) else None
        except (TypeError, ValueError, base64.binascii.Error):
            raw = design_blob if isinstance(design_blob, bytes) else None
        if not raw:
            return None
        try:
            from odoo.addons.multichannel_hub_core.services.design_thumbnail_generator import (
                ThumbnailGenerator,
            )
            preview = ThumbnailGenerator().generate_thumbnail(raw)
        except Exception:  # noqa: BLE001 — best-effort
            _logger.warning(
                "design.file: preview thumbnail generation raised; record will be saved without preview_file.",
                exc_info=True,
            )
            return None
        if not preview:
            _logger.warning(
                "design.file: preview thumbnail generator returned no data "
                "(unsupported MIME, RGBA-only mode, or corrupt blob); "
                "record will be saved without preview_file."
            )
        return preview

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-populate preview_file from design_file blob (best-effort).

        Skipped when `preview_file` is already set in vals (caller-supplied
        thumbnail wins) or when there is no `design_file` blob (URL/GDrive
        modes). Failures are non-fatal — the record is created without
        a preview rather than blocking the upload.
        """
        for vals in vals_list:
            blob = vals.get('design_file')
            if blob and not vals.get('preview_file'):
                preview = self._generate_preview_blob(blob)
                if preview:
                    # ir.attachment.create assumes Binary values are
                    # base64-encoded — raw bytes break with "Incorrect padding".
                    vals['preview_file'] = base64.b64encode(preview)
        return super().create(vals_list)

    def write(self, vals):
        """Gate state writes by destination + enforce state machine.

        - target=proof_sent → BA+ allowed (sending a proof is BA work).
        - target in {approved, rejected, pending} → MP only.
        Internal context flag `bypass_design_state_guard` opts out of
        BOTH the ACL gate and the transition guard (used by
        `action_send_proof_to_buyer`).
        """
        if 'state' in vals and not self.env.context.get(
                'bypass_design_state_guard'):
            target = vals['state']
            if target == 'proof_sent':
                self._check_ba_or_production_or_raise()
            else:
                self._check_production_team_or_raise()
            # Enforce allowed transitions on each record.
            for rec in self:
                old = rec.state
                if old == target:
                    continue
                allowed = self._ALLOWED_STATE_TRANSITIONS.get(old, set())
                if target not in allowed:
                    raise ValidationError(_(
                        "Cannot move design file '%(name)s' from "
                        "'%(old)s' to '%(new)s'.",
                        name=rec.name or '?',
                        old=old, new=target,
                    ))
        result = super().write(vals)
        # P1-DESIGN-AUTO-ARCHIVE — after the write applies, if any row
        # is now in state='approved', sweep its siblings on the same
        # order_line_id (or order_id when line is null) and soft-archive
        # them. Pre-existing rejected rows are NOT touched (audit trail).
        if 'state' in vals and vals.get('state') == 'approved':
            self._auto_archive_siblings()
        return result

    def _auto_archive_siblings(self):
        """Soft-archive sibling non-approved files for each approved row."""
        Sibling = self.with_context(active_test=False)
        for rec in self:
            if rec.state != 'approved':
                continue
            domain = [
                ('id', '!=', rec.id),
                ('state', '!=', 'approved'),
                ('active', '=', True),
            ]
            if rec.order_line_id:
                domain.append(('order_line_id', '=', rec.order_line_id.id))
            elif rec.order_id:
                domain.append(('order_id', '=', rec.order_id.id))
                domain.append(('order_line_id', '=', False))
            else:
                continue  # no scope to archive against
            siblings = Sibling.search(domain)
            if siblings:
                siblings.write({'active': False})

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

    def action_send_proof_to_buyer(self, buyer_message=None):
        """P1-DESIGN+GEARMENT — BA sends design proof to buyer.

        Per D2 §2.1 row 3+5. Allowed for files in {pending, rejected};
        transitions state to `proof_sent` and posts the proof URL +
        buyer message to the parent sale.order's chatter (Markup+escape
        for XSS hygiene).
        """
        self._check_ba_or_production_or_raise()
        for rec in self:
            if rec.state not in ('pending', 'rejected'):
                raise ValidationError(_(
                    "Cannot send proof for design '%(name)s' in state "
                    "'%(state)s' — only pending or rejected files may "
                    "be re-sent.",
                    name=rec.name or '?', state=rec.state,
                ))
            order = rec.order_id or (rec.order_line_id.order_id if rec.order_line_id else None)
            if order:
                url = rec.file_url or rec.gdrive_preview_url or '(no URL on file)'
                msg = (buyer_message or '').strip()
                body = Markup(
                    '<p><strong>Proof sent for design '
                    f'{escape(rec.name or "")}</strong></p>'
                    f'<p>URL: <a href="{escape(url)}" rel="noopener">'
                    f'{escape(url)}</a></p>'
                    + (f'<p>Buyer note: {escape(msg)}</p>' if msg else '')
                )
                order.message_post(body=body)
            rec.with_context(
                bypass_design_state_guard=True,
            ).write({
                'state': 'proof_sent',
                'proof_sent_at': fields.Datetime.now(),
                'proof_sent_by': self.env.user.id,
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

    # ------------------------------------------------------------------
    # P1-DESIGN-AUTO-CREATE-FROM-EMAIL — live ingest seeding
    # ------------------------------------------------------------------

    def _seed_design_files_from_lines(self, order, created_via='email_ingest'):
        """Seed design.file rows from a freshly-ingested order's lines.

        Called from `OrderCreator.process_parse_result` (email path) and
        `OrderCreator.process_etsy_payload` (API path) immediately after
        `sale.order.create()`. Walks each `order.order_line` and, for any line
        whose channel-agnostic `design_link_front` / `design_link_back` is
        non-empty, creates a `design.file` row with `state='pending'`,
        `storage_mode='url'`, and the provided `created_via` provenance marker.

        Idempotent on `(order_line_id, file_url)` — search before create — so
        re-ingestion of the same email/payload does not duplicate rows. The
        underlying SQL UNIQUE on the same key (see `init()`) is the
        belt-and-braces guarantee.

        Lines without parsed design links are skipped silently (zero design
        files for the order is a valid state — the operator will use the
        upload wizard instead). State stays `pending` so the existing
        operator-approval flow remains the gate before Gearment push.

        :param order: a `sale.order` recordset (singleton). Empty recordset
            is tolerated (returns 0).
        :param created_via: one of ``'email_ingest'`` or ``'api_ingest'``.
            Other values raise ValueError to fail-fast on caller drift.
        :return: int, count of newly created rows (excluding skipped duplicates).
        """
        if created_via not in ('email_ingest', 'api_ingest'):
            raise ValueError(
                "_seed_design_files_from_lines: created_via must be "
                "'email_ingest' or 'api_ingest', got %r" % (created_via,)
            )
        if not order:
            return 0

        roles = (
            ('design_link_front', 'Front'),
            ('design_link_back', 'Back'),
        )
        created = 0
        for line in order.order_line:
            for field_name, role_label in roles:
                url = (getattr(line, field_name, '') or '').strip()
                if not url:
                    continue
                existing = self.search([
                    ('order_line_id', '=', line.id),
                    ('file_url', '=', url),
                ], limit=1)
                if existing:
                    continue
                product_label = (
                    line.product_id.display_name
                    if line.product_id else (line.name or '?')
                )
                self.create({
                    'name': f"{product_label} — {role_label}",
                    'order_line_id': line.id,
                    'storage_mode': 'url',
                    'file_url': url,
                    'state': 'pending',
                    'is_seed': False,
                    'created_via': created_via,
                })
                created += 1

        if created:
            _logger.info(
                "design.file._seed_design_files_from_lines: seeded %s rows "
                "for sale.order %s (created_via=%s).",
                created, order.name or order.id, created_via,
            )
        return created

    # ------------------------------------------------------------------
    # P1-DESIGN-AUTO-GDRIVE — cron-driven approved → GDrive promotion
    # ------------------------------------------------------------------
    @api.model
    def _cron_sync_approved_to_gdrive(self):
        """Promote approved storage_mode='small' design files to GDrive.

        Picks design.file rows with state='approved' AND storage_mode='small'
        AND design_file (blob) IS NOT NULL AND gdrive_file_id IS NULL.
        Uploads each to the configured default folder via GdriveUploader,
        then writes storage_mode='gdrive' + gdrive_file_id + gdrive_folder_id
        + synced_to_gdrive_at.

        ICPs:
          - multichannel_hub.design_gdrive_auto_sync_enabled (default True)
          - multichannel_hub.design_file_default_gdrive_folder_id
            (cron no-ops silently when unset; demo prereq)

        Failures are logged at WARNING and the record is left untouched —
        the next cron pass retries. Per-record exceptions cannot abort
        the batch (savepoint per record).
        """
        ICP = self.env['ir.config_parameter'].sudo()
        if ICP.get_param(
            'multichannel_hub.design_gdrive_auto_sync_enabled', 'True',
        ) != 'True':
            _logger.debug("auto-gdrive: killswitch off; skipping cron run")
            return 0
        folder_id = ICP.get_param(
            'multichannel_hub.design_file_default_gdrive_folder_id', '',
        ).strip()
        if not folder_id:
            _logger.debug(
                "auto-gdrive: ICP design_file_default_gdrive_folder_id "
                "unset; cron is a no-op until operator configures it.")
            return 0
        # Defense-in-depth: GDrive file/folder IDs are URL-safe base64
        # alphabets (28-44 chars). An admin-misconfigured ICP shouldn't
        # leak arbitrary strings into Drive API calls.
        if not re.match(r'^[A-Za-z0-9_-]{20,80}$', folder_id):
            _logger.warning(
                "auto-gdrive: ICP design_file_default_gdrive_folder_id "
                "has invalid format; refusing to use it.")
            return 0

        candidates = self.search([
            ('state', '=', 'approved'),
            ('storage_mode', '=', 'small'),
            ('design_file', '!=', False),
            ('gdrive_file_id', '=', False),
        ])
        if not candidates:
            return 0

        # Lazy import to keep mhc importable without google-api-python-client
        # in environments where the cron never fires. Use the odoo.addons
        # prefix so test mocks at the same path land on the same symbol.
        from odoo.addons.multichannel_hub_core.services.gdrive_uploader import (
            GdriveUploader,
        )

        uploader = GdriveUploader()
        promoted = 0
        for rec in candidates:
            try:
                with self.env.cr.savepoint():
                    blob = base64.b64decode(rec.design_file)
                    file_name = rec.file_name or f'{rec.name or "design"}.bin'
                    result = uploader.upload_file(
                        file_blob=blob,
                        file_name=file_name,
                        folder_id=folder_id,
                    )
                    if result.get('error') or not result.get('file_id'):
                        _logger.warning(
                            "auto-gdrive: upload failed for design.file id=%s "
                            "(%s)", rec.id, result.get('error'))
                        continue
                    rec.write({
                        'storage_mode': 'gdrive',
                        'gdrive_file_id': result['file_id'],
                        'gdrive_folder_id': folder_id,
                        'synced_to_gdrive_at': fields.Datetime.now(),
                    })
                    promoted += 1
            except Exception as e:
                # Savepoint already rolled back this record; continue with
                # the rest of the batch — the next cron pass will retry.
                _logger.warning(
                    "auto-gdrive: unexpected error promoting "
                    "design.file id=%s: %s", rec.id, e)
        if promoted:
            _logger.info(
                "auto-gdrive: promoted %s/%s approved design files to GDrive.",
                promoted, len(candidates),
            )
        return promoted
