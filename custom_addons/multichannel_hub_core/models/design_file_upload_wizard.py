"""design.file.upload.wizard — Transient wizard for uploading design files.

Handles multiple storage modes (url, small, gdrive) with:
- Single-file legacy path via ``file_blob``/``file_url``/``gdrive_folder_id``.
- Multi-file path via ``attachment_ids`` (many2many_binary widget). One
  ``design.file`` row is created per attachment under the current
  ``storage_mode`` (URL mode stays single-valued).
- File validation (size caps, sanitization).
- GDrive uploader service integration.
- Thumbnail generation (auto via ``design.file.create()`` override for ``small``).
- FR-017 production-team RPC gate (fires once at action entry across N files).
- No-fallback behavior (ADR-012 §3).
"""
import base64
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

# Filename validation: alphanumeric + dot/dash/space/underscore
_SAFE_FILENAME_RE = re.compile(r'^[\w\-. ]{1,255}$')

# Hard cap on file blob size (100 MB)
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024


class DesignFileUploadWizard(models.TransientModel):
    _name = 'design.file.upload.wizard'
    _description = 'Design File Upload Wizard'

    # Order context (required)
    order_id = fields.Many2one(
        'sale.order',
        string='Order',
        required=True,
        ondelete='cascade',
    )

    # File content
    file_blob = fields.Binary(string='File', help='File content (base64)')
    file_name = fields.Char(string='File Name', default='design')
    file_url = fields.Char(string='File URL', help='Used for storage_mode=url')

    # Storage mode — default 'small' so the natural drag-and-drop flow works
    # without forcing the operator to switch modes (UX bug fix landed in
    # P1-DESIGN-MULTI-UPLOAD; previously defaulted to 'url').
    storage_mode = fields.Selection(
        [
            ('small', 'Small (filestore)'),
            ('url', 'URL'),
            ('gdrive', 'Google Drive'),
        ],
        string='Storage Mode',
        required=True,
        default='small',
    )

    # GDrive-specific fields
    gdrive_folder_id = fields.Char(
        string='GDrive Folder ID',
        help='Folder ID for upload (from etsy.shop cache or caller)',
    )

    # Multi-file picker (P1-DESIGN-MULTI-UPLOAD). When non-empty, one
    # design.file row is created per attachment in the current storage_mode.
    # URL mode ignores this and falls back to file_url (single-valued).
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'design_file_upload_wizard_attachment_rel',
        'wizard_id',
        'attachment_id',
        string='Files',
        help='Drop or pick multiple files. Each becomes a separate design.file row.',
    )

    @api.constrains('storage_mode', 'gdrive_folder_id')
    def _check_gdrive_folder_id_required(self):
        """C-DUW-001: gdrive mode requires gdrive_folder_id."""
        for rec in self:
            if rec.storage_mode == 'gdrive' and not rec.gdrive_folder_id:
                raise ValidationError(
                    _("GDrive mode requires a GDrive folder ID.")
                )

    @api.model
    def _check_production_team_or_raise(self):
        """RPC-level gate: FR-017 — only production_team can upload."""
        if self.env.user.has_group('multichannel_hub_core.group_production_team'):
            return
        if self.env.user.has_group('base.group_system'):
            return
        raise AccessError(
            _("Only members of the Production Team can upload design files.")
        )

    def action_upload(self):
        """Execute upload: validate, store, post chatter.

        FR-017 production-team RPC gate fires once at action entry, never
        per-file — N attachments share one access decision.

        Raises:
            ValidationError: On validation failure (file too large, etc)
            AccessError: If non-production-team user calls (FR-017)
        """
        # FR-017 RPC gate — fires once at entry across N attachments
        self._check_production_team_or_raise()

        for wizard in self:
            wizard._do_upload()

    def _do_upload(self):
        """Multi- or single-file dispatch.

        - ``attachment_ids`` non-empty (and mode != 'url'): loop, one design.file
          per attachment.
        - Otherwise: legacy single-file path using ``file_blob`` / ``file_url`` /
          ``gdrive_folder_id``.
        """
        if self.attachment_ids and self.storage_mode != 'url':
            for attachment in self.attachment_ids:
                self._do_upload_for_attachment(attachment)
        else:
            self._do_upload_for_mode()

    def _do_upload_for_attachment(self, attachment):
        """Per-attachment dispatch reusing the storage_mode-specific helpers.

        FR-017 defense-in-depth (P1-DESIGN-WIZ-ATTACH-SCOPE): explicit
        attachment-ownership gate. Odoo base ``ir.attachment`` record rules
        already constrain visibility, but we enforce a per-model gate as a
        second line of defense in case base rules are bypassed (e.g.,
        upstream sudo() write paths or a future relaxed record rule).

        Allowed:
        - ``attachment.create_uid == self.env.user`` (operator's own upload)
        - ``attachment.res_model == 'design.file.upload.wizard'`` AND
          ``attachment.res_id == self.id`` (carve-out for attachments
          auto-created by the many2many_binary widget for THIS wizard
          instance). The ``res_id == self.id`` check closes the bypass
          where an attacker could ``write`` ``res_model`` to an arbitrary
          orphan attachment they own and donate it to another wizard.
        """
        wizard_carve_out = (
            attachment.res_model == 'design.file.upload.wizard'
            and attachment.res_id == self.id
        )
        if (
            attachment.create_uid.id != self.env.user.id
            and not wizard_carve_out
        ):
            raise AccessError(
                _("You can only upload files that you created or that are attached to this wizard.")
            )

        blob = (
            base64.b64decode(attachment.datas) if attachment.datas else b''
        )
        file_name = attachment.name or 'design'
        if self.storage_mode == 'gdrive':
            self._upload_gdrive_with(file_blob=blob, file_name=file_name)
        elif self.storage_mode == 'small':
            self._upload_small_with(file_blob=blob, file_name=file_name)

    def _do_upload_for_mode(self):
        """Dispatch to upload handler based on storage_mode (legacy single-file)."""
        if self.storage_mode == 'gdrive':
            self._upload_gdrive()
        elif self.storage_mode == 'url':
            self._upload_url()
        elif self.storage_mode == 'small':
            self._upload_small()

    def _validate_file_blob(self) -> bytes:
        """Validate and decode file blob.

        Returns:
            Decoded bytes

        Raises:
            ValidationError: On oversized or invalid blob
        """
        try:
            blob = base64.b64decode(self.file_blob) if self.file_blob else b''
        except Exception:
            blob = self.file_blob if isinstance(self.file_blob, bytes) else b''

        if len(blob) > _MAX_UPLOAD_BYTES:
            raise ValidationError(
                _(
                    "File too large (%(size)s MB). Maximum is 100 MB.",
                    size=len(blob) // 1_048_576,
                )
            )
        return blob

    def _validate_file_name(self) -> str:
        """Validate and sanitize ``self.file_name`` (legacy single-file path)."""
        return self._validate_file_name_value(self.file_name or 'design')

    @staticmethod
    def _validate_file_name_value(name: str) -> str:
        """Validate and sanitize an arbitrary file name (multi-file path).

        Returns:
            Sanitized filename

        Raises:
            ValidationError: On invalid characters
        """
        name = name or 'design'
        if not _SAFE_FILENAME_RE.match(name):
            raise ValidationError(
                _(
                    "File name contains invalid characters. Allowed: letters, "
                    "digits, dot, dash, space, underscore."
                )
            )
        return name

    def _upload_gdrive(self):
        """Legacy single-file GDrive upload (uses self.file_blob/file_name)."""
        self._upload_gdrive_with(
            file_blob=self._validate_file_blob(),
            file_name=self._validate_file_name(),
        )

    def _upload_gdrive_with(self, file_blob: bytes, file_name: str):
        """Upload one file to GDrive via GdriveUploader service.

        Used by both the legacy single-file path and the multi-file
        ``attachment_ids`` loop.
        """
        from multichannel_hub_core.services.gdrive_uploader import GdriveUploader
        from multichannel_hub_core.services.design_thumbnail_generator import (
            ThumbnailGenerator,
        )

        if len(file_blob) > _MAX_UPLOAD_BYTES:
            raise ValidationError(
                _(
                    "File too large (%(size)s MB). Maximum is 100 MB.",
                    size=len(file_blob) // 1_048_576,
                )
            )
        safe_name = self._validate_file_name_value(file_name)

        # Ensure folder exists and get folder_id (cached or created)
        shop = self.order_id.shop_id if hasattr(self.order_id, 'shop_id') else None
        if not shop:
            raise ValidationError(
                _("Order has no associated shop; cannot determine GDrive folder.")
            )

        uploader = GdriveUploader()
        folder_id = self.gdrive_folder_id or uploader.ensure_shop_folder(shop)

        result = uploader.upload_file(
            file_blob=file_blob, file_name=safe_name, folder_id=folder_id
        )

        if result.get('error'):
            # No fallback per ADR-012 §3
            raise ValidationError(
                _("GDrive upload failed: %(error)s", error=result['error'])
            )

        file_id = result['file_id']

        # Generate thumbnail (non-fatal on failure). Encode to base64 for
        # attachment=True Binary fields (memory: feedback_odoo19_test_gotchas
        # entry 92 — same shape as preview_file).
        thumbnail_gen = ThumbnailGenerator()
        thumbnail = thumbnail_gen.generate_thumbnail(file_blob)
        gdrive_thumbnail = base64.b64encode(thumbnail) if thumbnail else False

        self.env['design.file'].create({
            'name': safe_name,
            'order_id': self.order_id.id,
            'storage_mode': 'gdrive',
            'gdrive_file_id': file_id,
            'gdrive_folder_id': folder_id,
            'gdrive_thumbnail': gdrive_thumbnail,
            'file_name': safe_name,
            'state': 'pending',
        })

    def _upload_url(self):
        """Store URL mode design file (no external upload)."""
        if not self.file_url:
            raise ValidationError(_("URL mode requires a file_url."))

        file_name = self._validate_file_name()

        self.env['design.file'].create({
            'name': file_name,
            'order_id': self.order_id.id,
            'storage_mode': 'url',
            'file_url': self.file_url,
            'file_name': file_name,
            'state': 'pending',
        })

    def _upload_small(self):
        """Legacy single-file small mode (uses self.file_blob/file_name)."""
        self._upload_small_with(
            file_blob=self._validate_file_blob(),
            file_name=self._validate_file_name(),
        )

    def _upload_small_with(self, file_blob: bytes, file_name: str):
        """Store one filestore design.file from explicit blob + name.

        Used by both the legacy single-file path and the multi-file
        ``attachment_ids`` loop. preview_file is auto-generated by the
        ``design.file.create()`` override (P1-DESIGN-MULTI-KANBAN).
        """
        if len(file_blob) > _MAX_UPLOAD_BYTES:
            raise ValidationError(
                _(
                    "File too large (%(size)s MB). Maximum is 100 MB.",
                    size=len(file_blob) // 1_048_576,
                )
            )
        safe_name = self._validate_file_name_value(file_name)

        # Pass base64-encoded blob to match the kanban-thumb convention so the
        # design.file.create() override can decode and feed
        # ThumbnailGenerator on the first try (raw-bytes path takes the
        # exception-fallback branch which still works but logs a misleading
        # b64decode error).
        self.env['design.file'].create({
            'name': safe_name,
            'order_id': self.order_id.id,
            'storage_mode': 'small',
            'design_file': base64.b64encode(file_blob),
            'file_name': safe_name,
            'state': 'pending',
        })
