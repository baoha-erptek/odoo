"""P1-OPS-DESIGN-LINK — sale.order design-file UI hooks (Slice 1).

Phase 1 (DB) + Phase 2 (ORM) tests pinning the contract:
  1. New form-view `view_order_form_design_link` inherits sale.view_order_form
     and contains the smart button + notebook tab.
  2. `sale.order.design_files_count` is a computed Integer aggregating
     header + line design files.
  3. `sale.order.action_open_design_files()` returns an act_window scoped
     to the order via context/domain.
  4. `sale.order.action_open_design_file_upload_wizard()` returns the
     wizard action with `default_order_id` injected, RPC-gated to
     production_team / system.

These tests fail before Slice 1 lands.
"""
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOpsDesignLinkPhase1DB(TransactionCase):
    """Phase 1 — XML data + view-arch sanity."""

    def test_view_order_form_design_link_exists(self):
        view = self.env.ref(
            'multichannel_hub_core.view_order_form_design_link',
            raise_if_not_found=False,
        )
        self.assertTrue(view, "Inherited sale.order form not registered.")
        self.assertEqual(view.model, 'sale.order')
        self.assertEqual(
            view.inherit_id.xml_id, 'sale.view_order_form',
            "Must inherit from the standard sale.order form.",
        )

    def test_view_arch_contains_smart_button_and_notebook_tab(self):
        view = self.env.ref('multichannel_hub_core.view_order_form_design_link')
        arch = view.arch_db or ''
        self.assertIn('action_open_design_files', arch,
                      "Smart button must call action_open_design_files.")
        self.assertIn('design_files_count', arch,
                      "Smart button must show design_files_count badge.")
        self.assertIn('action_open_design_file_upload_wizard', arch,
                      "Notebook tab header must include the upload wizard "
                      "button.")
        self.assertIn('design_file_ids', arch,
                      "Notebook tab must render the One2many list.")


@tagged('post_install', '-at_install')
class TestOpsDesignLinkPhase2ORM(TransactionCase):
    """Phase 2 — count compute + action wiring + ACL gate."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.prod_group = cls.env.ref('multichannel_hub_core.group_production_team')
        cls.user_group = cls.env.ref('base.group_user')
        cls.sales_mgr_group = cls.env.ref('sales_team.group_sale_manager')

        cls.partner = cls.env['res.partner'].create({'name': 'OPS-DL Buyer'})
        cls.product = cls.env['product.product'].create({
            'name': 'OPS-DL Product', 'list_price': 10.0,
        })
        cls.order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id, 'product_uom_qty': 1,
            })],
        })
        cls.line = cls.order.order_line[0]

        cls.mp_user = cls.env['res.users'].create({
            'name': 'OPS-DL MP', 'login': 'ops_dl_mp@test.com',
            'email': 'ops_dl_mp@test.com',
            'group_ids': [(6, 0, [
                cls.prod_group.id, cls.user_group.id, cls.sales_mgr_group.id,
            ])],
        })
        cls.salesman_user = cls.env['res.users'].create({
            'name': 'OPS-DL Salesman', 'login': 'ops_dl_sm@test.com',
            'email': 'ops_dl_sm@test.com',
            'group_ids': [(6, 0, [
                cls.user_group.id, cls.sales_mgr_group.id,
            ])],
        })

    def _make_design_file(self, *, on_line=False, name='df'):
        vals = {
            'name': name,
            'storage_mode': 'url',
            'file_url': 'https://drive.example/d/%s' % name,
            'state': 'pending',
        }
        if on_line:
            vals['order_line_id'] = self.line.id
        else:
            vals['order_id'] = self.order.id
        return self.env['design.file'].with_context(
            bypass_design_state_guard=True,
        ).create(vals)

    def test_design_files_count_aggregates_header_and_line_files(self):
        self._make_design_file(name='hdr1')
        self._make_design_file(name='hdr2')
        self._make_design_file(on_line=True, name='line1')
        self.order.invalidate_recordset(['design_files_count'])
        self.assertEqual(self.order.design_files_count, 3)

    def test_action_open_design_files_returns_filtered_action(self):
        self._make_design_file(name='hdr1')
        self._make_design_file(on_line=True, name='line1')
        action = self.order.action_open_design_files()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'design.file')
        order_ids = self.order._all_design_files().ids
        self.assertEqual(
            sorted(action['domain'][0][2]),
            sorted(order_ids),
            "Domain must scope to this order's design files.",
        )

    def test_action_open_upload_wizard_injects_default_order_id(self):
        action = self.order.with_user(self.mp_user) \
            .action_open_design_file_upload_wizard()
        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'design.file.upload.wizard')
        ctx = action.get('context') or {}
        self.assertEqual(ctx.get('default_order_id'), self.order.id)

    def test_action_open_upload_wizard_blocks_non_production(self):
        with self.assertRaises(AccessError):
            self.order.with_user(self.salesman_user) \
                .action_open_design_file_upload_wizard()
