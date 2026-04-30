"""P1-PIPELINE-FULL Phase 1 — DB schema verification.

Covers order.pipeline.state, pipeline.team, order.pipeline.transition.log:
- Tables + key columns
- UNIQUE constraints (drift-template mirror)
- Seed records (3 teams, 12 states across 3 pipelines)
- ACL rows
- Composite index for transition log hot-path
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPipelineStateDatabase(TransactionCase):

    def test_order_pipeline_state_table(self):
        self.env.cr.execute("""
            SELECT EXISTS(SELECT FROM information_schema.tables
            WHERE table_schema='public' AND table_name='order_pipeline_state')
        """)
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_order_pipeline_state_columns(self):
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name='order_pipeline_state'
        """)
        cols = {r[0] for r in self.env.cr.fetchall()}
        for col in ('pipeline_id', 'name', 'code', 'sequence',
                    'is_initial', 'is_terminal', 'color', 'team_id'):
            self.assertIn(col, cols, f"order_pipeline_state.{col} missing")

    def test_state_unique_pipeline_code(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname IN (
                'order_pipeline_state_uniq_pipeline_code',
                'order_pipeline_state_uniq_pipeline_state_code'
            )
        """)
        self.assertTrue(self.env.cr.fetchone(),
                        "UNIQUE(pipeline_id, code) on order_pipeline_state")

    def test_pipeline_team_table(self):
        self.env.cr.execute("""
            SELECT EXISTS(SELECT FROM information_schema.tables
            WHERE table_schema='public' AND table_name='pipeline_team')
        """)
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_pipeline_team_unique_code(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_constraint
            WHERE conname IN ('pipeline_team_uniq_code', 'pipeline_team_uniq_pipeline_team_code')
        """)
        self.assertTrue(self.env.cr.fetchone(),
                        "UNIQUE(code) on pipeline_team")

    def test_transition_log_table(self):
        self.env.cr.execute("""
            SELECT EXISTS(SELECT FROM information_schema.tables
            WHERE table_schema='public' AND table_name='order_pipeline_transition_log')
        """)
        self.assertTrue(self.env.cr.fetchone()[0])

    def test_transition_log_composite_index(self):
        self.env.cr.execute("""
            SELECT 1 FROM pg_indexes
            WHERE indexname = 'order_pipeline_transition_log_order_ts_idx'
        """)
        self.assertTrue(self.env.cr.fetchone(),
                        "Composite (sale_order_id, timestamp DESC) index missing")

    def test_seed_pipeline_teams(self):
        codes = set(self.env['pipeline.team'].search([]).mapped('code'))
        for expected in ('internal_production', 'drop_ship_liaison', 'qa_release'):
            self.assertIn(expected, codes)

    def test_seed_states_vn_internal(self):
        vn = self.env.ref('multichannel_hub_core.order_pipeline_vn_internal_production')
        codes = set(vn.state_ids.mapped('code'))
        self.assertEqual(
            codes,
            {'pending_file', 'in_production', 'packed', 'shipped', 'done'},
        )
        initial = vn.state_ids.filtered(lambda s: s.is_initial)
        self.assertEqual(len(initial), 1)
        self.assertEqual(initial.code, 'pending_file')

    def test_seed_states_gearment(self):
        g = self.env.ref('multichannel_hub_core.order_pipeline_gearment_pod')
        codes = set(g.state_ids.mapped('code'))
        self.assertEqual(codes, {'draft', 'quoted', 'confirmed', 'shipped'})

    def test_seed_states_hybrid(self):
        h = self.env.ref('multichannel_hub_core.order_pipeline_multi_technique_hybrid')
        codes = set(h.state_ids.mapped('code'))
        self.assertEqual(codes, {'setup', 'production', 'done'})

    def test_initial_state_id_computed_per_pipeline(self):
        for ref in ('multichannel_hub_core.order_pipeline_vn_internal_production',
                    'multichannel_hub_core.order_pipeline_gearment_pod',
                    'multichannel_hub_core.order_pipeline_multi_technique_hybrid'):
            p = self.env.ref(ref)
            self.assertTrue(p.initial_state_id,
                            f"Pipeline {p.code} must have initial_state_id stored")
            self.assertTrue(p.initial_state_id.is_initial)

    def test_acl_pipeline_state_manager_full(self):
        acl = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'order.pipeline.state'),
            ('group_id', '=', self.env.ref('sales_team.group_sale_manager').id),
        ])
        self.assertTrue(acl)
        self.assertTrue(acl.perm_read and acl.perm_write
                        and acl.perm_create and acl.perm_unlink)

    def test_acl_transition_log_salesman_read(self):
        acl = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'order.pipeline.transition.log'),
            ('group_id', '=', self.env.ref('sales_team.group_sale_salesman').id),
        ])
        self.assertTrue(acl)
        self.assertTrue(acl.perm_read)
        self.assertFalse(acl.perm_write)
        self.assertFalse(acl.perm_create)
        self.assertFalse(acl.perm_unlink)

    def test_acl_transition_log_manager_read_only(self):
        """Manager may read but not mutate the audit log directly."""
        acl = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'order.pipeline.transition.log'),
            ('group_id', '=', self.env.ref('sales_team.group_sale_manager').id),
        ])
        self.assertTrue(acl)
        self.assertTrue(acl.perm_read)
        self.assertFalse(acl.perm_write)
        self.assertFalse(acl.perm_create)
        self.assertFalse(acl.perm_unlink)

    def test_sale_order_x_pipeline_state_field_exists(self):
        field = self.env['sale.order']._fields.get('x_pipeline_state_id')
        self.assertIsNotNone(field)
        self.assertEqual(field.comodel_name, 'order.pipeline.state')
