"""P0-16a — RED-phase contract tests for EtsyOrderPayload.

These tests define the contract for the canonical in-memory payload
emitted by every adapter (`EtsyApiAdapter`, future `EtsyEmailAdapter`)
and consumed by `EtsyOrderIngestor`. Per `findings.md` 2026-04-28,
the dataclasses live in `etsy_integration/services/etsy_order_payload.py`
(NOT `multichannel_hub_core` — see findings entry for rationale).

Reference: `specs/005-etsy-api-channel/data-model.md` §"Adapter contract",
lines 215-258 (revised by findings entry 2026-04-28).
"""

from dataclasses import FrozenInstanceError
from datetime import datetime

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEtsyAddressPayload(TransactionCase):
    """Frozen dataclass for the buyer's shipping address.

    Required fields: name, street_1, city, zip, country_code.
    Optional (None-able): street_2, state.
    """

    def test_construction_with_all_fields(self):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyAddressPayload,
        )
        addr = EtsyAddressPayload(
            name="Alice Buyer",
            street_1="123 Main St",
            street_2="Apt 4B",
            city="Berlin",
            state="BE",
            zip="10001",
            country_code="DE",
        )
        self.assertEqual(addr.name, "Alice Buyer")
        self.assertEqual(addr.country_code, "DE")

    def test_optional_fields_accept_none(self):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyAddressPayload,
        )
        addr = EtsyAddressPayload(
            name="Bob",
            street_1="1 Road",
            street_2=None,
            city="Paris",
            state=None,
            zip="75001",
            country_code="FR",
        )
        self.assertIsNone(addr.street_2)
        self.assertIsNone(addr.state)

    def test_immutable(self):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyAddressPayload,
        )
        addr = EtsyAddressPayload(
            name="Carol",
            street_1="2 Lane",
            street_2=None,
            city="Rome",
            state=None,
            zip="00100",
            country_code="IT",
        )
        with self.assertRaises(FrozenInstanceError):
            addr.city = "Milan"

    def test_equality_by_value(self):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyAddressPayload,
        )
        a = EtsyAddressPayload(
            name="Same", street_1="1", street_2=None, city="X",
            state=None, zip="00000", country_code="US",
        )
        b = EtsyAddressPayload(
            name="Same", street_1="1", street_2=None, city="X",
            state=None, zip="00000", country_code="US",
        )
        self.assertEqual(a, b)

    def test_hashable_collapses_duplicates_in_set(self):
        """All address fields are str|None — hashable, so the dataclass is too."""
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyAddressPayload,
        )
        a = EtsyAddressPayload(
            name="X", street_1="1", street_2=None, city="Y",
            state=None, zip="z", country_code="US",
        )
        b = EtsyAddressPayload(
            name="X", street_1="1", street_2=None, city="Y",
            state=None, zip="z", country_code="US",
        )
        self.assertEqual(len({a, b}), 1)


@tagged('post_install', '-at_install')
class TestEtsyLineItemPayload(TransactionCase):
    """Frozen dataclass for one line item on a receipt.

    Required: transaction_id, title, quantity, unit_price.
    Optional: listing_id, sku, personalisation.
    Default-factory: variations (empty dict).
    """

    def test_construction_with_required_fields(self):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyLineItemPayload,
        )
        item = EtsyLineItemPayload(
            listing_id="L1",
            transaction_id="T1",
            title="Custom Mug",
            sku="SKU-001",
            quantity=2,
            unit_price=15.50,
        )
        self.assertEqual(item.transaction_id, "T1")
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, 15.50)

    def test_default_variations_is_empty_dict(self):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyLineItemPayload,
        )
        item = EtsyLineItemPayload(
            listing_id=None,
            transaction_id="T2",
            title="Sticker",
            sku=None,
            quantity=1,
            unit_price=2.0,
        )
        self.assertEqual(item.variations, {})

    def test_default_personalisation_is_none(self):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyLineItemPayload,
        )
        item = EtsyLineItemPayload(
            listing_id="L3",
            transaction_id="T3",
            title="Shirt",
            sku="SKU-3",
            quantity=1,
            unit_price=20.0,
        )
        self.assertIsNone(item.personalisation)

    def test_variations_can_be_passed_explicitly(self):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyLineItemPayload,
        )
        item = EtsyLineItemPayload(
            listing_id="L4",
            transaction_id="T4",
            title="Shirt",
            sku="SKU-4",
            quantity=1,
            unit_price=25.0,
            variations={"size": "L", "color": "blue"},
        )
        self.assertEqual(item.variations["size"], "L")

    def test_immutable(self):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyLineItemPayload,
        )
        item = EtsyLineItemPayload(
            listing_id="L5",
            transaction_id="T5",
            title="Hat",
            sku=None,
            quantity=1,
            unit_price=10.0,
        )
        with self.assertRaises(FrozenInstanceError):
            item.quantity = 99


