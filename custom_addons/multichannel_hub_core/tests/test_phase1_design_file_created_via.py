"""Phase 1 (DB-level) tests for P1-DESIGN-AUTO-CREATE-FROM-EMAIL.

Verifies schema changes at the database level:
- created_via column exists on design.file
- created_via column is indexed for query performance
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDesignFileCreatedViaColumn(TransactionCase):
    """Phase 1: Direct database verification for design.file.created_via."""

    def test_db_design_file_has_created_via_column(self):
        """Verify created_via column exists on design.file table."""
        self.env.cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'design_file'
              AND column_name = 'created_via'
        """)
        result = self.env.cr.fetchall()
        self.assertEqual(
            len(result), 1,
            "design.file must have a created_via column"
        )

    def test_db_design_file_created_via_indexed(self):
        """Verify created_via column has a database index for query performance."""
        self.env.cr.execute("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'design_file'
              AND indexdef LIKE '%created_via%'
        """)
        result = self.env.cr.fetchall()
        self.assertGreaterEqual(
            len(result), 1,
            "design.file.created_via must have at least one index"
        )

    def test_db_created_via_default_value(self):
        """Verify created_via column has proper default constraints.

        The field should accept NULL during migration (for existing rows)
        and provide default='operator_wizard' on new rows created via ORM.
        """
        # Create a design.file record and verify the default is applied
        # via ORM (not at DB level, which allows NULL migration).
        # Demo data is disabled in this DB; build minimal fixtures inline.
        partner = self.env['res.partner'].create({'name': 'TestDFCV Partner'})
        product = self.env['product.product'].create({
            'name': 'TestDFCV Product', 'list_price': 10.0,
        })
        order = self.env['sale.order'].create({'partner_id': partner.id})
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': product.id,
        })
        design_file = self.env['design.file'].create({
            'name': 'Test Design',
            'order_line_id': line.id,
            'storage_mode': 'url',
            'file_url': 'https://example.com/design.png',
            'state': 'pending',
        })
        # Verify ORM-level default is applied
        self.assertEqual(
            design_file.created_via, 'operator_wizard',
            "created_via should default to 'operator_wizard' when not specified"
        )
