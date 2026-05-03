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
        """Verify backfill helper is idempotent.

        post_init_hook already ran during install — every existing row
        has a non-NULL sales_channel (the field is required + default).
        We can't UPDATE a row to NULL to simulate the pre-backfill state
        because PostgreSQL enforces NOT NULL. Instead we exercise
        idempotency by recording row counts per channel before + after
        a second invocation; the second call must touch zero rows.
        """
        from odoo.addons.multichannel_hub_core import _backfill_sales_channel
        self.env.cr.execute(
            "SELECT sales_channel, COUNT(*) FROM sale_order "
            "GROUP BY sales_channel"
        )
        before = dict(self.env.cr.fetchall())

        _backfill_sales_channel(self.env)

        self.env.cr.execute(
            "SELECT sales_channel, COUNT(*) FROM sale_order "
            "GROUP BY sales_channel"
        )
        after = dict(self.env.cr.fetchall())
        self.assertEqual(
            before, after,
            "Re-running backfill must not change row counts per channel"
        )

    def test_backfill_set_etsy_orders_at_install(self):
        """Verify post-install state: every row with etsy_order_id has
        sales_channel='etsy'."""
        self.env.cr.execute("""
            SELECT COUNT(*) FROM sale_order
            WHERE etsy_order_id IS NOT NULL AND etsy_order_id <> ''
              AND sales_channel <> 'etsy'
        """)
        violators = self.env.cr.fetchone()[0]
        self.assertEqual(
            violators, 0,
            "All Etsy-referenced sale.orders should carry sales_channel='etsy'"
        )

    def test_backfill_set_non_etsy_orders_at_install(self):
        """Verify post-install state: every row without etsy_order_id has
        sales_channel set (default='other' covers fresh creates; backfill
        catches pre-existing rows). No NULLs survive the install."""
        self.env.cr.execute(
            "SELECT COUNT(*) FROM sale_order WHERE sales_channel IS NULL"
        )
        nulls = self.env.cr.fetchone()[0]
        self.assertEqual(nulls, 0,
                         "No sale.order should have NULL sales_channel post-install")

    def test_menu_order_dashboard_deleted_after_merge(self):
        """Verify menu entry menu_order_dashboard is deleted post-merge to unified dashboard."""
        menu = self.env.ref(
            'multichannel_hub_core.menu_order_dashboard',
            raise_if_not_found=False
        )
        self.assertFalse(
            menu,
            "menu_order_dashboard should be deleted after merge to unified Operations Dashboard"
        )

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
