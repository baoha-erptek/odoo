"""design.file.upload.wizard — Transient wizard for uploading design files to GDrive.

Handles multiple storage modes (url, small, gdrive) with:
- File validation (size caps, sanitization)
- GDrive uploader service integration
- Thumbnail generation
- FR-017 production-team RPC gate
- No-fallback behavior (ADR-012 §3)
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

    # Storage mode
    storage_mode = fields.Selection(
        [
            ('small', 'Small (filestore)'),
            ('url', 'URL'),
            ('gdrive', 'Google Drive'),
        ],
        string='Storage Mode',
        required=True,
        default='url',
    )

    # GDrive-specific fields
    gdrive_folder_id = fields.Char(
        string='GDrive Folder ID',
        help='Folder ID for upload (from etsy.shop cache or caller)',
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

        Raises:
            ValidationError: On validation failure (file too large, etc)
            AccessError: If non-production-team user calls (FR-017)
        """
        # FR-017 RPC gate
        self._check_production_team_or_raise()

        for wizard in self:
            wizard._do_upload_for_mode()

    def _do_upload_for_mode(self):
        """Dispatch to upload handler based on storage_mode."""
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
        """Validate and sanitize file name.

        Returns:
            Sanitized filename

        Raises:
            ValidationError: On invalid characters
        """
        name = self.file_name or 'design'
        if not _SAFE_FILENAME_RE.match(name):
            raise ValidationError(
                _(
                    "File name contains invalid characters. Allowed: letters, "
                    "digits, dot, dash, space, underscore."
                )
            )
        return name

    def _upload_gdrive(self):
        """Upload to GDrive via GdriveUploader service."""
        from multichannel_hub_core.services.gdrive_uploader import GdriveUploader
        from multichannel_hub_core.services.design_thumbnail_generator import (
            ThumbnailGenerator,
        )

        file_blob = self._validate_file_blob()
        file_name = self._validate_file_name()

        # Ensure folder exists and get folder_id (cached or created)
        shop = self.order_id.shop_id if hasattr(self.order_id, 'shop_id') else None
        if not shop:
            raise ValidationError(
                _("Order has no associated shop; cannot determine GDrive folder.")
            )

        uploader = GdriveUploader()
        folder_id = self.gdrive_folder_id or uploader.ensure_shop_folder(shop)

        # Upload file
        result = uploader.upload_file(
            file_blob=file_blob, file_name=file_name, folder_id=folder_id
        )

        if result.get('error'):
            # No fallback per ADR-012 §3
            raise ValidationError(
                _("GDrive upload failed: %(error)s", error=result['error'])
            )

        file_id = result['file_id']

        # Generate thumbnail (non-fatal on failure)
        thumbnail_gen = ThumbnailGenerator()
        thumbnail = thumbnail_gen.generate_thumbnail(file_blob)

        # Create design.file record
        self.env['design.file'].create({
            'name': file_name,
            'order_id': self.order_id.id,
            'storage_mode': 'gdrive',
            'gdrive_file_id': file_id,
            'gdrive_folder_id': folder_id,
            'gdrive_thumbnail': thumbnail,
            'file_name': file_name,
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
        """Store small mode design file (filestore)."""
        file_blob = self._validate_file_blob()
        file_name = self._validate_file_name()

        self.env['design.file'].create({
            'name': file_name,
            'order_id': self.order_id.id,
            'storage_mode': 'small',
            'design_file': file_blob,
            'file_name': file_name,
            'state': 'pending',
        })
