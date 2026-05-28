"""P0-16a — RED-phase contract tests for EtsyChannelAdapter Protocol.

Defines the duck-typed interface every channel-source adapter must
satisfy. `EtsyApiAdapter` (P0-16b) and the future `EtsyEmailAdapter`
both implement this Protocol so `EtsyOrderIngestor` can swap sources
based on `etsy.shop.sync_mode` without conditional branches per source.

Reference: `specs/005-etsy-api-channel/data-model.md` lines 260-269.
"""

from datetime import datetime
from typing import Iterator, get_type_hints

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHealthStatusEnum(TransactionCase):
    """`HealthStatus` enum for `EtsyChannelAdapter.health_check` return values."""

    def test_has_three_members(self):
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            HealthStatus,
        )
        members = {m.name for m in HealthStatus}
        self.assertEqual(members, {"OK", "DEGRADED", "DOWN"})

    def test_string_values(self):
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            HealthStatus,
        )
        self.assertEqual(HealthStatus.OK.value, "ok")
        self.assertEqual(HealthStatus.DEGRADED.value, "degraded")
        self.assertEqual(HealthStatus.DOWN.value, "down")

    def test_members_are_distinct(self):
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            HealthStatus,
        )
        self.assertEqual(
            len({HealthStatus.OK, HealthStatus.DEGRADED, HealthStatus.DOWN}),
            3,
        )


@tagged('post_install', '-at_install')
class TestEtsyChannelAdapterProtocol(TransactionCase):
    """`EtsyChannelAdapter` is a runtime-checkable Protocol with two methods:
    `fetch_new_orders(shop_id, since)` and `health_check(shop_id)`.
    Concrete adapters do NOT inherit from it — duck typing only.
    """

    def test_protocol_is_a_protocol(self):
        from typing import Protocol
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            EtsyChannelAdapter,
        )
        self.assertTrue(issubclass(EtsyChannelAdapter, Protocol))

    def test_protocol_declares_required_methods(self):
        """Verify both methods are part of the Protocol surface."""
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            EtsyChannelAdapter,
        )
        # Protocol stores its members in __annotations__ or as class methods.
        # Access via dir() — both must be visible attributes.
        attrs = set(dir(EtsyChannelAdapter))
        self.assertIn("fetch_new_orders", attrs)
        self.assertIn("health_check", attrs)

    def test_runtime_checkable_accepts_duck_typed_class(self):
        """A class with both methods passes `isinstance` against the Protocol
        if the Protocol is `@runtime_checkable`."""
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            EtsyChannelAdapter,
            HealthStatus,
        )

        class FakeAdapter:
            def fetch_new_orders(self, shop_id: int, since: datetime):
                return iter([])

            def health_check(self, shop_id: int) -> HealthStatus:
                return HealthStatus.OK

        self.assertIsInstance(FakeAdapter(), EtsyChannelAdapter)

    def test_runtime_checkable_rejects_class_missing_method(self):
        """A class missing `health_check` must NOT pass the isinstance check."""
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            EtsyChannelAdapter,
        )

        class IncompleteAdapter:
            def fetch_new_orders(self, shop_id: int, since: datetime):
                return iter([])

        self.assertNotIsInstance(IncompleteAdapter(), EtsyChannelAdapter)

    def test_fetch_new_orders_signature_returns_iterator(self):
        """The Protocol method's return annotation is Iterator[EtsyOrderPayload]."""
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            EtsyChannelAdapter,
        )
        hints = get_type_hints(EtsyChannelAdapter.fetch_new_orders)
        # Just verify a return hint exists; concrete origin is Iterator.
        self.assertIn("return", hints)

    def test_health_check_returns_health_status(self):
        """The Protocol method's return annotation is HealthStatus."""
        from odoo.addons.etsy_integration.services.etsy_channel_adapter import (
            EtsyChannelAdapter,
            HealthStatus,
        )
        hints = get_type_hints(EtsyChannelAdapter.health_check)
        self.assertIs(hints["return"], HealthStatus)
