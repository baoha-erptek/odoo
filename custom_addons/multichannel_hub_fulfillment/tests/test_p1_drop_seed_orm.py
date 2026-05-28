"""P1-DROP-SEED — Phase 2 (ORM) unit tests.

Tests verify that:
- create() with x_gearment_sku applies dropship route + Gearment seller_id
- create() without x_gearment_sku does NOT apply route or seller
- write() setting x_gearment_sku applies route + seller (onchange + write() defense)
- write() clearing x_gearment_sku removes route + seller (symmetric removal)
- Idempotency: re-writing same SKU does NOT duplicate seller row
- SKU change keeps single seller row for Gearment
- write() override enforces rule even when onchange bypassed (FR-017 case 9)
- Form-based onchange works in edit context
- Custom supplier_info price preserved when re-applying SKU

Tests use TransactionCase with savepoint isolation per test.
Tests are tagged post_install so full ORM registry loads.
"""

import logging

from odoo.tests import Form
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestP1DropSeedORM(TransactionCase):
    """Phase 2: ORM tests for x_gearment_sku auto-route and seller behavior."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test fixtures once for all tests."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Disable field tracking to avoid audit noise in test setup
        cls.gearment = cls.env.ref(
            'multichannel_hub_fulfillment.partner_gearment_vendor'
        )
        cls.dropship_route = cls.env.ref(
            'stock_dropshipping.route_drop_shipping'
        )

    def _create_product(self, **kwargs) -> 'product.template':
        """Factory method to create test product.template.

        Args:
            **kwargs: field overrides (x_gearment_sku, type, is_storable, etc.)

        Returns:
            product.template record
        """
        defaults = {
            'name': 'Test Product',
            'is_storable': True,
        }
        defaults.update(kwargs)
        return self.env['product.template'].create(defaults)

    def test_create_with_x_gearment_sku_sets_route_and_seller(self):
        """Test that create() with SKU applies dropship route and Gearment seller."""
        product = self._create_product(x_gearment_sku='SKU-001')

        self.assertIn(
            self.dropship_route,
            product.route_ids,
            "Dropship route must be applied when x_gearment_sku is set on create()"
        )

        gearment_sellers = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(
            len(gearment_sellers),
            1,
            "Exactly one Gearment seller_ids row must be created on create() with SKU"
        )

    def test_create_without_x_gearment_sku_no_route_no_seller(self):
        """Test that create() without SKU does NOT apply route or seller."""
        product = self._create_product()

        self.assertNotIn(
            self.dropship_route,
            product.route_ids,
            "Dropship route must NOT be applied when x_gearment_sku is empty on create()"
        )

        gearment_sellers = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(
            len(gearment_sellers),
            0,
            "No Gearment seller_ids row must exist when x_gearment_sku is empty"
        )

    def test_write_set_x_gearment_sku_applies_route_and_seller(self):
        """Test that write() setting SKU applies dropship route and Gearment seller."""
        product = self._create_product()

        # Verify initial state
        self.assertNotIn(
            self.dropship_route,
            product.route_ids,
            "Initial state: dropship route must NOT be present"
        )

        # Set SKU via write()
        product.write({'x_gearment_sku': 'SKU-002'})

        self.assertIn(
            self.dropship_route,
            product.route_ids,
            "Dropship route must be applied after write() with SKU"
        )

        gearment_sellers = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(
            len(gearment_sellers),
            1,
            "Exactly one Gearment seller_ids row must exist after write() with SKU"
        )

    def test_write_clear_x_gearment_sku_removes_route_and_seller(self):
        """Test that write() clearing SKU removes dropship route and Gearment seller."""
        product = self._create_product(x_gearment_sku='SKU-003')

        # Verify initial state
        self.assertIn(
            self.dropship_route,
            product.route_ids,
            "Initial state: dropship route must be present"
        )

        gearment_sellers = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(
            len(gearment_sellers),
            1,
            "Initial state: one Gearment seller_ids row must exist"
        )

        # Clear SKU via write() with False
        product.write({'x_gearment_sku': False})

        self.assertNotIn(
            self.dropship_route,
            product.route_ids,
            "Dropship route must be removed after clearing x_gearment_sku"
        )

        gearment_sellers_after = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(
            len(gearment_sellers_after),
            0,
            "Gearment seller_ids row must be removed after clearing x_gearment_sku"
        )

    def test_idempotent_write_no_duplicate_seller(self):
        """Test that write() with same SKU twice does NOT duplicate seller row."""
        product = self._create_product(x_gearment_sku='SKU-A')

        # Verify initial seller count
        gearment_sellers = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(
            len(gearment_sellers),
            1,
            "Initial: exactly one Gearment seller_ids row"
        )

        # Re-write same SKU
        product.write({'x_gearment_sku': 'SKU-A'})

        gearment_sellers_after = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(
            len(gearment_sellers_after),
            1,
            "Idempotency: re-writing same SKU must NOT create duplicate seller row"
        )

    def test_write_change_sku_value_keeps_single_seller_row(self):
        """Test that changing SKU value keeps exactly one Gearment seller row."""
        product = self._create_product(x_gearment_sku='SKU-A')

        gearment_sellers = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(
            len(gearment_sellers),
            1,
            "Initial: exactly one Gearment seller_ids row for SKU-A"
        )

        # Change SKU value
        product.write({'x_gearment_sku': 'SKU-B'})

        gearment_sellers_after = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(
            len(gearment_sellers_after),
            1,
            "SKU change must keep exactly one Gearment seller_ids row "
            "(no duplication, no deletion of pre-existing)"
        )

    def test_direct_rpc_write_bypasses_onchange_but_write_override_enforces(self):
        """Test that write() override enforces rule even when onchange is bypassed.

        This is the FR-017 case 9 (write-level defense): direct RPC write calls
        or backend.write() calls bypass onchange, but the write() override
        is the canonical gate. Rule must be enforced at ORM write() time.
        """
        product = self._create_product()

        # Direct write call (no form context, onchange bypassed)
        product.write({'x_gearment_sku': 'RPC-1'})

        self.assertIn(
            self.dropship_route,
            product.route_ids,
            "write() override must apply route even when onchange bypassed (FR-017)"
        )

        gearment_sellers = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(
            len(gearment_sellers),
            1,
            "write() override must apply seller even when onchange bypassed (FR-017)"
        )

    def test_onchange_x_gearment_sku_in_form_view(self):
        """Test that Form-based onchange updates route and seller in-memory.

        This tests the UI convenience onchange path (convenience, not canonical).
        """
        product = self._create_product()

        form = Form(product)
        form.x_gearment_sku = 'FORM-1'

        # In-memory state should reflect onchange updates
        # Note: onchange is form-context convenience; actual persistence
        # tested via write() override in other tests
        self.assertTrue(
            form.x_gearment_sku,
            "Form field must accept value"
        )

        # Now save the form (triggers write())
        form.save()
        product.invalidate_recordset()

        self.assertIn(
            self.dropship_route,
            product.route_ids,
            "After form.save(), dropship route must be applied"
        )

        gearment_sellers = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(
            len(gearment_sellers),
            1,
            "After form.save(), Gearment seller_ids row must exist"
        )

    def test_existing_seller_id_cost_preserved_on_reapply(self):
        """Test that custom supplier_info price is preserved on re-apply.

        Idempotency requirement: if a custom price was set on a
        Gearment seller_ids row, re-writing the SKU must not clobber
        that custom data or create a duplicate row.
        """
        product = self._create_product(x_gearment_sku='SKU-CUSTOM')

        # Pre-create a seller_ids row with custom price
        gearment_seller = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(len(gearment_seller), 1)

        # Set a custom price (simulating that business logic set it elsewhere)
        original_price = 99.99
        gearment_seller.write({'price': original_price})

        # Now re-write the SKU (simulating user re-applying same SKU via form)
        product.write({'x_gearment_sku': 'SKU-CUSTOM'})

        # Verify no duplicate was created and price is preserved
        gearment_sellers_after = product.seller_ids.filtered(
            lambda s: s.partner_id == self.gearment
        )
        self.assertEqual(
            len(gearment_sellers_after),
            1,
            "No duplicate seller row must be created on idempotent re-apply"
        )

        self.assertEqual(
            gearment_sellers_after.price,
            original_price,
            "Custom price must be preserved when re-applying SKU"
        )
