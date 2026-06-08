"""Phase 1 (DB) tests for P-LIST-PUBLISH-FROM-LISTING.

Verifies the view inherit lands in ir.ui.view with the right XPath
content: two header buttons (Publish to Etsy / Resume Publish) gated
on channel + state + etsy_shop_id, both bound to the new
``action_open_etsy_publish_wizard`` method on multichannel.listing.
"""

from lxml import etree

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPListPublishFromListingPhase1DB(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.view = cls.env.ref(
            'etsy_integration.view_multichannel_listing_form_etsy_publish_button',
            raise_if_not_found=False,
        )

    def _arch_root(self):
        self.assertTrue(self.view, "view inherit XML ID missing")
        return etree.fromstring(self.view.arch_db.encode('utf-8'))

    def _publish_buttons(self):
        root = self._arch_root()
        return root.xpath(
            "//button[@name='action_open_etsy_publish_wizard']",
        )

    def test_view_arch_has_publish_button(self):
        buttons = self._publish_buttons()
        self.assertGreaterEqual(
            len(buttons), 1,
            "expected at least one Publish-to-Etsy button on the listing form",
        )

    def test_button_has_ba_group_gate(self):
        for btn in self._publish_buttons():
            self.assertEqual(
                btn.get('groups'),
                'multichannel_hub_core.group_ba_user',
                "Publish-to-Etsy button must mirror wizard FR-017 group gate",
            )

    def test_button_visibility_hides_non_etsy(self):
        invis_expressions = [
            (btn.get('invisible') or '') for btn in self._publish_buttons()
        ]
        self.assertTrue(
            all("channel_id" in expr and "etsy" in expr for expr in invis_expressions),
            "every Publish button must hide for non-Etsy channels; got %r"
            % invis_expressions,
        )

    def test_button_visibility_hides_when_no_shop_resolved(self):
        invis_expressions = [
            (btn.get('invisible') or '') for btn in self._publish_buttons()
        ]
        self.assertTrue(
            all("etsy_shop_id" in expr for expr in invis_expressions),
            "every Publish button must hide when etsy_shop_id is NULL; got %r"
            % invis_expressions,
        )

    def test_resume_button_label_for_error_state(self):
        labels = {
            btn.get('string') for btn in self._publish_buttons()
        }
        self.assertIn(
            'Resume Publish', labels,
            "expected a 'Resume Publish' button variant; got %r" % labels,
        )
        self.assertIn(
            'Publish to Etsy', labels,
            "expected a 'Publish to Etsy' button variant; got %r" % labels,
        )

    def test_wizard_accepts_both_default_fields(self):
        """Sanity check that the wizard model has both fields the bridge will pre-fill."""
        fields_dict = self.env['etsy.publish.wizard']._fields
        self.assertIn('product_tmpl_id', fields_dict)
        self.assertIn('shop_id', fields_dict)
        self.assertEqual(fields_dict['shop_id'].comodel_name, 'etsy.shop')
        self.assertEqual(
            fields_dict['product_tmpl_id'].comodel_name, 'product.template',
        )
