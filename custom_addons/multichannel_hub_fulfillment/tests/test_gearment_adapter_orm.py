"""Tests for GearmentApiAdapter — non-schema-bound smoke + protocol coverage.

Schema-bound payload + URL routing + Money proto tests live in
`test_p4_01_b_payload.py` and `test_p4_01_b_adapter.py` (P4-01-B).

What stays in this file:
- Adapter protocol shape (the methods exist with the right names)
- Connection ping smoke test (was P0-18b1 baseline)
- `register_webhooks` / `parse_webhook_payload` still raise NotImplementedError
  (these are P0-18b2 stubs unrelated to P4-01-B)
- Catalog response shape verification (regression coverage on print_locations)
- PII scrubbing test against the new payload schema

What got removed (now covered by P4-01-B test files):
- `test_push_order_returns_partner_ref_and_quote` — old return shape
- `test_push_order_sets_idempotency_key_header` — covered by adapter URL tests
- `test_push_order_sets_reference_id_in_body` — covered by payload schema tests
- `test_push_order_writes_api_log_row` — covered by integration coverage
- `test_get_quote_returns_quote_dict` — covered by adapter URL tests
- `test_confirm_raises_not_implemented` — `confirm()` is now implemented (P4-01-B)
- `TestGearmentOrderPayload` class — fully replaced by `TestP401BPayloadSchema`
"""
from unittest import mock

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGearmentAdapterProtocol(TransactionCase):
    """The adapter exposes the Protocol-mandated methods."""

    def test_protocol_has_required_methods(self):
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        for method in (
            'test_connection',
            'push_order',
            'get_quote',
            'confirm',
            'register_webhooks',
            'parse_webhook_payload',
        ):
            self.assertTrue(
                callable(getattr(GearmentApiAdapter, method, None)),
                f"GearmentApiAdapter must expose `{method}` for the Protocol",
            )


@tagged('post_install', '-at_install')
class TestGearmentApiAdapterSmoke(TransactionCase):
    """Connection + catalog smoke tests against mocked HTTP."""

    def setUp(self):
        super().setUp()
        with mock.patch.dict(
            'os.environ',
            {
                'GEARMENT_API_KEY': 'TEST_KEY',
                'GEARMENT_API_SECRET': 'TEST_SECRET',
                'GEARMENT_API_BASE_URL': 'https://api.gearment.test',
            },
            clear=False,
        ):
            from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
                GearmentApiAdapter,
            )
            self.adapter = GearmentApiAdapter()

    def test_test_connection_returns_true_on_ping_ok(self):
        with mock.patch.object(
            self.adapter.client, '_session',
        ) as mock_session_factory:
            session = mock.MagicMock()
            response = mock.MagicMock()
            response.status_code = 200
            response.json.return_value = {'data': [], 'paging': {}}
            response.raise_for_status = mock.MagicMock()
            session.request.return_value = response
            mock_session_factory.return_value = session
            self.assertTrue(self.adapter.test_connection())

    def test_test_connection_returns_false_on_failure(self):
        with mock.patch.object(
            self.adapter.client, '_session',
        ) as mock_session_factory:
            session = mock.MagicMock()
            session.request.side_effect = RuntimeError("connection refused")
            mock_session_factory.return_value = session
            self.assertFalse(self.adapter.test_connection())

    def test_register_webhooks_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError) as ctx:
            self.adapter.register_webhooks('http://example.com/webhook', [])
        self.assertIn('P0-18b2', str(ctx.exception))

    def test_parse_webhook_payload_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError) as ctx:
            self.adapter.parse_webhook_payload({}, b'{}')
        self.assertIn('P0-18b2', str(ctx.exception))

    def test_extract_print_location_codes_from_catalog(self):
        with mock.patch.object(
            self.adapter.client, '_session',
        ) as mock_session_factory:
            session = mock.MagicMock()
            response = mock.MagicMock()
            response.status_code = 200
            response.json.return_value = {
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
            response.raise_for_status = mock.MagicMock()
            session.request.return_value = response
            mock_session_factory.return_value = session
            catalog = self.adapter._fetch_catalog()
            location_codes = {
                loc['code']
                for loc in catalog['data'][0]['print_locations']
            }
            self.assertEqual(
                location_codes,
                {'pocket', 'front', 'back', 'left_sleeve', 'right_sleeve'},
            )


@tagged('post_install', '-at_install')
class TestPiiScrubbing(TransactionCase):
    """`_scrub_pii` drops PII keys recursively from the new payload schema."""

    def test_scrub_pii_drops_addresses_first_last_street_email_phone(self):
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            _scrub_pii,
        )
        # Mirrors the new GearmentOrderPayload.serialize() shape (P4-01-B).
        body = {
            'data': {
                'reference_id': 'SO-001',
                'addresses': [{
                    'first_name': 'Alice',
                    'last_name': 'Buyer',
                    'street_1': '123 Main St',
                    'street_2': None,
                    'city': 'Boston',
                    'zip_code': '02108',
                    'country_code': 'US',
                    'email': 'alice@example.com',
                    'phone': '+1-555-0100',
                }],
                'line_items': [{'product_id': 99, 'quantity': 1}],
                'notes': 'Buyer-supplied note',
            },
        }
        scrubbed = _scrub_pii(body)
        # 'addresses' is in the PII keyset itself — entire list is dropped.
        self.assertNotIn('addresses', scrubbed['data'])
        # Notes are PII (free-text).
        self.assertNotIn('notes', scrubbed['data'])
        # Reference + line items survive (no PII in identifiers).
        self.assertEqual(scrubbed['data']['reference_id'], 'SO-001')
        self.assertEqual(
            scrubbed['data']['line_items'],
            [{'product_id': 99, 'quantity': 1}],
        )
