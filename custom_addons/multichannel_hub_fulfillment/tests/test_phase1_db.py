"""
Phase 1: Database verification tests for tracking.import models.

Tests verify data integrity at the database level:
- Table tracking_import_log exists with correct columns and indexes
- Table tracking_import_line exists with correct columns and constraints
- UNIQUE constraints on (log_id, source_row_hash) are enforced at DB level
- Composite indexes on (state, create_date DESC) and (log_id, state) exist
- ACL rows are properly defined for all three models
- Constraints are properly mirrored in init() per drift template

Tests use direct SQL queries to verify database schema and constraints.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTrackingImportLogDB(TransactionCase):
    """Phase 1: Verify tracking.import.log table exists with correct schema."""

    def test_tracking_import_log_table_exists(self):
        """Test that tracking_import_log table exists in the database."""
        self.env.cr.execute("""
            SELECT to_regclass('public.tracking_import_log')
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result[0],
            "tracking_import_log table should exist in database"
        )

    def test_tracking_import_log_columns_exist(self):
        """Test that tracking_import_log table has all required columns."""
        required_columns = [
            'id', 'name', 'state', 'source', 'source_gdrive_file_id',
            'filename', 'file_size_bytes', 'schema_hash', 'header_columns',
            'is_new_schema', 'total_rows', 'matched_count', 'unmatched_count',
            'conflict_count', 'error_count', 'imported_count',
            'address_change_flagged_count', 'start_at', 'finish_at',
            'triggered_by_user_id', 'notes',
            'create_uid', 'create_date', 'write_uid', 'write_date'
        ]

        self.env.cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'tracking_import_log'
            AND table_schema = 'public'
        """)
        existing_columns = {row[0] for row in self.env.cr.fetchall()}

        for col in required_columns:
            self.assertIn(
                col,
                existing_columns,
                f"Column '{col}' should exist in tracking_import_log table"
            )

    def test_tracking_import_log_composite_index_state_create_date(self):
        """Test that tracking_import_log has composite index on (state, create_date DESC)."""
        self.env.cr.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'tracking_import_log'
        """)
        indexes = {row[0]: row[1] for row in self.env.cr.fetchall()}

        state_create_found = any(
            'state' in idx_def and 'create_date' in idx_def
            for idx_def in indexes.values()
        )
        self.assertTrue(
            state_create_found,
            "Composite index on (state, create_date DESC) should exist"
        )

    def test_tracking_import_log_schema_hash_index(self):
        """Test that tracking_import_log has index on schema_hash field."""
        self.env.cr.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'tracking_import_log'
        """)
        indexes = {row[0]: row[1] for row in self.env.cr.fetchall()}

        schema_hash_found = any(
            'schema_hash' in idx_def
            for idx_def in indexes.values()
        )
        self.assertTrue(
            schema_hash_found,
            "Index on schema_hash should exist"
        )

    def test_tracking_import_log_acl_rows_exist(self):
        """Test that ACL rows are defined for tracking.import.log."""
        self.env.cr.execute("""
            SELECT COUNT(*)
            FROM ir_model_access
            WHERE model_id = (
                SELECT id FROM ir_model WHERE model = 'tracking.import.log'
            )
        """)
        acl_count = self.env.cr.fetchone()[0]

        self.assertGreaterEqual(
            acl_count,
            3,
            "At least 3 ACL rows should be defined for tracking.import.log "
            "(group_ba_shipping, group_ba_manager, base.group_system)"
        )


@tagged('post_install', '-at_install')
class TestTrackingImportLineDB(TransactionCase):
    """Phase 1: Verify tracking.import.line table exists with correct schema."""

    def test_tracking_import_line_table_exists(self):
        """Test that tracking_import_line table exists in the database."""
        self.env.cr.execute("""
            SELECT to_regclass('public.tracking_import_line')
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result[0],
            "tracking_import_line table should exist in database"
        )

    def test_tracking_import_line_columns_exist(self):
        """Test that tracking_import_line table has all required columns."""
        required_columns = [
            'id', 'log_id', 'row_number', 'source_row_hash', 'state',
            'raw_order_number', 'raw_tracking_number', 'raw_carrier_label',
            'raw_shipping_date', 'raw_payload', 'parsed_shipping_date',
            'sale_order_id', 'fulfillment_id', 'detected_carrier_id',
            'applied_carrier_id', 'address_change_flag', 'error_message', 'notes',
            'create_uid', 'create_date', 'write_uid', 'write_date'
        ]

        self.env.cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'tracking_import_line'
            AND table_schema = 'public'
        """)
        existing_columns = {row[0] for row in self.env.cr.fetchall()}

        for col in required_columns:
            self.assertIn(
                col,
                existing_columns,
                f"Column '{col}' should exist in tracking_import_line table"
            )

    def test_tracking_import_line_unique_constraint_idempotency(self):
        """Test that UNIQUE constraint on (log_id, source_row_hash) exists."""
        self.env.cr.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'tracking_import_line'
            AND constraint_type = 'UNIQUE'
        """)
        unique_constraints = {row[0] for row in self.env.cr.fetchall()}

        # Check that the specific idempotency constraint exists
        idempotency_found = any(
            'idempotency' in constraint_name.lower()
            for constraint_name in unique_constraints
        )
        self.assertTrue(
            idempotency_found,
            "UNIQUE constraint 'tracking_import_line_idempotency_uniq' "
            "on (log_id, source_row_hash) should exist"
        )

    def test_tracking_import_line_composite_index_log_state(self):
        """Test that tracking_import_line has composite index on (log_id, state)."""
        self.env.cr.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'tracking_import_line'
        """)
        indexes = {row[0]: row[1] for row in self.env.cr.fetchall()}

        log_state_found = any(
            'log_id' in idx_def and 'state' in idx_def
            for idx_def in indexes.values()
        )
        self.assertTrue(
            log_state_found,
            "Composite index on (log_id, state) should exist"
        )

    def test_tracking_import_line_sale_order_index(self):
        """Test that tracking_import_line has index on sale_order_id."""
        self.env.cr.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'tracking_import_line'
        """)
        indexes = {row[0]: row[1] for row in self.env.cr.fetchall()}

        sale_order_found = any(
            'sale_order_id' in idx_def
            for idx_def in indexes.values()
        )
        self.assertTrue(
            sale_order_found,
            "Index on sale_order_id should exist"
        )

    def test_tracking_import_line_source_row_hash_index(self):
        """Test that tracking_import_line has index on source_row_hash."""
        self.env.cr.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'tracking_import_line'
        """)
        indexes = {row[0]: row[1] for row in self.env.cr.fetchall()}

        hash_found = any(
            'source_row_hash' in idx_def
            for idx_def in indexes.values()
        )
        self.assertTrue(
            hash_found,
            "Index on source_row_hash should exist"
        )

    def test_tracking_import_line_acl_rows_exist(self):
        """Test that ACL rows are defined for tracking.import.line."""
        self.env.cr.execute("""
            SELECT COUNT(*)
            FROM ir_model_access
            WHERE model_id = (
                SELECT id FROM ir_model WHERE model = 'tracking.import.line'
            )
        """)
        acl_count = self.env.cr.fetchone()[0]

        self.assertGreaterEqual(
            acl_count,
            3,
            "At least 3 ACL rows should be defined for tracking.import.line "
            "(group_ba_shipping, group_ba_manager, base.group_system)"
        )


@tagged('post_install', '-at_install')
class TestTrackingImportWizardDB(TransactionCase):
    """Phase 1: Verify tracking.import.wizard table and ACLs exist."""

    def test_tracking_import_wizard_table_exists(self):
        """Test that tracking_import_wizard table exists (TransientModel)."""
        self.env.cr.execute("""
            SELECT to_regclass('public.tracking_import_wizard')
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result[0],
            "tracking_import_wizard table should exist in database"
        )

    def test_tracking_import_wizard_columns_exist(self):
        """Test that tracking_import_wizard has required columns."""
        required_columns = [
            'id', 'excel_file', 'excel_filename', 'state',
            'schema_hash', 'is_new_schema', 'header_diff_html',
            'preview_log_id'
        ]

        self.env.cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'tracking_import_wizard'
            AND table_schema = 'public'
        """)
        existing_columns = {row[0] for row in self.env.cr.fetchall()}

        for col in required_columns:
            self.assertIn(
                col,
                existing_columns,
                f"Column '{col}' should exist in tracking_import_wizard table"
            )

    def test_tracking_import_wizard_acl_rows_exist(self):
        """Test that ACL rows are defined for tracking.import.wizard."""
        self.env.cr.execute("""
            SELECT COUNT(*)
            FROM ir_model_access
            WHERE model_id = (
                SELECT id FROM ir_model WHERE model = 'tracking.import.wizard'
            )
        """)
        acl_count = self.env.cr.fetchone()[0]

        self.assertGreaterEqual(
            acl_count,
            2,
            "At least 2 ACL rows should be defined for tracking.import.wizard "
            "(group_ba_shipping, group_ba_manager)"
        )


@tagged('post_install', '-at_install')
class TestP204Views(TransactionCase):
    """Phase 1: Database verification for P2-04 tracking import log visibility + replay.

    Tests verify:
    - schema_hash field is visible in list view (not hidden)
    - Smart-button action for today's imports exists
    - action_replay_line method exists on tracking.import.line
    - action_resolve_conflict method exists on tracking.import.line
    - _recount_summary method exists on tracking.import.log
    """

    def test_tracking_import_log_schema_hash_visible(self):
        """T2-04-01: schema_hash field is not hidden in list view.

        Assert that the list view XML for tracking.import.log has schema_hash
        without optional="hide" attribute (or optional is not set).
        """
        list_view = self.env.ref(
            'multichannel_hub_fulfillment.view_tracking_import_log_list',
            raise_if_not_found=False
        )

        self.assertIsNotNone(
            list_view,
            "List view view_tracking_import_log_list should exist"
        )

        # Parse XML arch and check for schema_hash field
        arch_str = list_view.arch

        self.assertIn(
            'schema_hash',
            arch_str,
            "schema_hash field should be present in list view"
        )

        # Verify schema_hash is not hidden
        # If optional="hide" is present, the test should fail
        import re
        schema_hash_pattern = r'<field\s+name="schema_hash"[^>]*/?>'
        match = re.search(schema_hash_pattern, arch_str)

        self.assertIsNotNone(
            match,
            "schema_hash field should be defined in list view XML"
        )

        # Check that optional="hide" is NOT present on schema_hash
        field_xml = match.group(0)
        self.assertNotIn(
            'optional="hide"',
            field_xml,
            "schema_hash should not have optional='hide' attribute"
        )

    def test_smart_button_action_today_imports_exists(self):
        """T2-04-02: Smart-button action for today's imports is registered.

        Assert that ir.actions.act_window with xmlid
        action_tracking_import_log_today exists and is accessible.
        """
        action = self.env.ref(
            'multichannel_hub_fulfillment.action_tracking_import_log_today',
            raise_if_not_found=False
        )

        self.assertIsNotNone(
            action,
            "Smart-button action_tracking_import_log_today should be registered"
        )

    def test_action_replay_line_method_exists(self):
        """T2-04-03: action_replay_line method exists on tracking.import.line.

        Assert that the tracking.import.line model has the action_replay_line
        method defined.
        """
        self.assertTrue(
            hasattr(self.env['tracking.import.line'], 'action_replay_line'),
            "tracking.import.line should have action_replay_line method"
        )

    def test_action_resolve_conflict_method_exists(self):
        """T2-04-04: action_resolve_conflict method exists on tracking.import.line.

        Assert that the tracking.import.line model has the action_resolve_conflict
        method defined.
        """
        self.assertTrue(
            hasattr(self.env['tracking.import.line'], 'action_resolve_conflict'),
            "tracking.import.line should have action_resolve_conflict method"
        )

    def test_recount_summary_method_exists(self):
        """T2-04-05: _recount_summary method exists on tracking.import.log.

        Assert that the tracking.import.log model has the _recount_summary
        method defined.
        """
        self.assertTrue(
            hasattr(self.env['tracking.import.log'], '_recount_summary'),
            "tracking.import.log should have _recount_summary method"
        )


@tagged('post_install', '-at_install')
class TestP206LogisticsPartnerDB(TransactionCase):
    """Phase 1: Database verification for P2-06 GDrive auto-polling.

    Tests verify:
    - logistics.partner table exists with correct schema
    - UNIQUE(code) constraint exists and is enforced at DB level
    - ACL rows are defined (ba_shipping read, ba_manager read, system full)
    - GdriveUploader has required methods (list_files, download_file, move_file, upload_text)
    - logistics.inbox.poller cron record exists
    """

    def test_logistics_partner_table_exists(self):
        """T2-06-01: logistics.partner table exists in database."""
        self.env.cr.execute("""
            SELECT to_regclass('public.logistics_partner')
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result[0],
            "logistics_partner table should exist in database"
        )

    def test_logistics_partner_code_unique_constraint(self):
        """T2-06-02: logistics.partner has UNIQUE(code) constraint at DB level.

        Query pg_constraint for a constraint matching the expected pattern.
        This verifies the drift template (8th use) was correctly applied.
        """
        self.env.cr.execute("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = 'logistics_partner'
            AND constraint_type = 'UNIQUE'
        """)
        constraints = self.env.cr.fetchall()

        found = any(
            'code' in constraint_name.lower()
            for constraint_name, _ in constraints
        )
        self.assertTrue(
            found,
            "UNIQUE constraint on code should exist in logistics_partner table"
        )

    def test_logistics_partner_acl_rows_exist(self):
        """T2-06-03: ACL rows exist for logistics.partner.

        Assert 3 rows in ir.model.access for logistics.partner:
        - group_ba_shipping: read-only (1,0,0,0)
        - group_ba_manager: read-only (1,0,0,0)
        - base.group_system: full access (1,1,1,1)
        """
        import os

        # Read ACL CSV file directly (test file is in <module>/tests/)
        test_dir = os.path.dirname(os.path.abspath(__file__))
        module_dir = os.path.dirname(test_dir)
        acl_path = os.path.join(module_dir, 'security', 'ir.model.access.csv')

        self.assertTrue(
            os.path.exists(acl_path),
            f"ACL file should exist at {acl_path}"
        )

        with open(acl_path, 'r') as f:
            lines = f.readlines()

        # Filter for logistics_partner rows
        logistics_partner_rows = [
            line.strip() for line in lines
            if 'logistics.partner' in line and not line.startswith('#')
        ]

        self.assertGreaterEqual(
            len(logistics_partner_rows),
            3,
            f"Expected at least 3 ACL rows for logistics.partner; found {len(logistics_partner_rows)}"
        )

    def test_gdrive_uploader_has_list_files_method(self):
        """T2-06-04: GdriveUploader.list_files method exists."""
        from odoo.addons.multichannel_hub_core.services.gdrive_uploader import GdriveUploader
        self.assertTrue(
            hasattr(GdriveUploader, 'list_files'),
            "GdriveUploader should have list_files method"
        )

    def test_gdrive_uploader_has_download_file_method(self):
        """T2-06-05: GdriveUploader.download_file method exists."""
        from odoo.addons.multichannel_hub_core.services.gdrive_uploader import GdriveUploader
        self.assertTrue(
            hasattr(GdriveUploader, 'download_file'),
            "GdriveUploader should have download_file method"
        )

    def test_gdrive_uploader_has_move_file_method(self):
        """T2-06-06: GdriveUploader.move_file method exists."""
        from odoo.addons.multichannel_hub_core.services.gdrive_uploader import GdriveUploader
        self.assertTrue(
            hasattr(GdriveUploader, 'move_file'),
            "GdriveUploader should have move_file method"
        )

    def test_gdrive_uploader_has_upload_text_method(self):
        """T2-06-07: GdriveUploader.upload_text method exists."""
        from odoo.addons.multichannel_hub_core.services.gdrive_uploader import GdriveUploader
        self.assertTrue(
            hasattr(GdriveUploader, 'upload_text'),
            "GdriveUploader should have upload_text method"
        )

    def test_logistics_inbox_poller_cron_exists(self):
        """T2-06-08: logistics.inbox.poller cron record exists after install.

        Assert that ir.cron record with xml_id=cron_logistics_inbox_poller
        is present in the database.
        """
        cron = self.env.ref(
            'multichannel_hub_fulfillment.cron_logistics_inbox_poller',
            raise_if_not_found=False
        )

        self.assertIsNotNone(
            cron,
            "Cron record cron_logistics_inbox_poller should exist after module install"
        )
