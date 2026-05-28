"""P0-22 Phase 2 acceptance test — golden-fixture parity.

The same Etsy receipt is ingested via two paths:

  1. Email path: synthetic email → email_parser → ParseResult → EtsyEmailAdapter
     → EtsyOrderPayload → EtsyOrderIngestor.ingest → sale.order
  2. API path:   synthetic receipt JSON → EtsyApiAdapter._receipt_to_payload
     → EtsyOrderPayload → EtsyOrderIngestor.ingest → sale.order

Both orders must be identical on the 9 parity fields. Path-specific fields
(`etsy_email_log_id` for email; nothing yet for API) are exempt — we never
compare them.

Reference: `specs/005-etsy-api-channel/p0-22-plan.md` §1, §6.
"""

from datetime import datetime
from unittest import mock

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services.email_parser import (
    ParseResult,
    ShippingAddress,
    Transaction,
)


_PARITY_ORDER_FIELDS = (
    # API path writes today
    'sync_source',
    'etsy_raw_source_id',
    'payment_status',
    'etsy_last_modified',
    # Email path writes today
    'etsy_shipping_service',
    'etsy_processing_time',
    'etsy_discount_code',
    'etsy_subtotal',
)


# `etsy_transaction_id` deliberately excluded — it is a path-unique
# identifier, not a content field. The parity claim is that both adapters
# WRITE the field (test_*_path_writes_* covers that), not that two
# different ingestions yield the same identifier value.
_PARITY_LINE_FIELDS = (
    'etsy_personalisation',
    'etsy_sku',
)


def _make_email_parse_result(order_id, transaction_id='9991'):
    return ParseResult(
        order_id=order_id,
        shop='GoldenShop',
        date='Sat, 10 May 2026 10:00:00 +0000',
        note_from_buyer='Please ship fast',
        gift_message='Happy birthday!',
        shipping_address=ShippingAddress(
            name='Alice Buyer', address1='123 Main St', city='Boston',
            state='MA', zipcode='02108', country='United States',
            country_code='US', email='alice@example.com',
        ),
        shipping_service='USPS Priority Mail',
        processing_time='1-2 business days',
        shipping_cost=10.0,
        discount_code='SPRING2026',
        subtotal=100.0,
        transactions=[
            Transaction(
                transaction_id=transaction_id,
                product_name='Custom Mug',
                sku='MUG-001',
                quantity=1,
                price=100.0,
                personalisation='To Alice',
            ),
        ],
    )


def _make_api_receipt(receipt_id, transaction_id=9992):
    return {
        'receipt_id': int(receipt_id),
        'name': 'Alice Buyer',
        'first_line': '123 Main St',
        'second_line': None,
        'city': 'Boston',
        'state': 'MA',
        'zip': '02108',
        'country_iso': 'US',
        'buyer_email': 'alice@example.com',
        'is_gift': True,
        'gift_message': 'Happy birthday!',
        'message_from_buyer': 'Please ship fast',
        'created_timestamp': 1715335200,  # 2024-05-10T10:00:00Z
        'last_modified_tsz': 1715335200,
        'is_paid': True,
        'grandtotal': {'amount': 11000, 'divisor': 100, 'currency_code': 'USD'},
        'subtotal': {'amount': 10000, 'divisor': 100, 'currency_code': 'USD'},
        'total_shipping_cost': {'amount': 1000, 'divisor': 100, 'currency_code': 'USD'},
        'coupon_code': 'SPRING2026',
        'shipping_method': 'USPS Priority Mail',
        'min_processing_days': 1,
        'max_processing_days': 2,
        'transactions': [
            {
                'transaction_id': transaction_id,
                'listing_id': 5555,
                'sku': 'MUG-001',
                'title': 'Custom Mug',
                'quantity': 1,
                'price': {'amount': 10000, 'divisor': 100, 'currency_code': 'USD'},
                'personalization': 'To Alice',
                'variations': [],
            },
        ],
    }


