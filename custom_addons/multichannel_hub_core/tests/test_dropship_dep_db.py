"""P1-DROP-DEPS — Phase 1 (DB) verification.

Asserts that `multichannel_hub_core` brings `stock_dropshipping` (and its
transitive dep `purchase`) along, and that the standard Dropship
`stock.route` is loaded and active. This is the manifest-level guard for
the hybrid dropship plumbing introduced by ADR-010 amendment 2026-05-03.

See:
- specs/006-master-plan/adrs/ADR-010-configurable-order-pipeline.md
  §"Amendment 2026-05-03" / §"What we are now layering" §1
- specs/006-master-plan/findings.md §"P1-DROP-DEPS dep clarification"
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDropshipDep(TransactionCase):
    """Phase 1: dropship dependency closure is installed and route is active."""

    def test_stock_dropshipping_module_installed(self):
        module = self.env['ir.module.module'].search([
            ('name', '=', 'stock_dropshipping'),
        ])
        self.assertEqual(len(module), 1, "stock_dropshipping module should exist")
        self.assertEqual(
            module.state, 'installed',
            "stock_dropshipping must be installed as a transitive dep of "
            "multichannel_hub_core (ADR-010 amendment 2026-05-03)",
        )

    def test_purchase_module_installed(self):
        module = self.env['ir.module.module'].search([
            ('name', '=', 'purchase'),
        ])
        self.assertEqual(len(module), 1, "purchase module should exist")
        self.assertEqual(
            module.state, 'installed',
            "purchase must be installed (transitively via stock_dropshipping)",
        )

    def test_dropship_route_exists_and_active(self):
        route = self.env.ref('stock_dropshipping.route_drop_shipping')
        self.assertTrue(route, "Dropship stock.route must be loaded")
        self.assertEqual(route._name, 'stock.route')
        self.assertEqual(route.name, 'Dropship')
        self.assertTrue(
            route.active,
            "Dropship route must be active so it can be selected on products",
        )
        self.assertTrue(
            route.sale_selectable,
            "Dropship route must be sale_selectable for SO confirmation to "
            "auto-create a dropship picking (P1-DROP-CALLSITE prerequisite)",
        )
