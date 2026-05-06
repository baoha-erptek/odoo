"""P1-MTO-DEPS — Phase 1 (DB) verification.

Asserts that `multichannel_hub_core` brings `mrp` along, and that the
standard MTO `stock.route` (Replenish on Order) is loaded. This is the
manifest-level guard for the MTO plumbing introduced by ADR-010
amendment 2026-05-03 — `mrp.production` is used as a lifecycle anchor
(MO confirmed -> CHỜ FILE; MO done -> VN-Fulfilled), not as the
workflow engine.

See:
- specs/006-master-plan/adrs/ADR-010-configurable-order-pipeline.md
  §"Amendment 2026-05-03" / §"What we are now layering" §2-3
- Mirrors test_dropship_dep_db.py (P1-DROP-DEPS pattern).
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMtoDep(TransactionCase):
    """Phase 1: mrp dependency is installed and MTO route is loaded."""

    def test_mrp_module_installed(self):
        module = self.env['ir.module.module'].search([
            ('name', '=', 'mrp'),
        ])
        self.assertEqual(len(module), 1, "mrp module should exist")
        self.assertEqual(
            module.state, 'installed',
            "mrp must be installed as a dep of multichannel_hub_core "
            "(ADR-010 amendment 2026-05-03 — MO is the MTO lifecycle anchor)",
        )

    def test_mto_route_exists(self):
        route = self.env.ref('stock.route_warehouse0_mto')
        self.assertTrue(route, "MTO stock.route must be loaded")
        self.assertEqual(route._name, 'stock.route')
        self.assertIn(
            'MTO', route.name,
            "Route should be the standard 'Replenish on Order (MTO)' route",
        )