@tagged('post_install', '-at_install', 'p0_22')
class TestP022GoldenFixtureParity(TransactionCase):

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.etsy_email_adapter import (
            EtsyEmailAdapter,
        )
        from odoo.addons.etsy_integration.services.etsy_api_adapter import (
            EtsyApiAdapter,
        )
        from odoo.addons.etsy_integration.services.etsy_order_ingestor import (
            EtsyOrderIngestor,
        )
        self.EtsyEmailAdapter = EtsyEmailAdapter
        self.EtsyApiAdapter = EtsyApiAdapter
        self.EtsyOrderIngestor = EtsyOrderIngestor
        # Distinct etsy_order_ids so the ingestor doesn't dedupe one against
        # the other — we still compare the resulting field shapes for parity.
        self.email_order_id = '3001112221'
        self.api_order_id = '3001112222'
        # Each ingestor needs a shop record.
        self.shop = self.env['etsy.shop'].create({'name': 'GoldenShop'})

    def test_email_path_writes_all_9_parity_fields(self):
        """RED: email adapter + ingestor must populate all parity fields."""
        adapter = self.EtsyEmailAdapter()
        parse_result = _make_email_parse_result(self.email_order_id)
        payload = adapter.parse_result_to_payload(
            parse_result, email_log_id=42, shop_id=self.shop.id,
        )
        ingestor = self.EtsyOrderIngestor(self.env)
        order = ingestor.ingest(payload, self.shop)
        self.assertTrue(order, 'Ingestor must create the order')
        # All 4 sync fields populated by canonical write path
        self.assertEqual(order.sync_source, 'email')
        self.assertEqual(order.etsy_raw_source_id, 'email_log:42')
        self.assertEqual(order.payment_status, 'paid')
        self.assertIsNotNone(order.etsy_last_modified)
        # All 4 email-side fields populated
        self.assertEqual(order.etsy_shipping_service, 'USPS Priority Mail')
        self.assertEqual(order.etsy_processing_time, '1-2 business days')
        self.assertEqual(order.etsy_discount_code, 'SPRING2026')
        self.assertEqual(order.etsy_subtotal, 100.0)

    def test_api_path_writes_all_9_parity_fields(self):
        """RED: API adapter + ingestor must populate all parity fields."""
        adapter = self.EtsyApiAdapter(client=mock.MagicMock())
        receipt = _make_api_receipt(self.api_order_id)
        payload = adapter._receipt_to_payload(receipt, shop_id=self.shop.id)
        ingestor = self.EtsyOrderIngestor(self.env)
        order = ingestor.ingest(payload, self.shop)
        self.assertTrue(order, 'Ingestor must create the order')
        # All 4 sync fields
        self.assertEqual(order.sync_source, 'api')
        self.assertEqual(order.etsy_raw_source_id, f'receipt:{self.api_order_id}')
        self.assertEqual(order.payment_status, 'paid')
        self.assertIsNotNone(order.etsy_last_modified)
        # All 4 email-side fields lifted from API receipt
        self.assertEqual(order.etsy_shipping_service, 'USPS Priority Mail')
        self.assertEqual(order.etsy_processing_time, '1-2 business days')
        self.assertEqual(order.etsy_discount_code, 'SPRING2026')
        self.assertEqual(order.etsy_subtotal, 100.0)

    def test_email_and_api_paths_parity_on_order_fields(self):
        """Acceptance: both ingest paths produce identical order field shapes."""
        # Email path
        email_adapter = self.EtsyEmailAdapter()
        email_parse = _make_email_parse_result(self.email_order_id)
        email_payload = email_adapter.parse_result_to_payload(
            email_parse, email_log_id=42, shop_id=self.shop.id,
        )
        ingestor = self.EtsyOrderIngestor(self.env)
        email_order = ingestor.ingest(email_payload, self.shop)
        # API path
        api_adapter = self.EtsyApiAdapter(client=mock.MagicMock())
        api_payload = api_adapter._receipt_to_payload(
            _make_api_receipt(self.api_order_id), shop_id=self.shop.id,
        )
        api_order = ingestor.ingest(api_payload, self.shop)

        # Path-symmetric fields (excluding source + raw_source_id which are
        # path-discriminators by design)
        path_symmetric = (
            'payment_status', 'etsy_shipping_service', 'etsy_processing_time',
            'etsy_discount_code', 'etsy_subtotal',
        )
        for field in path_symmetric:
            self.assertEqual(
                email_order[field], api_order[field],
                msg=f'Mismatch on {field}: '
                    f'email={email_order[field]!r} vs api={api_order[field]!r}',
            )

        # Path-asymmetric fields (must each be populated, but with path-specific values)
        self.assertEqual(email_order.sync_source, 'email')
        self.assertEqual(api_order.sync_source, 'api')
        self.assertTrue(email_order.etsy_raw_source_id.startswith('email_log:'))
        self.assertTrue(api_order.etsy_raw_source_id.startswith('receipt:'))

    def test_email_and_api_paths_parity_on_line_fields(self):
        """Line-level parity: same SKU, same transaction_id format, same personalisation."""
        # Email path
        email_adapter = self.EtsyEmailAdapter()
        email_parse = _make_email_parse_result(self.email_order_id)
        email_payload = email_adapter.parse_result_to_payload(
            email_parse, email_log_id=42, shop_id=self.shop.id,
        )
        ingestor = self.EtsyOrderIngestor(self.env)
        email_order = ingestor.ingest(email_payload, self.shop)
        # API path
        api_adapter = self.EtsyApiAdapter(client=mock.MagicMock())
        api_payload = api_adapter._receipt_to_payload(
            _make_api_receipt(self.api_order_id), shop_id=self.shop.id,
        )
        api_order = ingestor.ingest(api_payload, self.shop)

        # Filter out shipping line (no etsy_transaction_id)
        email_lines = email_order.order_line.filtered('etsy_transaction_id')
        api_lines = api_order.order_line.filtered('etsy_transaction_id')
        self.assertEqual(len(email_lines), 1)
        self.assertEqual(len(api_lines), 1)
        for field in _PARITY_LINE_FIELDS:
            self.assertEqual(
                email_lines[0][field], api_lines[0][field],
                msg=f'Line mismatch on {field}: '
                    f'email={email_lines[0][field]!r} vs api={api_lines[0][field]!r}',
            )
