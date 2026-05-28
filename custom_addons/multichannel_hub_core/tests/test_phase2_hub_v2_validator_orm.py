"""
Phase 2: ORM unit tests for P-HUB-V2-VALIDATE-ON-CREATE (Spec 009 §7).

Covers 8 cases (T066):

  1. validate_v2_sku('MUG-CR-F11') -> True  (canonical)
  2. validate_v2_sku('mug-cr-f11') -> False (lowercase rejected)
  3. validate_v2_sku('MUG-CR-X99') -> False (bad size token)
  4. validate_v2_sku('M')          -> False (too short)
  5. legacy wizard + soft mode + non-v2 SKU -> created + x_sku_v2_status
       auto-marked 'ba_approved_legacy' + WARNING logged
  6. legacy wizard + hard mode + non-v2 SKU -> UserError before any
       product.template side effect (search_count unchanged)
  7. builder wizard + soft mode + canonical SKU -> created + status NOT
       'ba_approved_legacy' (compute path yields 'matches')
  8. Existing product with x_sku_v2_status='ba_approved_legacy' is
       preserved through ORM write (regression guard for product_template
       compute bypass at line 151)

Run with --http-port=8175 per memory item 134.

Spec 009 T066. RED before T062-T064 implementation lands.
"""

import logging

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from odoo.addons.multichannel_hub_core.services import sku_grammar_v2


_ICP_KEY = 'multichannel_hub.sku_v2_enforce_mode'


