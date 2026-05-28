"""
Phase 1: Database-level verification for shipping.carrier model.

Tests verify that the underlying PostgreSQL schema is correctly set up:
- shipping_carrier table exists with all required columns
- code column is indexed for fast lookups
- sale_order_fulfillment.shipping_carrier_id FK column exists with set null ondelete
- Seed data rows are present in the database

Tests use direct SQL via self.env.cr.execute to verify the database state
at the lowest level, independent of ORM machinery.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestPhase1ShippingCarrierDB(TransactionCase):
    """Direct PostgreSQL verification for shipping.carrier schema."""

    def test_table_shipping_carrier_exists(self):
        """Verify shipping_carrier table exists in the database."""
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'shipping_carrier'
            )
        """)
        table_exists = self.env.cr.fetchone()[0]
        self.assertTrue(table_exists, "shipping_carrier table must exist")

    def test_code_indexed(self):
        """Verify code column is indexed on shipping_carrier table."""
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename = 'shipping_carrier'
                AND indexname LIKE '%code%'
            )
        """)
        index_exists = self.env.cr.fetchone()[0]
        self.assertTrue(
            index_exists,
            "code index must exist on shipping_carrier"
        )

    def test_shipping_carrier_id_column_on_fulfillment(self):
        """Verify shipping_carrier_id column exists on sale_order_fulfillment table."""
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'sale_order_fulfillment'
                AND column_name = 'shipping_carrier_id'
            )
        """)
        column_exists = self.env.cr.fetchone()[0]
        self.assertTrue(
            column_exists,
            "sale_order_fulfillment.shipping_carrier_id column must exist"
        )

    def test_shipping_carrier_id_fk_set_null(self):
        """Verify FK from sale_order_fulfillment.shipping_carrier_id has SET NULL delete."""
        self.env.cr.execute("""
            SELECT confdeltype
            FROM pg_constraint
            WHERE conrelid = 'sale_order_fulfillment'::regclass
            AND conname LIKE '%shipping_carrier_id%'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "FK constraint on sale_order_fulfillment.shipping_carrier_id must exist"
        )
        confdeltype = result[0]
        self.assertEqual(
            confdeltype,
            'n',
            "FK must have SET NULL delete (confdeltype='n')"
        )

    def test_seed_rows_present_in_db(self):
        """Verify seed data rows (at least 7 carriers) are present in the database."""
        self.env.cr.execute("SELECT COUNT(*) FROM shipping_carrier")
        count = self.env.cr.fetchone()[0]
        self.assertGreaterEqual(
            count,
            7,
            "shipping_carrier table must contain at least 7 seed rows"
        )
