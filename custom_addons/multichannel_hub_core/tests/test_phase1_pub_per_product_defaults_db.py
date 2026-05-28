"""Phase 1 Database Verification for P-PUB-PER-PRODUCT-DEFAULTS.

Tests verify that the PostgreSQL schema for product.template per-product
listing defaults is correctly set up:
- x_taxonomy_id column exists with type character varying
- x_who_made column exists with type character varying
- x_when_made column exists with type character varying

Tests use direct SQL to verify the database state at the lowest level,
independent of ORM machinery.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPubPerProductDefaultsDB(TransactionCase):
    """Direct PostgreSQL verification for per-product defaults schema."""

    def test_per_product_defaults_columns_data_types(self):
        """Verify all 3 per-product-defaults columns exist with correct data types."""
        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'product_template'
            AND column_name IN (
                'x_taxonomy_id',
                'x_who_made',
                'x_when_made'
            )
            ORDER BY column_name
        """)
        rows = self.env.cr.fetchall()

        # Expecting exactly 3 columns
        self.assertEqual(len(rows), 3, "Expected 3 per-product-defaults columns")

        # Build a dict for easy assertion
        cols = {name: data_type for name, data_type in rows}

        # Verify each column exists with the right type (all character varying)
        self.assertIn('x_taxonomy_id', cols)
        self.assertEqual(cols['x_taxonomy_id'], 'character varying')

        self.assertIn('x_who_made', cols)
        self.assertEqual(cols['x_who_made'], 'character varying')

        self.assertIn('x_when_made', cols)
        self.assertEqual(cols['x_when_made'], 'character varying')
