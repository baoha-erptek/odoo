"""P4-01-B Phase 2 ORM — gearment_adapter URL rewrites + 503/504 retry.

Closes contract gap G1 (URL `/api/v3/orders` → `/api/v3/orders/draft`) and
addresses surprise S4 (production throttles via 503 + Cloudflare timeouts,
not 429). 429 retry stays unchanged.
"""

from unittest import mock

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
    GearmentApiAdapter,
)


def _stub_response(status_code=200, json_body=None, headers=None):
    """Build a mock requests.Response."""
    resp = mock.MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.headers = headers or {}
    resp.raise_for_status = mock.MagicMock()
    return resp


@tagged('post_install', '-at_install', 'p4_01_b')
class TestP401BAdapterUrls(TransactionCase):
    """Adapter calls the corrected URLs."""

    def setUp(self):
        super().setUp()
        # Patch the credential-check at __init__ so we don't need real env vars.
        with mock.patch.dict(
            'os.environ',
            {
                'GEARMENT_API_KEY': 'TEST_KEY',
                'GEARMENT_API_SECRET': 'TEST_SECRET',
                'GEARMENT_API_BASE_URL': 'https://api.gearment.test',
            },
            clear=False,
        ):
            self.adapter = GearmentApiAdapter()

    def _build_payload(self):
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentAddress,
            GearmentLineItem,
            GearmentOrderPayload,
        )
        return GearmentOrderPayload(
            reference_id='SO-TEST-001',
            store_id='42',
            platform='MARKETPLACE_PLATFORM_ETSY',
            addresses=(GearmentAddress(
                first_name='A', last_name='B', street_1='123 Main',
                street_2=None, city='Boston', state_code='MA', zip_code='02108',
                country_code='US', phone_no=None, email=None,
            ),),
            line_items=(GearmentLineItem(
                variant_id='GM0249020374', quantity=1,
                printing_options=({'location_code': 'PRINT_LOCATION_CODE_FRONT',
                                   'url': 'https://x/y.png'},),
                custom_attributes=None,
            ),),
            shipping_method=None, notes=None, custom_attributes=None,
        )

    def test_push_order_calls_orders_draft_url(self):
        payload = self._build_payload()
        with mock.patch.object(
            self.adapter.client, '_session',
        ) as mock_session_factory:
            session = mock.MagicMock()
            session.request.return_value = _stub_response(
                json_body={'data': {'reference_id': 'SO-TEST-001', 'order_id': 'GR-001'}},
            )
            mock_session_factory.return_value = session
            self.adapter.push_order(payload)
            session.request.assert_called_once()
            call_args = session.request.call_args
            # Method + URL — URL must be /api/v3/orders/draft (G1 fix)
            self.assertEqual(call_args.args[0], 'POST')
            self.assertIn('/api/v3/orders/draft', call_args.args[1])
            self.assertNotIn('/api/v3/orders/SO-TEST', call_args.args[1])  # not /orders/{ref}

    def test_get_quote_calls_orders_price_url(self):
        with mock.patch.object(
            self.adapter.client, '_session',
        ) as mock_session_factory:
            session = mock.MagicMock()
            session.request.return_value = _stub_response(
                json_body={
                    'data': {
                        'order_total': {
                            'currency_code': 'USD', 'units': '45', 'nanos': 99,
                        },
                        'order_sub_total': {
                            'currency_code': 'USD', 'units': '40', 'nanos': 0,
                        },
                        'order_shipping_fee': {
                            'currency_code': 'USD', 'units': '5', 'nanos': 99,
                        },
                    },
                    'message': '[API] Order price!',
                    'status': 'success',
                },
            )
            mock_session_factory.return_value = session
            self.adapter.get_quote({'order_platform': 'etsy', 'line_items': []})
            session.request.assert_called_once()
            call_args = session.request.call_args
            self.assertEqual(call_args.args[0], 'POST')
            self.assertTrue(call_args.args[1].endswith('/api/v3/orders/price'))
            self.assertNotIn('{ref}', call_args.args[1])

    def test_get_quote_decodes_money_proto(self):
        from decimal import Decimal
        with mock.patch.object(
            self.adapter.client, '_session',
        ) as mock_session_factory:
            session = mock.MagicMock()
            session.request.return_value = _stub_response(
                json_body={
                    'data': {
                        'order_total': {
                            'currency_code': 'USD', 'units': '45', 'nanos': 99,
                        },
                        'order_sub_total': {
                            'currency_code': 'USD', 'units': '40', 'nanos': 0,
                        },
                        'order_shipping_fee': {
                            'currency_code': 'USD', 'units': '5', 'nanos': 99,
                        },
                    },
                    'message': '[API] Order price!',
                    'status': 'success',
                },
            )
            mock_session_factory.return_value = session
            quote = self.adapter.get_quote({'order_platform': 'etsy', 'line_items': []})
            # Quote dict carries decoded decimals + currency
            self.assertEqual(quote['currency'], 'USD')
            self.assertEqual(quote['order_total'], Decimal('45.99'))
            self.assertEqual(quote['order_sub_total'], Decimal('40.00'))
            self.assertEqual(quote['order_shipping_fee'], Decimal('5.99'))

    def test_confirm_calls_orders_draft_labeled_url(self):
        with mock.patch.object(
            self.adapter.client, '_session',
        ) as mock_session_factory:
            session = mock.MagicMock()
            session.request.return_value = _stub_response(
                json_body={'data': {'reference_id': 'SO-TEST-001', 'status': 'confirmed'}},
            )
            mock_session_factory.return_value = session
            self.adapter.confirm('SO-TEST-001')
            session.request.assert_called_once()
            call_args = session.request.call_args
            self.assertEqual(call_args.args[0], 'POST')
            self.assertIn('/api/v3/orders/draft/labeled', call_args.args[1])

    def test_confirm_idempotency_key_is_sha256_of_reference_id(self):
        """Regression: Idempotency-Key must be hashed, not raw — defends
        against CRLF injection from user-editable `channel_order_ref` and
        keeps contract symmetric with `push_order`."""
        import hashlib
        with mock.patch.object(
            self.adapter.client, '_session',
        ) as mock_session_factory:
            session = mock.MagicMock()
            session.request.return_value = _stub_response(
                json_body={'data': {'reference_id': 'SO-TEST-001'}},
            )
            mock_session_factory.return_value = session
            self.adapter.confirm('SO-TEST-001')
            call_kwargs = session.request.call_args.kwargs
            sent_headers = call_kwargs.get('headers', {})
            expected = hashlib.sha256(b'SO-TEST-001').hexdigest()
            self.assertEqual(sent_headers.get('Idempotency-Key'), expected)
            # Must NOT be the raw reference_id (header injection vector)
            self.assertNotEqual(sent_headers.get('Idempotency-Key'), 'SO-TEST-001')

    def test_confirm_rejects_empty_reference_id(self):
        with self.assertRaises(ValueError):
            self.adapter.confirm('')
        with self.assertRaises(ValueError):
            self.adapter.confirm('   ')


