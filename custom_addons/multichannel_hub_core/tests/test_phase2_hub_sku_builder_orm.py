"""
Phase 2: ORM unit tests for P-HUB-SKU-BUILDER (Spec 009 §2.5).

Covers two intertwined deliverables:

1. DB-driven `services.sku_grammar_v2.evaluate(name, env)` — replaces the
   frozen Python tuple with a query against `mhc.sku.family`. Truth-table
   for match/no-match/priority-ordering/inactive-skipped/new-family-picked-up/
   regex-cache-invalidation/malformed-regex-graceful-fallback.

2. `product.sku.builder.wizard` 4-step TransientModel — happy paths for
   each family namespace (MUG/APR/DMT), family override, family-gated size,
   field-validation refusals, FR-017 method-top gate (24th confirmation).

Use --http-port=8175 (8170 collides locally per memory item 134).
Wrap `assertRaises` for tuple exception types in savepoint+try/except
per memory item 140 (TransactionCase._assertRaises broken with tuple).

Spec 009 T049. RED before T038-T047 implementation lands.
"""

import logging

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install')
class TestPhase2HubSkuBuilderORM(TransactionCase):
    """ORM tests for grammar service + 4-step builder wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Family = cls.env['mhc.sku.family']
        cls.Attribute = cls.env['product.attribute']
        cls.AttributeValue = cls.env['product.attribute.value']
        cls.Wizard = cls.env['product.sku.builder.wizard']
        cls.Template = cls.env['product.template']

        cls.ba_user = new_test_user(
            cls.env,
            login='hub_sku_builder_ba',
            groups='multichannel_hub_core.group_ba_user',
        )
        cls.plain_user = new_test_user(
            cls.env,
            login='hub_sku_builder_plain',
            groups='base.group_user',
        )

        # Seed-row lookups used across tests
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
        """Savepoint-wrapped raises check (memory item 140 — tuple assertRaises broken)."""
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

    # ==================================================================
    # services.sku_grammar_v2.evaluate(name, env) — DB-driven
    # ==================================================================

    def test_evaluate_matches_seeded_mug(self):
        """'Custom Engraved Mug' must match MUG family from DB."""
        from odoo.addons.multichannel_hub_core.services import sku_grammar_v2
        result = sku_grammar_v2.evaluate('Custom Engraved Mug', self.env)
        self.assertEqual(result, ('MUG', 'MUG'))

    def test_evaluate_no_match_returns_msc(self):
        """'Xyzzy widget' matches no family → MSC fallback."""
        from odoo.addons.multichannel_hub_core.services import sku_grammar_v2
        result = sku_grammar_v2.evaluate('Xyzzy widget', self.env)
        self.assertEqual(result, ('MSC', 'MSC'))

    def test_evaluate_priority_ordering_first_match_wins(self):
        """'Wooden Mug' matches MUG (priority 7) before WDS (priority 22)."""
        from odoo.addons.multichannel_hub_core.services import sku_grammar_v2
        result = sku_grammar_v2.evaluate('Wooden Mug', self.env)
        self.assertEqual(
            result, ('MUG', 'MUG'),
            "Priority ordering must put MUG (7) ahead of WDS (22)",
        )

    def test_evaluate_inactive_family_skipped(self):
        """Deactivating MUG family must remove it from evaluation."""
        from odoo.addons.multichannel_hub_core.services import sku_grammar_v2
        self.fam_mug.active = False
        # Force cache invalidation via write_date bump (already done by write())
        result = sku_grammar_v2.evaluate('Custom Mug', self.env)
        self.assertEqual(
            result, ('MSC', 'MSC'),
            "Inactive MUG family must not match; fallback to MSC",
        )

    def test_evaluate_new_family_picked_up_at_runtime(self):
        """Adding a family at runtime must be discovered by evaluate (proves DB-driven)."""
        from odoo.addons.multichannel_hub_core.services import sku_grammar_v2
        self.Family.create({
            'code': 'XYZ',
            'name': 'Test Family',
            'priority': 1,
            'regex_pattern': r'\bxyzzytest\b',
            'default_route': 'in_house',
            'active': True,
        })
        result = sku_grammar_v2.evaluate('A xyzzytest item', self.env)
        self.assertEqual(
            result, ('XYZ', 'XYZ'),
            "Newly created family must be picked up immediately (DB-driven, not frozen tuple)",
        )

    def test_evaluate_regex_cache_invalidates_on_write_date_change(self):
        """Changing regex_pattern busts the compile cache (write_date-keyed)."""
        from odoo.addons.multichannel_hub_core.services import sku_grammar_v2
        # First call compiles with original pattern
        sku_grammar_v2.evaluate('Custom Mug', self.env)
        # Mutate the MUG family pattern so 'Mug' no longer matches it
        self.fam_mug.regex_pattern = r'\bzzzzzzzzz\b'
        result = sku_grammar_v2.evaluate('Custom Mug', self.env)
        self.assertNotEqual(
            result, ('MUG', 'MUG'),
            "Cache must invalidate when regex_pattern (and thus write_date) changes",
        )

    def test_evaluate_malformed_regex_falls_back_gracefully(self):
        """A family with an invalid regex must log WARNING and not break evaluate()."""
        from odoo.addons.multichannel_hub_core.services import sku_grammar_v2
        # Create a high-priority family with broken regex
        self.Family.create({
            'code': 'BAD',
            'name': 'Broken Regex Family',
            'priority': 1,
            'regex_pattern': r'[unclosed',
            'default_route': 'in_house',
            'active': True,
        })
        with self.assertLogs(
            'odoo.addons.multichannel_hub_core.services.sku_grammar_v2',
            level='WARNING',
        ):
            result = sku_grammar_v2.evaluate('Custom Mug', self.env)
        # MUG family is still reachable despite broken BAD family
        self.assertEqual(
            result, ('MUG', 'MUG'),
            "Malformed regex on one family must not break evaluation of others",
        )

    # ==================================================================
    # Builder wizard — happy paths
    # ==================================================================

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

    def test_wizard_mug_11oz_no_color_yields_sku_mug_cr_f11(self):
        w = self._make_wizard()
        self.assertEqual(w.preview_sku, 'MUG-CR-F11')
        action = w.with_user(self.ba_user).action_create()
        self.assertIsInstance(action, dict)
        tmpl_id = action.get('res_id')
        self.assertTrue(tmpl_id, "wizard action must return res_id of new template")
        tmpl = self.Template.browse(tmpl_id)
        self.assertEqual(tmpl.default_code, 'MUG-CR-F11')

    def test_wizard_mug_15oz_with_black_yields_sku_mug_cr_f15_bk(self):
        w = self._make_wizard(
            size_id=self.size_f15.id,
            var2_color_id=self.color_bk.id,
        )
        self.assertEqual(w.preview_sku, 'MUG-CR-F15-BK')

    def test_wizard_apron_size_m_yields_sku_apr_tx_am(self):
        w = self._make_wizard(
            product_name='Linen Apron',
            family_id=self.fam_apr.id,
            material_id=self.mat_tx.id,
            size_id=self.size_am.id,
        )
        self.assertEqual(w.preview_sku, 'APR-TX-AM')

    def test_wizard_doormat_rect_30x18_yields_sku_dmt_tx_r30x18(self):
        """Rectangular size composed from rect_w + rect_h fields, not size_id."""
        w = self._make_wizard(
            product_name='Welcome Doormat',
            family_id=self.fam_dmt.id,
            material_id=self.mat_tx.id,
            size_id=False,
            rect_w=30,
            rect_h=18,
        )
        self.assertEqual(w.preview_sku, 'DMT-TX-R30X18')

    # ==================================================================
    # Builder wizard — family override
    # ==================================================================

    def test_wizard_family_override_supersedes_auto(self):
        """BA overrides auto-classifier: name says 'Mug' but family_id=RDS → RDS SKU."""
        w = self._make_wizard(
            product_name='Custom Engraved Mug',
            family_id=self.fam_rds.id,
            material_id=self.mat_ce.id,
            size_id=self.size_sq.id,
        )
        self.assertTrue(
            w.preview_sku.startswith('RDS-'),
            "Manual family_id override must beat auto-classifier (got %s)" % w.preview_sku,
        )

    # ==================================================================
    # Builder wizard — size-step family gating
    # ==================================================================

    def test_size_step_for_mug_only_allows_fluid_oz_values(self):
        """When family=MUG, picking a Shape value (SQ) for size_id must fail validation."""
        w = self._make_wizard(
            family_id=self.fam_mug.id,
            size_id=self.size_sq.id,  # SQ is shape namespace, not fluid_oz
        )
        # Wizard validation (in _check_size_matches_family or action_next) refuses
        self._expect_raises((UserError, ValidationError), w.action_create)

    def test_size_step_for_apparel_only_allows_apparel_sizes(self):
        """When family=APP-style (APR uses apparel sizes), only A* codes are valid."""
        w = self._make_wizard(
            family_id=self.fam_apr.id,
            material_id=self.mat_tx.id,
            size_id=self.size_f11.id,  # F11 is fluid_oz namespace, not apparel
        )
        self._expect_raises((UserError, ValidationError), w.action_create)

    # ==================================================================
    # Builder wizard — field validation refusals
    # ==================================================================

    def test_action_create_refuses_empty_material(self):
        w = self._make_wizard(material_id=False)
        self._expect_raises((UserError, ValidationError), w.action_create)

    def test_action_create_refuses_empty_size_and_no_rect(self):
        w = self._make_wizard(size_id=False, rect_w=0, rect_h=0)
        self._expect_raises((UserError, ValidationError), w.action_create)

    def test_action_create_refuses_empty_product_name(self):
        w = self._make_wizard(product_name='')
        self._expect_raises((UserError, ValidationError), w.action_create)

    # ==================================================================
    # FR-017 method-top gate — 24th confirmation
    # ==================================================================

    def test_non_ba_user_blocked_before_template_create(self):
        """FR-017 24th: non-BA AccessError BEFORE any product.template create."""
        before = self.Template.search_count([])
        w = self._make_wizard(user=self.plain_user)
        self._expect_raises(AccessError, w.with_user(self.plain_user).action_create)
        after = self.Template.search_count([])
        self.assertEqual(
            before, after,
            "Non-BA action_create must NOT create any product.template "
            "(FR-017 method-top gate; pattern memory feedback_fr017_write_defense_in_depth)",
        )

    def test_ba_user_can_create_product(self):
        """BA user succeeds; product.template count increases by exactly 1."""
        before = self.Template.search_count([])
        w = self._make_wizard()
        action = w.with_user(self.ba_user).action_create()
        self.assertIsInstance(action, dict)
        after = self.Template.search_count([])
        self.assertEqual(after, before + 1, "BA create must add exactly 1 template")
