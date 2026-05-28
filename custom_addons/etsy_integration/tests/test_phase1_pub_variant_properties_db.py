"""Phase 1 DB tests for P-PUB-VARIANT-PROPERTIES (MP006, Spec 011).

Verifies that the two new columns on `product_attribute` exist with the
expected types and that the Boolean default applies on new rows.

Fields:
- `x_etsy_property_id` — Char (varchar), nullable, stores Etsy attribute
  taxonomy ID as string to avoid XML-RPC int32 overflow on large IDs.
- `x_publish_as_property` — Boolean, default=True, gates whether the axis
  is sent to Etsy push_inventory products[].property_values[].
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPubVariantPropertiesDB(TransactionCase):
    """Phase 1 DB schema verification."""

    def test_x_etsy_property_id_column_exists(self):
        """product_attribute.x_etsy_property_id is varchar."""
        self.env.cr.execute(
            """
            SELECT data_type
              FROM information_schema.columns
             WHERE table_name = 'product_attribute'
               AND column_name = 'x_etsy_property_id'
            """
        )
        row = self.env.cr.fetchone()
        self.assertIsNotNone(
            row,
            "product_attribute.x_etsy_property_id column must exist",
        )
        self.assertIn(
            row[0],
            ('character varying', 'text'),
            f"Expected varchar/text, got {row[0]}",
        )

    def test_x_publish_as_property_column_exists(self):
        """product_attribute.x_publish_as_property is boolean."""
        self.env.cr.execute(
            """
            SELECT data_type
              FROM information_schema.columns
             WHERE table_name = 'product_attribute'
               AND column_name = 'x_publish_as_property'
            """
        )
        row = self.env.cr.fetchone()
        self.assertIsNotNone(
            row,
            "product_attribute.x_publish_as_property column must exist",
        )
        self.assertEqual(row[0], 'boolean', f"Expected boolean, got {row[0]}")

    def test_x_publish_as_property_default_false_on_new_row(self):
        """Opt-in default — new attributes do NOT publish to Etsy until an
        admin flips x_publish_as_property=True (fail-closed security per
        review HIGH 1 on 2026-05-27). Seed XML opts in the known
        publishable axes (Material/Color/Size/Shape/Fluid oz/Apparel Size)."""
        attr = self.env['product.attribute'].create({
            'name': 'Phase1 Probe',
            'create_variant': 'always',
            'display_type': 'select',
        })
        self.assertFalse(
            attr.x_publish_as_property,
            "x_publish_as_property must default to False (opt-in to publish)",
        )
