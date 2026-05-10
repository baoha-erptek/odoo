"""P0-22 Phase 2 ORM — adapter mapping unit tests.

These tests verify that the canonical `EtsyOrderPayload` carries the four
email-side fields (shipping_service, processing_time, discount_code, subtotal)
plus a `name_override` per line item, and that both `EtsyApiAdapter` and the
new `EtsyEmailAdapter` populate them correctly.

Reference: `specs/005-etsy-api-channel/p0-22-plan.md` §3, §5 (T0-22-04).
"""

from datetime import datetime
from unittest import mock

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services.email_parser import (
    ParseResult,
    ShippingAddress,
    Transaction,
)
from odoo.addons.etsy_integration.services.etsy_order_payload import (
    EtsyAddressPayload,
    EtsyLineItemPayload,
    EtsyOrderPayload,
)


def _make_parse_result(**overrides):
    """Synthetic ParseResult with all 9 parity fields populated."""
    defaults = dict(
        order_id='3001112223',
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
                transaction_id='T-9999',
                product_name='Custom Mug',
                sku='MUG-001',
                quantity=1,
                price=100.0,
                personalisation='To Alice',
            ),
        ],
    )
    defaults.update(overrides)
    return ParseResult(**defaults)


def _make_receipt_with_extras(**overrides):
    """Etsy v3 receipt with the optional shipping_service / processing_time
    fields populated. Real receipts may or may not carry these — adapter must
    handle absence gracefully.
    """
    defaults = {
        'receipt_id': 3001112223,
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
        'discount_amt': {'amount': 0, 'divisor': 100, 'currency_code': 'USD'},
        'coupon_code': 'SPRING2026',
        'shipping_method': 'USPS Priority Mail',
        'shipping_carrier': 'USPS',
        'min_processing_days': 1,
        'max_processing_days': 2,
        'transactions': [
            {
                'transaction_id': 9999,
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
    defaults.update(overrides)
    return defaults


@tagged('post_install', '-at_install', 'p0_22')
class TestP022PayloadSchema(TransactionCase):
    """The canonical payload must carry the 4 new optional fields."""

    def test_payload_has_shipping_service_field(self):
        payload = _build_minimal_payload(shipping_service='USPS Priority Mail')
        self.assertEqual(payload.shipping_service, 'USPS Priority Mail')

    def test_payload_has_processing_time_field(self):
        payload = _build_minimal_payload(processing_time='1-2 business days')
        self.assertEqual(payload.processing_time, '1-2 business days')

    def test_payload_has_discount_code_field(self):
        payload = _build_minimal_payload(discount_code='SPRING2026')
        self.assertEqual(payload.discount_code, 'SPRING2026')

    def test_payload_has_subtotal_field(self):
        payload = _build_minimal_payload(subtotal=100.0)
        self.assertEqual(payload.subtotal, 100.0)

    def test_payload_optional_fields_default_to_none(self):
        payload = _build_minimal_payload()
        self.assertIsNone(payload.shipping_service)
        self.assertIsNone(payload.processing_time)
        self.assertIsNone(payload.discount_code)
        self.assertIsNone(payload.subtotal)

    def test_line_item_payload_has_name_override_field(self):
        line = EtsyLineItemPayload(
            listing_id='5555',
            transaction_id='9999',
            title='Custom Mug',
            sku='MUG-001',
            quantity=1,
            unit_price=100.0,
            name_override='Custom Mug — engraved',
        )
        self.assertEqual(line.name_override, 'Custom Mug — engraved')

    def test_line_item_name_override_defaults_to_none(self):
        line = EtsyLineItemPayload(
            listing_id='5555',
            transaction_id='9999',
            title='Custom Mug',
            sku='MUG-001',
            quantity=1,
            unit_price=100.0,
        )
        self.assertIsNone(line.name_override)


@tagged('post_install', '-at_install', 'p0_22')
class TestP022EmailAdapter(TransactionCase):
    """`EtsyEmailAdapter` converts a `ParseResult` into a canonical payload."""

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.etsy_email_adapter import (
            EtsyEmailAdapter,
        )
        self.EtsyEmailAdapter = EtsyEmailAdapter

    def test_email_adapter_maps_shipping_service(self):
        adapter = self.EtsyEmailAdapter()
        parse_result = _make_parse_result()
        payload = adapter.parse_result_to_payload(
            parse_result, email_log_id=42, shop_id=1,
        )
        self.assertEqual(payload.shipping_service, 'USPS Priority Mail')

    def test_email_adapter_maps_processing_time(self):
        adapter = self.EtsyEmailAdapter()
        parse_result = _make_parse_result()
        payload = adapter.parse_result_to_payload(
            parse_result, email_log_id=42, shop_id=1,
        )
        self.assertEqual(payload.processing_time, '1-2 business days')

    def test_email_adapter_maps_discount_code(self):
        adapter = self.EtsyEmailAdapter()
        parse_result = _make_parse_result()
        payload = adapter.parse_result_to_payload(
            parse_result, email_log_id=42, shop_id=1,
        )
        self.assertEqual(payload.discount_code, 'SPRING2026')

    def test_email_adapter_maps_subtotal(self):
        adapter = self.EtsyEmailAdapter()
        parse_result = _make_parse_result()
        payload = adapter.parse_result_to_payload(
            parse_result, email_log_id=42, shop_id=1,
        )
        self.assertEqual(payload.subtotal, 100.0)

    def test_email_adapter_sets_source_email(self):
        adapter = self.EtsyEmailAdapter()
        parse_result = _make_parse_result()
        payload = adapter.parse_result_to_payload(
            parse_result, email_log_id=42, shop_id=1,
        )
        self.assertEqual(payload.source, 'email')

    def test_email_adapter_sets_raw_source_id_to_email_log_pattern(self):
        adapter = self.EtsyEmailAdapter()
        parse_result = _make_parse_result()
        payload = adapter.parse_result_to_payload(
            parse_result, email_log_id=42, shop_id=1,
        )
        self.assertEqual(payload.raw_source_id, 'email_log:42')

    def test_email_adapter_maps_transaction_id(self):
        adapter = self.EtsyEmailAdapter()
        parse_result = _make_parse_result()
        payload = adapter.parse_result_to_payload(
            parse_result, email_log_id=42, shop_id=1,
        )
        self.assertEqual(payload.line_items[0].transaction_id, 'T-9999')

    def test_email_adapter_maps_line_personalisation(self):
        adapter = self.EtsyEmailAdapter()
        parse_result = _make_parse_result()
        payload = adapter.parse_result_to_payload(
            parse_result, email_log_id=42, shop_id=1,
        )
        self.assertEqual(payload.line_items[0].personalisation, 'To Alice')

    def test_email_adapter_maps_line_sku(self):
        adapter = self.EtsyEmailAdapter()
        parse_result = _make_parse_result()
        payload = adapter.parse_result_to_payload(
            parse_result, email_log_id=42, shop_id=1,
        )
        self.assertEqual(payload.line_items[0].sku, 'MUG-001')

    def test_email_adapter_handles_missing_optional_fields(self):
        """Email parser may emit empty strings; adapter normalises to None."""
        adapter = self.EtsyEmailAdapter()
        parse_result = _make_parse_result(
            shipping_service='',
            processing_time='',
            discount_code='',
            subtotal=0.0,
        )
        payload = adapter.parse_result_to_payload(
            parse_result, email_log_id=42, shop_id=1,
        )
        self.assertIsNone(payload.shipping_service)
        self.assertIsNone(payload.processing_time)
        self.assertIsNone(payload.discount_code)
        self.assertEqual(payload.subtotal, 0.0)


@tagged('post_install', '-at_install', 'p0_22')
class TestP022ApiAdapterExtensions(TransactionCase):
    """`EtsyApiAdapter` populates the new payload fields from receipt JSON."""

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.etsy_api_adapter import (
            EtsyApiAdapter,
        )
        self.adapter = EtsyApiAdapter(client=mock.MagicMock())

    def test_api_adapter_extracts_shipping_service_from_shipping_method(self):
        receipt = _make_receipt_with_extras()
        payload = self.adapter._receipt_to_payload(receipt, shop_id=1)
        self.assertEqual(payload.shipping_service, 'USPS Priority Mail')

    def test_api_adapter_extracts_processing_time(self):
        receipt = _make_receipt_with_extras()
        payload = self.adapter._receipt_to_payload(receipt, shop_id=1)
        self.assertEqual(payload.processing_time, '1-2 business days')

    def test_api_adapter_extracts_discount_code_from_coupon_code(self):
        receipt = _make_receipt_with_extras()
        payload = self.adapter._receipt_to_payload(receipt, shop_id=1)
        self.assertEqual(payload.discount_code, 'SPRING2026')

    def test_api_adapter_extracts_subtotal(self):
        receipt = _make_receipt_with_extras()
        payload = self.adapter._receipt_to_payload(receipt, shop_id=1)
        self.assertEqual(payload.subtotal, 100.0)

    def test_api_adapter_handles_missing_shipping_service(self):
        receipt = _make_receipt_with_extras(shipping_method=None)
        payload = self.adapter._receipt_to_payload(receipt, shop_id=1)
        self.assertIsNone(payload.shipping_service)

    def test_api_adapter_handles_missing_processing_time(self):
        receipt = _make_receipt_with_extras(
            min_processing_days=None,
            max_processing_days=None,
        )
        payload = self.adapter._receipt_to_payload(receipt, shop_id=1)
        self.assertIsNone(payload.processing_time)

    def test_api_adapter_handles_missing_coupon_code(self):
        receipt = _make_receipt_with_extras(coupon_code=None)
        payload = self.adapter._receipt_to_payload(receipt, shop_id=1)
        self.assertIsNone(payload.discount_code)


def _build_minimal_payload(**overrides):
    """Construct an EtsyOrderPayload with the minimum required fields set
    plus any of the new optional fields under test.
    """
    defaults = dict(
        etsy_shop_id=1,
        etsy_receipt_id='3001112223',
        etsy_order_id='3001112223',
        buyer_name='Alice Buyer',
        buyer_country='US',
        order_date=datetime(2026, 5, 10, 10, 0),
        currency='USD',
        amount_total=110.0,
        shipping_total=10.0,
        line_items=tuple(),
        shipping_address=EtsyAddressPayload(
            name='Alice Buyer', street_1='123 Main St', street_2=None,
            city='Boston', state='MA', zip='02108', country_code='US',
        ),
        buyer_message=None,
        buyer_email='alice@example.com',
        listing_id=None,
        payment_status='paid',
        is_gift=False,
        gift_message=None,
        source='email',
        fetched_at=datetime(2026, 5, 10, 10, 0),
        raw_source_id='email_log:42',
        last_modified=datetime(2026, 5, 10, 10, 0),
    )
    defaults.update(overrides)
    return EtsyOrderPayload(**defaults)
