"""P0-16b2 — RED-phase tests for EtsyApiAdapter.

`EtsyApiAdapter` implements `EtsyChannelAdapter` Protocol against the
real Etsy v3 receipts endpoint. All tests here mock `EtsyApiClient.get`
so no live HTTP is issued; payload-mapping correctness is verified
against representative receipt JSON crafted in this file.

P0-16c will add cassette-style JSON fixtures + a syncer that drives
this adapter end-to-end. P0-16b2 stops at the adapter boundary.

References: spec 005 T021, T028, T030 (T030 partial — scope limited
to mapping correctness + pagination; live cassette recording deferred).
"""

from datetime import datetime, timezone
from unittest import mock

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services.etsy_order_payload import (
    EtsyOrderPayload,
)


def _make_receipt(receipt_id=1234, **overrides):
    """Build a representative Etsy receipt dict (v3 schema)."""
    receipt = {
        "receipt_id": receipt_id,
        "receipt_type": 0,
        "name": "Alice Buyer",
        "first_line": "123 Main St",
        "second_line": None,
        "city": "Boston",
        "state": "MA",
        "zip": "02108",
        "country_iso": "US",
        "buyer_email": "alice@example.com",
        "is_gift": False,
        "gift_message": "",
        "message_from_buyer": "Please wrap as gift",
        "create_timestamp": 1714294800,  # 2024-04-28T09:00:00Z
        "created_timestamp": 1714294800,
        "is_paid": True,
        "grandtotal": {"amount": 11000, "divisor": 100, "currency_code": "USD"},
        "subtotal": {"amount": 10000, "divisor": 100, "currency_code": "USD"},
        "total_shipping_cost": {"amount": 1000, "divisor": 100, "currency_code": "USD"},
        "transactions": [
            {
                "transaction_id": 9999,
                "listing_id": 5555,
                "sku": "MUG-001",
                "title": "Custom Mug",
                "quantity": 1,
                "price": {"amount": 10000, "divisor": 100, "currency_code": "USD"},
                "variations": [
                    {"property_id": 1, "formatted_name": "Color",
                     "formatted_value": "Blue"},
                ],
            },
        ],
    }
    receipt.update(overrides)
    return receipt


def _make_response(results, next_offset=None):
    """Build a paginated Etsy receipts list response."""
    return {
        "count": len(results),
        "results": results,
        "next_offset": next_offset,
    }


@tagged('post_install', '-at_install')
class TestEtsyApiAdapterImplementsProtocol(TransactionCase):

    def test_adapter_is_instance_of_protocol(self):
        from odoo.addons.etsy_integration.services.etsy_api_adapter import (
            EtsyApiAdapter,
        )
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            EtsyChannelAdapter,
        )
        client = mock.Mock()
        adapter = EtsyApiAdapter(client)
        self.assertIsInstance(adapter, EtsyChannelAdapter)


