"""RED tests for Spec 002 W3.2b idempotency — T053 (SC-009).

Tests that running action_migrate() twice on the same data produces
identical results (no duplicate data, no state churn, no field flip-flops).

RED phase: Helpers are stubs (no-ops), so both runs produce identical
(unchanged) state. Tests verify the infrastructure doesn't introduce
side effects.

GREEN phase: Helpers make changes. Tests verify changes are stable
after second run (no shipping line duplication, no state regression).
"""
import logging

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestDataMigrationIdempotency(TransactionCase):
    """T053 — Idempotency tests (SC-009)."""

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

    def _seed_orders(self, count):
        """Factory: create N draft Etsy orders for idempotency testing."""
        orders_data = []
        for i in range(1, count + 1):
            orders_data.append({
                'partner_id': self.partner.id,
                'etsy_order_id': f'idempotent-order-{i}',
                'etsy_shop_id': self.shop.id,
                'etsy_shipping_cost': 5.0,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 100.0 + i,
                    'etsy_transaction_id': f'idempotent-txn-{i}',
                })],
            })
        orders = self.env['sale.order'].create(orders_data)
        return orders.sorted('id')

    def _snapshot_order_state(self, order):
        """Take a snapshot of order state for comparison.

        Returns dict with:
          - state, invoice_status, fiscal_position_id, payment_term_id, team_id
          - pricelist_id, currency_id
          - order_line_count, shipping_line_count
          - product_is_storable (for each product line)
        """
        return {
            'state': order.state,
            'invoice_status': order.invoice_status,
            'fiscal_position_id': order.fiscal_position_id.id if order.fiscal_position_id else False,
            'payment_term_id': order.payment_term_id.id if order.payment_term_id else False,
            'team_id': order.team_id.id if order.team_id else False,
            'pricelist_id': order.pricelist_id.id if order.pricelist_id else False,
            'currency_id': order.currency_id.id if order.currency_id else False,
            'order_line_count': len(order.order_line),
            'shipping_line_count': len(order.order_line.filtered(
                lambda l: l.product_id.name == 'Etsy Shipping')),
            'product_configs': [
                {
                    'product_id': line.product_id.id,
                    'product_name': line.product_id.name,
                    'is_storable': line.product_id.is_storable,
                    'categ_id': line.product_id.categ_id.id if line.product_id.categ_id else False,
                }
                for line in order.order_line if line.product_id.name == 'Test Product'
            ],
            'picking_ids': [p.id for p in order.picking_ids],
            'picking_states': {p.id: p.state for p in order.picking_ids},
        }

    def _assert_snapshots_equal(self, snapshot1, snapshot2, run_num):
        """Compare two order snapshots; fail if they differ."""
        self.assertEqual(
            snapshot1['state'], snapshot2['state'],
            f"Order state changed between run 1 and run {run_num}"
        )
        self.assertEqual(
            snapshot1['invoice_status'], snapshot2['invoice_status'],
            f"Invoice status changed between run 1 and run {run_num}"
        )
        self.assertEqual(
            snapshot1['fiscal_position_id'], snapshot2['fiscal_position_id'],
            f"Fiscal position changed between runs"
        )
        self.assertEqual(
            snapshot1['payment_term_id'], snapshot2['payment_term_id'],
            f"Payment term changed between runs"
        )
        self.assertEqual(
            snapshot1['team_id'], snapshot2['team_id'],
            f"Team changed between runs"
        )
        self.assertEqual(
            snapshot1['pricelist_id'], snapshot2['pricelist_id'],
            f"Pricelist changed between runs"
        )
        self.assertEqual(
            snapshot1['currency_id'], snapshot2['currency_id'],
            f"Currency changed between runs"
        )
        self.assertEqual(
            snapshot1['order_line_count'], snapshot2['order_line_count'],
            f"Order line count changed between run 1 and run {run_num} "
            f"(no duplicate lines allowed)"
        )
        self.assertEqual(
            snapshot1['shipping_line_count'], snapshot2['shipping_line_count'],
            f"Shipping line count changed between runs "
            f"(indicates duplicate shipping lines)"
        )
        self.assertEqual(
            snapshot1['product_configs'], snapshot2['product_configs'],
            f"Product is_storable or categ_id flip-flopped between runs"
        )
        self.assertEqual(
            snapshot1['picking_states'], snapshot2['picking_states'],
            f"Picking states regressed between runs"
        )

    # =====================================================================
    # Test 1: Double Run Produces Identical State
    # =====================================================================

    def test_double_run_identical_state(self):
        """Test running action_migrate() twice produces identical order state.

        Seeds 10 orders. Takes snapshot after first run. Takes snapshot after
        second run. Verifies all snapshots match (no duplicate lines, no state
        changes, no field churn).

        RED: Helpers are stubs (no-ops), so both runs leave data unchanged.
        Snapshots should be identical before and after.
        GREEN: Helpers apply fixes idempotently; snapshots match after both runs.
        """
        orders = self._seed_orders(10)

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 5,
            'resume_from_checkpoint': False,
            'last_processed_id': 0,
            'fix_financial_config': True,
            'fix_shipping_lines': True,
            'fix_product_config': True,
            'auto_confirm': True,
            'generate_dedup_report': False,
        })

        # First run
        wizard.action_migrate()
        orders.invalidate_recordset()
        snapshots_after_run_1 = {o.id: self._snapshot_order_state(o) for o in orders}

        # Second run (resuming from first run's checkpoint)
        wizard.write({'resume_from_checkpoint': True})
        wizard.action_migrate()
        orders.invalidate_recordset()
        snapshots_after_run_2 = {o.id: self._snapshot_order_state(o) for o in orders}

        # Compare snapshots
        for order in orders:
            self._assert_snapshots_equal(
                snapshots_after_run_1[order.id],
                snapshots_after_run_2[order.id],
                run_num=2
            )

    # =====================================================================
    # Test 2: No Duplicate Shipping Lines
    # =====================================================================

    def test_no_duplicate_shipping_lines(self):
        """Test that running migrate twice doesn't create duplicate shipping
        lines on the same order.

        Seeds 1 order with etsy_shipping_cost=5.0, no shipping line.
        First run: adds shipping line (total 2 lines: product + shipping).
        Second run: checks line count still 2 (not 3 from duplicate).

        RED: Shipping line fix is stub, so no line added. Count stays 1.
        GREEN: First run adds line (count=2), second run skips (count=2).
        """
        orders = self._seed_orders(1)
        order = orders[0]

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 10,
            'resume_from_checkpoint': False,
            'last_processed_id': 0,
            'fix_financial_config': False,
            'fix_shipping_lines': True,
            'fix_product_config': False,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        # First run
        wizard.action_migrate()
        order.invalidate_recordset()
        line_count_after_first = len(order.order_line)

        # Second run
        wizard.write({'resume_from_checkpoint': True})
        wizard.action_migrate()
        order.invalidate_recordset()
        line_count_after_second = len(order.order_line)

        # Verify line count is stable
        self.assertEqual(
            line_count_after_first, line_count_after_second,
            "Second run should not create duplicate shipping lines"
        )

    # =====================================================================
    # Test 3: No State Regression (Draft → Sale → Draft)
    # =====================================================================

    def test_no_state_regression(self):
        """Test that running migrate twice doesn't regress order state
        (e.g., from 'sale' back to 'draft').

        Seeds 1 draft order. First run: confirms order (state='sale').
        Second run: verifies state stays 'sale' (not regressed).

        RED: Confirm is stub, so state stays draft both runs. No regression.
        GREEN: First run confirms (state='sale'), second run skips (state='sale').
        """
        orders = self._seed_orders(1)
        order = orders[0]

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 10,
            'resume_from_checkpoint': False,
            'last_processed_id': 0,
            'fix_financial_config': False,
            'fix_shipping_lines': False,
            'fix_product_config': False,
            'auto_confirm': True,
            'generate_dedup_report': False,
        })

        # First run
        wizard.action_migrate()
        order.invalidate_recordset()
        state_after_first = order.state

        # Second run
        wizard.write({'resume_from_checkpoint': True})
        wizard.action_migrate()
        order.invalidate_recordset()
        state_after_second = order.state

        # Verify state doesn't regress
        self.assertEqual(
            state_after_first, state_after_second,
            "Order state should not regress between runs"
        )

    # =====================================================================
    # Test 4: Consistent Sync Health Metrics
    # =====================================================================

    def test_consistent_sync_health_metrics(self):
        """Test that sync_health metrics are consistent across multiple runs
        (row_count, error_count, state).

        Seeds 10 orders. Runs twice. Verifies sync_health shows same metrics
        (or correctly incremental if counting cumulative).

        RED: Stubs mean no change. Metrics should be identical across runs.
        GREEN: Helpers apply fixes. Metrics should reflect stable processing.
        """
        orders = self._seed_orders(10)

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 5,
            'resume_from_checkpoint': False,
            'last_processed_id': 0,
            'fix_financial_config': True,
            'fix_shipping_lines': True,
            'fix_product_config': True,
            'auto_confirm': True,
            'generate_dedup_report': False,
        })

        # First run
        wizard.action_migrate()
        health_1 = wizard.sync_health_id
        row_count_1 = health_1.last_run_row_count
        error_count_1 = health_1.last_run_error_count
        state_1 = health_1.state

        # Second run (resume from checkpoint)
        wizard.write({'resume_from_checkpoint': True})
        wizard.action_migrate()
        health_2 = wizard.sync_health_id
        row_count_2 = health_2.last_run_row_count
        error_count_2 = health_2.last_run_error_count
        state_2 = health_2.state

        # If resume skips processed orders, run 2 should process 0 (all already done)
        # If resume_from_checkpoint resets to False, run 2 processes all 10 again
        # For RED phase (stubs), the comparison is just verifying infrastructure
        self.assertEqual(
            error_count_1, error_count_2,
            "Error count should be consistent across runs"
        )
        self.assertEqual(
            state_1, state_2,
            "Sync health state should be consistent across runs"
        )

    # =====================================================================
    # Test 5: Product Config Stability
    # =====================================================================

    def test_product_config_stability(self):
        """Test that running migrate twice doesn't flip product is_storable
        or category (config shouldn't regress).

        Seeds 3 orders with products having is_storable=False.
        First run: sets is_storable=True (fix_product_config=True).
        Second run: verifies is_storable stays True (not flipped back).

        RED: Config fix is stub, products stay is_storable=False both runs.
        GREEN: First run fixes (is_storable=True), second run stays stable.
        """
        orders = self._seed_orders(3)
        product_id = orders[0].order_line[0].product_id.id

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 2,
            'resume_from_checkpoint': False,
            'last_processed_id': 0,
            'fix_financial_config': False,
            'fix_shipping_lines': False,
            'fix_product_config': True,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        # First run
        wizard.action_migrate()
        product = self.env['product.product'].browse(product_id)
        is_storable_after_first = product.is_storable
        categ_id_after_first = product.categ_id.id if product.categ_id else False

        # Second run
        wizard.write({'resume_from_checkpoint': True})
        wizard.action_migrate()
        product.invalidate_recordset()
        is_storable_after_second = product.is_storable
        categ_id_after_second = product.categ_id.id if product.categ_id else False

        # Verify config doesn't flip
        self.assertEqual(
            is_storable_after_first, is_storable_after_second,
            "Product is_storable should not flip between runs"
        )
        self.assertEqual(
            categ_id_after_first, categ_id_after_second,
            "Product category should not flip between runs"
        )

    # =====================================================================
    # Test 6: Financial Config Stability
    # =====================================================================

    def test_financial_config_stability(self):
        """Test that running migrate twice doesn't change financial config
        (fiscal position, payment term, team, pricelist, currency).

        Seeds 3 orders. First run: sets financial config (fix_financial_config=True).
        Second run: verifies all fields stay the same.

        RED: Config fix is stub, fields remain empty both runs.
        GREEN: First run sets fields, second run keeps them unchanged.
        """
        orders = self._seed_orders(3)

        wizard = self.env['etsy.data.migration.wizard'].create({
            'batch_size': 2,
            'resume_from_checkpoint': False,
            'last_processed_id': 0,
            'fix_financial_config': True,
            'fix_shipping_lines': False,
            'fix_product_config': False,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        # First run
        wizard.action_migrate()
        orders.invalidate_recordset()
        snapshot_1 = {
            o.id: {
                'fiscal_position_id': o.fiscal_position_id.id if o.fiscal_position_id else False,
                'payment_term_id': o.payment_term_id.id if o.payment_term_id else False,
                'team_id': o.team_id.id if o.team_id else False,
                'pricelist_id': o.pricelist_id.id if o.pricelist_id else False,
                'currency_id': o.currency_id.id if o.currency_id else False,
            }
            for o in orders
        }

        # Second run
        wizard.write({'resume_from_checkpoint': True})
        wizard.action_migrate()
        orders.invalidate_recordset()
        snapshot_2 = {
            o.id: {
                'fiscal_position_id': o.fiscal_position_id.id if o.fiscal_position_id else False,
                'payment_term_id': o.payment_term_id.id if o.payment_term_id else False,
                'team_id': o.team_id.id if o.team_id else False,
                'pricelist_id': o.pricelist_id.id if o.pricelist_id else False,
                'currency_id': o.currency_id.id if o.currency_id else False,
            }
            for o in orders
        }

        # Verify config is stable
        for order_id, snap_1 in snapshot_1.items():
            snap_2 = snapshot_2[order_id]
            self.assertEqual(
                snap_1, snap_2,
                f"Order {order_id} financial config should not change between runs"
            )
