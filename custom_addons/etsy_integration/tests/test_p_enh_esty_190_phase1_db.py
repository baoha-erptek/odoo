"""Phase 1 DB tests for P-ENH-ESTY-190 / ADR-017 — shop brand-voice defaults."""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPEnhEsty190Phase1DB(TransactionCase):
    """DB-level assertions for shop brand-voice default columns."""

    def test_default_title_column_exists(self):
        self.env.cr.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'etsy_shop'
              AND column_name = 'default_title'
        """)
        row = self.env.cr.fetchone()
        self.assertEqual(
            row and row[0], 'character varying',
            "etsy_shop.default_title must be a varchar column",
        )

    def test_default_title_length_140(self):
        self.env.cr.execute("""
            SELECT character_maximum_length FROM information_schema.columns
            WHERE table_name = 'etsy_shop' AND column_name = 'default_title'
        """)
        row = self.env.cr.fetchone()
        self.assertEqual(
            row and row[0], 140,
            "etsy_shop.default_title size must be 140 per spec §5",
        )

    def test_default_description_column_exists(self):
        self.env.cr.execute("""
            SELECT data_type FROM information_schema.columns
            WHERE table_name = 'etsy_shop'
              AND column_name = 'default_description'
        """)
        row = self.env.cr.fetchone()
        self.assertEqual(
            row and row[0], 'text',
            "etsy_shop.default_description must be a text column",
        )

    def test_default_image_1920_field_exists(self):
        # ``fields.Image`` is attachment-backed in Odoo 19; it does not
        # create a column on the host table. Check ir.model.fields
        # instead (memory feedback_odoo19_test_gotchas item 152 pattern).
        self.env.cr.execute("""
            SELECT 1 FROM ir_model_fields
            WHERE model = 'etsy.shop'
              AND name = 'default_image_1920'
        """)
        self.assertTrue(
            self.env.cr.fetchone(),
            "etsy_shop.default_image_1920 field must be registered",
        )
