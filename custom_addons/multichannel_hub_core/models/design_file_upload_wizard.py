"""design.file.upload.wizard — GDrive upload wizard for design files.

Transient model for uploading a design file to Google Drive from a wizard form.

Workflow:
  1. User opens wizard from sale.order.line 'Upload Design' button
  2. Fills form: design_file (Binary), file_name (Char)
  3. Wizard loads design file into memory, generates thumbnail
  4. Calls GdriveUploader.ensure_shop_folder() to get/create Drive folder
  5. Calls GdriveUploader.upload_file() to upload to Drive
  6. On success: creates design.file record with gdrive_file_id + state='approved'
  7. On failure: displays error to user (wizard auto-closes on save)

ADR-006 §3 + FR-017 alignment: service-account-only, minimum scopes, RPC gate
on action_upload (has_group check at entry).

References: P1-09 spec, tasks.md T097, test_gdrive_upload_orm.py
TestUploadWizard.
"""
import base64
import hashlib
import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from ..services.gdrive_uploader import GdriveUploader
from ..services.design_thumbnail_generator import ThumbnailGenerator

_logger = logging.getLogger(__name__)


class DesignFileUploadWizard(models.TransientModel):
    _name = 'design.file.upload.wizard'
    _description = 'Upload Design File to Google Drive'

    order_line_id = fields.Many2one(
        'sale.order.line',
        string='Order Line',
        required=True,
        ondelete='cascade',
        help="The order line to attach the design file to.",
    )

    design_file = fields.Binary(
        string='Design File',
        required=True,
        help="The file to upload (JPEG, PNG, PDF, etc.).",
    )

    file_name = fields.Char(
        string='File Name',
        required=True,
        help="Display name for the file on Google Drive.",
    )

    def action_upload(self):
        """Upload design file to GDrive, create design.file record, close wizard.

        Flow:
        1. Validate user permission (production_team or system)
        2. Get order_line.order_id.shop_id
        3. Call GdriveUploader.ensure_shop_folder(shop) → folder_id
        4. Call GdriveUploader.upload_file(file_blob, file_name, folder_id)
        5. On success: create design.file with gdrive_file_id, approve it
        6. On failure: raise ValidationError (user sees error in wizard)
        7. Return ir.actions.act_window_close

        FR-017: RPC-level gate on action (has_group check at entry point).
        Never raises on Drive failure — returns error to ORM level with
        message for UI display.
        """
        # FR-017 defense: RPC-level gate (action method entry point)
        if not self.env.user.has_group('multichannel_hub_core.group_production_team'):
            if not self.env.user.has_group('base.group_system'):
                raise AccessError(_(
                    "Only members of the Production Team may upload design files "
                    "to Google Drive."
                ))

        self.ensure_one()
        order_line = self.order_line_id
        order = order_line.order_id
        shop = order.shop_id

        if not shop:
            raise ValidationError(_(
                "Order '%(order_name)s' has no associated shop. "
                "Cannot determine GDrive upload folder.",
                order_name=order.name or '?',
            ))

        # Decode file blob
        try:
            file_blob = base64.b64decode(self.design_file)
        except Exception as exc:
            raise ValidationError(_(
                "Invalid design file. Ensure the file was uploaded correctly. "
                "Error: %(error)s",
                error=str(exc),
            )) from exc

        file_size = len(file_blob)
        file_checksum = hashlib.sha256(file_blob).hexdigest()

        # Initialize services
        gdrive_uploader = GdriveUploader(env=self.env)
        thumbnail_gen = ThumbnailGenerator()

        # Generate thumbnail
        thumbnail_bytes = thumbnail_gen.generate_thumbnail(file_blob)

        # Ensure shop folder on GDrive
        try:
            folder_id = gdrive_uploader.ensure_shop_folder(shop)
        except Exception as exc:
            raise ValidationError(_(
                "Failed to access or create GDrive folder for shop '%(shop_name)s'. "
                "Ensure GDrive service account is configured. Error: %(error)s",
                shop_name=shop.name or '?',
                error=str(exc),
            )) from exc

        if not folder_id:
            raise ValidationError(_(
                "Failed to determine GDrive folder for shop '%(shop_name)s'. "
                "Check GDrive service account credentials.",
                shop_name=shop.name or '?',
            ))

        # Upload to GDrive
        result = gdrive_uploader.upload_file(
            file_blob, self.file_name, folder_id, mime_type='application/octet-stream'
        )

        if result.get('error'):
            raise ValidationError(_(
                "GDrive upload failed. Error: %(error)s",
                error=result['error'],
            ))

        gdrive_file_id = result.get('file_id')
        gdrive_web_view_link = result.get('web_view_link')

        if not gdrive_file_id:
            raise ValidationError(_(
                "GDrive upload succeeded but no file ID was returned. "
                "This is an internal error; contact support."
            ))

        # Create design.file record
        DesignFile = self.env['design.file']
        design_file_record = DesignFile.create({
            'order_line_id': order_line.id,
            'name': self.file_name,
            'storage_mode': 'gdrive',
            'design_file': self.design_file,
            'preview_file': base64.b64encode(thumbnail_bytes) if thumbnail_bytes else False,
            'file_name': self.file_name,
            'file_size': file_size,
            'file_checksum': file_checksum,
            'gdrive_file_id': gdrive_file_id,
            'gdrive_web_view_link': gdrive_web_view_link,
            'gdrive_upload_state': 'uploaded',
            'state': 'approved',
        })

        _logger.debug(
            "Design file uploaded to GDrive design_file_id=%s file_id=%s",
            design_file_record.id, gdrive_file_id,
        )

        # Close wizard (success message will be auto-generated by Odoo)
        return {'type': 'ir.actions.act_window_close'}
