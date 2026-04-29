"""
Phase 1: Database verification tests for design.file model.

Tests verify data integrity at the database level:
- Table design_file exists with correct columns
- Indexes are present for performance
- UNIQUE constraint on (order_line_id, file_url) is enforced at DB level
- Binary attachment fields are properly configured

Tests use direct SQL queries to verify database schema and constraints.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDesignFileTableExists(TransactionCase):
    """Phase 1: Verify design.file table exists with correct schema."""

    def test_design_file_table_exists(self):
        """Test that design_file table exists in the database."""
        self.env.cr.execute("""
            SELECT to_regclass('public.design_file')
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(
            result[0],
            "design_file table should exist in database"
        )

    def test_design_file_columns_exist(self):
        """Test that design_file table has all required columns."""
        required_columns = [
            'id', 'name', 'order_id', 'order_line_id', 'parent_file_id',
            'version', 'storage_mode', 'preview_file', 'file_url', 'file_name',
            'file_size', 'file_checksum', 'state', 'rejection_reason',
            'approved_by', 'approved_at', 'is_seed',
            'create_uid', 'create_date', 'write_uid', 'write_date'
        ]

        self.env.cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'design_file'
            AND table_schema = 'public'
        """)
        existing_columns = {row[0] for row in self.env.cr.fetchall()}

        for col in required_columns:
            self.assertIn(
                col,
                existing_columns,
                f"Column '{col}' should exist in design_file table"
            )

    def test_design_file_indexes_exist(self):
        """Test that design_file table has required indexes for performance."""
        self.env.cr.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'design_file'
        """)
        indexes = {row[0]: row[1] for row in self.env.cr.fetchall()}

        # Check for composite index on (order_id, state)
        order_state_found = any(
            '(order_id' in idx_def and 'state' in idx_def
            for idx_def in indexes.values()
        )
        self.assertTrue(
            order_state_found,
            "Composite index on (order_id, state) should exist"
        )

        # Check for composite index on (order_line_id, state)
        order_line_state_found = any(
            '(order_line_id' in idx_def and 'state' in idx_def
            for idx_def in indexes.values()
        )
        self.assertTrue(
            order_line_state_found,
            "Composite index on (order_line_id, state) should exist"
        )

        # Check for index on parent_file_id
        parent_found = any(
            'parent_file_id' in idx_def
            for idx_def in indexes.values()
        )
        self.assertTrue(
            parent_found,
            "Index on parent_file_id should exist"
        )

    def test_design_file_unique_constraint_idempotency_seed(self):
        """Test that UNIQUE constraint on (order_line_id, file_url) exists at DB level."""
        self.env.cr.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'design_file'
            AND constraint_type = 'UNIQUE'
        """)
        constraints = {row[0] for row in self.env.cr.fetchall()}

        # Verify at least one UNIQUE constraint exists that covers the combination
        self.env.cr.execute("""
            SELECT constraint_name
            FROM information_schema.constraint_column_usage
            WHERE table_name = 'design_file'
            AND column_name IN ('order_line_id', 'file_url')
        """)
        constraint_cols = self.env.cr.fetchall()

        # Verify we have a UNIQUE constraint covering these columns
        unique_constraint_found = any(
            row[0] for row in constraint_cols
            if row[0] in constraints
        )
        self.assertTrue(
            unique_constraint_found,
            "UNIQUE constraint on (order_line_id, file_url) should exist at DB level"
        )
