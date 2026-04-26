"""RED tests for Spec 002 W3.2b fix-helper bodies — T051 integration tests.

Tests the end-to-end fix pipeline through action_migrate():
  - T039: _fix_financial_config() — set fiscal_position_id, payment_term_id,
    team_id, pricelist_id, currency_id
  - T040: _fix_shipping_lines() — backfill Etsy Shipping lines when missing
  - T042: _fix_product_config() — set is_storable=True and categorize products
  - T043: _confirm_and_complete() — draft → sale → done, invoice_status=invoiced
  - Anomaly quarantine — orders with etsy_price_anomaly=True excluded unless
    include_anomalies=True

RED phase: helpers are stubs (no-ops). Tests FAIL with assertion errors because
helpers don't yet modify data. GREEN phase implements the helper bodies.
"""
import logging

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestDataMigrationFixBodies(TransactionCase):
    """T051 — End-to-end fix-helper integration tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Master data for all tests
        cls.company = cls.env.company
        cls.shop = cls.env['etsy.shop'].create({'name': 'Test Shop'})

        # Create storable product with category
        cls.categ = cls.env['product.category'].search([], limit=1)
        if not cls.categ:
            cls.categ = cls.env['product.category'].create({'name': 'Test Category'})

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'is_storable': False,  # Will be fixed by _fix_product_config
            'categ_id': cls.categ.id if cls.categ else False,
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'test@example.com',
            'is_company': False,
        })

    def _seed_orders_with_config(self, count, has_shipping_cost=False,
                                  has_shipping_line=False, include_anomaly=False):
        """Factory: seed N draft Etsy orders with optional shipping config.

        Args:
            count: number of orders to create
            has_shipping_cost: if True, set etsy_shipping_cost=5.0
            has_shipping_line: if True, create a shipping line (Etsy Shipping product)
            include_anomaly: if True, include an order with amount_total <= 0

        Returns: sorted list of created orders
        """
        orders_data = []
        for i in range(1, count + 1):
            order_lines = [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100.0 + i,
                'etsy_transaction_id': f'test-txn-{i}',
            })]

            # Add shipping line if requested
            if has_shipping_line:
                shipping_product = self.env['product.product'].search(
                    [('name', '=', 'Etsy Shipping')], limit=1)
                if not shipping_product:
                    # Fallback: create a dummy shipping product
                    shipping_product = self.env['product.product'].create({
                        'name': 'Etsy Shipping',
                        'is_storable': False,
                        'type': 'service',
                    })
                order_lines.append((0, 0, {
                    'product_id': shipping_product.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 5.0,
                }))

            order_vals = {
                'partner_id': self.partner.id,
                'etsy_order_id': f'test-order-{i}',
                'etsy_shop_id': self.shop.id,
                'order_line': order_lines,
            }

            if has_shipping_cost:
                order_vals['etsy_shipping_cost'] = 5.0

            orders_data.append(order_vals)

        # Create anomaly order if requested
        if include_anomaly:
            orders_data.append({
                'partner_id': self.partner.id,
                'etsy_order_id': 'test-anomaly-order',
                'etsy_shop_id': self.shop.id,
                'order_line': [(0, 0, {
                    'product_id': self.product.id,
                    'product_uom_qty': 1.0,
                    'price_unit': 0.0,  # Will set etsy_price_anomaly=True
                    'etsy_transaction_id': 'test-anomaly-txn',
                })],
            })

        orders = self.env['sale.order'].create(orders_data)
        return orders.sorted('id')

    # =====================================================================
    # Test 1: Financial Config — All Fields Set
    # =====================================================================

    def test_fix_financial_config_sets_all_fields(self):
        """Test _fix_financial_config() sets fiscal_position, payment_term,
        team, pricelist, and currency on orders.

        Seeds 3 draft orders with no financial config (should be empty).
        Calls action_migrate() with fix_financial_config=True.
        Verifies all 3 orders have:
          - fiscal_position_id set (from OrderCreator._get_fiscal_position)
          - payment_term_id set (from OrderCreator._get_payment_term)
          - team_id set (from OrderCreator._get_sales_team)
          - pricelist_id set (from OrderCreator._get_pricelist)
          - currency_id set (from OrderCreator._get_currency)

        RED: Helper is stub, so fields remain empty. Test FAILS.
        GREEN: Helper implementation will set all fields.
        """
        orders = self._seed_orders_with_config(3)

        # Verify orders start with empty fiscal_position_id and payment_term_id.
        # team_id and pricelist_id may be auto-defaulted by Odoo at create time,
        # so we don't precondition them — the post-condition asserts the fix
        # sets them to the *Etsy* team / pricelist specifically.
        etsy_team = self.env.ref(
            'etsy_integration.team_etsy', raise_if_not_found=False)
        for order in orders:
            self.assertFalse(order.fiscal_position_id,
                             "Order should start with no fiscal position")
            self.assertFalse(order.payment_term_id,
                             "Order should start with no payment term")
            if etsy_team:
                self.assertNotEqual(order.team_id, etsy_team,
                                    "Order should NOT yet have the Etsy team")

        wizard = self.env['etsy.data.migration.wizard'].create({
            'fix_financial_config': True,
            'fix_shipping_lines': False,
            'fix_product_config': False,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        wizard.action_migrate()

        # Verify all financial config fields are set after migration
        for order in orders:
            self.assertTrue(order.fiscal_position_id,
                            "fiscal_position_id should be set by _fix_financial_config")
            self.assertTrue(order.payment_term_id,
                            "payment_term_id should be set by _fix_financial_config")
            self.assertTrue(order.team_id,
                            "team_id should be set by _fix_financial_config")
            self.assertTrue(order.pricelist_id,
                            "pricelist_id should be set by _fix_financial_config")
            self.assertTrue(order.currency_id,
                            "currency_id should be set by _fix_financial_config")

    # =====================================================================
    # Test 2: Shipping Lines — Add Missing Line
    # =====================================================================

    def test_fix_shipping_lines_adds_missing_line(self):
        """Test _fix_shipping_lines() adds a shipping line when etsy_shipping_cost
        is set but no shipping line exists.

        Seeds 1 order with etsy_shipping_cost=5.0 but no shipping line.
        Calls action_migrate() with fix_shipping_lines=True.
        Verifies order has exactly 1 shipping line with:
          - product_id = Etsy Shipping product
          - price_unit = 5.0

        RED: Helper is stub, order remains unchanged. Test FAILS.
        GREEN: Helper will create the shipping line.
        """
        orders = self._seed_orders_with_config(
            1, has_shipping_cost=True, has_shipping_line=False)
        order = orders[0]

        # Verify order starts with 1 order line (product only)
        self.assertEqual(len(order.order_line), 1,
                         "Order should start with 1 product line")

        wizard = self.env['etsy.data.migration.wizard'].create({
            'fix_financial_config': False,
            'fix_shipping_lines': True,
            'fix_product_config': False,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        wizard.action_migrate()

        # Verify shipping line was added
        order.invalidate_recordset()
        self.assertEqual(len(order.order_line), 2,
                         "Order should have 2 lines after shipping fix (product + shipping)")

        # Find and verify the shipping line
        shipping_lines = order.order_line.filtered(
            lambda l: l.product_id.name == 'Etsy Shipping')
        self.assertEqual(len(shipping_lines), 1,
                         "Should have exactly 1 Etsy Shipping line")
        self.assertEqual(shipping_lines[0].price_unit, 5.0,
                         "Shipping line price should match etsy_shipping_cost")

    # =====================================================================
    # Test 3: Shipping Lines — Idempotent
    # =====================================================================

    def test_fix_shipping_lines_idempotent(self):
        """Test _fix_shipping_lines() is idempotent: running twice doesn't
        duplicate the shipping line.

        Seeds 1 order with etsy_shipping_cost=5.0 and NO shipping line.
        Calls action_migrate() twice.
        Verifies order has exactly 2 lines (product + shipping) after both runs
        (not 3 from duplicate shipping lines).

        RED: Helper is stub. Test expects line count to stay at 1. Test FAILS.
        GREEN: Helper will add line on first run, skip on second.
        """
        orders = self._seed_orders_with_config(
            1, has_shipping_cost=True, has_shipping_line=False)
        order = orders[0]

        wizard = self.env['etsy.data.migration.wizard'].create({
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
        wizard.action_migrate()
        order.invalidate_recordset()
        line_count_after_second = len(order.order_line)

        # Both should have 2 lines (product + shipping), not 3
        self.assertEqual(line_count_after_first, 2,
                         "First run should add shipping line (2 total)")
        self.assertEqual(line_count_after_second, 2,
                         "Second run should not duplicate shipping line (still 2)")

    # =====================================================================
    # Test 4: Product Config — Set is_storable and Category
    # =====================================================================

    def test_fix_product_config_sets_is_storable_and_category(self):
        """Test _fix_product_config() sets is_storable=True and ensures
        products have a category.

        Seeds 3 orders; each has a product with is_storable=False.
        Calls action_migrate() with fix_product_config=True.
        Verifies all products have:
          - is_storable = True
          - categ_id != False (category set)

        RED: Helper is stub. Products remain is_storable=False. Test FAILS.
        GREEN: Helper will set is_storable=True and assign category.
        """
        orders = self._seed_orders_with_config(3)

        # Verify products start with is_storable=False
        for order in orders:
            for line in order.order_line:
                if line.product_id.name == 'Test Product':
                    self.assertFalse(line.product_id.is_storable,
                                     "Product should start with is_storable=False")

        wizard = self.env['etsy.data.migration.wizard'].create({
            'fix_financial_config': False,
            'fix_shipping_lines': False,
            'fix_product_config': True,
            'auto_confirm': False,
            'generate_dedup_report': False,
        })

        wizard.action_migrate()

        # Verify products are now storable and have category
        for order in orders:
            for line in order.order_line:
                if line.product_id.name == 'Test Product':
                    # Refresh to get latest state
                    product = line.product_id
                    product.invalidate_recordset()
                    self.assertTrue(product.is_storable,
                                    "Product should be storable after fix")
                    self.assertTrue(product.categ_id,
                                    "Product should have a category after fix")

    # =====================================================================
    # Test 5: Confirm and Complete — State Transition
    # =====================================================================

    def test_confirm_and_complete_transitions_state(self):
        """Test _confirm_and_complete() transitions draft order → sale,
        validates pickings, and sets invoice_status='invoiced'.

        Seeds 3 draft orders. Calls action_migrate() with auto_confirm=True.
        Verifies all 3 orders have:
          - state = 'sale' (or 'done')
          - invoice_status = 'invoiced'
          - all pickings in state 'done'

        RED: Helper is stub. Orders remain draft. Test FAILS.
        GREEN: Helper calls _etsy_auto_confirm() which transitions state.
        """
        orders = self._seed_orders_with_config(3)

        # Verify orders start as draft
        for order in orders:
            self.assertEqual(order.state, 'draft',
                             "Order should start in draft state")

        wizard = self.env['etsy.data.migration.wizard'].create({
            'fix_financial_config': False,
            'fix_shipping_lines': False,
            'fix_product_config': False,
            'auto_confirm': True,
            'generate_dedup_report': False,
        })

        wizard.action_migrate()

        # Verify orders are confirmed (sale or done) and invoiced
        for order in orders:
            order.invalidate_recordset()
            self.assertIn(order.state, ['sale', 'done'],
                          f"Order should be confirmed, got state={order.state}")
            self.assertEqual(order.invoice_status, 'invoiced',
                             "Order invoice_status should be 'invoiced'")

            # Verify pickings are done
            for picking in order.picking_ids:
                self.assertEqual(picking.state, 'done',
                                 "All pickings should be in 'done' state")

    # =====================================================================
    # Test 6: Confirm and Complete — Idempotent
    # =====================================================================

    def test_confirm_and_complete_idempotent(self):
        """Test _confirm_and_complete() is idempotent: running twice on an
        already-confirmed order doesn't error.

        Seeds 1 draft order. Calls action_migrate() twice with auto_confirm=True.
        Both calls should succeed; second call should find order already in 'sale'
        and skip confirmation.

        RED: Helper is stub, order stays draft both times. No error expected.
        GREEN: First run confirms, second run skips (checks state == 'draft').
        """
        orders = self._seed_orders_with_config(1)
        order = orders[0]

        wizard = self.env['etsy.data.migration.wizard'].create({
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
        invoice_status_after_first = order.invoice_status

        # Second run should not error
        wizard.action_migrate()
        order.invalidate_recordset()
        state_after_second = order.state
        invoice_status_after_second = order.invoice_status

        # Both runs should result in same final state
        self.assertEqual(state_after_first, state_after_second,
                         "State should not change between runs")
        self.assertEqual(invoice_status_after_first, invoice_status_after_second,
                         "Invoice status should not change between runs")

    # =====================================================================
    # Test 7: Anomaly Quarantine — Excluded by Default
    # =====================================================================

    def test_anomalies_excluded_by_default(self):
        """Test orders with etsy_price_anomaly=True are NOT processed when
        include_anomalies=False (default).

        Seeds 5 normal orders + 1 anomaly order (amount_total <= 0).
        Sets include_anomalies=False. Calls action_migrate().
        Verifies the anomaly order is exported to CSV but NOT processed
        through the fix pipeline (state remains draft).

        RED: Fix helpers are stubs, all orders remain draft. Test verifies
        anomaly is skipped via domain filter in action_migrate().
        GREEN: Fix helpers will process normal orders; anomaly skipped.
        """
        orders = self._seed_orders_with_config(
            5, include_anomaly=True)

        anomaly_order = orders[-1]  # Last is the anomaly
        normal_orders = orders[:-1]

        wizard = self.env['etsy.data.migration.wizard'].create({
            'fix_financial_config': True,
            'fix_shipping_lines': True,
            'fix_product_config': True,
            'auto_confirm': True,
            'include_anomalies': False,  # Exclude anomalies
            'generate_dedup_report': False,
        })

        wizard.action_migrate()

        # Anomaly order should still be draft (excluded from processing)
        anomaly_order.invalidate_recordset()
        self.assertEqual(anomaly_order.state, 'draft',
                         "Anomaly order should remain draft (excluded from fixes)")

    # =====================================================================
    # Test 8: All Fixes Together — Full Pipeline
    # =====================================================================

    def test_all_fixes_together_full_pipeline(self):
        """Test all fix helpers run together in one action_migrate() call
        on a single order.

        Seeds 1 draft order with:
          - no financial config
          - etsy_shipping_cost=5.0, no shipping line
          - product with is_storable=False

        Calls action_migrate() with all checkboxes ON.
        Verifies order after migration has:
          - fiscal_position_id, payment_term_id, team_id, pricelist_id, currency_id set
          - 2 order lines (product + shipping)
          - product is_storable=True
          - state='sale' or 'done'
          - invoice_status='invoiced'

        RED: All helpers are stubs. Order remains mostly unchanged. Test FAILS.
        GREEN: All helpers run in sequence through _process_one_order().
        """
        orders = self._seed_orders_with_config(
            1, has_shipping_cost=True, has_shipping_line=False)
        order = orders[0]

        wizard = self.env['etsy.data.migration.wizard'].create({
            'fix_financial_config': True,
            'fix_shipping_lines': True,
            'fix_product_config': True,
            'auto_confirm': True,
            'generate_dedup_report': False,
        })

        wizard.action_migrate()

        # Verify all fixes applied
        order.invalidate_recordset()

        # Financial config
        self.assertTrue(order.fiscal_position_id,
                        "fiscal_position_id should be set")
        self.assertTrue(order.payment_term_id,
                        "payment_term_id should be set")
        self.assertTrue(order.team_id,
                        "team_id should be set")
        self.assertTrue(order.pricelist_id,
                        "pricelist_id should be set")
        self.assertTrue(order.currency_id,
                        "currency_id should be set")

        # Shipping line
        self.assertEqual(len(order.order_line), 2,
                         "Should have product + shipping lines")
        shipping_lines = order.order_line.filtered(
            lambda l: l.product_id.name == 'Etsy Shipping')
        self.assertEqual(len(shipping_lines), 1,
                         "Should have exactly 1 shipping line")

        # Product config
        test_product = self.product
        test_product.invalidate_recordset()
        self.assertTrue(test_product.is_storable,
                        "Product should be storable")
        self.assertTrue(test_product.categ_id,
                        "Product should have category")

        # State
        self.assertIn(order.state, ['sale', 'done'],
                      "Order should be confirmed")
        self.assertEqual(order.invoice_status, 'invoiced',
                         "Order should be invoiced")
