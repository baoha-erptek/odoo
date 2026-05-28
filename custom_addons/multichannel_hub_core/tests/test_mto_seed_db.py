"""P1-MTO-SEED — Phase 1 (DB) verification.

Asserts that the phantom product (MFG-Phantom, type=service) is seeded and
the MTO route is correctly loaded. This is the data-integrity guard for the
MTO auto-BOM wizard introduced by P1-MTO-SEED (ADR-010 amendment 2026-05-03).

See:
- specs/006-master-plan/adrs/ADR-010-configurable-order-pipeline.md
  §"Amendment 2026-05-03"
- Mirrors test_mto_dep_db.py + test_dropship_dep_db.py pattern.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMtoSeedDb(TransactionCase):
    """Phase 1: MTO seed data (phantom product, MTO route) loaded."""

    def test_phantom_product_seeded(self):
        """Phantom product (MFG-Phantom, type=service) must exist."""
        phantom = self.env.ref('multichannel_hub_core.product_mto_phantom_component')
        self.assertTrue(phantom, "Phantom product must be seeded")
        self.assertEqual(
            phantom._name, 'product.template',
            "Phantom must be a product.template",
        )
        self.assertEqual(
            phantom.name, 'MFG-Phantom',
            "Phantom name should be 'MFG-Phantom'",
        )
        self.assertEqual(
            phantom.type, 'service',
            "Phantom must be type='service' (non-storable)",
        )
        self.assertFalse(
            phantom.is_storable,
            "Service products must have is_storable=False",
        )

    def test_mto_route_available(self):
        """MTO stock.route (Replenish on Order) must be active."""
        route = self.env.ref('stock.route_warehouse0_mto')
        self.assertTrue(route, "MTO stock.route must be loaded")
        self.assertEqual(route._name, 'stock.route')
        self.assertTrue(
            route.active,
            "MTO route must be active",
        )
        self.assertIn(
            'MTO', route.name,
            "Route name should contain 'MTO'",
        )