@tagged('post_install', '-at_install')
class TestEtsyApiAdapterFetchNewOrders(TransactionCase):

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.etsy_api_adapter import (
            EtsyApiAdapter,
        )
        self.client = mock.Mock()
        self.adapter = EtsyApiAdapter(self.client)
        self.since = datetime(2026, 4, 1, 0, 0, 0)

    def test_fetch_returns_iterator(self):
        self.client.get.return_value = _make_response([])
        result = self.adapter.fetch_new_orders(shop_id=42, since=self.since)
        self.assertTrue(hasattr(result, '__iter__'))
        self.assertTrue(hasattr(result, '__next__'))

    def test_fetch_yields_payload_per_receipt(self):
        self.client.get.return_value = _make_response([
            _make_receipt(receipt_id=1001),
            _make_receipt(receipt_id=1002),
        ])
        payloads = list(self.adapter.fetch_new_orders(shop_id=42, since=self.since))
        self.assertEqual(len(payloads), 2)
        self.assertIsInstance(payloads[0], EtsyOrderPayload)
        self.assertEqual(payloads[0].etsy_receipt_id, "1001")
        self.assertEqual(payloads[1].etsy_receipt_id, "1002")

    def test_fetch_paginates_when_next_offset_present(self):
        page1 = _make_response(
            [_make_receipt(receipt_id=1001)], next_offset=1,
        )
        page2 = _make_response(
            [_make_receipt(receipt_id=1002)], next_offset=None,
        )
        self.client.get.side_effect = [page1, page2]
        payloads = list(self.adapter.fetch_new_orders(shop_id=42, since=self.since))
        self.assertEqual(len(payloads), 2)
        self.assertEqual(self.client.get.call_count, 2)

    def test_fetch_stops_when_results_shorter_than_limit(self):
        """If a response returns fewer than `limit` results AND no
        next_offset, stop paginating (defense against APIs that omit
        next_offset on the final page)."""
        partial = _make_response(
            [_make_receipt(receipt_id=1001)] * 3, next_offset=None,
        )
        self.client.get.return_value = partial
        list(self.adapter.fetch_new_orders(shop_id=42, since=self.since))
        self.assertEqual(self.client.get.call_count, 1)

    def test_fetch_passes_min_last_modified_unix_timestamp(self):
        self.client.get.return_value = _make_response([])
        list(self.adapter.fetch_new_orders(shop_id=42, since=self.since))
        called_path = self.client.get.call_args.args[0]
        called_params = self.client.get.call_args.kwargs.get('params', {})
        self.assertIn('shops/42/receipts', called_path)
        # min_last_modified must be Unix epoch seconds (integer).
        expected_ts = int(self.since.replace(tzinfo=timezone.utc).timestamp())
        self.assertEqual(called_params.get('min_last_modified'), expected_ts)

    def test_fetch_with_no_since_omits_min_last_modified(self):
        """First-ever sync (cursor NULL on shop) — no `since` filter."""
        self.client.get.return_value = _make_response([])
        list(self.adapter.fetch_new_orders(shop_id=42, since=None))
        called_params = self.client.get.call_args.kwargs.get('params', {})
        self.assertNotIn('min_last_modified', called_params)


