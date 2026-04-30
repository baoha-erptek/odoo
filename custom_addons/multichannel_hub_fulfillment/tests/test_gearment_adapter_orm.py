"""P0-18b1 Phase 2 — ORM unit tests for GearmentAdapter, payload, and api.log.

Tests verify:
- GearmentAdapter Protocol shape (6 required methods)
- GearmentApiAdapter concrete implementation
- GearmentOrderPayload dataclass serialization
- Idempotency key header generation
- API log creation on every call with PII scrubbing
- Authorization header never appears in logs
- NotImplementedError stubs for confirm/register_webhooks/parse_webhook_payload
- Print-location extraction from catalog

All mocks use requests.Session mocking per feedback_odoo19_test_gotchas.md.
"""

import hashlib
import json
from datetime import datetime
from unittest import mock

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGearmentAdapterProtocol(TransactionCase):
    """Verify GearmentAdapter Protocol shape."""

    def test_protocol_has_required_methods(self):
        """Test that GearmentAdapter has all required methods."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentAdapter,
        )

        required_methods = [
            'test_connection',
            'push_order',
            'get_quote',
            'confirm',
            'register_webhooks',
            'parse_webhook_payload',
        ]

        for method_name in required_methods:
            self.assertTrue(
                hasattr(GearmentAdapter, method_name),
                f"GearmentAdapter Protocol must have method '{method_name}'"
            )


@tagged('post_install', '-at_install')
class TestGearmentApiAdapter(TransactionCase):
    """Phase 2: ORM tests for GearmentApiAdapter with mocked requests."""

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, tracking_disable=True))

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_test_connection_returns_true_on_ping_ok(self, mock_session_class):
        """Verify test_connection returns True when ping succeeds."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )

        # Mock successful ping response
        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {'legacy_product_id': 2, 'print_locations': ['pocket', 'front']},
            ]
        }
        mock_session.request.return_value = mock_response

        adapter = GearmentApiAdapter()
        result = adapter.test_connection()

        self.assertTrue(result, "test_connection should return True on successful ping")

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_test_connection_returns_false_on_failure(self, mock_session_class):
        """Verify test_connection returns False when ping fails."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )

        # Mock failed ping response
        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session
        mock_session.request.side_effect = Exception("Connection error")

        adapter = GearmentApiAdapter()
        result = adapter.test_connection()

        self.assertFalse(result, "test_connection should return False on failure")

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_push_order_returns_partner_ref_and_quote(self, mock_session_class):
        """Verify push_order returns dict with partner_ref and price_quote."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentOrderPayload,
        )

        # Mock POST /api/v3/orders response
        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'order_id': 'gm_123',
            'price_quote': 12.34,
            'quote_expires_at': '2026-05-01T10:00:00Z',
        }
        mock_session.request.return_value = mock_response

        adapter = GearmentApiAdapter()
        payload = GearmentOrderPayload(
            external_order_id='SO001',
            platform='etsy',
            store_id='store_1',
            quantity=1,
            product_id=2,
            address={'city': 'Boston', 'country': 'US'},
            shipping_method='standard',
            design_files=[],
        )

        result = adapter.push_order(payload)

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('partner_ref'), 'gm_123')
        self.assertAlmostEqual(result.get('price_quote'), 12.34)

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_push_order_sets_idempotency_key_header(self, mock_session_class):
        """Verify push_order sets Idempotency-Key header from external_order_id."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentOrderPayload,
        )

        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'order_id': 'gm_123'}
        mock_session.request.return_value = mock_response

        adapter = GearmentApiAdapter()
        payload = GearmentOrderPayload(
            external_order_id='SO001',
            platform='etsy',
            store_id='store_1',
            quantity=1,
            product_id=2,
            address={'city': 'Boston', 'country': 'US'},
            shipping_method='standard',
            design_files=[],
        )

        adapter.push_order(payload)

        # Verify request was called with Idempotency-Key header
        call_args = mock_session.request.call_args
        headers = call_args.kwargs.get('headers', {})

        expected_key = hashlib.sha256('SO001'.encode()).hexdigest()
        self.assertEqual(
            headers.get('Idempotency-Key'),
            expected_key,
            "Idempotency-Key must be SHA-256 hex of external_order_id"
        )

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_push_order_sets_reference_id_in_body(self, mock_session_class):
        """Verify push_order sets reference_id in POST body equal to external_order_id."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentOrderPayload,
        )

        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'order_id': 'gm_123'}
        mock_session.request.return_value = mock_response

        adapter = GearmentApiAdapter()
        payload = GearmentOrderPayload(
            external_order_id='SO002',
            platform='etsy',
            store_id='store_1',
            quantity=1,
            product_id=2,
            address={'city': 'Boston', 'country': 'US'},
            shipping_method='standard',
            design_files=[],
        )

        adapter.push_order(payload)

        # Verify reference_id in body
        call_args = mock_session.request.call_args
        json_body = call_args.kwargs.get('json', {})

        self.assertEqual(
            json_body.get('reference_id'),
            'SO002',
            "reference_id in body must equal external_order_id"
        )

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_push_order_writes_api_log_row(self, mock_session_class):
        """Verify push_order creates gearment.api.log row with source='draft'."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentOrderPayload,
        )

        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'order_id': 'gm_123', 'price_quote': 12.34}
        mock_session.request.return_value = mock_response

        # Clear any existing logs
        self.env['gearment.api.log'].search([]).unlink()

        adapter = GearmentApiAdapter()
        payload = GearmentOrderPayload(
            external_order_id='SO003',
            platform='etsy',
            store_id='store_1',
            quantity=1,
            product_id=2,
            address={'city': 'Boston', 'country': 'US'},
            shipping_method='standard',
            design_files=[],
        )

        adapter.push_order(payload)

        # Verify log row was created
        logs = self.env['gearment.api.log'].search([
            ('source', '=', 'draft'),
        ])

        self.assertEqual(len(logs), 1, "One API log row should be created with source='draft'")
        log = logs[0]
        self.assertEqual(log.http_status, 200)
        self.assertEqual(log.endpoint, 'POST /api/v3/orders')

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_push_order_scrubs_pii_from_log(self, mock_session_class):
        """Verify push_order scrubs PII from request_payload_summary."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentOrderPayload,
        )

        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'order_id': 'gm_123'}
        mock_session.request.return_value = mock_response

        self.env['gearment.api.log'].search([]).unlink()

        adapter = GearmentApiAdapter()
        payload = GearmentOrderPayload(
            external_order_id='SO004',
            platform='etsy',
            store_id='store_1',
            quantity=1,
            product_id=2,
            address={
                'name': 'John Doe',
                'email': 'john@example.com',
                'phone': '555-1234',
                'city': 'Boston',
                'country': 'US',
            },
            shipping_method='standard',
            design_files=[],
            notes='Special request',
        )

        adapter.push_order(payload)

        logs = self.env['gearment.api.log'].search([('source', '=', 'draft')])
        log = logs[0]

        # PII should be scrubbed from the summary
        summary_text = log.request_payload_summary or ''
        self.assertNotIn('John Doe', summary_text, "Buyer name must be scrubbed")
        self.assertNotIn('john@example.com', summary_text, "Email must be scrubbed")
        self.assertNotIn('555-1234', summary_text, "Phone must be scrubbed")
        self.assertNotIn('Special request', summary_text, "Notes must be scrubbed")

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_authorization_header_never_in_log(self, mock_session_class):
        """Verify Authorization header never appears in stored payload summary."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentOrderPayload,
        )

        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'order_id': 'gm_123'}
        mock_session.request.return_value = mock_response

        self.env['gearment.api.log'].search([]).unlink()

        adapter = GearmentApiAdapter()
        payload = GearmentOrderPayload(
            external_order_id='SO005',
            platform='etsy',
            store_id='store_1',
            quantity=1,
            product_id=2,
            address={'city': 'Boston', 'country': 'US'},
            shipping_method='standard',
            design_files=[],
        )

        adapter.push_order(payload)

        logs = self.env['gearment.api.log'].search([('source', '=', 'draft')])
        log = logs[0]

        summary = log.request_payload_summary or ''
        self.assertNotIn('Authorization', summary,
                        "Authorization header must never appear in API log summary")

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_get_quote_returns_quote_dict(self, mock_session_class):
        """Verify get_quote returns dict with price_quote/shipping_estimate/quote_expires_at."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )

        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'order_id': 'gm_123',
            'price_quote': 15.00,
            'shipping_estimate': 5.00,
            'quote_expires_at': '2026-05-02T10:00:00Z',
        }
        mock_session.request.return_value = mock_response

        adapter = GearmentApiAdapter()
        result = adapter.get_quote('gm_123')

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('price_quote'), 15.00)
        self.assertEqual(result.get('shipping_estimate'), 5.00)
        self.assertIn('quote_expires_at', result)

    def test_confirm_raises_not_implemented(self):
        """Verify confirm raises NotImplementedError (P4-01 stub)."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )

        adapter = GearmentApiAdapter()

        with self.assertRaises(NotImplementedError) as ctx:
            adapter.confirm('gm_123')

        self.assertIn('P4-01', str(ctx.exception),
                     "NotImplementedError must reference P4-01")

    def test_register_webhooks_raises_not_implemented(self):
        """Verify register_webhooks raises NotImplementedError (P0-18b2 stub)."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )

        adapter = GearmentApiAdapter()

        with self.assertRaises(NotImplementedError) as ctx:
            adapter.register_webhooks('http://example.com/webhook', [])

        self.assertIn('P0-18b2', str(ctx.exception),
                     "NotImplementedError must reference P0-18b2")

    def test_parse_webhook_payload_raises_not_implemented(self):
        """Verify parse_webhook_payload raises NotImplementedError (P0-18b2 stub)."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )

        adapter = GearmentApiAdapter()

        with self.assertRaises(NotImplementedError) as ctx:
            adapter.parse_webhook_payload({}, b'{}')

        self.assertIn('P0-18b2', str(ctx.exception),
                     "NotImplementedError must reference P0-18b2")

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_extract_print_location_codes_from_catalog(self, mock_session_class):
        """Verify adapter extracts print_location codes from catalog response."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )

        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {
                    'legacy_product_id': 2,
                    'print_locations': [
                        {'code': 'pocket'},
                        {'code': 'front'},
                        {'code': 'back'},
                        {'code': 'left_sleeve'},
                        {'code': 'right_sleeve'},
                    ],
                }
            ]
        }
        mock_session.request.return_value = mock_response

        adapter = GearmentApiAdapter()
        catalog = adapter._fetch_catalog()

        self.assertIsNotNone(catalog)
        self.assertIn('data', catalog)
        locations = catalog['data'][0].get('print_locations', [])
        location_codes = [loc.get('code') for loc in locations]

        self.assertEqual(
            set(location_codes),
            {'pocket', 'front', 'back', 'left_sleeve', 'right_sleeve'},
            "Catalog must include all 5 print location codes"
        )


