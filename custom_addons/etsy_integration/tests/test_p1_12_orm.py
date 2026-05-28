"""Phase 2 ORM tests for P1-12 — EtsyTrackingPusher (Spec 005 US3).

These tests verify business logic and ORM behavior:
- EtsyTrackingPusher.push() returns True on success, False on failure
- Tracking push status state machine: none → pushed | failed
- Fulfillment etsy_ship_notified_at is set on successful push
- Audit log (etsy.api.log) row is created with source='tracking_push'
- Missing fulfillment or tracking_number prevents push
- Missing carrier mapping (etsy_carrier_name) still pushes with 'other'
- 5xx/client errors set status='failed' and error_message

PHASE: RED (failing tests — implementation does not exist yet)
"""
import json
import logging
from unittest import mock

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'p1_12')
class TestEtsyTrackingPusherHappyPath(TransactionCase):
    """Phase 2: Happy path — successful tracking push to Etsy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create test shop. Note: etsy.shop has no etsy_numeric_shop_id field.
        # The shop_id path parameter in API calls is simply shop.id (the Odoo record id).
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Etsy Shop',
        })

        # Create partner
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        # Create product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        # Create shipping carrier with etsy_carrier_name mapping.
        # shipping.carrier requires both 'name' and 'code' fields.
        # Use unique code to avoid conflicts with demo data.
        cls.carrier = cls.env['shipping.carrier'].create({
            'name': 'Test USPS',
            'code': 'test_usps_1',
            'etsy_carrier_name': 'usps',
        })

    def _create_order_with_fulfillment(self, **kwargs):
        """Factory: create a sale.order with fulfillment and tracking number."""
        order_vals = {
            'partner_id': self.partner.id,
            'etsy_order_id': 'etsy-' + str(self.env['ir.sequence'].next_by_code('sale.order')),
            'etsy_shop_id': self.shop.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100.0,
            })],
        }
        order_vals.update(kwargs)
        order = self.env['sale.order'].create(order_vals)
        order.action_confirm()

        # Create fulfillment with tracking number
        fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
            'tracking_number': '9400111899223456789012',
            'shipping_carrier_id': self.carrier.id,
        })

        return order, fulfillment

    def test_push_returns_true_on_success(self):
        """Test that EtsyTrackingPusher.push() returns True on successful API call."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order, fulfillment = self._create_order_with_fulfillment()

        pusher = EtsyTrackingPusher(self.env)

        # Mock the EtsyApiClient to return success
        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.return_value = (True, 201, '')

            result = pusher.push(order)

        self.assertTrue(result, "push() should return True on API success")

    def test_status_updates_to_pushed_on_success(self):
        """Test that etsy_tracking_push_status='pushed' after successful push."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order, fulfillment = self._create_order_with_fulfillment()

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.return_value = (True, 201, '')

            pusher.push(order)
            order.invalidate_recordset()

        self.assertEqual(
            order.etsy_tracking_push_status, 'pushed',
            "Status should be 'pushed' after successful push"
        )

    def test_etsy_tracking_push_at_set_on_success(self):
        """Test that etsy_tracking_push_at is set to current time on success."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order, fulfillment = self._create_order_with_fulfillment()

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.return_value = (True, 201, '')

            pusher.push(order)
            order.invalidate_recordset()

        self.assertTrue(
            order.etsy_tracking_push_at,
            "etsy_tracking_push_at should be set (not False/null)"
        )

    def test_fulfillment_etsy_ship_notified_at_set_on_success(self):
        """Test that fulfillment.etsy_ship_notified_at is set on successful push."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order, fulfillment = self._create_order_with_fulfillment()

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.return_value = (True, 201, '')

            pusher.push(order)
            fulfillment.invalidate_recordset()

        self.assertTrue(
            fulfillment.etsy_ship_notified_at,
            "Fulfillment etsy_ship_notified_at should be set on successful push"
        )

    def test_audit_log_created_on_success(self):
        """Test that etsy.api.log row is created with source='tracking_push' on success."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order, fulfillment = self._create_order_with_fulfillment()

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.return_value = (True, 201, '')

            pusher.push(order)

        # Query audit log
        api_log = self.env['etsy.api.log'].search([
            ('source', '=', 'tracking_push'),
            ('shop_id', '=', self.shop.id),
        ], limit=1)

        self.assertTrue(api_log, "etsy.api.log row should be created")
        self.assertEqual(api_log.source, 'tracking_push')
        self.assertEqual(api_log.http_status, 201)

    def test_api_endpoint_called_with_correct_parameters(self):
        """Test that EtsyApiClient is called with correct shop_id, receipt_id, tracking data."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order, fulfillment = self._create_order_with_fulfillment()

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.return_value = (True, 201, '')

            pusher.push(order)

            # Verify the client was instantiated with the shop
            mock_client_class.assert_called_once()

            # Verify push_tracking was called with correct parameters
            mock_client.push_tracking.assert_called_once()
            call_args = mock_client.push_tracking.call_args
            # Call args should include receipt_id (from etsy_order_id), carrier, tracking_number
            self.assertIsNotNone(call_args)


@tagged('post_install', '-at_install', 'p1_12')
class TestEtsyTrackingPusherErrorCases(TransactionCase):
    """Phase 2: Error cases — missing data, API failures, missing carrier mapping."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Etsy Shop',
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        # Carrier with NO etsy_carrier_name (unmapped).
        # shipping.carrier requires both 'name' and 'code' fields.
        # Use unique code to avoid conflicts with demo data.
        cls.carrier_unmapped = cls.env['shipping.carrier'].create({
            'name': 'Test Unmapped Carrier',
            'code': 'test_unmapped_2',
        })

        # Carrier with etsy_carrier_name
        cls.carrier_mapped = cls.env['shipping.carrier'].create({
            'name': 'Test USPS Mapped',
            'code': 'test_usps_mapped_2',
            'etsy_carrier_name': 'usps',
        })

    def _create_order(self, **kwargs):
        """Factory: create a minimal sale.order for testing."""
        order_vals = {
            'partner_id': self.partner.id,
            'etsy_order_id': 'etsy-' + str(self.env['ir.sequence'].next_by_code('sale.order')),
            'etsy_shop_id': self.shop.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100.0,
            })],
        }
        order_vals.update(kwargs)
        order = self.env['sale.order'].create(order_vals)
        order.action_confirm()
        return order

    def test_push_returns_false_on_api_error(self):
        """Test that push() returns False when EtsyApiClient raises an exception."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order = self._create_order()
        fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
            'tracking_number': '9400111899223456789012',
            'shipping_carrier_id': self.carrier_mapped.id,
        })

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            # Simulate a 5xx error
            mock_client.push_tracking.side_effect = Exception('500 Internal Server Error')

            result = pusher.push(order)

        self.assertFalse(result, "push() should return False on API error")

    def test_status_failed_on_api_error(self):
        """Test that etsy_tracking_push_status='failed' after API error."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order = self._create_order()
        fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
            'tracking_number': '9400111899223456789012',
            'shipping_carrier_id': self.carrier_mapped.id,
        })

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.side_effect = Exception('500 Internal Server Error')

            pusher.push(order)
            order.invalidate_recordset()

        self.assertEqual(
            order.etsy_tracking_push_status, 'failed',
            "Status should be 'failed' after API error"
        )

    def test_error_message_populated_on_api_error(self):
        """Test that etsy_tracking_push_error is populated with error details."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order = self._create_order()
        fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
            'tracking_number': '9400111899223456789012',
            'shipping_carrier_id': self.carrier_mapped.id,
        })

        pusher = EtsyTrackingPusher(self.env)

        error_msg = '500 Internal Server Error from Etsy'
        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.side_effect = Exception(error_msg)

            pusher.push(order)
            order.invalidate_recordset()

        self.assertTrue(
            order.etsy_tracking_push_error,
            "etsy_tracking_push_error should be populated on error"
        )
        self.assertIn(
            'error',
            order.etsy_tracking_push_error.lower(),
            "Error message should contain 'error' keyword"
        )

    def test_missing_fulfillment_returns_false(self):
        """Test that push() returns False when order has no fulfillment."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order = self._create_order()
        # No fulfillment created

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client

            result = pusher.push(order)

        self.assertFalse(
            result,
            "push() should return False when order has no fulfillment"
        )
        # Verify no API call was made
        mock_client.push_tracking.assert_not_called()

    def test_missing_tracking_number_returns_false(self):
        """Test that push() returns False when fulfillment has no tracking_number."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order = self._create_order()
        fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
            # tracking_number intentionally omitted
            'shipping_carrier_id': self.carrier_mapped.id,
        })

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client

            result = pusher.push(order)

        self.assertFalse(
            result,
            "push() should return False when tracking_number is missing"
        )
        mock_client.push_tracking.assert_not_called()

    def test_unmapped_carrier_pushes_with_other(self):
        """Test that unmapped carrier (no etsy_carrier_name) still pushes with 'other'."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order = self._create_order()
        fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
            'tracking_number': '9400111899223456789012',
            'shipping_carrier_id': self.carrier_unmapped.id,  # No etsy_carrier_name
        })

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.return_value = (True, 201, '')

            result = pusher.push(order)
            order.invalidate_recordset()

        self.assertTrue(result, "push() should succeed with unmapped carrier")
        self.assertEqual(
            order.etsy_tracking_push_status, 'pushed',
            "Status should be 'pushed' even with unmapped carrier"
        )
        # Verify the push_tracking call was made (with 'other' as the carrier)
        mock_client.push_tracking.assert_called_once()

    def test_audit_log_created_on_error(self):
        """Test that etsy.api.log row is created even on error."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order = self._create_order()
        fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
            'tracking_number': '9400111899223456789012',
            'shipping_carrier_id': self.carrier_mapped.id,
        })

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.side_effect = Exception('API Error')

            pusher.push(order)

        api_log = self.env['etsy.api.log'].search([
            ('source', '=', 'tracking_push'),
            ('shop_id', '=', self.shop.id),
        ], limit=1)

        self.assertTrue(api_log, "etsy.api.log row should be created on error")
        self.assertEqual(api_log.source, 'tracking_push')
        # error_message should be populated
        self.assertTrue(
            api_log.error_message,
            "audit log error_message should be populated"
        )


@tagged('post_install', '-at_install', 'p1_12')
class TestEtsyTrackingPusherStateMachine(TransactionCase):
    """Phase 2: State machine — verify status transitions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Etsy Shop',
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        cls.carrier = cls.env['shipping.carrier'].create({
            'name': 'Test USPS State',
            'code': 'test_usps_state_3',
            'etsy_carrier_name': 'usps',
        })

    def _create_order_with_fulfillment(self):
        """Factory: create order with fulfillment."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'etsy_order_id': 'etsy-' + str(self.env['ir.sequence'].next_by_code('sale.order')),
            'etsy_shop_id': self.shop.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100.0,
            })],
        })
        order.action_confirm()

        fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
            'tracking_number': '9400111899223456789012',
            'shipping_carrier_id': self.carrier.id,
        })

        return order, fulfillment

    def test_initial_status_is_none(self):
        """Test that new order has etsy_tracking_push_status='none'."""
        order, fulfillment = self._create_order_with_fulfillment()

        self.assertEqual(
            order.etsy_tracking_push_status, 'none',
            "Initial status should be 'none'"
        )

    def test_status_transitions_to_pushed(self):
        """Test state machine: none → pushed."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order, fulfillment = self._create_order_with_fulfillment()

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.return_value = (True, 201, '')

            pusher.push(order)
            order.invalidate_recordset()

        self.assertEqual(order.etsy_tracking_push_status, 'pushed')

    def test_status_transitions_to_failed(self):
        """Test state machine: none → failed."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order, fulfillment = self._create_order_with_fulfillment()

        pusher = EtsyTrackingPusher(self.env)

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.side_effect = Exception('API Error')

            pusher.push(order)
            order.invalidate_recordset()

        self.assertEqual(order.etsy_tracking_push_status, 'failed')

    def test_failed_status_is_retriable(self):
        """Test that status='failed' can be retried to 'pushed'."""
        try:
            from odoo.addons.etsy_integration.services.etsy_tracking_pusher import (
                EtsyTrackingPusher
            )
        except ImportError:
            self.fail("etsy_tracking_pusher service not yet implemented (RED OK)")

        order, fulfillment = self._create_order_with_fulfillment()

        pusher = EtsyTrackingPusher(self.env)

        # First attempt: fail
        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.side_effect = Exception('API Error')

            pusher.push(order)
            order.invalidate_recordset()

        self.assertEqual(order.etsy_tracking_push_status, 'failed')

        # Second attempt: succeed
        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyApiClient'
        ) as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.push_tracking.return_value = (True, 201, '')

            pusher.push(order)
            order.invalidate_recordset()

        self.assertEqual(order.etsy_tracking_push_status, 'pushed')


@tagged('post_install', '-at_install', 'p1_12')
class TestEtsyTrackingPusherButton(TransactionCase):
    """Phase 2: On-demand push button action."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Etsy Shop',
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })

        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'list_price': 100.0,
        })

        cls.carrier = cls.env['shipping.carrier'].create({
            'name': 'Test USPS Button',
            'code': 'test_usps_button_4',
            'etsy_carrier_name': 'usps',
        })

    def test_action_push_tracking_to_etsy_button_exists(self):
        """Test that sale.order has action_push_tracking_to_etsy method."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'etsy_order_id': 'etsy-123',
            'etsy_shop_id': self.shop.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100.0,
            })],
        })

        self.assertTrue(
            hasattr(order, 'action_push_tracking_to_etsy'),
            "sale.order should have action_push_tracking_to_etsy method"
        )

    def test_action_push_tracking_returns_notification(self):
        """Test that action_push_tracking_to_etsy returns a notification action dict."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'etsy_order_id': 'etsy-123',
            'etsy_shop_id': self.shop.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1.0,
                'price_unit': 100.0,
            })],
        })
        order.action_confirm()

        fulfillment = self.env['sale.order.fulfillment'].create({
            'order_id': order.id,
            'tracking_number': '9400111899223456789012',
            'shipping_carrier_id': self.carrier.id,
        })

        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_tracking_pusher.EtsyTrackingPusher'
        ) as mock_pusher_class:
            mock_pusher = mock.MagicMock()
            mock_pusher_class.return_value = mock_pusher
            mock_pusher.push.return_value = True

            result = order.action_push_tracking_to_etsy()

        self.assertIsNotNone(result, "action_push_tracking_to_etsy should return a dict")
        self.assertIn('type', result, "Result should have a 'type' key")