@tagged('post_install', '-at_install')
class TestEtsyOrderPayload(TransactionCase):
    """Frozen dataclass for one Etsy receipt's canonical payload.

    Carries enough state for `EtsyOrderIngestor` to write a `sale.order`
    without back-querying the source. `source` discriminates 'api' vs
    'email' so the ingestor can write `sale.order.sync_source` and audit
    provenance via `raw_source_id`.
    """

    def _build_payload(self, **overrides):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyAddressPayload,
            EtsyLineItemPayload,
            EtsyOrderPayload,
        )
        defaults = dict(
            etsy_shop_id=42,
            etsy_receipt_id="REC-1001",
            etsy_order_id="ORD-1001",
            buyer_name="Alice Buyer",
            buyer_country="US",
            order_date=datetime(2026, 4, 28, 12, 0, 0),
            currency="USD",
            amount_total=100.00,
            shipping_total=10.00,
            line_items=(
                EtsyLineItemPayload(
                    listing_id="L1",
                    transaction_id="T1",
                    title="Mug",
                    sku="SKU-1",
                    quantity=1,
                    unit_price=90.00,
                ),
            ),
            shipping_address=EtsyAddressPayload(
                name="Alice Buyer",
                street_1="123 Main St",
                street_2=None,
                city="Boston",
                state="MA",
                zip="02108",
                country_code="US",
            ),
            buyer_message=None,
            buyer_email="alice@example.com",
            listing_id="L1",
            payment_status="paid",
            is_gift=False,
            gift_message=None,
            source="api",
            fetched_at=datetime(2026, 4, 28, 12, 5, 0),
            raw_source_id="receipt:REC-1001",
        )
        defaults.update(overrides)
        return EtsyOrderPayload(**defaults)

    def test_construction_full_payload(self):
        payload = self._build_payload()
        self.assertEqual(payload.etsy_receipt_id, "REC-1001")
        self.assertEqual(payload.source, "api")
        self.assertEqual(len(payload.line_items), 1)
        self.assertEqual(payload.shipping_address.country_code, "US")

    def test_optional_fields_accept_none(self):
        payload = self._build_payload(
            buyer_message=None,
            buyer_email=None,
            listing_id=None,
            payment_status=None,
            is_gift=None,
            gift_message=None,
        )
        self.assertIsNone(payload.buyer_message)
        self.assertIsNone(payload.buyer_email)
        self.assertIsNone(payload.is_gift)

    def test_immutable_top_level_fields(self):
        payload = self._build_payload()
        with self.assertRaises(FrozenInstanceError):
            payload.amount_total = 999.99

    def test_equality_by_value(self):
        a = self._build_payload()
        b = self._build_payload()
        self.assertEqual(a, b)

    def test_source_can_be_email(self):
        """source is a Literal['api', 'email']; Python does not enforce
        Literal at runtime, but the field must accept both string values
        without coercion."""
        payload = self._build_payload(source="email", raw_source_id="email_log:42")
        self.assertEqual(payload.source, "email")

    def test_line_items_is_tuple_of_line_item_payloads(self):
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyLineItemPayload,
        )
        payload = self._build_payload(line_items=tuple(
            EtsyLineItemPayload(
                listing_id=f"L{n}", transaction_id=f"T{n}",
                title=f"item{n}", sku=None, quantity=1, unit_price=1.0,
            )
            for n in range(3)
        ))
        self.assertEqual(len(payload.line_items), 3)
        self.assertEqual(payload.line_items[2].listing_id, "L2")
        self.assertIsInstance(payload.line_items, tuple)

    def test_line_items_cannot_be_appended(self):
        """Regression test for security-reviewer P0-16a HIGH finding:
        `line_items` must be a tuple so consumers cannot bypass
        `frozen=True` by mutating the inner sequence."""
        from odoo.addons.etsy_integration.services.etsy_order_payload import (
            EtsyLineItemPayload,
        )
        payload = self._build_payload()
        rogue = EtsyLineItemPayload(
            listing_id="X", transaction_id="X", title="rogue",
            sku=None, quantity=1, unit_price=999.0,
        )
        with self.assertRaises(AttributeError):
            payload.line_items.append(rogue)
