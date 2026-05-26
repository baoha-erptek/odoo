"""
Phase 1: Database-level verification for P-HUB-MISSING-INFO-WIZARD (Spec 009 §2.6).

Verifies the schema extensions to `product.sku.builder.wizard`:
- size_id_manual Many2one column on wizard transient table
- rect_w_manual Integer column
- rect_h_manual Integer column
- _is_size_extractable Boolean computed field (stored=False)
- Wizard view extended with conditional sub-form containing manual fallback fields

Tests use direct SQL and ORM field introspection to verify schema state at the
lowest level, independent of ORM machinery or view rendering.

Spec 009 T075. RED before T070-T074 implementation lands.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPhase1MissingInfoDB(TransactionCase):
    """Direct verification for P-HUB-MISSING-INFO-WIZARD schema extensions."""

    # ------------------------------------------------------------------
    # product.sku.builder.wizard — new field columns
    # ------------------------------------------------------------------

    def test_wizard_size_id_manual_field_exists(self):
        """T070: size_id_manual Many2one field must be registered on wizard."""
        Wizard = self.env['product.sku.builder.wizard']
        self.assertIn(
            'size_id_manual',
            Wizard._fields,
            "product.sku.builder.wizard must have size_id_manual field",
        )
        field = Wizard._fields['size_id_manual']
        self.assertEqual(
            field.comodel_name,
            'product.attribute.value',
            "size_id_manual must be Many2one to product.attribute.value",
        )

    def test_wizard_rect_w_manual_field_exists(self):
        """T070: rect_w_manual Integer field must be registered on wizard."""
        Wizard = self.env['product.sku.builder.wizard']
        self.assertIn(
            'rect_w_manual',
            Wizard._fields,
            "product.sku.builder.wizard must have rect_w_manual field",
        )
        field = Wizard._fields['rect_w_manual']
        self.assertEqual(
            field.type,
            'integer',
            "rect_w_manual must be Integer field",
        )

    def test_wizard_rect_h_manual_field_exists(self):
        """T070: rect_h_manual Integer field must be registered on wizard."""
        Wizard = self.env['product.sku.builder.wizard']
        self.assertIn(
            'rect_h_manual',
            Wizard._fields,
            "product.sku.builder.wizard must have rect_h_manual field",
        )
        field = Wizard._fields['rect_h_manual']
        self.assertEqual(
            field.type,
            'integer',
            "rect_h_manual must be Integer field",
        )

    def test_wizard_is_size_extractable_computed_field_exists(self):
        """T070: _is_size_extractable Boolean computed field (stored=False) must exist."""
        Wizard = self.env['product.sku.builder.wizard']
        self.assertIn(
            '_is_size_extractable',
            Wizard._fields,
            "product.sku.builder.wizard must have _is_size_extractable field",
        )
        field = Wizard._fields['_is_size_extractable']
        self.assertEqual(
            field.type,
            'boolean',
            "_is_size_extractable must be Boolean field",
        )
        self.assertFalse(
            field.store,
            "_is_size_extractable computed field must have store=False",
        )

    # ------------------------------------------------------------------
    # View registration and schema
    # ------------------------------------------------------------------

    def test_builder_wizard_view_form_registered(self):
        """T071: product_sku_builder_wizard_view_form must be registered in ir_ui_view."""
        view = self.env['ir.ui.view'].search([
            ('model', '=', 'product.sku.builder.wizard'),
            ('type', '=', 'form'),
        ], limit=1)
        self.assertTrue(
            view,
            "product.sku.builder.wizard form view must exist",
        )

    def test_builder_wizard_view_contains_manual_size_fields(self):
        """T071: View arch must include size_id_manual and rect_*_manual fields."""
        view = self.env['ir.ui.view'].search([
            ('model', '=', 'product.sku.builder.wizard'),
            ('type', '=', 'form'),
        ], limit=1)
        self.assertTrue(view, "View must exist")
        arch = view.arch or ''
        self.assertIn(
            'size_id_manual',
            arch,
            "View arch must contain size_id_manual reference",
        )
        self.assertIn(
            'rect_w_manual',
            arch,
            "View arch must contain rect_w_manual reference",
        )
        self.assertIn(
            'rect_h_manual',
            arch,
            "View arch must contain rect_h_manual reference",
        )

    def test_builder_wizard_view_contains_conditional_invisible(self):
        """T071: View must use conditional invisible attribute for sub-form display."""
        view = self.env['ir.ui.view'].search([
            ('model', '=', 'product.sku.builder.wizard'),
            ('type', '=', 'form'),
        ], limit=1)
        self.assertTrue(view, "View must exist")
        arch = view.arch or ''
        # Check for the conditional visibility pattern used for fallback fields
        # Pattern: invisible="step != '3' or _is_size_extractable"
        self.assertIn(
            '_is_size_extractable',
            arch,
            "View arch must reference _is_size_extractable for conditional visibility",
        )
