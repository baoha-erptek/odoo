"""Tests for product categorization (T027 / US3).

Covers ProductCategorizer keyword matching, case-insensitivity, fallback behavior,
and the database persistence of category records loaded from
data/etsy_product_categories.xml.
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProductCategorizer(TransactionCase):
    """Test keyword-based product categorization."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_keyword_match_case_insensitive(self):
        """Test that keyword matching is case-insensitive."""
        from ..services.product_categorizer import ProductCategorizer
        categorizer = ProductCategorizer(self.env)

        # "ring dish" keyword should match mixed case
        cat = categorizer.categorize("RING DISH")
        self.assertNotEqual(cat, False, "RING DISH should match 'ring dish' keyword")
        self.assertEqual(
            cat.id,
            self.env.ref('etsy_integration.product_cat_etsy_ring_dishes').id,
            "Should resolve to Ring Dishes category",
        )

        # "Temporary Tattoo" keyword should match lowercase
        cat = categorizer.categorize("temporary tattoo sticker")
        self.assertNotEqual(cat, False, "temporary tattoo should match keyword")
        self.assertEqual(
            cat.id,
            self.env.ref('etsy_integration.product_cat_etsy_temporary_tattoos').id,
            "Should resolve to Temporary Tattoos category",
        )

    def test_multiple_keywords_per_category(self):
        """Test that a category with multiple keywords works."""
        from ..services.product_categorizer import ProductCategorizer
        categorizer = ProductCategorizer(self.env)

        # Test each keyword for "Mugs & Drinkware"
        for product_name in ["Coffee Mug", "Tea Tumbler", "Drinkware Set"]:
            cat = categorizer.categorize(product_name)
            self.assertNotEqual(cat, False, f"{product_name} should match a category")
            self.assertEqual(
                cat.id,
                self.env.ref('etsy_integration.product_cat_etsy_mugs_drinkware').id,
                f"{product_name} should resolve to Mugs & Drinkware",
            )

    def test_fallback_to_uncategorized(self):
        """Test that unmatchable product names fall back to Uncategorized."""
        from ..services.product_categorizer import ProductCategorizer
        categorizer = ProductCategorizer(self.env)

        cat = categorizer.categorize("XYZZZ Unknown Product 12345")
        self.assertNotEqual(cat, False, "Unmatchable name should fall back to Uncategorized")
        self.assertEqual(
            cat.id,
            self.env.ref('etsy_integration.product_cat_etsy_uncategorized').id,
            "Should resolve to Uncategorized category",
        )

    def test_first_keyword_wins(self):
        """Test that when multiple keywords could match, the first one wins."""
        from ..services.product_categorizer import ProductCategorizer
        categorizer = ProductCategorizer(self.env)

        # "personalized ring dish" contains both "ring dish" and "personalized"
        # "ring dish" appears first in the JSON, so it should win
        cat = categorizer.categorize("Personalized Ring Dish Custom")
        self.assertNotEqual(cat, False, "Should match ring dish keyword")
        self.assertEqual(
            cat.id,
            self.env.ref('etsy_integration.product_cat_etsy_ring_dishes').id,
            "First matching category (Ring Dishes) should win over later ones",
        )

    def test_empty_product_name_falls_back(self):
        """Test that empty or None product names fall back gracefully."""
        from ..services.product_categorizer import ProductCategorizer
        categorizer = ProductCategorizer(self.env)

        cat = categorizer.categorize("")
        self.assertNotEqual(cat, False, "Empty string should fall back to Uncategorized")
        self.assertEqual(
            cat.id,
            self.env.ref('etsy_integration.product_cat_etsy_uncategorized').id,
        )

        cat = categorizer.categorize(None)
        self.assertNotEqual(cat, False, "None should fall back to Uncategorized")
        self.assertEqual(
            cat.id,
            self.env.ref('etsy_integration.product_cat_etsy_uncategorized').id,
        )


@tagged('post_install', '-at_install')
class TestProductCategoriesLoaded(TransactionCase):
    """Phase 1: Verify category records are persisted in the database."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_product_categories_loaded(self):
        """Verify that etsy_product_categories.xml records were loaded.

        Phase 1 DB verification: Direct SQL check that the "Etsy Products"
        parent category has at least 9 children (the categories defined in
        data/etsy_product_categories.xml).
        """
        # Get the parent "Etsy Products" category
        parent = self.env.ref(
            'etsy_integration.product_cat_etsy',
            raise_if_not_found=False,
        )
        self.assertTrue(parent, "Parent 'Etsy Products' category should exist")

        # Count children via direct SQL
        self.env.cr.execute(
            "SELECT COUNT(*) FROM product_category WHERE parent_id = %s",
            (parent.id,),
        )
        child_count = self.env.cr.fetchone()[0]
        self.assertGreaterEqual(
            child_count, 9,
            f"Expected at least 9 child categories, found {child_count}",
        )

        # Verify specific child categories exist
        expected_children = [
            'etsy_integration.product_cat_etsy_ring_dishes',
            'etsy_integration.product_cat_etsy_temporary_tattoos',
            'etsy_integration.product_cat_etsy_mugs_drinkware',
            'etsy_integration.product_cat_etsy_jewelry',
            'etsy_integration.product_cat_etsy_home_decor',
            'etsy_integration.product_cat_etsy_personalized_gifts',
            'etsy_integration.product_cat_etsy_stickers',
            'etsy_integration.product_cat_etsy_clothing',
            'etsy_integration.product_cat_etsy_pet_products',
            'etsy_integration.product_cat_etsy_uncategorized',
        ]
        for xmlid in expected_children:
            cat = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(cat, f"Category {xmlid} should exist")
            self.assertEqual(cat.parent_id.id, parent.id,
                           f"Category {xmlid} should be a child of Etsy Products")
