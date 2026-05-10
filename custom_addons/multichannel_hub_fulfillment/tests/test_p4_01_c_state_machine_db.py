"""P4-01-C Phase 1 DB — schema verification for the Gearment outbound state
machine + quote shadow fields + transient wizard model.

Reference: `specs/004-fulfillment-routing/p4-01-c-plan.md` §1 (decisions E1.b,
E2.a) + §2 (file change list).
"""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'p4_01_c')
class TestP401CSaleOrderFields(TransactionCase):

    def test_x_gearment_outbound_state_field_exists(self):
        self.assertIn(
            'x_gearment_outbound_state', self.env['sale.order']._fields,
        )

    def test_x_gearment_outbound_state_is_selection(self):
        field = self.env['sale.order']._fields['x_gearment_outbound_state']
        self.assertEqual(field.type, 'selection')

    def test_x_gearment_outbound_state_has_5_keys(self):
        field = self.env['sale.order']._fields['x_gearment_outbound_state']
        keys = {key for key, _ in field.selection}
        self.assertEqual(
            keys,
            {'draft', 'quoted', 'operator_review', 'confirmed', 'cancelled'},
        )

    def test_x_gearment_outbound_state_default_is_draft(self):
        partner = self.env['res.partner'].create({'name': 'P4-01-C Test'})
        order = self.env['sale.order'].create({'partner_id': partner.id})
        self.assertEqual(order.x_gearment_outbound_state, 'draft')

    def test_x_gearment_outbound_state_is_tracked(self):
        field = self.env['sale.order']._fields['x_gearment_outbound_state']
        self.assertTrue(field.tracking, 'state changes must hit chatter')

    def test_x_gearment_quote_total_field_exists(self):
        self.assertIn('x_gearment_quote_total', self.env['sale.order']._fields)
        field = self.env['sale.order']._fields['x_gearment_quote_total']
        self.assertTrue(field.readonly)

    def test_x_gearment_quote_currency_field_exists(self):
        self.assertIn('x_gearment_quote_currency', self.env['sale.order']._fields)
        field = self.env['sale.order']._fields['x_gearment_quote_currency']
        self.assertTrue(field.readonly)

    def test_x_gearment_quote_expires_at_field_exists(self):
        self.assertIn(
            'x_gearment_quote_expires_at', self.env['sale.order']._fields,
        )
        field = self.env['sale.order']._fields['x_gearment_quote_expires_at']
        self.assertTrue(field.readonly)

    def test_x_gearment_quote_breakdown_json_field_exists(self):
        self.assertIn(
            'x_gearment_quote_breakdown_json', self.env['sale.order']._fields,
        )
        field = self.env['sale.order']._fields['x_gearment_quote_breakdown_json']
        self.assertTrue(field.readonly)

    def test_legacy_x_gearment_status_still_exists(self):
        """E1.b — both fields coexist; legacy status survives."""
        self.assertIn('x_gearment_status', self.env['sale.order']._fields)


@tagged('post_install', '-at_install', 'p4_01_c')
class TestP401CWizardModel(TransactionCase):

    def test_wizard_model_exists(self):
        self.assertIn('gearment.quote.wizard', self.env)

    def test_wizard_is_transient(self):
        Wizard = self.env['gearment.quote.wizard']
        self.assertTrue(
            Wizard._transient,
            'gearment.quote.wizard must be a TransientModel',
        )
