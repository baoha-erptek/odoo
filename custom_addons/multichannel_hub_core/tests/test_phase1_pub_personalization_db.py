"""Phase 1 Database Verification for P-PUB-PERSONALIZATION.

Tests verify that the PostgreSQL schema for product.template personalization
fields is correctly set up:
- x_is_personalizable column exists with type boolean
- x_personalization_required column exists with type boolean
- x_personalization_char_count column exists with type integer
- x_personalization_instructions column exists with type text

Tests use direct SQL to verify the database state at the lowest level,
independent of ORM machinery.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPubPersonalizationDB(TransactionCase):
    """Direct PostgreSQL verification for personalization schema."""

    def test_personalization_columns_data_types(self):
        """Verify all 4 personalization columns exist with correct data types."""
        self.env.cr.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'product_template'
            AND column_name IN (
                'x_is_personalizable',
                'x_personalization_required',
                'x_personalization_char_count',
                'x_personalization_instructions'
            )
            ORDER BY column_name
        """)
        rows = self.env.cr.fetchall()

        # Expecting exactly 4 columns
        self.assertEqual(len(rows), 4, "Expected 4 personalization columns")

        # Build a dict for easy assertion
        cols = {name: data_type for name, data_type in rows}

        # Verify each column exists with the right type
        self.assertIn('x_is_personalizable', cols)
        self.assertEqual(cols['x_is_personalizable'], 'boolean')

        self.assertIn('x_personalization_required', cols)
        self.assertEqual(cols['x_personalization_required'], 'boolean')

        self.assertIn('x_personalization_char_count', cols)
        self.assertEqual(cols['x_personalization_char_count'], 'integer')

        self.assertIn('x_personalization_instructions', cols)
        self.assertEqual(cols['x_personalization_instructions'], 'text')
