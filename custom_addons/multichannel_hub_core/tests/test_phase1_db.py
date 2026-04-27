"""
Phase 1: Database-level verification for sale.order.fulfillment delegation mixin.

Tests verify that the underlying PostgreSQL schema is correctly set up:
- sale_order_fulfillment table exists with all required columns
- sale_order.fulfillment_id FK column exists with cascade delete
- Indexes on critical fields (tracking_number, pic_user_id) are in place
- Foreign key constraints are properly configured

Tests use direct SQL via self.env.cr.execute to verify the database state
at the lowest level, independent of ORM machinery.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestPhase1DB(TransactionCase):
    """Direct PostgreSQL verification for sale.order.fulfillment schema."""

    def test_table_sale_order_fulfillment_exists(self):
        """Verify sale_order_fulfillment table exists in the database."""
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'sale_order_fulfillment'
            )
        """)
        table_exists = self.env.cr.fetchone()[0]
        self.assertTrue(table_exists, "sale_order_fulfillment table must exist")

    def test_fulfillment_id_column_on_sale_order(self):
        """Verify fulfillment_id column exists on sale_order table."""
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'sale_order'
                AND column_name = 'fulfillment_id'
            )
        """)
        column_exists = self.env.cr.fetchone()[0]
        self.assertTrue(
            column_exists,
            "sale_order.fulfillment_id column must exist"
        )

    def test_fulfillment_id_fk_cascade(self):
        """Verify FK from sale_order.fulfillment_id has CASCADE delete."""
        self.env.cr.execute("""
            SELECT confdeltype
            FROM pg_constraint
            WHERE conrelid = 'sale_order'::regclass
            AND conname LIKE '%fulfillment_id%'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "FK constraint on sale_order.fulfillment_id must exist"
        )
        confdeltype = result[0]
        self.assertEqual(
            confdeltype,
            'c',
            "FK must have CASCADE delete (confdeltype='c')"
        )

    def test_tracking_number_indexed(self):
        """Verify tracking_number column is indexed on sale_order_fulfillment."""
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename = 'sale_order_fulfillment'
                AND indexname LIKE '%tracking_number%'
            )
        """)
        index_exists = self.env.cr.fetchone()[0]
        self.assertTrue(
            index_exists,
            "tracking_number index must exist on sale_order_fulfillment"
        )

    # NOTE: shipping_carrier_id (Many2one to shipping.carrier) is deferred
    # to P1-06, which lands the shipping.carrier model + this FK together.
    # Odoo 19's registry build rejects unknown comodel_name strings, so a
    # forward reference in this slice is not viable. Re-add this test in
    # P1-06.

    def test_pic_user_id_indexed(self):
        """Verify pic_user_id column is indexed on sale_order_fulfillment."""
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT 1 FROM pg_indexes
                WHERE schemaname = 'public'
                AND tablename = 'sale_order_fulfillment'
                AND indexname LIKE '%pic_user_id%'
            )
        """)
        index_exists = self.env.cr.fetchone()[0]
        self.assertTrue(
            index_exists,
            "pic_user_id index must exist on sale_order_fulfillment"
        )