@tagged('post_install', '-at_install', 'p4_01_b')
class TestP401B503RetryBranch(TransactionCase):
    """503/504 retries with longer backoff (S4)."""

    def setUp(self):
        super().setUp()
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client import (
            GearmentApiClient,
            ServiceUnavailableError,
        )
        with mock.patch.dict(
            'os.environ',
            {
                'GEARMENT_API_KEY': 'TEST_KEY',
                'GEARMENT_API_SECRET': 'TEST_SECRET',
                'GEARMENT_API_BASE_URL': 'https://api.gearment.test',
            },
            clear=False,
        ):
            self.client = GearmentApiClient()
        self.ServiceUnavailableError = ServiceUnavailableError

    def test_503_triggers_retry_then_raises(self):
        with mock.patch.object(self.client, '_session') as mock_session_factory, \
             mock.patch(
                 'odoo.addons.multichannel_hub_fulfillment.services'
                 '.gearment_api_client.time.sleep'
             ):
            session = mock.MagicMock()
            session.request.return_value = _stub_response(status_code=503)
            mock_session_factory.return_value = session
            with self.assertRaises(self.ServiceUnavailableError):
                self.client._request('GET', 'api/v3/catalog')
            # 1 initial + 3 retries = 4 attempts on 503
            self.assertEqual(session.request.call_count, 4)

    def test_504_triggers_same_retry_path(self):
        with mock.patch.object(self.client, '_session') as mock_session_factory, \
             mock.patch(
                 'odoo.addons.multichannel_hub_fulfillment.services'
                 '.gearment_api_client.time.sleep'
             ):
            session = mock.MagicMock()
            session.request.return_value = _stub_response(status_code=504)
            mock_session_factory.return_value = session
            with self.assertRaises(self.ServiceUnavailableError):
                self.client._request('GET', 'api/v3/catalog')
            self.assertEqual(session.request.call_count, 4)

    def test_503_then_200_succeeds(self):
        with mock.patch.object(self.client, '_session') as mock_session_factory, \
             mock.patch(
                 'odoo.addons.multichannel_hub_fulfillment.services'
                 '.gearment_api_client.time.sleep'
             ):
            session = mock.MagicMock()
            session.request.side_effect = [
                _stub_response(status_code=503),
                _stub_response(status_code=200, json_body={'ok': True}),
            ]
            mock_session_factory.return_value = session
            result = self.client._request('GET', 'api/v3/catalog')
            self.assertEqual(result, {'ok': True})
            self.assertEqual(session.request.call_count, 2)

    def test_429_path_unchanged(self):
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client import (
            RateLimitError,
        )
        with mock.patch.object(self.client, '_session') as mock_session_factory, \
             mock.patch(
                 'odoo.addons.multichannel_hub_fulfillment.services'
                 '.gearment_api_client.time.sleep'
             ):
            session = mock.MagicMock()
            session.request.return_value = _stub_response(
                status_code=429, headers={'Retry-After': '1'},
            )
            mock_session_factory.return_value = session
            with self.assertRaises(RateLimitError):
                self.client._request('GET', 'api/v3/catalog')
            # 1 initial + 3 retries = 4 attempts on 429 (unchanged)
            self.assertEqual(session.request.call_count, 4)