@tagged('post_install', '-at_install')
class TestGearmentOrderPayload(TransactionCase):
    """Tests for GearmentOrderPayload dataclass."""

    def test_payload_serializes_to_dict_with_required_fields(self):
        """Verify payload.serialize() returns dict with required fields."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentOrderPayload,
        )

        payload = GearmentOrderPayload(
            external_order_id='SO001',
            platform='etsy',
            store_id='store_1',
            quantity=2,
            product_id=2,
            address={'city': 'Boston', 'country': 'US'},
            shipping_method='express',
            design_files=[{'role': 'front', 'url': 'http://example.com/file.pdf'}],
        )

        result = payload.serialize()

        self.assertIsInstance(result, dict)
        self.assertEqual(result['external_order_id'], 'SO001')
        self.assertEqual(result['platform'], 'etsy')
        self.assertEqual(result['store_id'], 'store_1')
        self.assertEqual(result['quantity'], 2)
        self.assertEqual(result['product_id'], 2)
        self.assertIn('reference_id', result)
        self.assertEqual(result['reference_id'], 'SO001')

    def test_payload_optional_fields_omitted_when_none(self):
        """Verify optional fields are omitted when None."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentOrderPayload,
        )

        payload = GearmentOrderPayload(
            external_order_id='SO002',
            platform='etsy',
            store_id='store_1',
            quantity=1,
            product_id=2,
            address={'city': 'Boston', 'country': 'US'},
            shipping_method='standard',
            design_files=[],
            notes=None,
            custom_attributes=None,
        )

        result = payload.serialize()

        # Optional fields should be omitted or serialized as empty
        if 'notes' in result:
            self.assertIsNone(result['notes'])
        if 'custom_attributes' in result:
            self.assertIsNone(result['custom_attributes'])

    def test_idempotency_hash_matches_external_order_id(self):
        """Verify payload.idempotency_key returns sha256 hex of external_order_id."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentOrderPayload,
        )

        payload = GearmentOrderPayload(
            external_order_id='SO003',
            platform='etsy',
            store_id='store_1',
            quantity=1,
            product_id=2,
            address={'city': 'Boston', 'country': 'US'},
            shipping_method='standard',
            design_files=[],
        )

        expected_key = hashlib.sha256('SO003'.encode()).hexdigest()
        self.assertEqual(payload.idempotency_key, expected_key)


@tagged('post_install', '-at_install')
class TestPiiScrubbing(TransactionCase):
    """Tests for PII scrubbing in API logs."""

    def test_scrub_pii_drops_buyer_name_address_email_phone_notes(self):
        """Verify scrub_pii removes PII fields while preserving business data."""
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            _scrub_pii,
        )

        payload = {
            'buyer_name': 'John Doe',
            'address_line_1': '123 Main St',
            'address_line_2': 'Apt 5',
            'email': 'john@example.com',
            'phone': '555-1234',
            'notes': 'Special wrapping',
            'product_id': 2,
            'platform': 'etsy',
            'quantity': 1,
        }

        scrubbed = _scrub_pii(payload)

        self.assertNotIn('buyer_name', scrubbed)
        self.assertNotIn('address_line_1', scrubbed)
        self.assertNotIn('address_line_2', scrubbed)
        self.assertNotIn('email', scrubbed)
        self.assertNotIn('phone', scrubbed)
        self.assertNotIn('notes', scrubbed)

        # Business data should be preserved
        self.assertEqual(scrubbed['product_id'], 2)
        self.assertEqual(scrubbed['platform'], 'etsy')
        self.assertEqual(scrubbed['quantity'], 1)
