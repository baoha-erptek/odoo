"""
Phase 1 (Database Verification): GDrive upload schema + ACL tests.

Tests verify at the database level:
- design.file table has gdrive_* columns (gdrive_file_id, gdrive_preview_url, gdrive_folder_id, gdrive_thumbnail)
- storage_mode Selection includes 'gdrive' value
- design.file.upload.wizard TransientModel is registered
- etsy.shop has gdrive folder cache field (x_gdrive_design_folder_id)
- ir.model.access ACL rows exist for wizard

Uses direct SQL queries for data-integrity verification.
"""

import logging

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestGdriveUploadDatabaseSchema(TransactionCase):
    """Phase 1: Verify GDrive schema + ACL at database level."""

    def test_design_file_has_gdrive_columns(self):
        """Verify design.file table has required GDrive columns."""
        columns_to_check = [
            'gdrive_file_id',
            'gdrive_preview_url',
            'gdrive_folder_id',
            'gdrive_thumbnail',
        ]

        for col in columns_to_check:
            self.env.cr.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'design_file' AND column_name = %s
            """, (col,))
            row = self.env.cr.fetchone()
            self.assertIsNotNone(
                row,
                f"Column '{col}' missing from design_file table"
            )

    def test_design_file_storage_mode_includes_gdrive(self):
        """Verify storage_mode Selection includes 'gdrive' value."""
        # Check that the field definition includes the 'gdrive' selection
        design_file_model = self.env['design.file']
        storage_mode_field = design_file_model._fields['storage_mode']

        # Get selection values
        selection_values = [val for val, _ in storage_mode_field.selection]

        self.assertIn(
            'gdrive',
            selection_values,
            "storage_mode Selection must include 'gdrive' option"
        )

    def test_upload_wizard_is_transient_model(self):
        """Verify design.file.upload.wizard is registered as TransientModel."""
        wizard_model = self.env['design.file.upload.wizard']

        self.assertTrue(
            wizard_model._transient,
            "design.file.upload.wizard must be a TransientModel"
        )

    def test_etsy_shop_has_gdrive_folder_cache_field(self):
        """Verify etsy.shop has x_gdrive_design_folder_id cache field."""
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'x_gdrive_design_folder_id'
        """)
        row = self.env.cr.fetchone()
        self.assertIsNotNone(
            row,
            "etsy.shop table must have x_gdrive_design_folder_id column (cache field)"
        )

    def test_upload_wizard_acl_rows_exist(self):
        """Verify ir.model.access rows for wizard exist with correct permissions."""
        wizard_model_id = self.env['ir.model']._get_id('design.file.upload.wizard')

        # Check for group_production_team access
        self.env.cr.execute("""
            SELECT perm_read, perm_write, perm_create, perm_unlink
            FROM ir_model_access
            WHERE model_id = %s
            AND group_id IN (
                SELECT id FROM res_groups WHERE name = 'Production Team'
            )
        """, (wizard_model_id,))
        prod_row = self.env.cr.fetchone()
        self.assertIsNotNone(
            prod_row,
            "ACL row missing for group_production_team on design.file.upload.wizard"
        )
        # Verify permissions (read, write, create)
        perm_read, perm_write, perm_create, _ = prod_row
        self.assertTrue(perm_read, "Production Team must have read permission on wizard")
        self.assertTrue(perm_write, "Production Team must have write permission on wizard")
        self.assertTrue(perm_create, "Production Team must have create permission on wizard")

        # Check for base.group_system access (full)
        system_group_id = self.env.ref('base.group_system').id
        self.env.cr.execute("""
            SELECT perm_read, perm_write, perm_create, perm_unlink
            FROM ir_model_access
            WHERE model_id = %s AND group_id = %s
        """, (wizard_model_id, system_group_id))
        system_row = self.env.cr.fetchone()
        self.assertIsNotNone(
            system_row,
            "ACL row missing for base.group_system on design.file.upload.wizard"
        )
        perm_read, perm_write, perm_create, perm_unlink = system_row
        self.assertTrue(perm_read, "System must have read permission on wizard")
        self.assertTrue(perm_write, "System must have write permission on wizard")
        self.assertTrue(perm_create, "System must have create permission on wizard")
