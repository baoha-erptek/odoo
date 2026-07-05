"""P4-01-C Phase 2 ORM — Gearment state machine + quote wizard behaviour.

Covers:
  - state transitions via _advance_gearment_state (forward-only, idempotent)
  - action_get_gearment_quote calls adapter, writes quote fields, transitions
  - E5.b: action_get_gearment_quote raises if no Gearment-eligible lines
  - E3 + FR-017 11th confirmation: wizard.action_confirm gate
  - E4: wizard.action_confirm raises on expired quote
  - double-click race: second action_confirm finds 'confirmed' and raises
  - wizard.action_cancel transitions to 'cancelled' + clears outbound_ref

Reference: `specs/004-fulfillment-routing/p4-01-c-plan.md` §3 task list.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


_TEST_ENV = {
    'GEARMENT_API_KEY': 'TEST_KEY',
    'GEARMENT_API_SECRET': 'TEST_SECRET',
    'GEARMENT_API_BASE_URL': 'https://api.gearment.test',
}


def _state_machine_helpers():
    """Defer adapter import so the module loads even before GREEN ships."""
    from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
        GearmentApiAdapter,
    )
    return GearmentApiAdapter


@tagged('post_install', '-at_install', 'p4_01_c')
class TestP401CStateTransitions(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'P4-01-C ST'})
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })

    def test_initial_state_is_draft(self):
        self.assertEqual(self.order.x_gearment_outbound_state, 'draft')

    def test_advance_gearment_state_draft_to_quoted(self):
        self.order._advance_gearment_state('quoted')
        self.assertEqual(self.order.x_gearment_outbound_state, 'quoted')

    def test_advance_gearment_state_full_forward_path(self):
        self.order._advance_gearment_state('quoted')
        self.order._advance_gearment_state('operator_review')
        self.order._advance_gearment_state('confirmed')
        self.assertEqual(self.order.x_gearment_outbound_state, 'confirmed')

    def test_advance_gearment_state_idempotent(self):
        """Calling _advance to a state already past is a no-op (forward-only)."""
        self.order._advance_gearment_state('quoted')
        self.order._advance_gearment_state('operator_review')
        # Attempt to go back to 'draft' — must not regress
        self.order._advance_gearment_state('draft')
        self.assertEqual(self.order.x_gearment_outbound_state, 'operator_review')

    def test_advance_gearment_state_cancel_from_quoted(self):
        """Cancel is reachable from any pre-confirmed state."""
        self.order._advance_gearment_state('quoted')
        self.order._advance_gearment_state('cancelled')
        self.assertEqual(self.order.x_gearment_outbound_state, 'cancelled')


@tagged('post_install', '-at_install', 'p4_01_c')
class TestP401CGetQuote(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'P4-01-C GQ', 'street': '123 Main', 'city': 'Boston',
            'zip': '02108', 'country_id': self.env.ref('base.us').id,
        })
        # Order has no x_gearment_sku → E5.b gate must trip
        self.order_no_sku = self.env['sale.order'].create({
            'partner_id': self.partner.id, 'sales_channel': 'etsy',
        })
        # Order with at least one Gearment-eligible line
        self.product = self.env['product.template'].create({
            'name': 'Mug', 'x_gearment_sku': '12345',
        })
        self.order_with_sku = self.env['sale.order'].create({
            'partner_id': self.partner.id, 'sales_channel': 'etsy',
            'order_line': [(0, 0, {
                'product_id': self.product.product_variant_ids[:1].id,
                'product_uom_qty': 1, 'price_unit': 10.0,
            })],
        })

    def _stub_quote(self):
        return {
            'currency': 'USD',
            'order_total': Decimal('45.99'),
            'order_sub_total': Decimal('40.00'),
            'order_shipping_fee': Decimal('5.99'),
            'order_tax': Decimal('0E-9'),
            'order_discount': Decimal('0E-9'),
            'order_handle_fee': Decimal('0E-9'),
            'order_gift_message_fee': Decimal('0E-9'),
            'order_fee': Decimal('0E-9'),
            'raw_response': {'data': {'order_total': {
                'currency_code': 'USD', 'units': '45', 'nanos': 990000000,
            }}},
        }

    def test_get_quote_raises_when_no_gearment_eligible_lines(self):
        with self.assertRaises(UserError):
            self.order_no_sku.action_get_gearment_quote()

    def test_get_quote_fr017_13th_blocks_non_shipping_user(self):
        """FR-017 13th confirmation — direct RPC by non-shipping user
        is rejected BEFORE any write to x_gearment_* fields."""
        non_shipping = self.env['res.users'].create({
            'name': 'Cara D', 'login': 'cara_p4d@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            self.order_with_sku.with_user(non_shipping).action_get_gearment_quote()
        # State must NOT have advanced
        self.assertEqual(
            self.order_with_sku.x_gearment_outbound_state, 'draft',
        )

    def test_get_quote_calls_adapter_and_writes_fields(self):
        GearmentApiAdapter = _state_machine_helpers()
        with mock.patch.dict('os.environ', _TEST_ENV, clear=False), \
             mock.patch.object(
                 GearmentApiAdapter, 'get_quote',
                 return_value=self._stub_quote(),
             ):
            self.order_with_sku.action_get_gearment_quote()
        self.assertEqual(self.order_with_sku.x_gearment_outbound_state, 'quoted')
        self.assertEqual(self.order_with_sku.x_gearment_quote_currency, 'USD')
        self.assertAlmostEqual(
            self.order_with_sku.x_gearment_quote_total, 45.99, places=2,
        )
        self.assertTrue(self.order_with_sku.x_gearment_quote_expires_at)

    def test_get_quote_idempotent_replaces_old_quote(self):
        GearmentApiAdapter = _state_machine_helpers()
        with mock.patch.dict('os.environ', _TEST_ENV, clear=False):
            with mock.patch.object(
                GearmentApiAdapter, 'get_quote',
                return_value=self._stub_quote(),
            ):
                self.order_with_sku.action_get_gearment_quote()
            new_quote = self._stub_quote()
            new_quote['order_total'] = Decimal('50.00')
            with mock.patch.object(
                GearmentApiAdapter, 'get_quote', return_value=new_quote,
            ):
                self.order_with_sku.action_get_gearment_quote()
        self.assertAlmostEqual(
            self.order_with_sku.x_gearment_quote_total, 50.00, places=2,
        )


@tagged('post_install', '-at_install', 'p4_01_c')
class TestP401CWizardConfirm(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'P4-01-C Wiz', 'street': '123 Main', 'city': 'Boston',
            'zip': '02108', 'country_id': self.env.ref('base.us').id,
        })
        self.product = self.env['product.template'].create({
            'name': 'Mug', 'x_gearment_sku': '12345',
        })
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id, 'sales_channel': 'etsy',
            'order_line': [(0, 0, {
                'product_id': self.product.product_variant_ids[:1].id,
                'product_uom_qty': 1, 'price_unit': 10.0,
            })],
        })
        # Stage to operator_review with a fresh quote
        self.order.x_gearment_outbound_state = 'operator_review'
        self.order.x_gearment_quote_total = 45.99
        self.order.x_gearment_quote_currency = 'USD'
        self.order.x_gearment_quote_expires_at = (
            fields.Datetime.now() + timedelta(minutes=15)
        )
        # P-GEAR-AUTOCONFIRM: wizard confirm now routes through the shared
        # chargeable core — needs the owner killswitch ON and an existing
        # pushed draft (killswitch-off behavior is covered in
        # test_gear_confirm_button.py).
        self.env['ir.config_parameter'].sudo().set_param(
            'multichannel_hub.gearment_confirm_enabled', 'True')
        self.order.x_gearment_outbound_ref = 'GM-DRAFT-WIZ'
        self.wizard = self.env['gearment.quote.wizard'].create({
            'order_id': self.order.id,
        })

    def _stub_confirm(self):
        return {'data': {'reference_id': self.order.name, 'status': 'accepted'}}

    def test_wizard_confirm_requires_operator_review_state(self):
        self.order.x_gearment_outbound_state = 'draft'
        with self.assertRaises(UserError):
            self.wizard.action_confirm()

    def test_wizard_confirm_raises_on_expired_quote(self):
        self.order.x_gearment_quote_expires_at = (
            fields.Datetime.now() - timedelta(minutes=1)
        )
        with self.assertRaises(UserError):
            self.wizard.action_confirm()

    def test_wizard_confirm_fr_017_blocks_non_shipping_user(self):
        """FR-017 11th confirmation: must call _check_ba_shipping_or_raise
        BEFORE any sudo write."""
        non_shipping = self.env['res.users'].create({
            'name': 'Bob', 'login': 'bob_p4c@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        wizard = self.wizard.with_user(non_shipping)
        with self.assertRaises(AccessError):
            wizard.action_confirm()
        # State must NOT have advanced
        self.assertEqual(self.order.x_gearment_outbound_state, 'operator_review')

    def test_wizard_confirm_calls_adapter_and_advances_state(self):
        GearmentApiAdapter = _state_machine_helpers()
        with mock.patch.dict('os.environ', _TEST_ENV, clear=False), \
             mock.patch.object(
                 GearmentApiAdapter, 'confirm',
                 return_value=self._stub_confirm(),
             ) as mock_confirm:
            self.wizard.action_confirm()
        mock_confirm.assert_called_once()
        self.assertEqual(self.order.x_gearment_outbound_state, 'confirmed')

    def test_wizard_confirm_double_click_race(self):
        """Second action_confirm finds state='confirmed' and raises."""
        GearmentApiAdapter = _state_machine_helpers()
        with mock.patch.dict('os.environ', _TEST_ENV, clear=False):
            with mock.patch.object(
                GearmentApiAdapter, 'confirm',
                return_value=self._stub_confirm(),
            ):
                self.wizard.action_confirm()
            self.assertEqual(self.order.x_gearment_outbound_state, 'confirmed')
            # Second click — wizard finds advanced state and raises
            with self.assertRaises(UserError):
                self.wizard.action_confirm()


@tagged('post_install', '-at_install', 'p4_01_c')
class TestP401CWizardCancel(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'P4-01-C Cnl'})
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id, 'sales_channel': 'etsy',
            'x_gearment_outbound_ref': 'GR-PRE-001',
        })
        self.order.x_gearment_outbound_state = 'operator_review'
        self.wizard = self.env['gearment.quote.wizard'].create({
            'order_id': self.order.id,
        })

    def test_wizard_cancel_transitions_to_cancelled(self):
        self.wizard.action_cancel()
        self.assertEqual(self.order.x_gearment_outbound_state, 'cancelled')

    def test_wizard_cancel_clears_outbound_ref(self):
        self.wizard.action_cancel()
        self.assertFalse(self.order.x_gearment_outbound_ref)
