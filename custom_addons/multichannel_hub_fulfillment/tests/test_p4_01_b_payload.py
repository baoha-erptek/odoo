"""P4-01-B Phase 2 ORM — new GearmentOrderPayload schema + builder + Money proto.

Closes contract gaps G2 (payload shape) and G3 (Money proto in /orders/price
response) per `specs/004-fulfillment-routing/findings.md` 2026-05-09 readiness
probe. The legacy schema (external_order_id / address dict / quantity /
product_id) is fully replaced — see plan §3 Sub-phase B.

P4-01-FIX-PAYLOAD-SCHEMA (2026-05-10): line_items shape further corrected
after live `/orders/draft` rejected `product_id` + flat `design_url_front/back`.
Real fields: `legacy_id` + `printing_options[]` (see test_p4_01_fix_payload_schema.py).
"""

from decimal import Decimal
from unittest import mock

from odoo.tests.common import TransactionCase, tagged


def _payload_classes():
    """Defer import so module loads even when GREEN hasn't shipped yet."""
    from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
        GearmentAddress,
        GearmentLineItem,
        GearmentOrderPayload,
    )
    return GearmentAddress, GearmentLineItem, GearmentOrderPayload


@tagged('post_install', '-at_install', 'p4_01_b')
class TestP401BPayloadSchema(TransactionCase):
    """The new GearmentOrderPayload mirrors the live /orders/draft contract."""

    def test_payload_carries_reference_id(self):
        payload = _make_payload(reference_id='SO-2026-00123')
        self.assertEqual(payload.reference_id, 'SO-2026-00123')

    def test_payload_carries_addresses_tuple(self):
        addr = _make_address()
        payload = _make_payload(addresses=(addr,))
        self.assertIsInstance(payload.addresses, tuple)
        self.assertEqual(payload.addresses[0].first_name, 'Alice')
        self.assertEqual(payload.addresses[0].last_name, 'Buyer')
        self.assertEqual(payload.addresses[0].street_1, '123 Main St')
        self.assertEqual(payload.addresses[0].zip_code, '02108')
        self.assertEqual(payload.addresses[0].country_code, 'US')

    def test_payload_carries_line_items_tuple(self):
        line = _make_line_item()
        payload = _make_payload(line_items=(line,))
        self.assertIsInstance(payload.line_items, tuple)
        self.assertEqual(payload.line_items[0].legacy_id, 1234)
        self.assertEqual(payload.line_items[0].quantity, 1)

    def test_payload_idempotency_key_is_sha256(self):
        payload = _make_payload(reference_id='SO-2026-00123')
        self.assertEqual(len(payload.idempotency_key), 64)
        # Same input → same key (idempotent)
        same = _make_payload(reference_id='SO-2026-00123')
        self.assertEqual(payload.idempotency_key, same.idempotency_key)

    def test_payload_serialize_envelope_is_data_object(self):
        """`/orders/draft` rejected `data: []` per probe S3 — single object envelope."""
        payload = _make_payload(reference_id='SO-2026-00123')
        body = payload.serialize()
        # Probe S3 finding: /orders/draft uses {"data": {...}} bare object envelope
        self.assertIn('data', body)
        self.assertIsInstance(body['data'], dict)

    def test_payload_serialize_includes_reference_id_in_data(self):
        payload = _make_payload(reference_id='SO-2026-00123')
        body = payload.serialize()
        self.assertEqual(body['data']['reference_id'], 'SO-2026-00123')

    def test_payload_serialize_addresses_use_real_field_names(self):
        addr = _make_address()
        payload = _make_payload(addresses=(addr,))
        body = payload.serialize()
        addr_dict = body['data']['addresses'][0]
        self.assertEqual(addr_dict['first_name'], 'Alice')
        self.assertEqual(addr_dict['last_name'], 'Buyer')
        self.assertEqual(addr_dict['street_1'], '123 Main St')
        self.assertEqual(addr_dict['zip_code'], '02108')
        self.assertEqual(addr_dict['country_code'], 'US')

    def test_payload_serialize_line_items_uses_real_key(self):
        """Probe G2: line items live under `line_items` not `items`.

        Schema corrected by P4-01-FIX-PAYLOAD-SCHEMA: `legacy_id` not `product_id`.
        """
        line = _make_line_item()
        payload = _make_payload(line_items=(line,))
        body = payload.serialize()
        self.assertIn('line_items', body['data'])
        self.assertNotIn('items', body['data'])
        self.assertEqual(body['data']['line_items'][0]['legacy_id'], 1234)


@tagged('post_install', '-at_install', 'p4_01_b')
class TestP401BMoneyProto(TransactionCase):
    """`_money_to_decimal` decodes Gearment's proto-Money shape."""

    def setUp(self):
        super().setUp()
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            _money_to_decimal,
        )
        self._money_to_decimal = _money_to_decimal

    def test_money_units_only(self):
        result = self._money_to_decimal(
            {'currency_code': 'USD', 'units': '45', 'nanos': 0}
        )
        self.assertEqual(result, (Decimal('45.000000000'), 'USD'))

    def test_money_units_and_nanos(self):
        # 45.99 USD — 45 units + 990_000_000 nanos
        result = self._money_to_decimal(
            {'currency_code': 'USD', 'units': '45', 'nanos': 990000000}
        )
        amount, currency = result
        self.assertEqual(currency, 'USD')
        # Float comparison is fine here since 990M nanos = 0.99 exactly
        self.assertEqual(amount, Decimal('45.990000000'))

    def test_money_zero(self):
        result = self._money_to_decimal(
            {'currency_code': 'USD', 'units': '0', 'nanos': 0}
        )
        self.assertEqual(result[0], Decimal('0E-9'))

    def test_money_handles_missing_keys(self):
        # If Gearment ever returns partial Money (real probe S3 saw this on
        # some endpoints), we degrade to zero rather than KeyError.
        result = self._money_to_decimal({'currency_code': 'USD'})
        self.assertEqual(result, (Decimal('0E-9'), 'USD'))

    def test_money_handles_none(self):
        result = self._money_to_decimal(None)
        self.assertEqual(result, (Decimal('0E-9'), ''))


# ---------------------------------------------------------------- helpers

def _make_address(**overrides):
    GearmentAddress, _, _ = _payload_classes()
    defaults = dict(
        first_name='Alice', last_name='Buyer',
        street_1='123 Main St', street_2=None,
        city='Boston', state='MA', zip_code='02108',
        country_code='US', phone=None, email=None,
    )
    defaults.update(overrides)
    return GearmentAddress(**defaults)


def _make_line_item(**overrides):
    _, GearmentLineItem, _ = _payload_classes()
    defaults = dict(
        legacy_id=1234, quantity=1, sku='MUG-001',
        printing_options=({'location_code': 'front', 'url': 'https://example/x.png'},),
        personalisation=None, custom_attributes=None,
    )
    defaults.update(overrides)
    return GearmentLineItem(**defaults)


def _make_payload(**overrides):
    _, _, GearmentOrderPayload = _payload_classes()
    defaults = dict(
        reference_id='SO-2026-00123',
        store_id='12345',
        addresses=(_make_address(),),
        line_items=(_make_line_item(),),
        shipping_method=None,
        notes=None,
        custom_attributes=None,
    )
    defaults.update(overrides)
    return GearmentOrderPayload(**defaults)
