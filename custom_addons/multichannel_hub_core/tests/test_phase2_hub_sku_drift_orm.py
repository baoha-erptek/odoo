"""
Phase 2: ORM tests for P-HUB-SKU-DRIFT (Spec 009 US4) — mhc-half (checkpoint a).

Covers Keep-legacy + Accept-canonical paths. The Etsy push hook is a no-op
in mhc; the actual Etsy implementation + push-success / push-failure tests
land in checkpoint (b) after Spec 011 P-PUB-CLIENT.
"""

from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestHubSkuDriftORM(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env['product.sku.canonicalise.wizard']
        cls.Template = cls.env['product.template']
        cls.ba_user = new_test_user(
            cls.env,
            login='hub_drift_ba',
            groups='multichannel_hub_core.group_ba_user',
        )
        cls.plain_user = new_test_user(
            cls.env,
            login='hub_drift_plain',
            groups='base.group_user',
        )

    def _make_drifted_template(self, name='Custom Ring Dish 3.5"',
                                default_code='LEGACY-RING-001'):
        return self.Template.create({'name': name, 'default_code': default_code})

    # ------------------------------------------------------------------
    # Keep-legacy
    # ------------------------------------------------------------------

    def test_keep_legacy_sets_ba_approved_status(self):
        tmpl = self._make_drifted_template()
        self.assertEqual(tmpl.x_sku_v2_status, 'non_canonical')
        w = self.Wizard.with_user(self.ba_user).create({
            'product_tmpl_id': tmpl.id,
        })
        w.with_user(self.ba_user).action_keep_legacy()
        tmpl.invalidate_recordset()
        self.assertEqual(tmpl.x_sku_v2_status, 'ba_approved_legacy')
        self.assertEqual(tmpl.default_code, 'LEGACY-RING-001')

    def test_keep_legacy_pins_status_against_name_change(self):
        """After keep-legacy, name change does NOT recompute status."""
        tmpl = self._make_drifted_template()
        w = self.Wizard.with_user(self.ba_user).create({
            'product_tmpl_id': tmpl.id,
        })
        w.with_user(self.ba_user).action_keep_legacy()
        tmpl.write({'name': 'Coffee Mug Personalized'})
        self.assertEqual(tmpl.x_sku_v2_status, 'ba_approved_legacy')

    # ------------------------------------------------------------------
    # Accept-canonical (no Etsy link → no push)
    # ------------------------------------------------------------------

    def test_accept_canonical_swaps_default_code_and_archives_legacy(self):
        tmpl = self._make_drifted_template()
        self.assertEqual(tmpl.x_sku_v2_suggested, 'RDS')
        w = self.Wizard.with_user(self.ba_user).create({
            'product_tmpl_id': tmpl.id,
        })
        w.with_user(self.ba_user).action_accept_canonical()
        tmpl.invalidate_recordset()
        self.assertEqual(tmpl.default_code, 'RDS')
        self.assertEqual(tmpl.x_sku_legacy, 'LEGACY-RING-001')
        # Status recomputes to matches after the swap
        self.assertEqual(tmpl.x_sku_v2_status, 'matches')

    def test_accept_canonical_no_etsy_link_no_push_fired(self):
        """Without an active channel linkage, the push hook is invoked but
        with no channel codes (or returns immediately)."""
        tmpl = self._make_drifted_template()
        w = self.Wizard.with_user(self.ba_user).create({
            'product_tmpl_id': tmpl.id,
        })
        # Patch the no-op hook to count calls
        with patch.object(
            type(tmpl), '_push_sku_to_channel', return_value=True,
        ) as m:
            w.with_user(self.ba_user).action_accept_canonical()
        # The hook may be called per applicable channel — with no channel
        # applicability set, it should be called 0 times.
        self.assertEqual(m.call_count, 0, "no channels → no push hook calls")

    def test_accept_canonical_with_etsy_channel_calls_push_hook(self):
        """When the product has etsy channel applicability, push hook fires."""
        ChannelAll = self.env['multichannel.sales.channel'].with_context(active_test=False)
        etsy = ChannelAll.search([('code', '=', 'etsy')], limit=1)
        tmpl = self._make_drifted_template()
        tmpl.x_channel_applicability_ids = [(4, etsy.id)]
        w = self.Wizard.with_user(self.ba_user).create({
            'product_tmpl_id': tmpl.id,
        })
        with patch.object(
            type(tmpl), '_push_sku_to_channel', return_value=True,
        ) as m:
            w.with_user(self.ba_user).action_accept_canonical()
        self.assertGreaterEqual(m.call_count, 1, "etsy channel → push hook fires")

    def test_accept_canonical_rollback_on_push_failure(self):
        """If push hook raises, the SKU swap rolls back."""
        ChannelAll = self.env['multichannel.sales.channel'].with_context(active_test=False)
        etsy = ChannelAll.search([('code', '=', 'etsy')], limit=1)
        tmpl = self._make_drifted_template()
        tmpl.x_channel_applicability_ids = [(4, etsy.id)]
        original_default = tmpl.default_code
        w = self.Wizard.with_user(self.ba_user).create({
            'product_tmpl_id': tmpl.id,
        })

        def boom(*args, **kwargs):
            raise RuntimeError("simulated Etsy push failure")

        with patch.object(type(tmpl), '_push_sku_to_channel', side_effect=boom):
            raised = False
            try:
                with self.env.cr.savepoint():
                    w.with_user(self.ba_user).action_accept_canonical()
            except RuntimeError:
                raised = True
        self.assertTrue(raised)
        tmpl.invalidate_recordset()
        # SKU NOT swapped because the wizard rolled back
        self.assertEqual(tmpl.default_code, original_default)
        self.assertFalse(tmpl.x_sku_legacy)

    # ------------------------------------------------------------------
    # FR-017
    # ------------------------------------------------------------------

    def test_non_ba_user_blocked_by_fr017_gate(self):
        tmpl = self._make_drifted_template()
        w = self.Wizard.with_user(self.plain_user).create({
            'product_tmpl_id': tmpl.id,
        })
        with self.assertRaises(AccessError):
            w.with_user(self.plain_user).action_keep_legacy()
        with self.assertRaises(AccessError):
            w.with_user(self.plain_user).action_accept_canonical()
