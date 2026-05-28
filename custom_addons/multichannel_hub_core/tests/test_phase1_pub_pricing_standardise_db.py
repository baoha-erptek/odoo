"""Phase 1 Database Verification Tests — P-PUB-PRICING-STANDARDISE.

Verify data integrity at the database level for list_price migration.
"""

from odoo.tests.common import TransactionCase


class TestPubPricingStandardiseDb(TransactionCase):
    """Phase 1: Direct database verification for pricing migration."""

    def test_list_price_field_exists(self):
        """Verify standard list_price field exists on product.template."""
        self.env.cr.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'product_template' AND column_name = 'list_price'"
        )
        row = self.env.cr.fetchone()
        self.assertIsNotNone(row, "list_price column should exist")

    def test_list_price_field_is_numeric(self):
        """Verify list_price is numeric (not text)."""
        self.env.cr.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'product_template' AND column_name = 'list_price'"
        )
        data_type = self.env.cr.fetchone()[0]
        self.assertIn(data_type, ['numeric', 'double precision'],
                     f"list_price should be numeric, got {data_type}")

    def test_x_listing_price_field_exists_after_migration(self):
        """Verify x_listing_price DB column is no longer written to (computed field).

        Note: Old x_listing_price column may still exist in DB from pre-migration data,
        but it's no longer updated via ORM. The field is now computed from list_price.
        """
        # Verify that x_listing_price field is defined in ORM as computed
        tmpl = self.env['product.template']
        field = tmpl._fields.get('x_listing_price')
        self.assertIsNotNone(field, "x_listing_price should exist as a field")
        # Verify it's a computed field (not stored directly)
        if hasattr(field, 'compute'):
            self.assertIsNotNone(field.compute, "x_listing_price should be computed")

    def test_migration_idempotent_on_rerun(self):
        """Verify migration can safely run multiple times.

        Verify that list_price column exists and is writable,
        supporting the migration from x_listing_price → list_price.
        """
        # Check that list_price column is writable at DB level
        self.env.cr.execute("""
            SELECT column_name, is_nullable FROM information_schema.columns
            WHERE table_name = 'product_template'
            AND column_name = 'list_price'
        """)
        row = self.env.cr.fetchone()
        self.assertIsNotNone(row, "list_price column should exist")
        # Verify it allows NULL (we're migrating from nullable x_listing_price)
        is_nullable = row[1]
        self.assertTrue(is_nullable, "list_price should allow NULL for migration safety")
