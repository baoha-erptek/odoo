"""P-GEAR-AUTOCONFIRM — RED tests for the gated 'Confirm at Gearment' path.

Safety contract (spec 015, findings 2026-07-05 (C/D)): the chargeable
`/orders/draft/labeled` call must be impossible unless the owner flips the
ICP `multichannel_hub.gearment_confirm_enabled` to 'True' (ships OFF), the
caller passes the BA-shipping FR-017 gate, the order has actually been
pushed (draft exists), and it has never been confirmed before (idempotency
via `x_gearment_confirmed_at`). E2E tooling stays draft-only — this suite
mocks the adapter and never touches the real endpoint.
"""
from unittest import mock

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_fulfillment.models import sale_order as so_module


@tagged('post_install', '-at_install', 'gear_confirm_button')
class TestGearmentConfirmButton(TransactionCase):

    _ICP = 'multichannel_hub.gearment_confirm_enabled'

    def setUp(self):
        super().setUp()
        partner = self.env['res.partner'].create({'name': 'Confirm Buyer'})
        product = self.env['product.product'].create({
            'name': 'Confirm Tee', 'type': 'consu', 'list_price': 9.0,
        })
        product.product_tmpl_id.x_gearment_sku = 'GM0249020374'
        self.order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 1})],
        })

    def _confirm(self, *, icp=None, pushed=True, response=None, side_effect=None):
        if icp is not None:
            self.env['ir.config_parameter'].sudo().set_param(self._ICP, icp)
        if pushed and not self.order.x_gearment_outbound_ref:
            self.order.write({'x_gearment_outbound_ref': 'GM-DRAFT-1'})
        mock_adapter = mock.MagicMock()
        mock_adapter.return_value.confirm.return_value = (
            response if response is not None else {'status': 'success'})
        if side_effect is not None:
            mock_adapter.return_value.confirm.side_effect = side_effect
        with mock.patch.object(
                so_module.gearment_adapter, 'GearmentApiAdapter', mock_adapter):
            self.order.action_confirm_at_gearment()
        return mock_adapter.return_value.confirm

    def test_killswitch_off_by_default_blocks_confirm(self):
        """Ships disabled: no ICP set -> UserError, adapter never called."""
        with self.assertRaises(UserError):
            self._confirm()
        self.assertFalse(self.order.x_gearment_confirmed_at)

    def test_not_pushed_blocks_confirm(self):
        with self.assertRaises(UserError):
            self._confirm(icp='True', pushed=False)

    def test_confirm_calls_adapter_and_stamps(self):
        confirm = self._confirm(icp='True')
        confirm.assert_called_once()
        args, kwargs = confirm.call_args
        reference = args[0] if args else kwargs.get('reference_id')
        self.assertEqual(reference, self.order.name)
        self.assertTrue(self.order.x_gearment_confirmed_at)

    def test_second_confirm_blocked_idempotent(self):
        self._confirm(icp='True')
        with self.assertRaises(UserError):
            self._confirm(icp='True')

    def test_adapter_failure_leaves_no_stamp(self):
        with self.assertRaises(UserError):
            self._confirm(icp='True', side_effect=RuntimeError('gearment 500'))
        self.assertFalse(self.order.x_gearment_confirmed_at)

    def test_stamp_immutable_once_set(self):
        """Audit-trail guard: clearing the stamp via RPC write must fail
        (readonly=True is only a UI hint)."""
        self._confirm(icp='True')
        self.assertTrue(self.order.x_gearment_confirmed_at)
        with self.assertRaises(UserError):
            self.order.write({'x_gearment_confirmed_at': False})

    def test_wizard_path_blocked_by_killswitch(self):
        """The quote wizard's confirm routes through the same core — with
        the killswitch off (default) it must refuse before any adapter call."""
        self.env['ir.config_parameter'].sudo().set_param(self._ICP, 'False')
        self.order.write({
            'x_gearment_outbound_ref': 'GM-DRAFT-1',
            'x_gearment_outbound_state': 'operator_review',
        })
        wizard = self.env['gearment.quote.wizard'].create({
            'order_id': self.order.id,
        })
        mock_adapter = mock.MagicMock()
        with mock.patch.object(
                so_module.gearment_adapter, 'GearmentApiAdapter', mock_adapter):
            with self.assertRaises(UserError):
                wizard.action_confirm()
        mock_adapter.return_value.confirm.assert_not_called()

    def test_po_wrapper_confirms_each_unconfirmed_so_once(self):
        self.env['ir.config_parameter'].sudo().set_param(self._ICP, 'True')
        self.order.write({'x_gearment_outbound_ref': 'GM-DRAFT-1'})
        po = self.env['purchase.order'].create({
            'partner_id': self.env['res.partner'].create(
                {'name': 'PO Vendor'}).id,
            'order_line': [(0, 0, {
                'product_id': self.order.order_line[0].product_id.id,
                'product_qty': 1,
                'price_unit': 1.0,
                'sale_line_id': self.order.order_line[0].id,
            })],
        })
        mock_adapter = mock.MagicMock()
        mock_adapter.return_value.confirm.return_value = {'status': 'success'}
        with mock.patch.object(
                so_module.gearment_adapter, 'GearmentApiAdapter', mock_adapter):
            po.action_confirm_at_gearment()
            mock_adapter.return_value.confirm.assert_called_once()
            # All source SOs now confirmed -> wrapper refuses a second run.
            with self.assertRaises(UserError):
                po.action_confirm_at_gearment()
        self.assertTrue(self.order.x_gearment_confirmed_at)

    def test_non_shipping_user_rejected_before_anything(self):
        """FR-017: plain internal user fails the gate even with ICP on."""
        self.env['ir.config_parameter'].sudo().set_param(self._ICP, 'True')
        self.order.write({'x_gearment_outbound_ref': 'GM-DRAFT-1'})
        user = self.env['res.users'].create({
            'name': 'Plain User', 'login': 'plain_confirm_user',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('sales_team.group_sale_salesman').id])],
        })
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            self.order.with_user(user).action_confirm_at_gearment()
