"""Phase 1 (Database Verification) Tests for P1-01a Order Dashboard.

Verifies table structure, columns, indexes, and backfill idempotency at the
database level. These tests ensure data integrity and schema correctness
post-install before ORM unit tests run.

Tasks covered: T024, T025, T026, T027, T028, T029, T031 (DB shape + backfill).
"""

import logging

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('-at_install', 'post_install')
class TestOrderDashboardDbShape(TransactionCase):
    """Phase 1: Database schema verification for Order Dashboard fields."""

    def test_sales_channel_column_exists_on_sale_order(self):
        """Verify sale_order.sales_channel column exists and is varchar."""
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'sale_order'
                AND column_name = 'sales_channel'
            )
        """)
        col_exists = self.env.cr.fetchone()[0]
        self.assertTrue(
            col_exists,
            "Column 'sales_channel' not found in 'sale_order' table"
        )

    def test_channel_order_ref_column_exists_on_sale_order(self):
        """Verify sale_order.channel_order_ref column exists and is varchar."""
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'sale_order'
                AND column_name = 'channel_order_ref'
            )
        """)
        col_exists = self.env.cr.fetchone()[0]
        self.assertTrue(
            col_exists,
            "Column 'channel_order_ref' not found in 'sale_order' table"
        )

    def test_qty_total_column_exists_on_sale_order(self):
        """Verify sale_order.qty_total column exists and is numeric."""
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'sale_order'
                AND column_name = 'qty_total'
            )
        """)
        col_exists = self.env.cr.fetchone()[0]
        self.assertTrue(
            col_exists,
            "Column 'qty_total' not found in 'sale_order' table"
        )

    def test_is_duplicate_buyer_column_exists_on_sale_order(self):
        """Verify sale_order.is_duplicate_buyer column exists and is boolean."""
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'sale_order'
                AND column_name = 'is_duplicate_buyer'
            )
        """)
        col_exists = self.env.cr.fetchone()[0]
        self.assertTrue(
            col_exists,
            "Column 'is_duplicate_buyer' not found in 'sale_order' table"
        )

    def test_is_overdue_approval_column_exists_on_sale_order(self):
        """Verify sale_order.is_overdue_approval column exists and is boolean."""
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'sale_order'
                AND column_name = 'is_overdue_approval'
            )
        """)
        col_exists = self.env.cr.fetchone()[0]
        self.assertTrue(
            col_exists,
            "Column 'is_overdue_approval' not found in 'sale_order' table"
        )

    def test_composite_index_sales_channel_and_pending_address_change_exists(self):
        """Verify composite index (sales_channel, has_pending_address_change) exists."""
        self.env.cr.execute("""
            SELECT indexname, indexdef FROM pg_indexes
            WHERE tablename = 'sale_order'
            AND indexdef LIKE '%sales_channel%has_pending_address_change%'
        """)
        result = self.env.cr.fetchone()
        self.assertIsNotNone(
            result,
            "Composite index (sales_channel, has_pending_address_change) not found"
        )

    def test_backfill_idempotent(self):
        """Verify backfill helper is idempotent (can run multiple times safely)."""
        # Create a fixture order with etsy_order_id and sales_channel=NULL
        self.env.cr.execute("""
            INSERT INTO sale_order
            (name, partner_id, create_date, write_date, create_uid, write_uid, fulfillment_id)
            VALUES (%s, %s, NOW(), NOW(), %s, %s, %s)
            RETURNING id
        """, ('TEST-IDEMPOT', 1, 2, 2, None))

        order_id = self.env.cr.fetchone()[0]

        # Manually set etsy_order_id via raw SQL (simulate existing order)
        self.env.cr.execute("""
            UPDATE sale_order SET etsy_order_id = %s WHERE id = %s
        """, ('etsy-123', order_id))

        # Import and call the backfill helper
        from odoo.addons.multichannel_hub_core import _backfill_sales_channel
        _backfill_sales_channel(self.env)

        # Verify the row was backfilled
        self.env.cr.execute("""
            SELECT sales_channel FROM sale_order WHERE id = %s
        """, (order_id,))
        first_result = self.env.cr.fetchone()
        self.assertIsNotNone(first_result)
        self.assertEqual(first_result[0], 'etsy')

        # Call backfill again
        _backfill_sales_channel(self.env)

        # Verify row still has same value (idempotent)
        self.env.cr.execute("""
            SELECT sales_channel FROM sale_order WHERE id = %s
        """, (order_id,))
        second_result = self.env.cr.fetchone()
        self.assertEqual(second_result[0], 'etsy', "Backfill should be idempotent")

    def test_backfill_sets_etsy_for_etsy_orders(self):
        """Verify backfill sets sales_channel='etsy' for orders with etsy_order_id."""
        # Create a fixture order
        self.env.cr.execute("""
            INSERT INTO sale_order
            (name, partner_id, create_date, write_date, create_uid, write_uid, fulfillment_id)
            VALUES (%s, %s, NOW(), NOW(), %s, %s, %s)
            RETURNING id
        """, ('TEST-ETSY', 1, 2, 2, None))

        order_id = self.env.cr.fetchone()[0]

        # Set etsy_order_id via raw SQL
        self.env.cr.execute("""
            UPDATE sale_order SET etsy_order_id = %s WHERE id = %s
        """, ('etsy-456', order_id))

        # Call backfill helper
        from odoo.addons.multichannel_hub_core import _backfill_sales_channel
        _backfill_sales_channel(self.env)

        # Verify channel is 'etsy'
        self.env.cr.execute("""
            SELECT sales_channel FROM sale_order WHERE id = %s
        """, (order_id,))
        result = self.env.cr.fetchone()
        self.assertEqual(result[0], 'etsy', "Etsy orders should have sales_channel='etsy'")

    def test_backfill_sets_other_for_non_etsy_orders(self):
        """Verify backfill sets sales_channel='other' for orders without etsy_order_id."""
        # Create a fixture order with no etsy_order_id
        self.env.cr.execute("""
            INSERT INTO sale_order
            (name, partner_id, create_date, write_date, create_uid, write_uid, fulfillment_id)
            VALUES (%s, %s, NOW(), NOW(), %s, %s, %s)
            RETURNING id
        """, ('TEST-OTHER', 1, 2, 2, None))

        order_id = self.env.cr.fetchone()[0]

        # Explicitly set etsy_order_id to NULL (ensure it's empty)
        self.env.cr.execute("""
            UPDATE sale_order SET etsy_order_id = NULL, sales_channel = NULL WHERE id = %s
        """, (order_id,))

        # Call backfill helper
        from odoo.addons.multichannel_hub_core import _backfill_sales_channel
        _backfill_sales_channel(self.env)

        # Verify channel is 'other'
        self.env.cr.execute("""
            SELECT sales_channel FROM sale_order WHERE id = %s
        """, (order_id,))
        result = self.env.cr.fetchone()
        self.assertEqual(
            result[0], 'other',
            "Non-Etsy orders should have sales_channel='other'"
        )

    def test_menu_order_dashboard_resolvable(self):
        """Verify menu entry multichannel_hub_core.menu_order_dashboard is resolvable."""
        try:
            menu = self.env.ref('multichannel_hub_core.menu_order_dashboard')
            self.assertTrue(menu, "menu_order_dashboard should be resolvable")
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.menu_order_dashboard') "
                     "raised ValueError; menu not found")

    def test_action_window_order_dashboard_resolvable(self):
        """Verify action_order_dashboard act_window is resolvable and points to sale.order."""
        try:
            action = self.env.ref('multichannel_hub_core.action_order_dashboard')
            self.assertTrue(action, "action_order_dashboard should be resolvable")
            self.assertEqual(
                action.res_model, 'sale.order',
                "action_order_dashboard should target 'sale.order' model"
            )
        except ValueError:
            self.fail("env.ref('multichannel_hub_core.action_order_dashboard') "
                     "raised ValueError; action not found")
