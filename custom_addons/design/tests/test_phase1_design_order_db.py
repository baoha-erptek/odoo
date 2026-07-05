"""Phase 1 (DB-level) tests for the design module — ESTY-244."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'design')
class TestDesignOrderDB(TransactionCase):

    def _columns(self, table):
        self.env.cr.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s", (table,))
        return {r[0] for r in self.env.cr.fetchall()}

    def test_design_order_table_and_columns(self):
        cols = self._columns('design_order')
        self.assertTrue(cols, "design_order table should exist")
        for c in ('name', 'sale_order_id', 'state', 'company_id',
                  'approved_by', 'approved_at', 'rejection_reason'):
            self.assertIn(c, cols, "design_order missing column %s" % c)

    def test_design_file_has_design_order_id(self):
        self.assertIn('design_order_id', self._columns('design_file'),
                      "design.file should gain design_order_id (ESTY-244)")

    def test_unique_sale_order_constraint(self):
        self.env.cr.execute(
            "SELECT 1 FROM pg_constraint WHERE conname = %s",
            ('design_order_uniq_design_order_sale_order',))
        self.assertTrue(self.env.cr.fetchone(),
                        "UNIQUE(sale_order_id) constraint should be deployed")

    def test_sequence_seeded(self):
        seq = self.env['ir.sequence'].search([('code', '=', 'design.order')])
        self.assertTrue(seq, "design.order sequence should be seeded")

    def test_design_ready_pipeline_states_seeded(self):
        states = self.env['order.pipeline.state'].search(
            [('code', '=', 'design_ready')])
        self.assertGreaterEqual(
            len(states), 1,
            "at least one 'design_ready' pipeline state should be seeded")

    def test_auto_create_param_default_true(self):
        val = self.env['ir.config_parameter'].sudo().get_param(
            'design.auto_create_on_confirm')
        self.assertEqual(val, 'True')

    def test_mo_exposes_design_ready_fields(self):
        # ESTY-249: mrp.production gains computed (non-stored) design_ready +
        # design_order_id — registry-level presence check (no DB columns).
        info = self.env['mrp.production'].fields_get(
            ['design_ready', 'design_order_id'])
        self.assertIn('design_ready', info,
                      "mrp.production should expose design_ready (ESTY-249)")
        self.assertIn('design_order_id', info,
                      "mrp.production should expose design_order_id (ESTY-249)")
        self.assertFalse(info['design_ready'].get('store', False),
                         "design_ready is a non-stored computed field")