@tagged('post_install', '-at_install')
class TestEtsyApiAdapterReceiptMapping(TransactionCase):

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.etsy_api_adapter import (
            EtsyApiAdapter,
        )
        self.adapter = EtsyApiAdapter(mock.Mock())

    def test_maps_basic_identifiers(self):
        receipt = _make_receipt(receipt_id=2001)
        payload = self.adapter._receipt_to_payload(receipt, shop_id=42)
        self.assertEqual(payload.etsy_shop_id, 42)
        self.assertEqual(payload.etsy_receipt_id, "2001")
        self.assertEqual(payload.etsy_order_id, "2001")  # receipt_id == order_id

    def test_maps_grandtotal_using_divisor(self):
        receipt = _make_receipt(grandtotal={
            "amount": 12345, "divisor": 100, "currency_code": "USD",
        })
        payload = self.adapter._receipt_to_payload(receipt, shop_id=42)
        self.assertEqual(payload.amount_total, 123.45)
        self.assertEqual(payload.currency, "USD")

    def test_maps_shipping_total_using_divisor(self):
        receipt = _make_receipt(total_shipping_cost={
            "amount": 1500, "divisor": 100, "currency_code": "USD",
        })
        payload = self.adapter._receipt_to_payload(receipt, shop_id=42)
        self.assertEqual(payload.shipping_total, 15.00)

    def test_maps_buyer_country(self):
        receipt = _make_receipt(country_iso="DE")
        payload = self.adapter._receipt_to_payload(receipt, shop_id=42)
        self.assertEqual(payload.buyer_country, "DE")

    def test_maps_order_date_from_unix_timestamp(self):
        receipt = _make_receipt(created_timestamp=1714294800)
        payload = self.adapter._receipt_to_payload(receipt, shop_id=42)
        self.assertEqual(
            payload.order_date,
            datetime(2024, 4, 28, 9, 0, 0),
        )

    def test_maps_buyer_message_from_message_from_buyer(self):
        receipt = _make_receipt(message_from_buyer="ship by Friday")
        payload = self.adapter._receipt_to_payload(receipt, shop_id=42)
        self.assertEqual(payload.buyer_message, "ship by Friday")

    def test_buyer_message_empty_string_becomes_none(self):
        """An empty string from Etsy normalizes to None — keeps the
        downstream renderer's `or '—'` fallback simple."""
        receipt = _make_receipt(message_from_buyer="")
        payload = self.adapter._receipt_to_payload(receipt, shop_id=42)
        self.assertIsNone(payload.buyer_message)

    def test_maps_shipping_address(self):
        receipt = _make_receipt()
        payload = self.adapter._receipt_to_payload(receipt, shop_id=42)
        addr = payload.shipping_address
        self.assertEqual(addr.name, "Alice Buyer")
        self.assertEqual(addr.street_1, "123 Main St")
        self.assertIsNone(addr.street_2)
        self.assertEqual(addr.city, "Boston")
        self.assertEqual(addr.state, "MA")
        self.assertEqual(addr.zip, "02108")
        self.assertEqual(addr.country_code, "US")

    def test_maps_line_items(self):
        receipt = _make_receipt()
        payload = self.adapter._receipt_to_payload(receipt, shop_id=42)
        self.assertEqual(len(payload.line_items), 1)
        item = payload.line_items[0]
        self.assertEqual(item.transaction_id, "9999")
        self.assertEqual(item.listing_id, "5555")
        self.assertEqual(item.title, "Custom Mug")
        self.assertEqual(item.sku, "MUG-001")
        self.assertEqual(item.quantity, 1)
        self.assertEqual(item.unit_price, 100.00)

    def test_maps_variations_list_to_flat_dict(self):
        receipt = _make_receipt(transactions=[{
            "transaction_id": 1,
            "listing_id": 1,
            "sku": "X",
            "title": "Y",
            "quantity": 1,
            "price": {"amount": 100, "divisor": 100, "currency_code": "USD"},
            "variations": [
                {"property_id": 1, "formatted_name": "Color",
                 "formatted_value": "Blue"},
                {"property_id": 2, "formatted_name": "Size",
                 "formatted_value": "Large"},
            ],
        }])
        payload = self.adapter._receipt_to_payload(receipt, shop_id=42)
        item = payload.line_items[0]
        self.assertEqual(item.variations, {"Color": "Blue", "Size": "Large"})

    def test_provenance_fields_set(self):
        receipt = _make_receipt(receipt_id=3003)
        payload = self.adapter._receipt_to_payload(receipt, shop_id=42)
        self.assertEqual(payload.source, "api")
        self.assertEqual(payload.raw_source_id, "receipt:3003")
        self.assertIsNotNone(payload.fetched_at)

    def test_is_gift_passthrough(self):
        receipt = _make_receipt(is_gift=True, gift_message="Happy Birthday")
        payload = self.adapter._receipt_to_payload(receipt, shop_id=42)
        self.assertTrue(payload.is_gift)
        self.assertEqual(payload.gift_message, "Happy Birthday")

    def test_payment_status_from_is_paid(self):
        paid = _make_receipt(is_paid=True)
        unpaid = _make_receipt(is_paid=False)
        self.assertEqual(
            self.adapter._receipt_to_payload(paid, shop_id=42).payment_status,
            "paid",
        )
        self.assertEqual(
            self.adapter._receipt_to_payload(unpaid, shop_id=42).payment_status,
            "unpaid",
        )


@tagged('post_install', '-at_install')
class TestEtsyApiAdapterHealthCheck(TransactionCase):

    def setUp(self):
        super().setUp()
        from odoo.addons.etsy_integration.services.etsy_api_adapter import (
            EtsyApiAdapter,
        )
        self.client = mock.Mock()
        self.adapter = EtsyApiAdapter(self.client)

    def test_health_ok_on_successful_ping(self):
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            HealthStatus,
        )
        self.client.ping.return_value = {"user_id": 12345}
        self.assertEqual(
            self.adapter.health_check(shop_id=42),
            HealthStatus.OK,
        )

    def test_health_degraded_on_rate_limit(self):
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            HealthStatus,
        )
        from odoo.addons.etsy_integration.services.etsy_api_client import (
            RateLimitError,
        )
        self.client.ping.side_effect = RateLimitError("rate limited")
        self.assertEqual(
            self.adapter.health_check(shop_id=42),
            HealthStatus.DEGRADED,
        )

    def test_health_down_on_value_error(self):
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            HealthStatus,
        )
        self.client.ping.side_effect = ValueError("auth failed")
        self.assertEqual(
            self.adapter.health_check(shop_id=42),
            HealthStatus.DOWN,
        )
