"""Phase 1 DB tests for P-LIST-SHIP-CREATE (Jira ESTY-201).

Verifies the storage + registration surface for the "create Etsy
shipping profile from Odoo" feature:

- ``etsy.shipping.profile`` gains ``source`` + ``created_at`` columns.
- The create wizard model is registered with an ACL row for BA users.
- ``etsy.api.log`` carries the new ``shipping_profile_create`` source.
- The shop + listing forms expose the "Create new" button action.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestShipCreateSchema(TransactionCase):

    def _columns(self, table):
        self.env.cr.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s
            """,
            (table,),
        )
        return {r[0] for r in self.env.cr.fetchall()}

    def test_source_column_exists(self):
        self.assertIn('source', self._columns('etsy_shipping_profile'))

    def test_created_at_column_exists(self):
        self.assertIn('created_at', self._columns('etsy_shipping_profile'))

    def test_wizard_model_registered(self):
        self.assertIn(
            'etsy.shipping.profile.create.wizard', self.env.registry.models,
        )

    def test_wizard_acl_grants_ba_user(self):
        acl = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'etsy.shipping.profile.create.wizard'),
            ('group_id', '=', self.env.ref(
                'multichannel_hub_core.group_ba_user').id),
        ])
        self.assertTrue(acl, "BA group must have an ACL row on the wizard")
        self.assertTrue(any(a.perm_write and a.perm_create for a in acl))

    def test_api_log_source_value_added(self):
        sources = dict(
            self.env['etsy.api.log']._fields['source'].selection,
        )
        self.assertIn('shipping_profile_create', sources)

    def test_shop_form_exposes_create_button(self):
        view = self.env.ref('etsy_integration.etsy_shop_view_form')
        self.assertIn(
            'action_open_shipping_profile_create_wizard', view.arch,
        )

    def test_listing_form_exposes_create_button(self):
        view = self.env.ref(
            'etsy_integration.view_multichannel_listing_form_etsy')
        self.assertIn(
            'action_open_shipping_profile_create_wizard', view.arch,
        )
