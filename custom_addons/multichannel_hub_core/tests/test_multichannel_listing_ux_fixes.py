"""Phase 2 ORM tests for P-LIST-UX-FIXES (BA/UX retroactive slice).

Locks the behaviours flagged in `specs/012-listing-model-split/ux-review-2026-06-06.md`:
- R1 Open in Etsy returns a well-formed act_url when external_ref is digit.
- R3 readonly behaviour is *view-level* only (Odoo doesn't enforce
  field-level readonly server-side without a constraint), so we don't
  assert it in ORM tests. The R3 audit instead verifies that the form
  view declares `readonly="state != 'draft'"` on the editable groups —
  a Phase 1 DB-style assertion against `ir.ui.view.arch_db`.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOpenInEtsy(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Listing = cls.env['multichannel.listing']
        cls.channel = cls.env.ref('multichannel_hub_core.channel_etsy')
        cls.tmpl = cls.env['product.template'].create({
            'name': 'UX-FIXES Tmpl', 'list_price': 1.0,
        })

    def test_action_url_well_formed_when_external_ref_is_digit(self):
        listing = self.Listing.create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
            'external_ref': '1234567890',
            'state': 'published',
        })
        action = listing.action_open_in_etsy_shop_manager()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertIn('1234567890', action['url'])
        self.assertIn('/your/shops/me/tools/listings/', action['url'])
        self.assertEqual(action['target'], 'new')

    def test_action_url_falls_back_to_dashboard_when_external_ref_blank(self):
        listing = self.Listing.create({
            'product_tmpl_id': self.tmpl.id,
            'channel_id': self.channel.id,
        })
        action = listing.action_open_in_etsy_shop_manager()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertEqual(
            action['url'],
            'https://www.etsy.com/your/shops/me/tools/listings',
        )


@tagged('post_install', '-at_install')
class TestFormReadonlyAttrs(TransactionCase):
    """View-level audit: form arch declares state!='draft' readonly on the
    editable groups. Phase 1 DB-style assertion against ir.ui.view.arch_db."""

    def test_form_view_has_readonly_attrs_on_editable_fields(self):
        view = self.env.ref(
            'multichannel_hub_core.view_multichannel_listing_form')
        arch = view.arch_db
        # The title field must carry the readonly attr.
        self.assertIn("readonly=\"state != 'draft'\"", arch,
            'form view must lock fields when state != draft (R3 safety)')

    def test_form_view_has_workflow_alert(self):
        view = self.env.ref(
            'multichannel_hub_core.view_multichannel_listing_form')
        arch = view.arch_db
        self.assertIn('Publishing workflow', arch,
            'R2 — workflow context alert must be present')

    def test_form_view_has_open_in_etsy_button(self):
        view = self.env.ref(
            'multichannel_hub_core.view_multichannel_listing_form')
        arch = view.arch_db
        self.assertIn('action_open_in_etsy_shop_manager', arch,
            'R1 — Open in Etsy button must be present in form arch')

    def test_form_view_collapses_scope_under_advanced_settings(self):
        view = self.env.ref(
            'multichannel_hub_core.view_multichannel_listing_form')
        arch = view.arch_db
        self.assertIn('Advanced settings', arch,
            'Finding-5 — Scope group must live under Advanced settings')
