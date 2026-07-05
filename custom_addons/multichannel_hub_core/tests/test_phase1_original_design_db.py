"""Phase 1: Database-level verification for ESTY-250 (Original Design tab).

Verifies the underlying PostgreSQL schema:
- product_document.x_is_original_design column exists
- product.template field metadata registers x_original_design_ids
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('at_install', '-post_install')
class TestPhase1OriginalDesignDB(TransactionCase):

    def test_x_is_original_design_column_exists(self):
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'product_document'
              AND column_name = 'x_is_original_design'
        """)
        self.assertIsNotNone(
            self.env.cr.fetchone(),
            "product_document.x_is_original_design column must exist",
        )

    def test_product_template_x_original_design_ids_field_registered(self):
        self.assertIn(
            'x_original_design_ids',
            self.env['product.template']._fields,
            "product.template must expose x_original_design_ids",
        )
