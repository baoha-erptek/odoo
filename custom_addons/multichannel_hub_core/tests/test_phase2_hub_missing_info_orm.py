"""
Phase 2: ORM unit tests for P-HUB-MISSING-INFO-WIZARD (Spec 009 §2.6).

Extends product.sku.builder.wizard with conditional fallback sub-steps:
- Step 3 size parser detection logic (_is_size_extractable)
- Manual size/rectangle input fields (size_id_manual, rect_w_manual, rect_h_manual)
- Fallback integration into _build_sku_or_blank() and _validate()

8 test cases covering:
1. MUG + name with no oz token → fallback to manual size_id → SKU build succeeds
2. APR + name with no apparel-size letter → fallback to manual size_id → SKU build succeeds
3. DMT + name with no rect tokens → family override + fallback to manual rect_w/h → SKU build succeeds
4. RDS + name with no shape token → fallback to manual size_id → SKU build succeeds
5. HAPPY-PATH REGRESSION: MUG + name WITH oz token → auto-detection works, no fallback needed
6. FR-017 reuse: non-BA user blocked before any product.template create (defense-in-depth)
7. Validation failure: both size_id and all manual fields empty → UserError before create
8. Validation failure: rect_*_manual with invalid range (one zero, other valid; or out of 1-999) → UserError

Use --http-port=8175 (8170 collides per memory item 134).
Wrap assertRaises in savepoint per memory item 140 (TransactionCase._assertRaises broken with tuple).

Spec 009 T076. RED before T070-T074 implementation lands.
"""

