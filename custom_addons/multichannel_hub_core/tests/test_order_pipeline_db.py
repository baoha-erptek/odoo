"""P1-PIPELINE-MIN Phase 1 — DB schema verification for order.pipeline.

Tests verify:
- Table + columns exist
- 3 seed pipelines + ICP default
- product.template / product.category fields exist
- sale.order.x_pipeline_id stored compute column
- ACL rows
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOrderPipelineDatabase(TransactionCase):
    """Phase 1 — direct schema verification."""

    def test_order_pipeline_table_exists(self):
        self.env.cr.execute("""
            SELECT EXISTS(
                SELECT FROM information_schema.tables
                WHERE table_schema='public' AND table_name='order_pipeline'
            )
        """)
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_order_pipeline_columns(self):
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='order_pipeline'
        """)
        cols = {r[0] for r in self.env.cr.fetchall()}
        for required in ('name', 'code', 'sequence', 'is_active', 'channel_hint', 'description'):
            self.assertIn(required, cols, f"order_pipeline must have column {required}")

    def test_order_pipeline_unique_code_constraint(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname IN ('order_pipeline_uniq_code', 'order_pipeline_uniq_order_pipeline_code')
        """)
        self.assertTrue(self.env.cr.fetchone(), "UNIQUE on order_pipeline.code must exist")

    def test_three_seed_pipelines(self):
        codes = set(self.env['order.pipeline'].search([]).mapped('code'))
        for expected in ('vn_internal_production', 'gearment_pod', 'multi_technique_hybrid'):
            self.assertIn(expected, codes, f"Seed pipeline {expected} missing")

    def test_default_pipeline_icp(self):
        val = self.env['ir.config_parameter'].get_param('multichannel_hub.default_pipeline_code')
        self.assertEqual(val, 'vn_internal_production')

    def test_product_template_x_default_pipeline_field_exists(self):
        self.assertIn('x_default_pipeline_id', self.env['product.template']._fields)

    def test_product_category_x_default_pipeline_field_exists(self):
        self.assertIn('x_default_pipeline_id', self.env['product.category']._fields)

    def test_sale_order_x_pipeline_field_stored(self):
        field = self.env['sale.order']._fields.get('x_pipeline_id')
        self.assertIsNotNone(field, "sale.order.x_pipeline_id must exist")
        self.assertTrue(field.store, "x_pipeline_id must be stored")

    def test_acl_order_pipeline_manager_full(self):
        acl = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'order.pipeline'),
            ('group_id', '=', self.env.ref('sales_team.group_sale_manager').id),
        ])
        self.assertTrue(acl)
        self.assertTrue(acl.perm_read and acl.perm_write and acl.perm_create and acl.perm_unlink)

    def test_acl_order_pipeline_salesman_read_only(self):
        acl = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'order.pipeline'),
            ('group_id', '=', self.env.ref('sales_team.group_sale_salesman').id),
        ])
        self.assertTrue(acl)
        self.assertTrue(acl.perm_read)
        self.assertFalse(acl.perm_write)
        self.assertFalse(acl.perm_create)
        self.assertFalse(acl.perm_unlink)
