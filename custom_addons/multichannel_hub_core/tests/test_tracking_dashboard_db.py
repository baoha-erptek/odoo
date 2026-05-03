"""
Phase 1: Database Verification Tests for Tracking Dashboard.

Tests verify schema-level implementation of P1-03 fields and constraints:
- pd_pic_user_id column and index
- warehouse_zone column and nullable default
- tracking_number btree index (regression from P1-05)
- Constraint: _check_block_reason_when_blocked (regression from P1-05)

Tests use direct SQL to verify database schema independent of ORM layer.
"""

import logging

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestTrackingDashboardSchema(TransactionCase):
    """Phase 1 DB: Verify tracking dashboard schema changes."""

    def test_pd_pic_user_id_column_exists(self):
        """Verify pd_pic_user_id column exists with correct type and nullable."""
        self.env.cr.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'sale_order_fulfillment'
            AND column_name = 'pd_pic_user_id'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(result, "Column pd_pic_user_id should exist in sale_order_fulfillment")
        column_name, data_type, is_nullable = result
        self.assertEqual(column_name, 'pd_pic_user_id')
        self.assertEqual(data_type, 'integer', "pd_pic_user_id should be integer type (M2O to res.users)")
        self.assertEqual(is_nullable, 'YES', "pd_pic_user_id should be nullable")

    def test_pd_pic_user_id_indexed(self):
        """Verify pd_pic_user_id has a btree index for query performance."""
        self.env.cr.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'sale_order_fulfillment'
            AND indexname LIKE '%pd_pic_user_id%'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(result, "pd_pic_user_id should have an index")
        indexname, indexdef = result
        self.assertIn('pd_pic_user_id', indexdef, "Index definition should reference pd_pic_user_id")
        self.assertIn('btree', indexdef, "Index should use btree type (Odoo default for index=True)")

    def test_warehouse_zone_column_exists(self):
        """Verify warehouse_zone column exists with correct type and is nullable."""
        self.env.cr.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'sale_order_fulfillment'
            AND column_name = 'warehouse_zone'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(result, "Column warehouse_zone should exist in sale_order_fulfillment")
        column_name, data_type, is_nullable = result
        self.assertEqual(column_name, 'warehouse_zone')
        self.assertEqual(data_type, 'character varying', "warehouse_zone should be varchar (Odoo Selection field)")
        self.assertEqual(is_nullable, 'YES', "warehouse_zone should be nullable (no default override)")

    def test_warehouse_zone_indexed(self):
        """Verify warehouse_zone has a btree index for filter performance."""
        self.env.cr.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'sale_order_fulfillment'
            AND indexname LIKE '%warehouse_zone%'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(result, "warehouse_zone should have an index")
        indexname, indexdef = result
        self.assertIn('warehouse_zone', indexdef, "Index definition should reference warehouse_zone")

    def test_tracking_number_btree_index_exists(self):
        """Regression test: verify tracking_number index from P1-05 is present."""
        self.env.cr.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'sale_order_fulfillment'
            AND indexname LIKE '%tracking_number%'
        """)
        result = self.env.cr.fetchone()

        self.assertIsNotNone(result, "tracking_number should have a btree index (P1-05)")
        indexname, indexdef = result
        self.assertIn('tracking_number', indexdef, "Index definition should reference tracking_number")

    def test_c_sof_001_constraint_present(self):
        """Regression test: verify C-SOF-001 constraint exists in ORM.

        C-SOF-001: block_reason is required when production_blocked=True.
        """
        fulfillment_model = self.env['sale.order.fulfillment']
        constraint_methods = fulfillment_model._constraint_methods

        self.assertIsNotNone(
            constraint_methods,
            "sale.order.fulfillment should have constraint methods"
        )

        constraint_method_names = [method.__name__ for method in constraint_methods]
        self.assertIn(
            '_check_block_reason_when_blocked',
            constraint_method_names,
            "Constraint _check_block_reason_when_blocked should be registered (C-SOF-001)"
        )

    def test_action_window_tracking_dashboard_exists(self):
        """Verify action_tracking_dashboard action_window record exists."""
        action = self.env.ref('multichannel_hub_core.action_tracking_dashboard')

        self.assertIsNotNone(action, "action_tracking_dashboard should be defined in XML")
        self.assertEqual(action.res_model, 'sale.order.fulfillment')
        self.assertIn('list', action.view_mode, "Tracking dashboard should support list view")

    def test_menu_tracking_dashboard_deleted_after_merge(self):
        """Verify menu_tracking_dashboard is deleted post-merge to unified dashboard."""
        menu = self.env.ref(
            'multichannel_hub_core.menu_tracking_dashboard',
            raise_if_not_found=False
        )
        self.assertFalse(
            menu,
            "menu_tracking_dashboard should be deleted after merge to unified Operations Dashboard"
        )