import logging

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestPhase2MissingInfoORM(TransactionCase):
    """ORM tests for missing-info fallback sub-steps in builder wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Family = cls.env['mhc.sku.family']
        cls.AttributeValue = cls.env['product.attribute.value']
        cls.Wizard = cls.env['product.sku.builder.wizard']
        cls.Template = cls.env['product.template']

        cls.ba_user = new_test_user(
            cls.env,
            login='hub_missing_info_ba',
            groups='multichannel_hub_core.group_ba_user',
        )
        cls.plain_user = new_test_user(
            cls.env,
            login='hub_missing_info_plain',
            groups='base.group_user',
        )

        # Seed-row lookups
        cls.fam_mug = cls.Family.search([('code', '=', 'MUG')], limit=1)
        cls.fam_apr = cls.Family.search([('code', '=', 'APR')], limit=1)
        cls.fam_dmt = cls.Family.search([('code', '=', 'DMT')], limit=1)
        cls.fam_rds = cls.Family.search([('code', '=', 'RDS')], limit=1)

        cls.mat_cr = cls.AttributeValue.search([('x_code', '=', 'CR')], limit=1)
        cls.mat_tx = cls.AttributeValue.search([('x_code', '=', 'TX')], limit=1)
        cls.mat_ce = cls.AttributeValue.search([('x_code', '=', 'CE')], limit=1)

        cls.size_f11 = cls.AttributeValue.search([('x_code', '=', 'F11')], limit=1)
        cls.size_f15 = cls.AttributeValue.search([('x_code', '=', 'F15')], limit=1)
        cls.size_am = cls.AttributeValue.search([('x_code', '=', 'AM')], limit=1)
        cls.size_sq = cls.AttributeValue.search([('x_code', '=', 'SQ')], limit=1)

        cls.color_bk = cls.AttributeValue.search([('x_code', '=', 'BK')], limit=1)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _expect_raises(self, exception_types, callable_, *args, **kwargs):
        """Savepoint-wrapped raises check (memory item 140)."""
        raised = False
        caught = None
        try:
            with self.env.cr.savepoint():
                callable_(*args, **kwargs)
        except exception_types as exc:
            raised = True
            caught = exc
        self.assertTrue(
            raised,
            "Expected one of %s, got nothing" % (exception_types,),
        )
        return caught

    def _make_wizard(self, user=None, **overrides):
        """Create a builder wizard with default valid state, optional overrides."""
        user = user or self.ba_user
        vals = {
            'step': '1',
            'product_name': 'Custom Engraved Mug',
            'family_id': self.fam_mug.id,
            'material_id': self.mat_cr.id,
            'size_id': self.size_f11.id,
        }
        vals.update(overrides)
        return self.Wizard.with_user(user).create(vals)

    # ==================================================================
    # Case 1: MUG + no oz in name → manual size fallback → preview renders
    # ==================================================================

    def test_mug_no_oz_in_name_shows_fallback_and_builds_via_manual_size(self):
        """Case 1: 'Stainless Steel Mug' (no oz) → _is_size_extractable=False.
        BA picks size_id_manual=F11 → preview builds MUG-CR-F11."""
        w = self._make_wizard(
            product_name='Stainless Steel Mug',
            family_id=self.fam_mug.id,
            material_id=self.mat_cr.id,
            size_id=False,  # No size_id picked yet
            size_id_manual=self.size_f11.id,
        )
        # When no oz detected in name, _is_size_extractable should be False
        self.assertFalse(
            w._is_size_extractable,
            "'Stainless Steel Mug' contains no oz token; _is_size_extractable should be False",
        )
        # Preview via manual size should work
        self.assertEqual(
            w.preview_sku, 'MUG-CR-F11',
            "Preview should use manual size_id when size_id empty and size_id_manual filled",
        )
        # action_create should succeed
        action = w.with_user(self.ba_user).action_create()
        self.assertIsInstance(action, dict)
        tmpl_id = action.get('res_id')
        self.assertTrue(tmpl_id, "action_create must return res_id")
        tmpl = self.Template.browse(tmpl_id)
        self.assertEqual(
            tmpl.default_code, 'MUG-CR-F11',
            "Created template must use manual size fallback",
        )

    # ==================================================================
    # Case 2: APR + no size letter in name → manual apparel size → preview renders
    # ==================================================================

    def test_apron_no_size_letter_fallback_via_manual_apparel_size(self):
        """Case 2: 'Apron' (no size letter) → _is_size_extractable=False.
        BA picks size_id_manual=AM → preview APR-TX-AM."""
        w = self._make_wizard(
            product_name='Apron',
            family_id=self.fam_apr.id,
            material_id=self.mat_tx.id,
            size_id=False,
            size_id_manual=self.size_am.id,
        )
        self.assertFalse(
            w._is_size_extractable,
            "'Apron' contains no apparel-size letter; _is_size_extractable should be False",
        )
        self.assertEqual(
            w.preview_sku, 'APR-TX-AM',
            "Preview should render APR-TX-AM via manual size_id",
        )

    # ==================================================================
    # Case 3: DMT + no rect tokens → classify MSC → override to DMT → manual rect → preview
    # ==================================================================

    def test_dmt_msc_classify_override_then_rect_manual_fallback(self):
        """Case 3: 'Color Changing Beverage' → family auto-suggests MSC
        → BA overrides to DMT → no rect tokens detected → manual rect_w=30 rect_h=18
        → preview DMT-TX-R30X18."""
        w = self._make_wizard(
            product_name='Color Changing Beverage',
            family_id=self.fam_dmt.id,  # Overridden from MSC
            material_id=self.mat_tx.id,
            size_id=False,
            rect_w=0,
            rect_h=0,
            rect_w_manual=30,
            rect_h_manual=18,
        )
        # No oz/apparel/shape tokens; rectangles only in _manual fields
        self.assertFalse(
            w._is_size_extractable,
            "'Color Changing Beverage' has no rect tokens; _is_size_extractable should be False",
        )
        self.assertEqual(
            w.preview_sku, 'DMT-TX-R30X18',
            "Preview should use manual rect dimensions",
        )
        action = w.with_user(self.ba_user).action_create()
        self.assertIsInstance(action, dict)
        tmpl = self.Template.browse(action['res_id'])
        self.assertEqual(tmpl.default_code, 'DMT-TX-R30X18')

    # ==================================================================
    # Case 4: RDS + no shape token → manual shape fallback → preview renders
    # ==================================================================

    def test_rds_no_shape_token_fallback_via_manual_shape(self):
        """Case 4: 'Beautiful Dish' (no SQ/HT/OV token) → _is_size_extractable=False.
        BA picks size_id_manual=SQ (shape) → preview RDS-CE-SQ."""
        w = self._make_wizard(
            product_name='Beautiful Dish',
            family_id=self.fam_rds.id,
            material_id=self.mat_ce.id,
            size_id=False,
            size_id_manual=self.size_sq.id,
        )
        self.assertFalse(
            w._is_size_extractable,
            "'Beautiful Dish' contains no shape token; _is_size_extractable should be False",
        )
        self.assertEqual(
            w.preview_sku, 'RDS-CE-SQ',
            "Preview should render RDS-CE-SQ via manual size_id",
        )

    # ==================================================================
    # Case 5: HAPPY-PATH REGRESSION — oz in name auto-detected, no fallback
    # ==================================================================

    def test_happy_path_regression_oz_in_name_no_fallback_needed(self):
        """Case 5: 'Custom 11oz Coffee Mug' → _is_size_extractable=True.
        Auto-detected oz token; no fallback needed. size_id auto-populated to F11
        → preview MUG-CR-F11."""
        w = self._make_wizard(
            product_name='Custom 11oz Coffee Mug',
            family_id=self.fam_mug.id,
            material_id=self.mat_cr.id,
            size_id=self.size_f11.id,
            size_id_manual=False,  # Not using manual
        )
        # oz token detected; extraction successful
        self.assertTrue(
            w._is_size_extractable,
            "'Custom 11oz Coffee Mug' contains oz token; _is_size_extractable should be True",
        )
        self.assertEqual(
            w.preview_sku, 'MUG-CR-F11',
            "Preview should use auto-detected size_id, not manual fallback",
        )

    # ==================================================================
    # Case 6: FR-017 reuse — non-BA user blocked BEFORE template create
    # ==================================================================

    def test_fr017_gate_non_ba_user_blocked_via_manual_fallback_path(self):
        """Case 6: Non-BA user attempts create with manual fallback fields filled.
        FR-017 gate must fire BEFORE any product.template side effect.
        Assert product.template.search_count unchanged after AccessError."""
        before = self.Template.search_count([])
        w = self._make_wizard(
            user=self.plain_user,
            product_name='Stainless Steel Mug',
            family_id=self.fam_mug.id,
            material_id=self.mat_cr.id,
            size_id=False,
            size_id_manual=self.size_f11.id,
        )
        self._expect_raises(
            AccessError,
            w.with_user(self.plain_user).action_create,
        )
        after = self.Template.search_count([])
        self.assertEqual(
            before, after,
            "Non-BA action_create must NOT create any product.template "
            "(FR-017 gate fires BEFORE side effect; pattern memory_feedback_fr017_write_defense_in_depth)",
        )

    # ==================================================================
    # Case 7: Validation failure — both size_id and manual fields empty
    # ==================================================================

    def test_validate_blocks_when_size_id_and_manual_both_empty(self):
        """Case 7: All size input fields empty (size_id, size_id_manual, rect_w_manual, rect_h_manual).
        action_create must raise UserError matching 'Size or manual fallback required'."""
        w = self._make_wizard(
            product_name='Stainless Steel Mug',
            family_id=self.fam_mug.id,
            material_id=self.mat_cr.id,
            size_id=False,  # Empty
            size_id_manual=False,  # Empty
            rect_w=0,
            rect_h=0,
            rect_w_manual=0,  # Empty
            rect_h_manual=0,  # Empty
        )
        exc = self._expect_raises(
            (UserError, ValidationError),
            w.with_user(self.ba_user).action_create,
        )
        self.assertIn(
            'Size or manual fallback required',
            str(exc),
            "UserError must hint at needing size or fallback input",
        )

    # ==================================================================
    # Case 8: Validation failure — invalid rect_*_manual dimensions
    # ==================================================================

    def test_validate_blocks_invalid_rect_manual_dims_one_zero(self):
        """Case 8a: rect_w_manual=0 (zero not allowed), rect_h_manual=10 (valid).
        action_create must raise UserError about dimension range (1-999)."""
        w = self._make_wizard(
            product_name='Welcome Doormat',
            family_id=self.fam_dmt.id,
            material_id=self.mat_tx.id,
            size_id=False,
            rect_w_manual=0,  # Invalid: zero
            rect_h_manual=10,  # Valid
        )
        exc = self._expect_raises(
            (UserError, ValidationError),
            w.with_user(self.ba_user).action_create,
        )
        self.assertIn(
            'Dimensions',
            str(exc),
            "UserError should mention dimension validation",
        )

    def test_validate_blocks_invalid_rect_manual_dims_out_of_range(self):
        """Case 8b: rect_w_manual=1500 (exceeds 999), rect_h_manual=20 (valid).
        action_create must raise UserError about dimension range (1-999)."""
        w = self._make_wizard(
            product_name='Welcome Doormat',
            family_id=self.fam_dmt.id,
            material_id=self.mat_tx.id,
            size_id=False,
            rect_w_manual=1500,  # Invalid: exceeds 999
            rect_h_manual=20,  # Valid
        )
        exc = self._expect_raises(
            (UserError, ValidationError),
            w.with_user(self.ba_user).action_create,
        )
        self.assertIn(
            'Dimensions',
            str(exc),
            "UserError should mention dimension validation",
        )
