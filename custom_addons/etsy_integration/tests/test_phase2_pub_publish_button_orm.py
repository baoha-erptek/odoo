"""Phase 2 ORM tests for Spec 011 P-PUB-PUBLISH T027 — product form button."""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPubPublishButtonORM(TransactionCase):

    def test_action_returns_window_with_default_context(self):
        tmpl = self.env['product.template'].create({
            'name': 'Button Test', 'default_code': 'BTN-1',
        })
        result = tmpl.action_open_etsy_publish_wizard()
        self.assertEqual(result.get('type'), 'ir.actions.act_window')
        self.assertEqual(result.get('res_model'), 'etsy.publish.wizard')
        self.assertEqual(result.get('target'), 'new')
        self.assertEqual(
            result.get('context', {}).get('default_product_tmpl_id'),
            tmpl.id,
        )

    def test_button_view_registered(self):
        view = self.env.ref(
            'etsy_integration.view_product_template_form_etsy_inherit',
            raise_if_not_found=False,
        )
        self.assertTrue(view)
        self.assertIn('action_open_etsy_publish_wizard', view.arch_db or '')
