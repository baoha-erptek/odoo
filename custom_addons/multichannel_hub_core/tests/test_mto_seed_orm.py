"""P1-MTO-SEED — Phase 2 (ORM) business logic verification.

Tests the MTO auto-BOM wizard (`product.mto.bom.wizard`) and the integration
with `sale.order.action_confirm()` to create `mrp.production` records.

Phantom product + BOM + route assignment workflow:
1. User selects a product on vn_internal_production pipeline.
2. Calls wizard action_create_bom() (idempotent).
3. BOM auto-created with 1 line: finished good ← 1 phantom component.
4. MTO route assigned to product.route_ids.
5. User creates SO with product line.
6. SO confirm creates mrp.production (via standard MTO procurement).

See:
- specs/006-master-plan/adrs/ADR-010-configurable-order-pipeline.md
  §"Amendment 2026-05-03"
- Tracker P1-MTO-SEED entry.
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMtoSeedOrm(TransactionCase):
    """Phase 2: Wizard idempotency, BOM creation, route assignment."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Phantom product (must exist from seed; created in GREEN phase)
        cls.phantom = cls.env.ref('multichannel_hub_core.product_mto_phantom_component')

        # Default partner for SO lines (demo data may be absent — create fresh).
        cls.partner = cls.env.ref('base.partner_demo', raise_if_not_found=False)
        if not cls.partner:
            cls.partner = cls.env['res.partner'].create({
                'name': 'Demo Partner',
                'email': 'demo@example.com',
            })

        # Test product category (for later)
        cls.category = cls.env['product.category'].search([], limit=1)
        if not cls.category:
            cls.category = cls.env['product.category'].create({
                'name': 'Test Category',
            })

    def _create_product(self, name, **kwargs):
        """Factory: create product.template on vn_internal_production pipeline."""
        defaults = {
            'name': name,
            'type': 'consu',
            'is_storable': True,
            'categ_id': self.category.id,
            'x_default_pipeline_id': self.env.ref(
                'multichannel_hub_core.order_pipeline_vn_internal_production'
            ).id,
        }
        defaults.update(kwargs)
        return self.env['product.template'].create(defaults)

    def _create_sale_order(self, product, partner=None, qty=1):
        """Factory: create sale.order with one line."""
        if partner is None:
            partner = self.partner
        variant = product.product_variant_ids[0] if product.product_variant_ids else product.product_variant_id
        return self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [
                (0, 0, {
                    'product_id': variant.id,
                    'product_uom_qty': qty,
                    'price_unit': 100.0,
                })
            ],
        })

    def test_wizard_creates_bom_and_assigns_route(self):
        """Wizard creates BOM and assigns MTO route to product."""
        product = self._create_product('Test MTO Product')

        # Call wizard action (assumes wizard model exists in GREEN)
        wizard = self.env['product.mto.bom.wizard'].create({
            'product_id': product.id,
        })
        wizard.action_create_bom()

        # Assert exactly one BOM exists
        boms = self.env['mrp.bom'].search([('product_tmpl_id', '=', product.id)])
        self.assertEqual(
            len(boms), 1,
            "Exactly one BOM should exist for the product",
        )
        bom = boms[0]

        # Assert BOM has exactly one line (phantom)
        self.assertEqual(
            len(bom.bom_line_ids), 1,
            "BOM should have exactly one line (phantom component)",
        )
        bom_line = bom.bom_line_ids[0]
        self.assertEqual(
            bom_line.product_id.product_tmpl_id, self.phantom,
            "BOM line should point to phantom component",
        )

        # Assert MTO route in product.route_ids
        mto_route = self.env.ref('stock.route_warehouse0_mto')
        self.assertIn(
            mto_route, product.route_ids,
            "MTO route should be assigned to product",
        )

    def test_confirm_so_creates_mo(self):
        """Confirming SO with MTO product creates mrp.production."""
        product = self._create_product('Test MTO Product 2')

        # Run wizard to set up BOM and route
        wizard = self.env['product.mto.bom.wizard'].create({
            'product_id': product.id,
        })
        wizard.action_create_bom()

        # Create and confirm SO
        so = self._create_sale_order(product, qty=2)
        so.action_confirm()

        # Assert mrp.production created
        mos = self.env['mrp.production'].search([
            ('origin', '=', so.name),
        ])
        self.assertGreaterEqual(
            len(mos), 1,
            "At least one mrp.production should be created for the confirmed SO",
        )

    def test_wizard_idempotent_no_duplicate_bom(self):
        """Calling wizard twice on same product does not duplicate BOM."""
        product = self._create_product('Test MTO Product 3')

        # Call wizard first time
        wizard1 = self.env['product.mto.bom.wizard'].create({
            'product_id': product.id,
        })
        wizard1.action_create_bom()

        # Call wizard second time
        wizard2 = self.env['product.mto.bom.wizard'].create({
            'product_id': product.id,
        })
        wizard2.action_create_bom()

        # Assert still exactly one BOM
        boms = self.env['mrp.bom'].search([('product_tmpl_id', '=', product.id)])
        self.assertEqual(
            len(boms), 1,
            "Wizard must be idempotent — exactly one BOM even after two calls",
        )

    def test_wizard_error_on_wrong_pipeline(self):
        """Wizard raises ValidationError if product is not on vn_internal_production."""
        # Create product on a different pipeline (e.g., gearment_pod)
        other_pipeline = self.env.ref('multichannel_hub_core.order_pipeline_gearment_pod')
        product = self._create_product(
            'Test Non-MTO Product',
            x_default_pipeline_id=other_pipeline.id,
        )

        # Attempt wizard — should raise ValidationError
        wizard = self.env['product.mto.bom.wizard'].create({
            'product_id': product.id,
        })
        with self.assertRaises(ValidationError):
            wizard.action_create_bom()
