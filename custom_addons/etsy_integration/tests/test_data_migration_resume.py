"""RED tests for Spec 002 W3.2b resumability — T052 failure recovery tests.

Tests the resumability contract (R4) with actual forced failures:
  - Batch-aware last_processed_id checkpoint
  - Per-order savepoint isolation (one order error doesn't fail the batch)
  - Resume-from-checkpoint skips already-processed orders
  - resume_from_checkpoint=False forces full re-scan

RED phase: Tests insert forced failures via monkey-patching. Helpers are stubs,
so failures come from artificial exceptions in the test setup. Tests verify
checkpoint logic and error isolation, not the actual fix helpers.

GREEN phase: Implement stub helpers with real logic; checkpoint advances
as documented; failed orders are logged and skipped.
"""
import logging
from unittest import mock

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestDataMigrationResumability(TransactionCase):
    """T052 — Resumability and failure recovery tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.shop = cls.env['etsy.shop'].create({'name': 'Test Shop'})
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'is_storable': True,
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'test@example.com',
        })

    def _seed_many_orders(self, count):
        """Factory: create N draft Etsy orders for batch testing.

        Args:
            count: total orders to create

        Returns: sorted list of order records
        """
        orders_data = []
        for i in range(1, count + 1):
            orders_data.append({
                'partner_id': self.partner.id,
                'etsy_order_id': f'batch-order-{i}',
                'etsy_shop_id': self.shop.id,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 100.0 + i,
                    'etsy_transaction_id': f'batch-txn-{i}',
                })],
            })
        orders = self.env['sale.order'].create(orders_data)
        return orders.sorted('id')

    # =====================================================================
    # Test 1: Checkpoint Advances Per Batch (Even With Errors)
    # =====================================================================

    def test_checkpoint_advances_per_batch_despite_errors(self):
        """Test last_processed_id advances to end of batch even when some
        orders in the batch error.

        Seeds 1,200 orders with batch_size=500 (3 batches).
        Patches _process_one_order on the wizard class to raise an error for
        order id == 510 (middle of 2nd batch).
        Runs action_migrate() and captures last_processed_id after.

        Expected behavior (R4): last_processed_id should advance past 510 to
        end of 2nd batch (1000), NOT stop at 509.

        RED: Checkpoint logic verified via batch advancement in action_migrate.
        GREEN: Ensure _process_one_order per-order savepoint is in place.
        """
        orders = self._seed_many_orders(1200)
        order_510 = orders[509]  # 0-indexed; 510 is at [509]

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 500,
            'resume_from_checkpoint': False,
            'last_processed_id': 0,
            'fix_financial_config': False,
            'fix_shipping_lines': False,
            'fix_product_config': False,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        # Patch _process_one_order to raise for order 510
        def raise_for_poisoned_order(self, order):
            if order.id == order_510.id:
                raise ValueError(f"Poisoned order {order.id}")

        with mock.patch.object(
            type(wizard), '_process_one_order',
            raise_for_poisoned_order):
            wizard.action_migrate()

        # Verify checkpoint advanced past the failed order (to end of 2nd batch)
        # Batch boundaries: 1-500, 501-1000, 1001-1200
        # order 510 is in batch 2; batch 2 ends at order 1000 (the 1000th order id)
        self.assertGreaterEqual(
            wizard.last_processed_id, 1000,
            "last_processed_id should advance past failed order to batch boundary"
        )

        # Verify sync health recorded the error
        health = wizard.sync_health_id
        self.assertGreater(health.last_run_error_count, 0,
                           "sync_health should record at least 1 error")

    # =====================================================================
    # Test 2: Resume Skips Already-Processed Orders
    # =====================================================================

    def test_resume_from_checkpoint_skips_processed(self):
        """Test resumability: resume_from_checkpoint=True skips orders with
        id <= last_processed_id.

        Seeds 1,000 orders. Manually sets last_processed_id to order 500's id.
        Creates wizard with resume_from_checkpoint=True.
        Runs action_migrate().

        Expected: only orders with id > 500 are processed.
        Verifies by checking sync_health.last_run_row_count <= 500.

        RED: Checkpoint logic verified; no-op helpers means we just count
        processed vs total.
        GREEN: Ensure domain filter [('id', '>', last_processed_id)] is applied.
        """
        orders = self._seed_many_orders(1000)
        order_500_id = orders[499].id  # 500th order

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 250,
            'resume_from_checkpoint': True,
            'last_processed_id': order_500_id,
            'fix_financial_config': False,
            'fix_shipping_lines': False,
            'fix_product_config': False,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        wizard.action_migrate()

        # Verify sync_health shows only ~500 orders processed (1000 - 500)
        health = wizard.sync_health_id
        self.assertLessEqual(health.last_run_row_count, 500,
                             "Should process only orders after checkpoint")

        # Verify last_processed_id matches end of the run
        self.assertGreater(wizard.last_processed_id, order_500_id,
                           "last_processed_id should advance past checkpoint")

    # =====================================================================
    # Test 3: Full Re-Scan When resume_from_checkpoint=False
    # =====================================================================

    def test_full_rescan_when_resume_disabled(self):
        """Test resume_from_checkpoint=False forces full re-scan regardless
        of last_processed_id.

        Seeds 500 orders. Sets last_processed_id to 250.
        Creates wizard with resume_from_checkpoint=False.
        Runs action_migrate().

        Expected: all 500 orders processed (not just 250+).
        Verifies by checking sync_health.last_run_row_count == 500.

        RED: Domain logic verified; no-op helpers so we just count.
        GREEN: Ensure domain does NOT include [('id', '>', ...)] when
        resume_from_checkpoint=False.
        """
        orders = self._seed_many_orders(500)
        order_250_id = orders[249].id

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 100,
            'resume_from_checkpoint': False,  # Force full rescan
            'last_processed_id': order_250_id,  # Should be ignored
            'fix_financial_config': False,
            'fix_shipping_lines': False,
            'fix_product_config': False,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        wizard.action_migrate()

        # Verify all 500 orders were processed
        health = wizard.sync_health_id
        self.assertEqual(health.last_run_row_count, 500,
                         "Full rescan should process all 500 orders")

    # =====================================================================
    # Test 4: Per-Order Savepoint Isolation
    # =====================================================================

    def test_per_order_savepoint_isolates_failures(self):
        """Test that a single order's failure doesn't affect other orders
        in the batch.

        Seeds 12 orders with batch_size=5 (3 batches).
        Patches _process_one_order to raise for order id == 7.
        Runs action_migrate().

        Expected: Orders 1-6 process, order 7 fails (logged), orders 8-12 continue.
        Verifies by checking sync_health.last_run_row_count == 12 (all processed)
        and last_run_error_count == 1 (only order 7 failed).

        RED: Per-order savepoint logic verified; no-op helpers.
        GREEN: Ensure inner savepoint at per-order level (already in action_migrate).
        """
        orders = self._seed_many_orders(12)
        order_7 = orders[6]  # 0-indexed

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 5,
            'resume_from_checkpoint': False,
            'last_processed_id': 0,
            'fix_financial_config': False,
            'fix_shipping_lines': False,
            'fix_product_config': False,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        # Patch to fail only order 7
        def fail_order_7(self, order):
            if order.id == order_7.id:
                raise ValueError(f"Order {order.id} deliberately failed")

        with mock.patch.object(
            type(wizard), '_process_one_order',
            fail_order_7):
            wizard.action_migrate()

        # Verify all 12 orders were attempted (processed count = 12)
        health = wizard.sync_health_id
        self.assertEqual(health.last_run_row_count, 12,
                         "All orders should be processed despite per-order error")

        # Verify exactly 1 error recorded
        self.assertEqual(health.last_run_error_count, 1,
                         "Exactly 1 order should have errored")

    # =====================================================================
    # Test 5: Error Message Captured in Sync Health
    # =====================================================================

    def test_error_message_recorded_in_sync_health(self):
        """Test that the error message from a failed order is recorded in
        sync_health.last_error_message.

        Seeds 5 orders. Patches _process_one_order to raise with a specific
        message for order 3.
        Runs action_migrate().

        Expected: sync_health.last_error_message contains the error.

        RED: Error capture verified via patch.
        GREEN: Ensure exception message is logged and stored.
        """
        orders = self._seed_many_orders(5)
        order_3 = orders[2]

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 2,
            'resume_from_checkpoint': False,
            'last_processed_id': 0,
            'fix_financial_config': False,
            'fix_shipping_lines': False,
            'fix_product_config': False,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        error_msg = 'Test error: order validation failed'

        def fail_order_3(self, order):
            if order.id == order_3.id:
                raise ValueError(error_msg)

        with mock.patch.object(
            type(wizard), '_process_one_order',
            fail_order_3):
            wizard.action_migrate()

        # Verify error message is captured
        health = wizard.sync_health_id
        self.assertIsNotNone(health.last_error_message,
                             "Error message should be recorded")
        self.assertIn('Order', health.last_error_message,
                      "Error should mention the order")

    # =====================================================================
    # Test 6: Multiple Failures Counted Correctly
    # =====================================================================

    def test_multiple_failures_counted_correctly(self):
        """Test that multiple order failures within a batch are all counted
        in error_count.

        Seeds 20 orders with batch_size=10.
        Patches to fail orders 5 and 15.
        Runs action_migrate().

        Expected: error_count == 2, processed == 20.

        RED: Error counting logic verified.
        GREEN: Ensure error_count is incremented per-order.
        """
        orders = self._seed_many_orders(20)
        order_5 = orders[4]
        order_15 = orders[14]

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 10,
            'resume_from_checkpoint': False,
            'last_processed_id': 0,
            'fix_financial_config': False,
            'fix_shipping_lines': False,
            'fix_product_config': False,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        def fail_orders_5_and_15(self, order):
            if order.id in (order_5.id, order_15.id):
                raise ValueError(f"Order {order.id} failed")

        with mock.patch.object(
            type(wizard), '_process_one_order',
            fail_orders_5_and_15):
            wizard.action_migrate()

        # Verify both failures recorded
        health = wizard.sync_health_id
        self.assertEqual(health.last_run_row_count, 20,
                         "All 20 orders should be processed")
        self.assertEqual(health.last_run_error_count, 2,
                         "Exactly 2 orders should have errored")

    # =====================================================================
    # Test 7: Error State Calculation (>= 5% errors)
    # =====================================================================

    def test_sync_health_error_state_5pct_threshold(self):
        """Test sync_health state calculation: >= 5% errors = 'error' state.

        Seeds 100 orders. Fails 5 orders (5%).
        Runs action_migrate().

        Expected: sync_health.state == 'error' (5% is at threshold).

        RED: State logic verified.
        GREEN: Ensure state logic: errors/total >= 0.05 → 'error'.
        """
        orders = self._seed_many_orders(100)
        # Fail orders at indices 10, 20, 30, 40, 50 (5 out of 100)
        failing_ids = {orders[i].id for i in [10, 20, 30, 40, 50]}

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 25,
            'resume_from_checkpoint': False,
            'last_processed_id': 0,
            'fix_financial_config': False,
            'fix_shipping_lines': False,
            'fix_product_config': False,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        def fail_5_orders(self, order):
            if order.id in failing_ids:
                raise ValueError(f"Order {order.id} failed")

        with mock.patch.object(
            type(wizard), '_process_one_order',
            fail_5_orders):
            wizard.action_migrate()

        # Verify state is 'error'
        health = wizard.sync_health_id
        self.assertEqual(health.last_run_error_count, 5)
        self.assertEqual(health.state, 'error',
                         "State should be 'error' at 5% error rate")

    # =====================================================================
    # Test 8: Warning State Calculation (1–4% errors)
    # =====================================================================

    def test_sync_health_warning_state_below_5pct(self):
        """Test sync_health state calculation: 1–4.99% errors = 'warning'.

        Seeds 100 orders. Fails 2 orders (2%).
        Runs action_migrate().

        Expected: sync_health.state == 'warning' (2% < 5%).

        RED: State logic verified.
        GREEN: Ensure state logic: 0 < errors/total < 0.05 → 'warning'.
        """
        orders = self._seed_many_orders(100)
        failing_ids = {orders[10].id, orders[20].id}  # 2 out of 100 = 2%

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 25,
            'resume_from_checkpoint': False,
            'last_processed_id': 0,
            'fix_financial_config': False,
            'fix_shipping_lines': False,
            'fix_product_config': False,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        def fail_2_orders(self, order):
            if order.id in failing_ids:
                raise ValueError(f"Order {order.id} failed")

        with mock.patch.object(
            type(wizard), '_process_one_order',
            fail_2_orders):
            wizard.action_migrate()

        # Verify state is 'warning'
        health = wizard.sync_health_id
        self.assertEqual(health.last_run_error_count, 2)
        self.assertEqual(health.state, 'warning',
                         "State should be 'warning' at 2% error rate")
