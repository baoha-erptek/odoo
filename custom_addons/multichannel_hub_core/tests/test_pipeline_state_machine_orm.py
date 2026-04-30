"""P1-PIPELINE-FULL Phase 2 — ORM tests for the state machine + audit log."""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPipelineStateMachine(TransactionCase):

    def setUp(self):
        super().setUp()
        self.vn = self.env.ref(
            'multichannel_hub_core.order_pipeline_vn_internal_production')
        self.gearment = self.env.ref(
            'multichannel_hub_core.order_pipeline_gearment_pod')
        self.s_pending = self.env.ref(
            'multichannel_hub_core.state_vn_pending_file')
        self.s_production = self.env.ref(
            'multichannel_hub_core.state_vn_in_production')
        self.s_done = self.env.ref('multichannel_hub_core.state_vn_done')
        self.s_gearment_draft = self.env.ref(
            'multichannel_hub_core.state_gearment_draft')

        self.partner = self.env['res.partner'].create({'name': 'Buyer'})
        cat = self.env.ref('product.product_category_goods')
        self.product = self.env['product.product'].create({
            'name': 'Internal Product',
            'list_price': 1.0,
            'categ_id': cat.id,
            'product_tmpl_id_x_default_pipeline': self.vn.id,
        }) if False else self.env['product.product'].create({
            'name': 'Internal Product',
            'list_price': 1.0,
            'categ_id': cat.id,
        })
        self.product.product_tmpl_id.x_default_pipeline_id = self.vn.id

    def _make_order(self):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': 1.0})],
        })

    def test_initial_state_assigned_on_create(self):
        order = self._make_order()
        self.assertEqual(order.x_pipeline_id, self.vn)
        self.assertEqual(order.x_pipeline_state_id, self.s_pending)

    def test_initial_state_logs_transition(self):
        order = self._make_order()
        log = self.env['order.pipeline.transition.log'].search([
            ('sale_order_id', '=', order.id),
        ])
        self.assertEqual(len(log), 1)
        self.assertFalse(log.from_state_id)
        self.assertEqual(log.to_state_id, self.s_pending)
        self.assertEqual(log.change_type, 'initial')
        self.assertEqual(log.pipeline_id, self.vn)

    def test_write_pipeline_state_happy_path(self):
        order = self._make_order()
        order._write_pipeline_state(self.s_production, note='moving to prod')
        self.assertEqual(order.x_pipeline_state_id, self.s_production)
        logs = self.env['order.pipeline.transition.log'].search(
            [('sale_order_id', '=', order.id)],
            order='timestamp asc, id asc',
        )
        self.assertEqual(len(logs), 2)
        latest = logs[-1]
        self.assertEqual(latest.from_state_id, self.s_pending)
        self.assertEqual(latest.to_state_id, self.s_production)
        self.assertEqual(latest.change_type, 'manual')
        self.assertEqual(latest.note, 'moving to prod')

    def test_write_pipeline_state_rejects_cross_pipeline(self):
        order = self._make_order()
        with self.assertRaises(ValidationError):
            order._write_pipeline_state(self.s_gearment_draft)

    def test_write_pipeline_state_rejects_empty(self):
        order = self._make_order()
        empty = self.env['order.pipeline.state']
        with self.assertRaises(ValidationError):
            order._write_pipeline_state(empty)

    def test_write_pipeline_state_change_type_param(self):
        order = self._make_order()
        order._write_pipeline_state(
            self.s_done, note='auto-done', change_type='automatic')
        latest = self.env['order.pipeline.transition.log'].search(
            [('sale_order_id', '=', order.id)],
            order='timestamp desc, id desc', limit=1,
        )
        self.assertEqual(latest.change_type, 'automatic')

    def test_constraint_one_initial_per_pipeline(self):
        with self.assertRaises(ValidationError):
            self.env['order.pipeline.state'].create({
                'pipeline_id': self.vn.id,
                'name': 'Second Initial',
                'code': 'second_initial_test',
                'is_initial': True,
            })

    def test_compute_initial_state_id_reflects_state_change(self):
        new_pipeline = self.env['order.pipeline'].create({
            'name': 'Tmp Pipeline', 'code': 'tmp_pipeline_test',
            'channel_hint': 'other',
        })
        self.assertFalse(new_pipeline.initial_state_id)
        s1 = self.env['order.pipeline.state'].create({
            'pipeline_id': new_pipeline.id,
            'name': 'Init', 'code': 'init',
            'is_initial': True,
        })
        new_pipeline.invalidate_recordset(['initial_state_id'])
        self.assertEqual(new_pipeline.initial_state_id, s1)

    def test_is_in_use_flips_when_order_assigned(self):
        new_pipeline = self.env['order.pipeline'].create({
            'name': 'Unused', 'code': 'unused_test',
            'channel_hint': 'other',
        })
        self.assertFalse(new_pipeline.is_in_use)
        # Create order on default pipeline (vn) — `unused_test` stays unused.
        self._make_order()
        new_pipeline.invalidate_recordset(['is_in_use'])
        self.assertFalse(new_pipeline.is_in_use)
        self.vn.invalidate_recordset(['is_in_use'])
        self.assertTrue(self.vn.is_in_use)

    def test_state_unique_pipeline_code(self):
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env['order.pipeline.state'].create({
                    'pipeline_id': self.vn.id,
                    'name': 'Dup',
                    'code': 'pending_file',
                })

    def test_direct_write_to_x_pipeline_state_id_blocked(self):
        """FR-017: bypassing _write_pipeline_state must raise."""
        order = self._make_order()
        with self.assertRaises(ValidationError):
            order.write({'x_pipeline_state_id': self.s_production.id})

    def test_direct_write_allowed_with_bypass_context(self):
        order = self._make_order()
        order.with_context(
            bypass_pipeline_state_guard=True,
        ).write({'x_pipeline_state_id': self.s_production.id})
        self.assertEqual(order.x_pipeline_state_id, self.s_production)

    def test_unlink_pipeline_in_use_blocked_by_state_restrict(self):
        """Pipeline with an active order cannot be deleted thanks to the
        order.pipeline.transition.log.pipeline_id ondelete='restrict'."""
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger
        order = self._make_order()
        self.assertTrue(order.x_pipeline_id)
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.vn.unlink()
