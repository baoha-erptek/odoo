"""
Phase 2: ORM Unit Tests for Tracking Dashboard and Bulk Actions.

Tests verify business logic implementation of P1-03:
- action_bulk_mark_shipped excludes pending address-change rows
- Warning notification displayed when rows are excluded
- RPC access gate blocks salesman users
- bus.bus emit on write/create with proper channel and payload
- Search by tracking_number
- warehouse_zone filter

Tests use TransactionCase with mocked bus.bus._sendone for event emission.
"""

import logging
from unittest.mock import patch, ANY

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestTrackingDashboardActions(TransactionCase):
    """Phase 2 ORM: Test tracking dashboard business logic."""

    @classmethod
    def setUpClass(cls):
        """Set up test data: partners, products, orders, fulfillments."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create test partners
        cls.buyer1 = cls.env['res.partner'].create({
            'name': 'Buyer 1',
            'email': 'buyer1@example.com',
            'is_company': False,
            'is_etsy_customer': True,
        })
        cls.buyer2 = cls.env['res.partner'].create({
            'name': 'Buyer 2',
            'email': 'buyer2@example.com',
            'is_company': False,
            'is_etsy_customer': True,
        })

        # Create test products
        cls.product1 = cls.env['product.product'].create({
            'name': 'Test Product 1',
            'is_storable': True,
            'list_price': 100.0,
        })
        cls.product2 = cls.env['product.product'].create({
            'name': 'Test Product 2',
            'is_storable': True,
            'list_price': 150.0,
        })

        # Create test carrier
        cls.carrier = cls.env.ref('multichannel_hub_core.shipping_carrier_usps')

        # Create first sale order with pending address-change
        cls.order1 = cls.env['sale.order'].create({
            'partner_id': cls.buyer1.id,
            'order_line': [(0, 0, {
                'product_id': cls.product1.id,
                'product_uom_qty': 1,
                'price_unit': 100.0,
            })],
        })
        cls.order1.action_confirm()

        # Create second sale order (clean, no pending requests)
        cls.order2 = cls.env['sale.order'].create({
            'partner_id': cls.buyer2.id,
            'order_line': [(0, 0, {
                'product_id': cls.product2.id,
                'product_uom_qty': 1,
                'price_unit': 150.0,
            })],
        })
        cls.order2.action_confirm()

        # Create fulfillments
        # P1-LBL — label_status Selection→M2O. Use seed reference; admin
        # user in setUpClass passes the FR-017 ba_manager gate.
        cls.label_vn_fulfilled = cls.env.ref(
            'multichannel_hub_core.label_status_vn_fulfilled')
        cls.label_cho_duyet = cls.env.ref(
            'multichannel_hub_core.label_status_cho_duyet')
        cls.fulfillment1 = cls.env['sale.order.fulfillment'].create({
            'order_id': cls.order1.id,
            'tracking_number': '9400111899223456789001',
            'shipping_carrier_id': cls.carrier.id,
            'label_status_id': cls.label_vn_fulfilled.id,
            'tracking_state': 'label_ready',
        })
        cls.fulfillment2 = cls.env['sale.order.fulfillment'].create({
            'order_id': cls.order2.id,
            'tracking_number': '9400111899223456789002',
            'shipping_carrier_id': cls.carrier.id,
            'label_status_id': cls.label_vn_fulfilled.id,
            'tracking_state': 'label_ready',
        })

        # Create pending address-change request on order1
        cls.address_request = cls.env['etsy.address.change.request'].create({
            'order_id': cls.order1.id,
            'requested_fields': ['partner_shipping_id'],
            'new_values': {'partner_shipping_id': {'id': cls.buyer1.id}},
            'state': 'requested',
            'reason': 'Customer requested address change',
        })

        # Create test users — Odoo 19 renamed res.users.groups_id -> group_ids.
        cls.salesman = cls.env['res.users'].create({
            'name': 'Test Salesman',
            'login': 'salesman@example.com',
            'group_ids': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman').id])],
        })
        cls.prod_user = cls.env['res.users'].create({
            'name': 'Production User',
            'login': 'prod@example.com',
            'group_ids': [(6, 0, [cls.env.ref('multichannel_hub_core.group_production_team').id])],
        })

    def test_action_bulk_mark_shipped_excludes_pending_address(self):
        """Test T035: action_bulk_mark_shipped excludes rows with pending address-change."""
        # Verify order1 has pending address-change
        self.assertTrue(self.order1.has_pending_address_change)
        # Verify order2 does not
        self.assertFalse(self.order2.has_pending_address_change)

        # Prepare: order2 fulfillment should NOT be shipped yet
        self.assertNotEqual(self.fulfillment2.tracking_state, 'shipped')

        # Action: call bulk mark shipped on both fulfillments
        result = (self.fulfillment1 | self.fulfillment2).action_bulk_mark_shipped()

        # Verify: order1's fulfillment remains unchanged (excluded)
        self.fulfillment1.invalidate_recordset()
        self.assertNotEqual(
            self.fulfillment1.tracking_state,
            'shipped',
            "Fulfillment with pending address-change should be skipped"
        )

        # Verify: order2's fulfillment is marked shipped
        self.fulfillment2.invalidate_recordset()
        self.assertEqual(
            self.fulfillment2.tracking_state,
            'shipped',
            "Fulfillment without pending address-change should be updated"
        )
        self.assertTrue(
            self.fulfillment2.shipping_date,
            "shipping_date should be set when marking shipped"
        )

    def test_action_bulk_mark_shipped_returns_warning_notification_when_excluded(self):
        """Test T035 + T061: action_bulk_mark_shipped returns warning dict when rows excluded."""
        result = (self.fulfillment1 | self.fulfillment2).action_bulk_mark_shipped()

        # Verify: result is a dict (not True)
        self.assertIsInstance(result, dict, "Should return notification dict when rows are excluded")

        # Verify: notification structure
        self.assertEqual(result.get('tag'), 'display_notification')
        self.assertEqual(result.get('type'), 'ir.actions.client')

        # Verify: params
        params = result.get('params', {})
        self.assertEqual(params.get('type'), 'warning')
        self.assertTrue(params.get('sticky'), "Notification should be sticky")

        # Verify: message includes skipped order reference
        message = params.get('message', '')
        self.assertIn(self.order1.name, message, "Message should include skipped order name")

    def test_action_bulk_mark_shipped_returns_true_when_no_excluded(self):
        """Test T035: action_bulk_mark_shipped returns True when no rows excluded."""
        # Action: only call on fulfillment without pending address-change
        result = self.fulfillment2.action_bulk_mark_shipped()

        # Verify: returns True (not notification dict)
        self.assertTrue(result, "Should return True when no rows are excluded")

    def test_action_bulk_mark_shipped_blocks_salesman_user(self):
        """Test T035 RPC gate: salesman user cannot call action_bulk_mark_shipped."""
        # Action: attempt action as salesman
        with self.assertRaises(AccessError):
            self.fulfillment2.with_user(self.salesman).action_bulk_mark_shipped()

    def test_action_bulk_mark_shipped_allows_production_team_user(self):
        """Test T035 RPC gate: production_team user can call action_bulk_mark_shipped."""
        # Verify: fulfillment2 is not yet shipped
        self.assertNotEqual(self.fulfillment2.tracking_state, 'shipped')

        # Action: call as production user
        result = self.fulfillment2.with_user(self.prod_user).action_bulk_mark_shipped()

        # Verify: action succeeds and fulfillment is marked shipped
        self.fulfillment2.invalidate_recordset()
        self.assertEqual(self.fulfillment2.tracking_state, 'shipped')

    def test_search_by_tracking_number_returns_match(self):
        """Test: search by tracking_number finds the correct record."""
        tracking = '9400111899223456789001'
        results = self.env['sale.order.fulfillment'].search([
            ('tracking_number', '=', tracking)
        ])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.fulfillment1)

    def test_search_by_tracking_number_case_insensitive(self):
        """Test: tracking_number search is case-insensitive."""
        tracking_upper = self.fulfillment1.tracking_number.upper()
        results = self.env['sale.order.fulfillment'].search([
            ('tracking_number', 'ilike', tracking_upper)
        ])

        self.assertIn(self.fulfillment1, results)

    def test_warehouse_zone_filter_works(self):
        """Test: filter by warehouse_zone returns matching records."""
        # Create a fulfillment with warehouse_zone set
        fulfillment_vn = self.env['sale.order.fulfillment'].create({
            'order_id': self.order1.id,
            'warehouse_zone': 'vn',
            'tracking_number': '9400111899223456789003',
            'shipping_carrier_id': self.carrier.id,
            'label_status_id': False,
            'tracking_state': 'none',
        })

        # Search by warehouse_zone
        vn_results = self.env['sale.order.fulfillment'].search([
            ('warehouse_zone', '=', 'vn')
        ])

        self.assertIn(fulfillment_vn, vn_results)

    @patch('odoo.addons.bus.models.bus.BusBus._sendone')
    def test_bus_push_emit_on_tracking_state_write(self, mock_sendone):
        """Test T037: bus.bus._sendone called on tracking_state write."""
        # Reset the mock
        mock_sendone.reset_mock()

        # Action: write tracking_state
        self.fulfillment2.write({'tracking_state': 'in_transit'})

        # Verify: _sendone called once
        self.assertEqual(
            mock_sendone.call_count,
            1,
            "bus.bus._sendone should be called once on tracking_state write"
        )

        # Verify: channel is correct
        call_args = mock_sendone.call_args
        channel = call_args[0][0] if call_args[0] else call_args[1].get('target')
        self.assertIn('multichannel_hub.fulfillment_update', str(channel))

    @patch('odoo.addons.bus.models.bus.BusBus._sendone')
    def test_bus_push_no_emit_on_unrelated_field_write(self, mock_sendone):
        """Test T037: bus.bus._sendone NOT called on unrelated field write."""
        mock_sendone.reset_mock()

        # Action: write unrelated field (mp_note)
        self.fulfillment2.write({'mp_note': 'Some note'})

        # Verify: _sendone NOT called
        self.assertEqual(
            mock_sendone.call_count,
            0,
            "bus.bus._sendone should NOT be called for unrelated field writes"
        )

    @patch('odoo.addons.bus.models.bus.BusBus._sendone')
    def test_bus_push_emit_on_create(self, mock_sendone):
        """Test T037: bus.bus._sendone called on fulfillment create."""
        mock_sendone.reset_mock()

        # Action: create a new fulfillment
        new_fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': self.order2.id,
            'tracking_number': '9400111899223456789099',
            'shipping_carrier_id': self.carrier.id,
            'label_status_id': False,
            'tracking_state': 'none',
        })

        # Verify: _sendone called at least once
        self.assertGreaterEqual(
            mock_sendone.call_count,
            1,
            "bus.bus._sendone should be called on fulfillment create"
        )

    @patch('odoo.addons.bus.models.bus.BusBus._sendone')
    def test_bus_push_emit_includes_required_payload_keys(self, mock_sendone):
        """Test T037: bus emit payload includes required keys."""
        mock_sendone.reset_mock()

        # Action: write tracking-relevant field
        self.fulfillment2.write({'tracking_state': 'delivered'})

        # Capture the call
        self.assertEqual(mock_sendone.call_count, 1)
        call_args = mock_sendone.call_args

        # Extract payload from the message dict
        # _sendone(target, notification_type, message)
        notification_type = call_args[0][1] if len(call_args[0]) > 1 else None
        payload = call_args[0][2] if len(call_args[0]) > 2 else {}

        # Verify: notification_type
        self.assertEqual(notification_type, 'fulfillment_update')

        # Verify: payload keys (adapt based on actual implementation)
        required_keys = {'fulfillment_id', 'order_id', 'order_name', 'tracking_state'}
        actual_keys = set(payload.keys()) if isinstance(payload, dict) else set()
        self.assertTrue(
            required_keys.issubset(actual_keys),
            f"Payload should contain {required_keys}, got {actual_keys}"
        )

    def test_direct_write_blocked_when_address_change_pending(self):
        """FR-017 defense-in-depth — direct fulfillment.write() that touches
        ship-progress fields must be blocked when parent has pending
        address-change. Prevents bulk-action bypass via XML-RPC.
        """
        # order1 has pending address-change (set in setUpClass)
        self.assertTrue(self.order1.has_pending_address_change)

        with self.assertRaises(UserError):
            self.fulfillment1.write({'tracking_state': 'shipped'})

        with self.assertRaises(UserError):
            self.fulfillment1.write({
                'shipping_date': fields.Date.context_today(self.fulfillment1),
            })

    def test_direct_write_allowed_with_bypass_context(self):
        """Bypass context flag exists for system tooling / explicit override."""
        self.fulfillment1.with_context(
            bypass_address_change_check=True
        ).write({'tracking_state': 'shipped'})
        self.fulfillment1.invalidate_recordset()
        self.assertEqual(self.fulfillment1.tracking_state, 'shipped')

    def test_direct_write_to_unrelated_field_allowed_when_pending(self):
        """Operator notes (mp_note) must remain editable while address
        change is pending — only ship-progress fields are locked.
        """
        self.fulfillment1.write({'mp_note': 'pending review'})
        self.assertEqual(self.fulfillment1.mp_note, 'pending review')

    def test_action_bulk_mark_shipped_sets_shipping_date(self):
        """Test T035: shipping_date is set when marking shipped."""
        # Verify: shipping_date not set initially (Odoo Date returns False, not None)
        self.assertFalse(self.fulfillment2.shipping_date)

        # Action: mark shipped
        self.fulfillment2.action_bulk_mark_shipped()

        # Verify: shipping_date is set to today
        self.fulfillment2.invalidate_recordset()
        self.assertTrue(self.fulfillment2.shipping_date)
        self.assertEqual(
            self.fulfillment2.shipping_date,
            fields.Date.context_today(self.fulfillment2),
            "shipping_date should be set to today"
        )
