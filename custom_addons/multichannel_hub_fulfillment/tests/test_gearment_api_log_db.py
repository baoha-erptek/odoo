"""P0-18b1 Phase 1 — Database schema verification for gearment.api.log.

Tests verify:
- Table structure (11 columns)
- Composite index on (sale_order_id, request_started_at)
- Selection values for 'source' field (6 values)
- ACL rows for group_system and group_sale_manager
- Retention cron registration
- ICP default for retention days

Uses direct SQL queries via information_schema to verify persistence.
This phase catches schema drift before ORM tests run.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGearmentApiLogDatabase(TransactionCase):
    """Phase 1: Direct database verification for gearment.api.log schema."""

    def test_gearment_api_log_table_exists(self):
        """Verify gearment.api.log table exists in database."""
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'gearment_api_log'
            )
        """)
        exists = self.env.cr.fetchone()[0]
        self.assertTrue(exists, "gearment_api_log table must exist")

    def test_gearment_api_log_columns_present(self):
        """Verify all 11 required columns are present."""
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = 'gearment_api_log'
            AND column_name NOT IN ('id', 'create_date', 'create_uid', 'write_date', 'write_uid')
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in self.env.cr.fetchall()]

        required = [
            'sale_order_id',
            'endpoint',
            'http_status',
            'request_started_at',
            'duration_ms',
            'request_payload_summary',
            'response_summary',
            'error_message',
            'rate_limit_remaining',
            'source',
        ]

        for col in required:
            self.assertIn(col, columns,
                         f"Column '{col}' must exist in gearment_api_log")

    def test_source_selection_values(self):
        """Verify source field has exactly 6 selection values."""
        model = self.env['gearment.api.log']
        source_field = model._fields['source']
        selection_values = dict(source_field.selection)

        expected_sources = {'probe', 'draft', 'quote', 'confirm', 'callback', 'health_check'}
        actual_sources = set(selection_values.keys())

        self.assertEqual(
            actual_sources,
            expected_sources,
            f"Source selection must have exactly {expected_sources}, got {actual_sources}"
        )

    def test_composite_index_request_started_at(self):
        """Verify composite index on (sale_order_id, request_started_at)."""
        self.env.cr.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename = 'gearment_api_log'
        """)
        indexes = self.env.cr.fetchall()

        # At least one index should include both columns
        found = False
        for indexname, indexdef in indexes:
            if 'sale_order_id' in indexdef and 'request_started_at' in indexdef:
                found = True
                break

        self.assertTrue(
            found,
            f"Composite index on (sale_order_id, request_started_at) must exist. Found indexes: {[idx[0] for idx in indexes]}"
        )

    def test_acl_group_system_full(self):
        """Verify ir.model.access row for group_system has all perms."""
        system_group = self.env.ref('base.group_system')
        acl = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'gearment.api.log'),
            ('group_id', '=', system_group.id),
        ])

        self.assertTrue(acl, "ACL row must exist for gearment.api.log + group_system")

        # Check all 4 permissions are granted
        self.assertTrue(acl.perm_read, "group_system must have read permission")
        self.assertTrue(acl.perm_write, "group_system must have write permission")
        self.assertTrue(acl.perm_create, "group_system must have create permission")
        self.assertTrue(acl.perm_unlink, "group_system must have unlink permission")

    def test_acl_group_sale_manager_read_only(self):
        """Verify ir.model.access row for group_sale_manager is read-only."""
        sale_manager_group = self.env.ref('sales_team.group_sale_manager')
        acl = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'gearment.api.log'),
            ('group_id', '=', sale_manager_group.id),
        ])

        self.assertTrue(acl, "ACL row must exist for gearment.api.log + group_sale_manager")

        # Check read-only
        self.assertTrue(acl.perm_read, "group_sale_manager must have read permission")
        self.assertFalse(acl.perm_write, "group_sale_manager must NOT have write permission")
        self.assertFalse(acl.perm_create, "group_sale_manager must NOT have create permission")
        self.assertFalse(acl.perm_unlink, "group_sale_manager must NOT have unlink permission")

    def test_retention_cron_exists(self):
        """Verify ir.cron record for _cron_cleanup_old_logs exists."""
        cron = self.env['ir.cron'].search([
            ('model_id.model', '=', 'gearment.api.log'),
        ])

        self.assertTrue(cron, "Cron job for gearment.api.log retention must exist")

        # Verify the method name references cleanup
        self.assertIn('cleanup', cron.code.lower(),
                     "Cron code must reference cleanup method")

    def test_retention_icp_default(self):
        """Verify ir.config_parameter for retention days defaults to 30."""
        icp_key = 'multichannel_hub_fulfillment.api_log_retention_days'
        icp = self.env['ir.config_parameter'].get_param(icp_key)

        self.assertIsNotNone(icp, f"ICP '{icp_key}' must be defined")
        self.assertEqual(icp, '30', f"Retention days default must be '30', got '{icp}'")
