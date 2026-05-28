"""Phase 1 DB tests for P-PUB-WEIGHT-DIMENSIONS (MP006, Spec 011).

Verifies that the two new columns on `etsy_shop` exist with the expected types
and that the Selection defaults apply on new rows.

Fields:
- `weight_unit_pref` — Char (varchar), Selection, default='oz'
- `dimensions_unit_pref` — Char (varchar), Selection, default='cm'
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPubWeightDimensionsDB(TransactionCase):
    """Phase 1 DB schema verification."""

    def test_weight_unit_pref_column_exists(self):
        """etsy_shop.weight_unit_pref is varchar."""
        self.env.cr.execute(
            """
            SELECT data_type
              FROM information_schema.columns
             WHERE table_name = 'etsy_shop'
               AND column_name = 'weight_unit_pref'
            """
        )
        row = self.env.cr.fetchone()
        self.assertIsNotNone(
            row,
            "etsy_shop.weight_unit_pref column must exist",
        )
        self.assertIn(
            row[0],
            ('character varying', 'text'),
            f"Expected varchar/text, got {row[0]}",
        )

    def test_dimensions_unit_pref_column_exists(self):
        """etsy_shop.dimensions_unit_pref is varchar."""
        self.env.cr.execute(
            """
            SELECT data_type
              FROM information_schema.columns
             WHERE table_name = 'etsy_shop'
               AND column_name = 'dimensions_unit_pref'
            """
        )
        row = self.env.cr.fetchone()
        self.assertIsNotNone(
            row,
            "etsy_shop.dimensions_unit_pref column must exist",
        )
        self.assertIn(
            row[0],
            ('character varying', 'text'),
            f"Expected varchar/text, got {row[0]}",
        )

    def test_weight_unit_pref_default_oz(self):
        """etsy_shop.weight_unit_pref defaults to 'oz' on new row."""
        shop = self.env['etsy.shop'].create({
            'name': 'Test Shop OZ',
        })
        self.assertEqual(
            shop.weight_unit_pref,
            'oz',
            "weight_unit_pref must default to 'oz'",
        )

    def test_dimensions_unit_pref_default_cm(self):
        """etsy_shop.dimensions_unit_pref defaults to 'cm' on new row."""
        shop = self.env['etsy.shop'].create({
            'name': 'Test Shop CM',
        })
        self.assertEqual(
            shop.dimensions_unit_pref,
            'cm',
            "dimensions_unit_pref must default to 'cm'",
        )
