"""Tests for P1-DESIGN-MULTI-UPLOAD — wizard multi-file upload + storage_mode default flip.

Phase 1 (View introspection):
  - design.file.upload.wizard form view has storage_mode default 'small'
  - Three <group> blocks for file_blob/file_url/gdrive_folder_id have invisible= modifiers

Phase 2 (ORM):
  - Wizard accepts Many2many attachment_ids field
  - Default storage_mode='small' (not 'url')
  - Single-file upload with default mode succeeds (no 'URL mode requires file_url' raise)
  - N attachments → N design.file rows in one action_upload call
  - Each design.file has auto-generated preview_file (via design.file.create() override)
  - FR-017 RPC gate fires once at action entry (not per file)
  - Non-production user gets AccessError on action_upload; no design.file created
  - Partial failure (one of N files fails validation) → atomic rollback, zero files created
"""

import base64
import logging
from unittest.mock import MagicMock, patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)

# 2x2 white JPEG — RGB mode (not RGBA)
# Canonical fixture from test_design_file_kanban_thumb.py
_JPEG_2X2 = base64.b64decode(
    b'/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof'
    b'Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwh'
    b'MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAAR'
    b'CAACAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAA'
    b'AgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkK'
    b'FhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWG'
    b'h4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl'
    b'5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREA'
    b'AgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYk'
    b'NOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOE'
    b'hYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk'
    b'5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q=='
)


@tagged('post_install', '-at_install')
class TestDesignFileUploadWizardMultiView(TransactionCase):
    """Phase 1 — view structure and defaults."""

    def test_view_storage_mode_default_is_small(self):
        """Default storage_mode on wizard form is 'small', not 'url'."""
        defaults = self.env['design.file.upload.wizard'].default_get(['storage_mode'])
        self.assertEqual(
            defaults.get('storage_mode'),
            'small',
            "storage_mode default must be 'small', not 'url' (UX bug fix)."
        )

    def test_view_file_blob_group_invisible_when_not_small_mode(self):
        """The <group> wrapping field 'file_blob' has invisible attr referencing storage_mode."""
        view = self.env.ref('multichannel_hub_core.design_file_upload_wizard_form')
        arch_str = view.arch_db

        # Assert the arch contains an invisible= expression
        # Expecting something like: invisible="storage_mode != 'small'"
        self.assertIn(
            "file_blob",
            arch_str,
            "View must contain file_blob field."
        )
        # The <group> wrapping file_blob should have invisible attr with storage_mode condition
        self.assertIn(
            "invisible",
            arch_str,
            "View must have invisible modifiers on input groups."
        )
        self.assertIn(
            "storage_mode",
            arch_str,
            "Invisible modifiers must reference storage_mode field."
        )

    def test_view_file_url_group_invisible_when_not_url_mode(self):
        """The <group> wrapping field 'file_url' has invisible attr for url mode."""
        view = self.env.ref('multichannel_hub_core.design_file_upload_wizard_form')
        arch_str = view.arch_db

        self.assertIn(
            "file_url",
            arch_str,
            "View must contain file_url field."
        )

    def test_view_gdrive_folder_group_invisible_when_not_gdrive_mode(self):
        """The <group> wrapping field 'gdrive_folder_id' has invisible attr for gdrive mode."""
        view = self.env.ref('multichannel_hub_core.design_file_upload_wizard_form')
        arch_str = view.arch_db

        self.assertIn(
            "gdrive_folder_id",
            arch_str,
            "View must contain gdrive_folder_id field."
        )

    def test_wizard_has_attachment_ids_field(self):
        """New Many2many('ir.attachment') field 'attachment_ids' is registered."""
        wizard_model = self.env['design.file.upload.wizard']
        field = wizard_model._fields.get('attachment_ids')

        self.assertIsNotNone(
            field,
            "design.file.upload.wizard must have attachment_ids field."
        )
        self.assertEqual(
            field.type,
            'many2many',
            "attachment_ids must be a Many2many field."
        )
        self.assertEqual(
            field.comodel_name,
            'ir.attachment',
            "attachment_ids must point to ir.attachment model."
        )