@tagged('post_install', '-at_install')
class TestHubV2ValidatorORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.LegacyWizard = cls.env['product.creation.wizard']
        cls.BuilderWizard = cls.env['product.sku.builder.wizard']
        cls.Template = cls.env['product.template']
        cls.Category = cls.env['product.category']
        cls.ICP = cls.env['ir.config_parameter']
        ChannelAll = cls.env['multichannel.sales.channel'].with_context(active_test=False)
        cls.etsy = ChannelAll.search([('code', '=', 'etsy')], limit=1)
        cls.categ_root = cls.Category.search([], limit=1)
        cls.ba_user = new_test_user(
            cls.env,
            login='hub_v2_validator_ba',
            groups='multichannel_hub_core.group_ba_user',
        )

    def setUp(self):
        super().setUp()
        # Reset ICP to default at the start of each test; restore in tearDown.
        self._original_mode = self.ICP.sudo().get_param(_ICP_KEY, 'soft')
        self.ICP.sudo().set_param(_ICP_KEY, 'soft')

    def tearDown(self):
        # Restore whatever was set at install (should be 'soft').
        self.ICP.sudo().set_param(_ICP_KEY, self._original_mode)
        super().tearDown()

    # ------------------------------------------------------------------
    # Helper-function tests (cases 1-4)
    # ------------------------------------------------------------------

    def test_case1_validate_v2_sku_canonical_passes(self):
        self.assertTrue(sku_grammar_v2.validate_v2_sku('MUG-CR-F11'))

    def test_case2_validate_v2_sku_rejects_lowercase(self):
        self.assertFalse(sku_grammar_v2.validate_v2_sku('mug-cr-f11'))

    def test_case3_validate_v2_sku_rejects_bad_size_token(self):
        self.assertFalse(sku_grammar_v2.validate_v2_sku('MUG-CR-X99'))

    def test_case4_validate_v2_sku_rejects_too_short(self):
        self.assertFalse(sku_grammar_v2.validate_v2_sku('M'))

    # ------------------------------------------------------------------
    # Legacy wizard soft-mode behaviour (case 5)
    # ------------------------------------------------------------------

    def _legacy_vals(self, **kw):
        vals = {
            'name': 'Custom Hand-Painted Mug',
            'default_code': 'ABC-DEF-123',  # non-v2 SKU
            'categ_id': self.categ_root.id,
            'x_listing_price': 19.99,
            'x_shipping_price_internal': 0.0,
            'x_channel_applicability_ids': [(4, self.etsy.id)],
        }
        vals.update(kw)
        return vals

    def test_case5_legacy_wizard_soft_mode_marks_non_v2_as_legacy(self):
        self.ICP.sudo().set_param(_ICP_KEY, 'soft')
        wizard = self.LegacyWizard.with_user(self.ba_user).create(self._legacy_vals())
        wizard_logger = 'odoo.addons.multichannel_hub_core.wizards.product_creation_wizard'
        with self.assertLogs(wizard_logger, level=logging.WARNING) as captured:
            wizard.with_user(self.ba_user).action_create()
        tmpl = self.Template.search([('default_code', '=', 'ABC-DEF-123')], limit=1)
        self.assertTrue(tmpl, "soft mode must still create the product")
        self.assertEqual(
            tmpl.x_sku_v2_status,
            'ba_approved_legacy',
            "soft-mode + non-v2 SKU must auto-mark x_sku_v2_status=ba_approved_legacy",
        )
        # WARNING must mention v2/grammar/SKU so an operator can grep audit logs.
        joined = '\n'.join(captured.output).lower()
        self.assertTrue(
            ('v2' in joined) or ('grammar' in joined) or ('sku' in joined),
            "Soft-mode WARNING must reference v2/grammar/SKU for grep-ability",
        )

    # ------------------------------------------------------------------
    # Legacy wizard hard-mode behaviour (case 6)
    # ------------------------------------------------------------------

    def test_case6_legacy_wizard_hard_mode_raises_before_side_effect(self):
        self.ICP.sudo().set_param(_ICP_KEY, 'hard')
        before = self.Template.search_count([])
        wizard = self.LegacyWizard.with_user(self.ba_user).create(self._legacy_vals())
        raised = False
        try:
            with self.env.cr.savepoint():
                wizard.with_user(self.ba_user).action_create()
        except UserError:
            raised = True
        self.assertTrue(raised, "hard-mode + non-v2 SKU must raise UserError")
        after = self.Template.search_count([])
        self.assertEqual(
            before,
            after,
            "hard-mode UserError must fire BEFORE product.template create",
        )

    # ------------------------------------------------------------------
    # Builder wizard canonical-SKU happy path (case 7)
    # ------------------------------------------------------------------

    def test_case7_builder_wizard_soft_canonical_not_marked_legacy(self):
        self.ICP.sudo().set_param(_ICP_KEY, 'soft')
        Family = self.env['mhc.sku.family']
        AttrValue = self.env['product.attribute.value']
        mug = Family.search([('code', '=', 'MUG')], limit=1)
        material_cr = AttrValue.search(
            [('x_code', '=', 'CR'), ('attribute_id.name', '=', 'Material')], limit=1,
        )
        size_f11 = AttrValue.search(
            [('x_code', '=', 'F11'), ('x_namespace', '=', 'fluid_oz')], limit=1,
        )
        self.assertTrue(mug, "seed: MUG family missing")
        self.assertTrue(material_cr, "seed: material CR missing")
        self.assertTrue(size_f11, "seed: size F11 missing")
        wizard = self.BuilderWizard.with_user(self.ba_user).create({
            'product_name': 'Premium Coffee Mug 11oz',
            'family_id': mug.id,
            'material_id': material_cr.id,
            'size_id': size_f11.id,
        })
        wizard.with_user(self.ba_user).action_create()
        tmpl = self.Template.search([('default_code', '=', 'MUG-CR-F11')], limit=1)
        self.assertTrue(tmpl, "canonical SKU must create product")
        self.assertNotEqual(
            tmpl.x_sku_v2_status,
            'ba_approved_legacy',
            "canonical SKU must not be auto-marked legacy (compute should yield 'matches')",
        )

    # ------------------------------------------------------------------
    # Existing legacy-status regression guard (case 8)
    # ------------------------------------------------------------------

    def test_case8_existing_ba_approved_legacy_preserved_through_write(self):
        """Regression: product_template._compute_x_sku_v2 line 151 bypass."""
        tmpl = self.Template.sudo().create({
            'name': 'Legacy Free-Form Product',
            'default_code': 'XYZ-FOO-BAR',
            'x_sku_v2_status': 'ba_approved_legacy',
        })
        # Re-trigger compute via @api.depends('name', 'default_code')
        tmpl.write({'name': 'Legacy Free-Form Product (renamed)'})
        self.assertEqual(
            tmpl.x_sku_v2_status,
            'ba_approved_legacy',
            "ba_approved_legacy must survive name change; compute bypass is canonical",
        )
        tmpl.write({'default_code': 'TOTALLY-NEW-CODE'})
        self.assertEqual(
            tmpl.x_sku_v2_status,
            'ba_approved_legacy',
            "ba_approved_legacy must survive default_code change too",
        )
