"""P1-DESIGN+GEARMENT Phase 2 — design.file proof_sent state machine + dashboard helpers."""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDesignProofWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.prod_group = cls.env.ref('multichannel_hub_core.group_production_team')
        cls.ba_group = cls.env.ref(
            'multichannel_hub_fulfillment.group_ba_shipping')
        cls.user_group = cls.env.ref('base.group_user')
        cls.salesman_group = cls.env.ref('sales_team.group_sale_salesman')
        cls.sales_mgr_group = cls.env.ref('sales_team.group_sale_manager')
        cls.partner = cls.env['res.partner'].create({'name': 'P1-DG Buyer'})
        cls.product = cls.env['product.product'].create({
            'name': 'P1-DG Test Product',
            'list_price': 10.0,
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id, 'product_uom_qty': 1,
            })],
        })
        cls.line = cls.order.order_line[0]
        cls.ba_user = cls.env['res.users'].create({
            'name': 'P1-DG BA', 'login': 'p1dg_ba@test.com',
            'email': 'p1dg_ba@test.com',
            'group_ids': [(6, 0, [cls.ba_group.id, cls.user_group.id, cls.sales_mgr_group.id])],
        })
        cls.mp_user = cls.env['res.users'].create({
            'name': 'P1-DG MP', 'login': 'p1dg_mp@test.com',
            'email': 'p1dg_mp@test.com',
            'group_ids': [(6, 0, [cls.prod_group.id, cls.user_group.id, cls.sales_mgr_group.id])],
        })
        cls.regular_user = cls.env['res.users'].create({
            'name': 'P1-DG REG', 'login': 'p1dg_reg@test.com',
            'email': 'p1dg_reg@test.com',
            'group_ids': [(6, 0, [cls.user_group.id])],
        })

    def _make_design_file(self, state='pending', name='design'):
        df = self.env['design.file'].with_context(
            bypass_design_state_guard=True,
        ).create({
            'name': name,
            'order_line_id': self.line.id,
            'storage_mode': 'url',
            'file_url': 'https://drive.example/d/foo',
            'state': state,
        })
        # Return a context-clean recordset so subsequent writes go through
        # the gate + state-machine guard.
        return df.with_env(df.env(context={}))

    def test_send_proof_pending_to_proof_sent(self):
        df = self._make_design_file('pending')
        df.with_user(self.ba_user).action_send_proof_to_buyer(buyer_message='Pls review')
        self.assertEqual(df.state, 'proof_sent')
        self.assertTrue(df.proof_sent_at)
        self.assertEqual(df.proof_sent_by, self.ba_user)

    def test_send_proof_rejected_to_proof_sent(self):
        df = self._make_design_file('rejected')
        df.with_user(self.ba_user).action_send_proof_to_buyer()
        self.assertEqual(df.state, 'proof_sent')

    def test_send_proof_blocks_regular_user(self):
        df = self._make_design_file('pending')
        with self.assertRaises(AccessError):
            df.with_user(self.regular_user).action_send_proof_to_buyer()

    def test_send_proof_chatter_escapes_xss(self):
        df = self._make_design_file('pending')
        evil = "<script>alert('xss')</script>"
        df.with_user(self.ba_user).action_send_proof_to_buyer(buyer_message=evil)
        last = self.order.message_ids.sorted('id', reverse=True)[:1]
        self.assertTrue(last)
        body = (last.body or '')
        self.assertNotIn('<script>', body)
        self.assertIn('&lt;script&gt;', body)

    def test_approval_blocks_ba(self):
        df = self._make_design_file('pending')
        df.with_user(self.ba_user).action_send_proof_to_buyer()
        # BA cannot approve.
        with self.assertRaises(AccessError):
            df.with_user(self.ba_user).action_approve()

    def test_approval_allows_production(self):
        df = self._make_design_file('pending')
        df.with_user(self.ba_user).action_send_proof_to_buyer()
        df.with_user(self.mp_user).action_approve()
        self.assertEqual(df.state, 'approved')

    def test_state_machine_blocks_invalid_transition(self):
        df = self._make_design_file('pending')
        df.with_user(self.ba_user).action_send_proof_to_buyer()
        df.with_user(self.mp_user).action_approve()
        # Approved → cannot move (terminal). Memory #51: TransactionCase
        # assertRaises(tuple) breaks; use savepoint+try/except.
        raised = False
        try:
            with self.env.cr.savepoint():
                df.with_user(self.mp_user).write({'state': 'pending'})
        except (ValidationError, AccessError):
            raised = True
        self.assertTrue(raised, "approved→pending must raise")


@tagged('post_install', '-at_install')
class TestDashboardActions(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.prod_group = cls.env.ref('multichannel_hub_core.group_production_team')
        cls.ba_group = cls.env.ref(
            'multichannel_hub_fulfillment.group_ba_shipping')
        cls.user_group = cls.env.ref('base.group_user')
        cls.salesman_group = cls.env.ref('sales_team.group_sale_salesman')
        cls.sales_mgr_group = cls.env.ref('sales_team.group_sale_manager')
        cls.partner = cls.env['res.partner'].create({'name': 'P1-DG Buyer DA'})
        cls.product = cls.env['product.product'].create({
            'name': 'P1-DG DA Product', 'list_price': 5.0,
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id, 'product_uom_qty': 1,
            })],
        })
        cls.ba = cls.env['res.users'].create({
            'name': 'BA-DA', 'login': 'ba_da@t.com', 'email': 'ba_da@t.com',
            'group_ids': [(6, 0, [cls.ba_group.id, cls.user_group.id, cls.sales_mgr_group.id])],
        })
        cls.regular = cls.env['res.users'].create({
            'name': 'Reg-DA', 'login': 'reg_da@t.com', 'email': 'reg_da@t.com',
            'group_ids': [(6, 0, [cls.user_group.id])],
        })

    def _make_files(self, *states):
        out = self.env['design.file']
        for i, st in enumerate(states):
            df = self.env['design.file'].with_context(
                bypass_design_state_guard=True,
            ).create({
                'name': f'd{i}',
                'order_line_id': self.order.order_line[0].id,
                'storage_mode': 'url',
                'file_url': f'https://drive.example/d/{i}',
                'state': st,
            })
            out |= df.with_env(df.env(context={}))
        return out

    def test_dashboard_send_proof_fans_out(self):
        files = self._make_files('pending', 'pending', 'approved')
        self.order.with_user(self.ba).action_dashboard_send_proof()
        states = sorted(files.mapped('state'))
        self.assertEqual(states, ['approved', 'proof_sent', 'proof_sent'])

    def test_dashboard_approve_designs_fans_out(self):
        files = self._make_files('pending', 'pending')
        self.order.with_user(self.ba).action_dashboard_send_proof()
        # Approve as production_team via order method.
        prod = self.env['res.users'].create({
            'name': 'MP-DA', 'login': 'mp_da@t.com', 'email': 'mp_da@t.com',
            'group_ids': [(6, 0, [self.prod_group.id, self.user_group.id, self.sales_mgr_group.id])],
        })
        self.order.with_user(prod).action_dashboard_approve_designs()
        self.assertEqual(set(files.mapped('state')), {'approved'})

    def test_dashboard_send_proof_blocks_regular(self):
        self._make_files('pending')
        with self.assertRaises(AccessError):
            self.order.with_user(self.regular).action_dashboard_send_proof()
