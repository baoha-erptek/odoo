"""Phase 2 (ORM Unit Tests) for P1-DASH-MERGE Operations Dashboard.

Tests the unified Operations Dashboard ORM behavior:
- Saved filters apply correct domains and return expected rows
- Bulk Mark Shipped action works on the merged sale.order list
- RPC access gates (FR-017) prevent unauthorized callers
- Related fields from sale.order.fulfillment are readable on sale.order
"""

import logging

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestOperationsDashboardMergeORM(TransactionCase):
    """Phase 2: ORM tests for unified Operations Dashboard behavior."""

    @classmethod
    def setUpClass(cls):
        """Set up test data: partners, products, orders, fulfillments."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create test partner
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'test@example.com',
            'is_company': False,
        })

        # Create test product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'is_storable': True,
            'list_price': 100.0,
        })

        # Create test carrier
        cls.carrier = cls.env.ref('multichannel_hub_core.shipping_carrier_usps')

        # P1-LBL — label_status seed references for fixture writes
        cls.label_vn_fulfilled = cls.env.ref(
            'multichannel_hub_core.label_status_vn_fulfilled')

        # Create test users with appropriate groups
        # Marketing User group
        cls.marketing_user = cls.env['res.users'].create({
            'name': 'Marketing User',
            'login': 'marketing@example.com',
            'group_ids': [(6, 0, [cls.env.ref('multichannel_hub_core.group_marketing_user').id])],
        })

        # BA Lead group
        cls.ba_lead_user = cls.env['res.users'].create({
            'name': 'BA Lead',
            'login': 'ba@example.com',
            'group_ids': [(6, 0, [cls.env.ref('multichannel_hub_core.group_ba_lead').id])],
        })

        # Production Team group
        cls.prod_user = cls.env['res.users'].create({
            'name': 'Production User',
            'login': 'prod@example.com',
            'group_ids': [(6, 0, [cls.env.ref('multichannel_hub_core.group_production_team').id])],
        })

        # Salesman (no special group)
        cls.salesman = cls.env['res.users'].create({
            'name': 'Salesman',
            'login': 'salesman@example.com',
            'group_ids': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman').id])],
        })

    def _create_order_with_fulfillment(self, **order_kwargs):
        """Factory: create sale.order, populate its auto-created fulfillment.

        sale.order has `_inherits = {'sale.order.fulfillment': 'fulfillment_id'}`
        (P1-05 D-23) so a fulfillment row is auto-created on every order
        create. We write test values onto THAT row — not a separate one
        — because the dashboard view, saved filters, and the bulk
        Mark-Shipped wrapper all read fulfillment data through
        `order.fulfillment_id`.

        action_confirm() runs unless caller passes state='draft' (some
        filter tests need orders to remain in draft).
        """
        defaults = {
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        }
        defaults.update(order_kwargs)

        order = self.env['sale.order'].create(defaults)
        order.fulfillment_id.write({
            'tracking_number': f'TRK{order.id:010d}',
            'shipping_carrier_id': self.carrier.id,
            'label_status_id': self.label_vn_fulfilled.id,
            'tracking_state': 'label_ready',
            'warehouse_zone': 'vn',
            'production_blocked': False,
        })

        if order_kwargs.get('state') != 'draft':
            order.action_confirm()

        return order, order.fulfillment_id

    def test_filter_marketing_user_domain_returns_draft_orders(self):
        """Test filter_operations_marketing_user domain returns draft orders only."""
        # Create one draft and one confirmed order
        draft_order, _ = self._create_order_with_fulfillment(state='draft')
        confirmed_order, _ = self._create_order_with_fulfillment()

        # Get the marketing filter
        filter_rec = self.env.ref('multichannel_hub_core.filter_operations_marketing_user')
        domain = safe_eval(filter_rec.domain)

        # Apply domain to sale.order
        results = self.env['sale.order'].search(domain)

        # Marketing filter should include draft orders
        self.assertIn(
            draft_order.id,
            results.ids,
            "Marketing user filter should include draft orders"
        )

        # Draft orders should be in the results
        draft_count = len([o for o in results if o.state == 'draft'])
        self.assertGreater(
            draft_count, 0,
            "Marketing filter should return at least one draft order"
        )

    def test_filter_ba_lead_domain_returns_open_orders(self):
        """Test filter_operations_ba_lead domain returns draft and confirmed orders."""
        # Create draft, confirmed, and cancelled orders
        draft_order, _ = self._create_order_with_fulfillment(state='draft')
        confirmed_order, _ = self._create_order_with_fulfillment()
        cancelled_order, _ = self._create_order_with_fulfillment()
        cancelled_order.action_cancel()

        # Get the BA Lead filter
        filter_rec = self.env.ref('multichannel_hub_core.filter_operations_ba_lead')
        domain = safe_eval(filter_rec.domain)

        # Apply domain to sale.order
        results = self.env['sale.order'].search(domain)

        # BA Lead filter should include draft and confirmed, not cancelled
        states = [o.state for o in results if o.id in [draft_order.id, confirmed_order.id, cancelled_order.id]]

        # Should have both draft and confirmed
        self.assertIn(
            'draft', states,
            "BA Lead filter should include draft orders"
        )
        self.assertIn(
            'sale', states,
            "BA Lead filter should include confirmed (state='sale') orders"
        )

        # Should NOT have cancelled
        for result in results:
            if result.id == cancelled_order.id:
                self.fail("BA Lead filter should exclude cancelled orders")

    def test_filter_production_team_domain_returns_unblocked_with_label(self):
        """Test filter_operations_production_team returns unblocked orders with label."""
        # Create orders with various states
        # 1. Unblocked with label (should match)
        unblocked_order, unblocked_fulfillment = self._create_order_with_fulfillment(
            sales_channel='etsy'
        )
        unblocked_fulfillment.write({
            'production_blocked': False,
            'label_status_id': self.label_vn_fulfilled.id,
        })

        # 2. Blocked (should NOT match)
        blocked_order, blocked_fulfillment = self._create_order_with_fulfillment(
            sales_channel='etsy'
        )
        blocked_fulfillment.write({
            'production_blocked': True,
            'block_reason': 'Address issue',
            'label_status_id': self.label_vn_fulfilled.id,
        })

        # 3. Unblocked without label (should NOT match — label_status_id IS False)
        no_label_order, no_label_fulfillment = self._create_order_with_fulfillment(
            sales_channel='etsy'
        )
        no_label_fulfillment.write({
            'production_blocked': False,
            'label_status_id': False,
        })

        # Get the Production Team filter
        filter_rec = self.env.ref('multichannel_hub_core.filter_operations_production_team')
        domain = safe_eval(filter_rec.domain)

        # Apply domain to sale.order
        results = self.env['sale.order'].search(domain)
        result_ids = results.ids

        # Verify correct order is included
        self.assertIn(
            unblocked_order.id, result_ids,
            "Production filter should include unblocked orders with label"
        )

        # Verify blocked order is excluded
        self.assertNotIn(
            blocked_order.id, result_ids,
            "Production filter should exclude blocked orders"
        )

        # Verify no-label order is excluded
        self.assertNotIn(
            no_label_order.id, result_ids,
            "Production filter should exclude orders without label"
        )

    def test_bulk_mark_shipped_on_merged_list_marks_all(self):
        """Test bulk_mark_shipped on merged sale.order list marks all unblocked orders."""
        # Create 3 orders with fulfillments
        order1, fulfillment1 = self._create_order_with_fulfillment(sales_channel='etsy')
        order2, fulfillment2 = self._create_order_with_fulfillment(sales_channel='amazon')
        order3, fulfillment3 = self._create_order_with_fulfillment(sales_channel='website')

        # Verify initial state
        self.assertNotEqual(
            fulfillment1.tracking_state, 'shipped',
            "Initial tracking_state should not be shipped"
        )

        # Create a recordset of orders and call action via the unified interface
        orders = order1 | order2 | order3

        # Call bulk mark shipped as production user
        result = orders.with_user(self.prod_user).action_bulk_mark_shipped()

        # Verify all are marked shipped
        fulfillment1.invalidate_recordset()
        fulfillment2.invalidate_recordset()
        fulfillment3.invalidate_recordset()

        self.assertEqual(
            fulfillment1.tracking_state, 'shipped',
            "All orders should be marked shipped"
        )
        self.assertEqual(
            fulfillment2.tracking_state, 'shipped',
            "All orders should be marked shipped"
        )
        self.assertEqual(
            fulfillment3.tracking_state, 'shipped',
            "All orders should be marked shipped"
        )

    def test_bulk_mark_shipped_rpc_blocked_for_non_production_team(self):
        """Test bulk_mark_shipped RPC is blocked for non-production-team users (FR-017)."""
        order, fulfillment = self._create_order_with_fulfillment()

        # Verify initial state
        self.assertNotEqual(fulfillment.tracking_state, 'shipped')

        # Attempt to call as salesman (no production_team group)
        with self.assertRaises(AccessError):
            order.with_user(self.salesman).action_bulk_mark_shipped()

        # Verify fulfillment was NOT modified
        fulfillment.invalidate_recordset()
        self.assertNotEqual(
            fulfillment.tracking_state, 'shipped',
            "Non-production-team user should be blocked from marking shipped"
        )

    def test_bulk_mark_shipped_allowed_for_production_team_user(self):
        """Test bulk_mark_shipped RPC is allowed for production_team group members."""
        order, fulfillment = self._create_order_with_fulfillment()

        # Verify initial state
        self.assertNotEqual(fulfillment.tracking_state, 'shipped')

        # Call as production user (should succeed)
        result = order.with_user(self.prod_user).action_bulk_mark_shipped()

        # Verify fulfillment was marked shipped
        fulfillment.invalidate_recordset()
        self.assertEqual(
            fulfillment.tracking_state, 'shipped',
            "Production user should be able to mark shipped"
        )

    def test_related_tracking_state_readable_via_sale_order_record(self):
        """Test tracking_state is readable via sale.order due to _inherits delegation."""
        order, fulfillment = self._create_order_with_fulfillment()

        # Test that tracking_state can be read from the order (via _inherits)
        # Odoo 19 with _inherits allows accessing fulfillment fields on the order
        order_tracking_state = order.tracking_state
        fulfillment_tracking_state = fulfillment.tracking_state

        self.assertEqual(
            order_tracking_state,
            fulfillment_tracking_state,
            "tracking_state should be readable from sale.order via _inherits"
        )

        self.assertEqual(
            order_tracking_state, 'label_ready',
            "Initial tracking_state should be 'label_ready'"
        )

    def test_related_label_status_id_readable_via_sale_order_record(self):
        """Test label_status_id is readable via sale.order due to _inherits delegation (P1-LBL)."""
        order, fulfillment = self._create_order_with_fulfillment()

        # Test that label_status_id can be read from the order (via _inherits)
        order_label = order.label_status_id
        fulfillment_label = fulfillment.label_status_id

        self.assertEqual(
            order_label.id,
            fulfillment_label.id,
            "label_status_id should be readable from sale.order via _inherits"
        )
        self.assertEqual(
            order_label.code, 'vn_fulfilled',
            "M2O traversal to comodel.code works via _inherits"
        )

    def test_related_warehouse_zone_readable_via_sale_order_record(self):
        """Test warehouse_zone is readable via sale.order due to _inherits delegation."""
        order, fulfillment = self._create_order_with_fulfillment()

        # Test that warehouse_zone can be read from the order (via _inherits)
        order_warehouse = order.warehouse_zone
        fulfillment_warehouse = fulfillment.warehouse_zone

        self.assertEqual(
            order_warehouse,
            fulfillment_warehouse,
            "warehouse_zone should be readable from sale.order via _inherits"
        )
        self.assertEqual(
            order_warehouse, 'vn',
            "warehouse_zone should be 'vn' as set in fixture"
        )

    def test_related_shipping_date_readable_via_sale_order_record(self):
        """Test shipping_date is readable via sale.order due to _inherits delegation."""
        order, fulfillment = self._create_order_with_fulfillment()

        # Test that shipping_date can be read from the order (via _inherits)
        # Initial state: should be NULL or falsy
        self.assertFalse(
            order.shipping_date,
            "Initial shipping_date should be empty"
        )

        # Mark shipped (which should populate shipping_date)
        fulfillment.write({'tracking_state': 'shipped', 'shipping_date': '2026-05-03'})

        order.invalidate_recordset()
        self.assertEqual(
            order.shipping_date, fulfillment.shipping_date,
            "shipping_date should be readable from sale.order via _inherits"
        )

    def test_related_order_pipeline_fields_readable_via_sale_order(self):
        """Test order_priority is readable via sale.order (related to order_id on fulfillment)."""
        order, fulfillment = self._create_order_with_fulfillment()

        # Set a priority on the fulfillment's related order_id
        fulfillment.order_id.write({'order_priority': 'push'})

        order.invalidate_recordset()

        # Should be readable via the order
        self.assertEqual(
            order.order_priority, 'push',
            "order_priority should be readable via order due to delegation"
        )
