"""P1-DROP-SEED — Phase 1 (DB) verification.

Tests verify that:
- Gearment partner seed is loaded and resolves via XML id
- Dropship route from stock_dropshipping is available and active
- product.template.x_gearment_sku column is indexed (existing from P0-18b1)
- Seed is idempotent (noupdate=True prevents duplication on re-install)

Tests use direct SQL to verify database state.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestP1DropSeedDB(TransactionCase):
    """Phase 1: Database verification for Gearment partner seed and route."""

    def test_gearment_partner_seed_resolves(self):
        """Test that Gearment partner seed exists and has correct attributes."""
        gearment = self.env.ref(
            'multichannel_hub_fulfillment.partner_gearment_vendor',
            raise_if_not_found=False
        )

        self.assertIsNotNone(
            gearment,
            "Gearment partner must be seeded via XML id "
            "'multichannel_hub_fulfillment.partner_gearment_vendor'"
        )
        self.assertEqual(
            gearment.name,
            'Gearment',
            "Partner name must be 'Gearment'"
        )
        self.assertEqual(
            gearment.supplier_rank,
            1,
            "Gearment supplier_rank must be 1 (first choice vendor)"
        )
        self.assertEqual(
            gearment.customer_rank,
            0,
            "Gearment customer_rank must be 0 (not a customer)"
        )
        self.assertTrue(
            gearment.active,
            "Gearment partner must be active"
        )

    def test_dropship_route_exists_and_active(self):
        """Test that dropship route is available and active."""
        route = self.env.ref(
            'stock_dropshipping.route_drop_shipping',
            raise_if_not_found=False
        )

        self.assertIsNotNone(
            route,
            "Dropship route must exist via 'stock_dropshipping.route_drop_shipping'"
        )
        self.assertEqual(
            route._name,
            'stock.route',
            "Reference must resolve to a stock.route model"
        )
        self.assertTrue(
            route.active,
            "Dropship route must be active for product assignment"
        )

    def test_x_gearment_sku_column_indexed(self):
        """Test that product_template.x_gearment_sku has an index (P0-18b1)."""
        self.env.cr.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'product_template'
            AND indexdef LIKE '%x_gearment_sku%'
        """)
        indexes = self.env.cr.fetchall()

        self.assertTrue(
            len(indexes) > 0,
            "product_template.x_gearment_sku must have at least one index "
            "(added in P0-18b1)"
        )

    def test_seed_loaded_only_once(self):
        """Test that seed is idempotent (noupdate=True prevents duplication)."""
        count = self.env['res.partner'].search_count([
            ('name', '=', 'Gearment'),
            ('supplier_rank', '=', 1),
        ])

        self.assertEqual(
            count,
            1,
            "Only one Gearment partner with supplier_rank=1 must exist; "
            "noupdate=True ensures re-install does not duplicate"
        )
