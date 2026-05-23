"""
Phase 2: ORM unit tests for P-HUB-WIZARD (Spec 009 US3).

Covers acceptance criteria 1-5:
- Required fields validated (name, default_code, categ_id, listing_price > 0, ≥1 channel)
- Shipping_price_internal allows 0
- Grammar v2 status surfaced; non-canonical passes through
- Happy path creates product.template + product.channel.status rows
- FR-017 method-top gate: non-BA AccessError BEFORE any create
"""

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestHubWizardORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['product.creation.wizard']
        cls.Template = cls.env['product.template']
        cls.Status = cls.env['product.channel.status']
        cls.Category = cls.env['product.category']
        ChannelAll = cls.env['multichannel.sales.channel'].with_context(active_test=False)
        cls.etsy = ChannelAll.search([('code', '=', 'etsy')], limit=1)
        cls.amazon = ChannelAll.search([('code', '=', 'amazon')], limit=1)
        cls.categ_root = cls.Category.search([], limit=1)
        cls.ba_user = new_test_user(
            cls.env,
            login='hub_wizard_ba',
            groups='multichannel_hub_core.group_ba_user',
        )
        cls.plain_user = new_test_user(
            cls.env,
            login='hub_wizard_plain',
            groups='base.group_user',
        )

    # ------------------------------------------------------------------
    # Validation gates
    # ------------------------------------------------------------------

    def _base_vals(self, **kw):
        vals = {
            'name': 'Custom Ring Dish 3.5"',
            'default_code': 'RDS',
            'categ_id': self.categ_root.id,
            'x_listing_price': 49.99,
            'x_shipping_price_internal': 0.0,
            'x_channel_applicability_ids': [(4, self.etsy.id)],
        }
        vals.update(kw)
        return vals

    def _assert_validation_raises(self, wizard):
        raised = False
        try:
            with self.env.cr.savepoint():
                wizard.action_create()
        except (UserError, ValidationError):
            raised = True
        self.assertTrue(raised, "action_create must reject invalid input")

    def test_action_create_rejects_empty_name(self):
        w = self.Wizard.with_user(self.ba_user).create(self._base_vals(name=''))
        self._assert_validation_raises(w)

    def test_action_create_rejects_empty_default_code(self):
        w = self.Wizard.with_user(self.ba_user).create(self._base_vals(default_code=''))
        self._assert_validation_raises(w)

    def test_action_create_rejects_listing_price_zero(self):
        w = self.Wizard.with_user(self.ba_user).create(self._base_vals(x_listing_price=0.0))
        self._assert_validation_raises(w)

    def test_action_create_rejects_no_channel(self):
        w = self.Wizard.with_user(self.ba_user).create(
            self._base_vals(x_channel_applicability_ids=[(5,)])
        )
        self._assert_validation_raises(w)

    def test_action_create_allows_zero_shipping(self):
        w = self.Wizard.with_user(self.ba_user).create(self._base_vals(x_shipping_price_internal=0.0))
        result = w.action_create()
        self.assertIsNotNone(result)

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_action_create_creates_template_and_status(self):
        # Create a second active channel for multi-channel test (don't rely on
        # inactive amazon — M2M domain filters may drop it during wizard reads)
        second = self.env['multichannel.sales.channel'].create({
            'code': 'orm_test_ch2', 'name': 'ORM Test Ch2',
        })
        w = self.Wizard.with_user(self.ba_user).create(self._base_vals(
            x_channel_applicability_ids=[(6, 0, [self.etsy.id, second.id])],
        ))
        action = w.action_create()
        self.assertIsInstance(action, dict)
        tmpl_id = action.get('res_id')
        self.assertTrue(tmpl_id, "wizard action must return res_id of new template")
        tmpl = self.Template.browse(tmpl_id)
        self.assertEqual(tmpl.name, 'Custom Ring Dish 3.5"')
        self.assertEqual(tmpl.default_code, 'RDS')
        channels = tmpl.x_channel_applicability_ids
        self.assertIn(self.etsy, channels)
        self.assertIn(second, channels)
        statuses = self.Status.search([('product_tmpl_id', '=', tmpl.id)])
        self.assertEqual(len(statuses), 2, "one status row per ticked channel")
        for status in statuses:
            self.assertEqual(status.state, 'draft')

    def test_action_create_non_canonical_sku_passes_through(self):
        """Non-canonical SKU saves; surfaces non_canonical status — no block."""
        w = self.Wizard.with_user(self.ba_user).create(self._base_vals(
            name='Custom Ring Dish 3.5"',
            default_code='LEGACY-RING-001',
        ))
        action = w.action_create()
        tmpl = self.Template.browse(action['res_id'])
        self.assertEqual(tmpl.default_code, 'LEGACY-RING-001')
        self.assertEqual(tmpl.x_sku_v2_status, 'non_canonical')

    # ------------------------------------------------------------------
    # FR-017 method-top gate
    # ------------------------------------------------------------------

    def test_non_ba_user_blocked_by_fr017_gate(self):
        """Plain group_user cannot launch action_create — AccessError BEFORE template create."""
        templates_before = self.Template.search_count([])
        w = self.Wizard.with_user(self.plain_user).create(self._base_vals())
        with self.assertRaises(AccessError):
            w.with_user(self.plain_user).action_create()
        templates_after = self.Template.search_count([])
        self.assertEqual(
            templates_before, templates_after,
            "non-BA action_create must not create any product.template",
        )

    def test_ba_user_can_create(self):
        w = self.Wizard.with_user(self.ba_user).create(self._base_vals())
        action = w.with_user(self.ba_user).action_create()
        self.assertTrue(action.get('res_id'))
