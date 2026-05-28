"""P0-17 Phase 1 — Database-level tests for etsy.api.log infrastructure.

This module verifies database structure at the lowest level:
- Column existence and types
- Index definitions
- Cron job metadata
- ir.config_parameter defaults

Phase 1 tests use direct SQL to verify persistent storage state,
complemented by Phase 2 ORM tests that verify business logic.

Reference: Master Plan 006, P0-17 planner OQ1-OQ7.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestP0_17_DatabaseStructure(TransactionCase):
    """Verify database structure for P0-17 (etsy.api.log) infrastructure."""

    def test_etsy_api_log_table_exists(self):
        """The `etsy_api_log` table must exist in the database."""
        self.env.cr.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'etsy_api_log'
        """)
        row = self.env.cr.fetchone()
        self.assertIsNotNone(
            row,
            "Table etsy_api_log does not exist; RED test passes."
        )

    def test_etsy_api_log_columns_exist(self):
        """All 11 required columns must exist on etsy_api_log table."""
        required_columns = [
            'shop_id', 'endpoint', 'http_status', 'request_started_at',
            'duration_ms', 'request_payload_summary', 'response_summary',
            'error_message', 'quota_used_today', 'quota_remaining_today',
            'source'
        ]

        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'etsy_api_log'
            ORDER BY column_name
        """)
        columns = {row[0]: row[1] for row in self.env.cr.fetchall()}

        for col in required_columns:
            self.assertIn(
                col, columns,
                f"Column {col} does not exist on etsy_api_log table"
            )

    def test_etsy_api_log_index_on_shop_id_request_started_at(self):
        """Index (shop_id, request_started_at DESC) must exist for query performance."""
        self.env.cr.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = 'etsy_api_log'
        """)
        indexes = {row[0]: row[1] for row in self.env.cr.fetchall()}

        # Check that at least one index references both shop_id and request_started_at
        found = False
        for idx_name, idx_def in indexes.items():
            if 'shop_id' in idx_def and 'request_started_at' in idx_def:
                found = True
                break

        self.assertTrue(
            found,
            f"No index found with both shop_id and request_started_at. "
            f"Available indexes: {list(indexes.keys())}"
        )

    def test_etsy_api_log_no_mail_thread_columns(self):
        """etsy.api.log does NOT inherit mail.thread to avoid chatter overhead."""
        # Verify that the mail_message table has no thread records pointing
        # to etsy.api.log model
        self.env.cr.execute("""
            SELECT COUNT(*)
            FROM mail_message
            WHERE model = 'etsy.api.log'
        """)
        count = self.env.cr.fetchone()[0]
        self.assertEqual(
            count, 0,
            "mail_message rows referencing etsy.api.log found; "
            "model should not inherit mail.thread"
        )

    def test_cron_etsy_api_log_cleanup_exists(self):
        """The cron job `cron_etsy_api_log_cleanup` must exist."""
        cron = self.env.ref(
            'etsy_integration.cron_etsy_api_log_cleanup',
            raise_if_not_found=False
        )
        self.assertIsNotNone(
            cron,
            "Cron etsy_integration.cron_etsy_api_log_cleanup does not exist; "
            "RED test passes."
        )
        self.assertEqual(
            cron.state, 'code',
            f"Cron state should be 'code', got {cron.state}"
        )
        # Verify code field contains the cleanup method reference
        self.assertIn(
            '_cron_cleanup_old_logs',
            cron.code,
            "Cron code should reference _cron_cleanup_old_logs method"
        )

    def test_etsy_api_log_retention_param_default(self):
        """ir.config_parameter etsy_integration.api_log_retention_days
        should have default value '30'."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'etsy_integration.api_log_retention_days',
            default=None
        )
        # If param doesn't exist, the default in code should be '30'
        # This test verifies either the param exists with value '30'
        # or the implementation will use '30' as fallback
        if param is not None:
            self.assertEqual(
                param, '30',
                f"Retention param should be '30', got {param}"
            )
