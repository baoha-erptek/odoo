"""Tests for product creation with categorization (T025-T026 / US3).

Covers find_or_create_product() with is_storable=True flag and automatic
category assignment via keyword matching.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProductCreation(TransactionCase):
    """Test product creation with categorization and storable flag."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_find_or_create_product_sets_storable(self):
        """T025: New products should have is_storable=True."""
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)

        product = creator.find_or_create_product('Test Ring Dish')
        self.assertTrue(product, "Product should be created")
        self.assertTrue(product.is_storable, "Product should have is_storable=True")

    def test_find_or_create_product_categorizes(self):
        """T026: Product names matching keywords should be auto-categorized."""
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)

        # "Ring Dish Custom Gold" contains "ring dish" keyword
        product = creator.find_or_create_product('Ring Dish Custom Gold')
        self.assertTrue(product, "Product should be created")

        # Should be categorized to "Ring Dishes"
        expected_categ = self.env.ref(
            'etsy_integration.product_cat_etsy_ring_dishes',
            raise_if_not_found=False,
        )
        self.assertTrue(expected_categ, "Ring Dishes category should exist")
        self.assertEqual(
            product.categ_id.id, expected_categ.id,
            "Product should be categorized to 'Ring Dishes'",
        )

    def test_find_or_create_product_multiple_keyword_matches(self):
        """Test product with keyword that matches multiple categories."""
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)

        # "Coffee Mug with Custom Name" matches "mug" keyword
        product = creator.find_or_create_product('Coffee Mug with Custom Name')
        self.assertTrue(product, "Product should be created")

        # "mug" matches "Mugs & Drinkware" category
        expected_categ = self.env.ref(
            'etsy_integration.product_cat_etsy_mugs_drinkware',
            raise_if_not_found=False,
        )
        self.assertTrue(expected_categ, "Mugs & Drinkware category should exist")
        self.assertEqual(
            product.categ_id.id, expected_categ.id,
            "Product should be categorized to 'Mugs & Drinkware'",
        )

    def test_find_or_create_product_uncategorized_fallback(self):
        """Edge case: Product name without matching keywords falls back to Uncategorized."""
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)

        # "XYZZZ unknown product 9999" does not match any keyword
        product = creator.find_or_create_product('XYZZZ unknown product 9999')
        self.assertTrue(product, "Product should be created")

        # Should fall back to "Uncategorized"
        expected_categ = self.env.ref(
            'etsy_integration.product_cat_etsy_uncategorized',
            raise_if_not_found=False,
        )
        self.assertTrue(expected_categ, "Uncategorized category should exist")
        self.assertEqual(
            product.categ_id.id, expected_categ.id,
            "Product should fall back to 'Uncategorized'",
        )

    def test_find_or_create_product_existing_not_recategorized(self):
        """Edge case: Existing product's category is not overwritten."""
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)

        # Pre-create a product with "Jewelry" category
        jewelry_categ = self.env.ref(
            'etsy_integration.product_cat_etsy_jewelry',
            raise_if_not_found=False,
        )
        self.assertTrue(jewelry_categ, "Jewelry category should exist")

        product1 = self.env['product.product'].create({
            'name': 'Ring Dish Classic',
            'categ_id': jewelry_categ.id,
            'is_storable': False,
        })
        self.assertEqual(product1.categ_id.id, jewelry_categ.id)
        self.assertFalse(product1.is_storable)

        # Call find_or_create with the same product name
        # Should return the existing product WITHOUT changing its category
        product2 = creator.find_or_create_product('Ring Dish Classic')
        self.assertEqual(product1.id, product2.id, "Should return existing product")
        self.assertEqual(
            product2.categ_id.id, jewelry_categ.id,
            "Existing product category should not be changed",
        )

    def test_find_or_create_product_is_etsy_flag(self):
        """Test that created products are marked as Etsy products."""
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)

        product = creator.find_or_create_product('Etsy Tattoo Sticker Pack')
        self.assertTrue(product.is_etsy_product, "Product should be marked as Etsy product")

    def test_find_or_create_product_empty_name_handled(self):
        """Edge case: Empty product name should be replaced with default."""
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)

        product = creator.find_or_create_product('')
        self.assertTrue(product, "Product should be created with empty name")
        self.assertEqual(
            product.name, 'Etsy Product (unnamed)',
            "Empty product name should get default name",
        )