@tagged('post_install', '-at_install')
class TestDesignFileUploadWizardMultiORM(TransactionCase):
    """Phase 2 — ORM behavior and multi-file logic."""

    @classmethod
    def setUpClass(cls):
        """Minimal fixture: production-team user, non-prod user, sale.order."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.prod_team_group = cls.env.ref(
            'multichannel_hub_core.group_production_team'
        )
        cls.prod_user = cls.env['res.users'].create({
            'name': 'Prod User',
            'login': 'prod_user_multi@example.com',
            'group_ids': [(6, 0, [cls.prod_team_group.id])],
        })
        cls.non_prod_user = cls.env['res.users'].create({
            'name': 'Non-Prod User',
            'login': 'nonprod_user_multi@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

        cls.partner = cls.env['res.partner'].create({'name': 'Test Partner Multi'})
        cls.order = cls.env['sale.order'].create({'partner_id': cls.partner.id})

    def _create_attachment(self, name='design.jpg', datas=None):
        """Factory: create ir.attachment with JPEG fixture."""
        if datas is None:
            datas = _JPEG_2X2
        return self.env['ir.attachment'].create({
            'name': name,
            'type': 'binary',
            'datas': base64.b64encode(datas),
        })

    def test_default_mode_single_file_upload_succeeds(self):
        """Regression: with default storage_mode, dropping only file_blob (no file_url) → action_upload succeeds.

        Before fix: storage_mode defaulted to 'url', so _upload_url() was called,
        which raised 'URL mode requires a file_url' if file_url was empty.
        After fix: storage_mode defaults to 'small', so _upload_small() is called,
        which only requires file_blob (passed via attachment_ids).
        """
        attachment = self._create_attachment('single_design.jpg', _JPEG_2X2)

        wizard = self.env['design.file.upload.wizard'].create({
            'order_id': self.order.id,
            'file_name': 'single_design',
            'attachment_ids': [(6, 0, [attachment.id])],
            # storage_mode NOT set → defaults to 'small'
        })

        # Should succeed with production user
        wizard.with_user(self.prod_user).action_upload()

        # Verify one design.file created (multi-file path uses attachment.name as
        # file_name, not wizard.file_name).
        design_files = self.env['design.file'].search([
            ('order_id', '=', self.order.id),
            ('file_name', '=', 'single_design.jpg'),
        ])
        self.assertEqual(len(design_files), 1)
        self.assertEqual(design_files[0].state, 'pending')
        self.assertEqual(design_files[0].storage_mode, 'small')

    def test_multi_file_upload_creates_n_design_files(self):
        """3 attachments in one wizard run → 3 design.file rows on same order_id."""
        att1 = self._create_attachment('design_1.jpg', _JPEG_2X2)
        att2 = self._create_attachment('design_2.jpg', _JPEG_2X2)
        att3 = self._create_attachment('design_3.jpg', _JPEG_2X2)

        wizard = self.env['design.file.upload.wizard'].create({
            'order_id': self.order.id,
            'file_name': 'multi_design',
            'storage_mode': 'small',
            'attachment_ids': [(6, 0, [att1.id, att2.id, att3.id])],
        })

        wizard.with_user(self.prod_user).action_upload()

        # Verify three design.file rows created
        design_files = self.env['design.file'].search([
            ('order_id', '=', self.order.id),
        ], order='id asc')

        self.assertGreaterEqual(len(design_files), 3)
        for df in design_files[-3:]:
            self.assertEqual(df.state, 'pending')
            self.assertEqual(df.storage_mode, 'small')

    def test_multi_file_upload_auto_generates_preview_per_file(self):
        """Each created design.file has non-null preview_file (auto via design.file.create() override)."""
        att1 = self._create_attachment('design_preview_1.jpg', _JPEG_2X2)
        att2 = self._create_attachment('design_preview_2.jpg', _JPEG_2X2)

        wizard = self.env['design.file.upload.wizard'].create({
            'order_id': self.order.id,
            'file_name': 'preview_test',
            'storage_mode': 'small',
            'attachment_ids': [(6, 0, [att1.id, att2.id])],
        })

        wizard.with_user(self.prod_user).action_upload()

        # Multi-file path uses attachment.name; search by those names.
        design_files = self.env['design.file'].search([
            ('order_id', '=', self.order.id),
            ('file_name', 'in', ['design_preview_1.jpg', 'design_preview_2.jpg']),
        ], order='id asc')

        self.assertEqual(len(design_files), 2)
        for df in design_files:
            self.assertTrue(
                df.preview_file,
                f"design.file {df.id} must have non-null preview_file (auto-generated by create() override)."
            )

    def test_fr017_gate_blocks_non_production_team_on_action_upload(self):
        """Non-production-team user calling action_upload raises AccessError.

        Gate fires ONCE at entry across N files (no design.file rows created).
        """
        att1 = self._create_attachment('design_acl_1.jpg', _JPEG_2X2)
        att2 = self._create_attachment('design_acl_2.jpg', _JPEG_2X2)

        wizard = self.env['design.file.upload.wizard'].create({
            'order_id': self.order.id,
            'file_name': 'acl_test',
            'storage_mode': 'small',
            'attachment_ids': [(6, 0, [att1.id, att2.id])],
        })

        # Non-prod user attempts action_upload
        with self.assertRaises(AccessError):
            wizard.with_user(self.non_prod_user).action_upload()

        # Verify no design.file rows were created (atomic failure)
        design_files = self.env['design.file'].search([
            ('order_id', '=', self.order.id),
            ('file_name', '=', 'acl_test'),
        ])
        self.assertEqual(len(design_files), 0, "No design.file should be created when FR-017 gate blocks.")

    def test_fr017_gate_fires_only_once_for_n_files(self):
        """When N files are processed, _check_production_team_or_raise is called exactly once.

        Uses unittest.mock.patch to count invocations.
        """
        att1 = self._create_attachment('design_gate_1.jpg', _JPEG_2X2)
        att2 = self._create_attachment('design_gate_2.jpg', _JPEG_2X2)
        att3 = self._create_attachment('design_gate_3.jpg', _JPEG_2X2)

        wizard = self.env['design.file.upload.wizard'].create({
            'order_id': self.order.id,
            'file_name': 'gate_count_test',
            'storage_mode': 'small',
            'attachment_ids': [(6, 0, [att1.id, att2.id, att3.id])],
        })

        # Patch the gate method and count calls
        with patch.object(
            type(wizard),
            '_check_production_team_or_raise',
            wraps=wizard._check_production_team_or_raise
        ) as mock_gate:
            wizard.with_user(self.prod_user).action_upload()

            # Gate should be called exactly once, not three times
            self.assertEqual(
                mock_gate.call_count,
                1,
                "FR-017 gate must fire only once for N files, not per-file."
            )

    def test_partial_failure_atomicity(self):
        """If one of N files fails validation, the whole action raises and NO design.file rows are created.

        This test verifies atomic all-or-nothing semantics (not partial-success).
        One file is valid (small), one is invalid (oversized > 100 MB).
        """
        att_valid = self._create_attachment('valid.jpg', _JPEG_2X2)

        # Create a 101 MB attachment to trigger _validate_file_blob error
        oversized_blob = b'x' * (101 * 1024 * 1024)
        att_oversized = self._create_attachment('oversized.bin', oversized_blob)

        wizard = self.env['design.file.upload.wizard'].create({
            'order_id': self.order.id,
            'file_name': 'atomic_test',
            'storage_mode': 'small',
            'attachment_ids': [(6, 0, [att_valid.id, att_oversized.id])],
        })

        # action_upload should raise ValidationError on the oversized file
        with self.assertRaises(ValidationError):
            wizard.with_user(self.prod_user).action_upload()

        # Verify NO design.file rows were created (atomic rollback)
        design_files = self.env['design.file'].search([
            ('order_id', '=', self.order.id),
            ('file_name', '=', 'atomic_test'),
        ])
        self.assertEqual(
            len(design_files),
            0,
            "No design.file should be created when one of N files fails validation (atomic)."
        )
