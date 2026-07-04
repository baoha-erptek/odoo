"""Phase D#3 — pipeline transition wizard + "In Lại" reprint state.

Flow 3a #3 / Flow 4 #3. The Pipeline tab exposes the current stage read-only;
transitions go through order.pipeline.transition.wizard, which calls the
audited sale.order._write_pipeline_state helper. Also seeds an "In Lại"
(reprint) state that loops a completed order back into production.
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPipelineTransitionWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vn = cls.env.ref(
            'multichannel_hub_core.order_pipeline_vn_internal_production')
        cls.s_done = cls.env.ref('multichannel_hub_core.state_vn_done')
        cls.s_reprint = cls.env.ref('multichannel_hub_core.state_vn_reprint')
        cls.s_production = cls.env.ref(
            'multichannel_hub_core.state_vn_in_production')
        cls.partner = cls.env['res.partner'].create({'name': 'Buyer D3'})
        cls.product = cls.env['product.product'].create({
            'name': 'Internal Product D3',
            'list_price': 1.0,
            'categ_id': cls.env.ref('product.product_category_goods').id,
        })
        cls.product.product_tmpl_id.x_default_pipeline_id = cls.vn.id

    def _order(self):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id, 'product_uom_qty': 1.0})],
        })

    def test_reprint_state_seeded_and_loops_to_production(self):
        self.assertEqual(self.s_reprint.pipeline_id, self.vn)
        self.assertEqual(self.s_reprint.code, 'reprint')
        self.assertIn(self.s_production, self.s_reprint.next_state_ids)

    def test_wizard_transitions_and_logs(self):
        order = self._order()
        # complete the order, then reprint it via the wizard
        order._write_pipeline_state(self.s_done, note='done')
        wizard = self.env['order.pipeline.transition.wizard'].create({
            'order_id': order.id,
            'new_state_id': self.s_reprint.id,
            'note': 'Defective — reprint',
        })
        wizard.action_confirm()
        self.assertEqual(order.x_pipeline_state_id, self.s_reprint)
        latest = self.env['order.pipeline.transition.log'].search(
            [('sale_order_id', '=', order.id)],
            order='timestamp asc, id asc')[-1]
        self.assertEqual(latest.to_state_id, self.s_reprint)
        self.assertEqual(latest.from_state_id, self.s_done)
        self.assertEqual(latest.change_type, 'manual')
        self.assertEqual(latest.note, 'Defective — reprint')

    def test_wizard_default_get_populates_pipeline_for_domain(self):
        # Regression: ISSUE-QA-D3-01 — new_state_id's domain filters on
        # pipeline_id; if default_get does not seed the related pipeline_id /
        # current_state_id, the form opens with pipeline_id empty and the New
        # State dropdown lists ZERO states (wizard unusable). The other wizard
        # test create()s the record directly, bypassing this path.
        # Found by /qa on 2026-06-21.
        order = self._order()
        order._write_pipeline_state(self.s_production, note='setup')
        Wizard = self.env['order.pipeline.transition.wizard'].with_context(
            default_order_id=order.id)
        defaults = Wizard.default_get(
            ['order_id', 'pipeline_id', 'current_state_id'])
        self.assertEqual(defaults.get('order_id'), order.id)
        self.assertEqual(defaults.get('pipeline_id'), self.vn.id,
                         'pipeline_id must be seeded so the domain resolves')
        self.assertEqual(defaults.get('current_state_id'), self.s_production.id)
        # The new_state domain [('pipeline_id','=',pipeline_id)] must now match
        # the pipeline's real states.
        states = self.env['order.pipeline.state'].search(
            [('pipeline_id', '=', defaults['pipeline_id'])])
        self.assertIn(self.s_reprint, states)

    def test_direct_state_write_still_blocked(self):
        order = self._order()
        with self.assertRaises(ValidationError):
            order.x_pipeline_state_id = self.s_done.id
