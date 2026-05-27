"""
Phase 2: ORM unit tests for P-HUB-PROD-MODEL (Spec 009).

Covers:
- multichannel.sales.channel CRUD + defaults
- product.channel.status CRUD + state validation + cascade
- product.template extensions: M2M write, O2M back-ref, x_unit_margin compute
- sku_grammar_v2.evaluate truth table (matches / non_canonical / msc_catchall)
- ba_approved_legacy status not overwritten by recompute on name change
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHubProductModelORM(TransactionCase):
    """ORM tests for P-HUB-PROD-MODEL."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Channel = cls.env['multichannel.sales.channel']
        cls.Status = cls.env['product.channel.status']
        cls.Template = cls.env['product.template']
        ChannelAll = cls.Channel.with_context(active_test=False)
        cls.etsy = ChannelAll.search([('code', '=', 'etsy')], limit=1)
        cls.amazon = ChannelAll.search([('code', '=', 'amazon')], limit=1)

    # ------------------------------------------------------------------
    # Channel CRUD
    # ------------------------------------------------------------------

    def test_create_channel_defaults(self):
        ch = self.Channel.create({'code': 'orm_test_a', 'name': 'ORM Test A'})
        self.assertEqual(ch.sequence, 10)
        self.assertTrue(ch.active)

    def test_seed_etsy_active(self):
        self.assertTrue(self.etsy, "etsy seed must exist")
        self.assertTrue(self.etsy.active)

    def test_seed_amazon_website_inactive(self):
        website = self.Channel.with_context(active_test=False).search(
            [('code', '=', 'website')], limit=1,
        )
        self.assertFalse(self.amazon.active)
        self.assertFalse(website.active)

    # ------------------------------------------------------------------
    # product.channel.status CRUD
    # ------------------------------------------------------------------

    def _make_template(self, name='Hub Test Template', code=None):
        vals = {'name': name}
        if code is not None:
            vals['default_code'] = code
        return self.Template.create(vals)

    def test_status_create_default_state(self):
        tmpl = self._make_template()
        st = self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy.id,
        })
        self.assertEqual(st.state, 'draft')

    def test_status_unique_per_product_channel(self):
        tmpl = self._make_template()
        self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy.id,
        })
        # Second insert with same (product, channel) must fail at DB level.
        from psycopg2 import IntegrityError
        from odoo.tools import mute_logger
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            with self.env.cr.savepoint():
                self.Status.create({
                    'product_tmpl_id': tmpl.id,
                    'channel_id': self.etsy.id,
                })

    def test_status_cascade_on_product_delete(self):
        tmpl = self._make_template()
        st = self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy.id,
        })
        st_id = st.id
        tmpl.unlink()
        leftover = self.Status.search([('id', '=', st_id)])
        self.assertFalse(leftover, "status row must cascade-delete with product")

    def test_status_back_ref_on_template(self):
        tmpl = self._make_template()
        st = self.Status.create({
            'product_tmpl_id': tmpl.id,
            'channel_id': self.etsy.id,
        })
        self.assertIn(st, tmpl.x_sales_channel_status_ids)

    # ------------------------------------------------------------------
    # product.template M2M channel applicability
    # ------------------------------------------------------------------

    def test_template_m2m_add_channel(self):
        tmpl = self._make_template()
        tmpl.x_channel_applicability_ids = [(4, self.etsy.id)]
        self.assertIn(self.etsy, tmpl.x_channel_applicability_ids)

    def test_template_m2m_remove_channel(self):
        tmpl = self._make_template()
        tmpl.x_channel_applicability_ids = [(4, self.etsy.id)]
        tmpl.x_channel_applicability_ids = [(3, self.etsy.id)]
        self.assertNotIn(self.etsy, tmpl.x_channel_applicability_ids)

    # ------------------------------------------------------------------
    # x_unit_margin compute
    # ------------------------------------------------------------------

    def test_unit_margin_zero_when_all_zero(self):
        tmpl = self._make_template()
        # Reset all pricing fields to zero
        tmpl.write({
            'list_price': 0.0,
            'standard_price': 0.0,
            'x_shipping_price_internal': 0.0,
            'x_additional_cost': 0.0,
        })
        self.assertEqual(tmpl.x_unit_margin, 0.0)

    def test_unit_margin_formula(self):
        tmpl = self._make_template()
        tmpl.standard_price = 50.0
        tmpl.write({
            'list_price': 100.0,
            'x_shipping_price_internal': 10.0,
            'x_additional_cost': 5.0,
        })
        # 100 - 50 - 10 - 5 = 35
        self.assertAlmostEqual(tmpl.x_unit_margin, 35.0, places=4)

    def test_unit_margin_recompute_on_price_change(self):
        tmpl = self._make_template()
        tmpl.write({'list_price': 100.0})
        tmpl.standard_price = 20.0
        first = tmpl.x_unit_margin
        tmpl.write({'list_price': 200.0})
        self.assertNotEqual(tmpl.x_unit_margin, first)
        self.assertAlmostEqual(tmpl.x_unit_margin, 180.0, places=4)

    # ------------------------------------------------------------------
    # Grammar v2 status truth table
    # ------------------------------------------------------------------

    def test_grammar_v2_matches_when_default_code_equals_suggested(self):
        """Ring Dish family → suggested='RDS'; if default_code='RDS', status='matches'."""
        tmpl = self.Template.create({
            'name': 'Custom Ring Dish 3.5"',
            'default_code': 'RDS',
        })
        self.assertEqual(tmpl.x_sku_v2_suggested, 'RDS')
        self.assertEqual(tmpl.x_sku_v2_status, 'matches')

    def test_grammar_v2_non_canonical_when_default_code_differs(self):
        tmpl = self.Template.create({
            'name': 'Custom Ring Dish 3.5"',
            'default_code': 'LEGACY-RING-001',
        })
        self.assertEqual(tmpl.x_sku_v2_suggested, 'RDS')
        self.assertEqual(tmpl.x_sku_v2_status, 'non_canonical')

    def test_grammar_v2_msc_catchall_for_unmatched_name(self):
        tmpl = self.Template.create({
            'name': 'Some Random Widget XYZ',
            'default_code': 'WIDGET-001',
        })
        self.assertEqual(tmpl.x_sku_v2_suggested, 'MSC')
        self.assertEqual(tmpl.x_sku_v2_status, 'msc_catchall')

    def test_grammar_v2_msc_catchall_even_if_default_code_equals_msc(self):
        """Family=MSC always wins over matches/non_canonical comparison."""
        tmpl = self.Template.create({
            'name': 'Some Random Widget',
            'default_code': 'MSC',
        })
        self.assertEqual(tmpl.x_sku_v2_status, 'msc_catchall')

    def test_grammar_v2_mug_family(self):
        tmpl = self.Template.create({
            'name': 'Coffee Mug Personalized',
            'default_code': 'MUG',
        })
        self.assertEqual(tmpl.x_sku_v2_suggested, 'MUG')
        self.assertEqual(tmpl.x_sku_v2_status, 'matches')

    def test_grammar_v2_recompute_on_name_change(self):
        tmpl = self.Template.create({
            'name': 'Coffee Mug Personalized',
            'default_code': 'MUG',
        })
        self.assertEqual(tmpl.x_sku_v2_status, 'matches')
        tmpl.write({'name': 'Wedding Ring Dish 3.5"'})
        self.assertEqual(tmpl.x_sku_v2_suggested, 'RDS')

    def test_grammar_v2_ba_approved_legacy_not_overwritten(self):
        """When x_sku_v2_status='ba_approved_legacy', recompute must skip it."""
        tmpl = self.Template.create({
            'name': 'Custom Ring Dish 3.5"',
            'default_code': 'LEGACY-RING-001',
        })
        # Manually pin to ba_approved_legacy (simulates canonicalisation wizard).
        tmpl.write({'x_sku_v2_status': 'ba_approved_legacy'})
        # Trigger a recompute by changing name.
        tmpl.write({'name': 'Custom Ring Dish 4.0"'})
        self.assertEqual(
            tmpl.x_sku_v2_status,
            'ba_approved_legacy',
            "ba_approved_legacy must not be overwritten on name change",
        )

    # ------------------------------------------------------------------
    # state field constraint
    # ------------------------------------------------------------------

    def test_status_state_selection_valid_values(self):
        tmpl = self._make_template()
        for valid in ('draft', 'published', 'archived', 'error'):
            st = self.Status.create({
                'product_tmpl_id': tmpl.id,
                'channel_id': self.amazon.id,
                'state': valid,
            })
            self.assertEqual(st.state, valid)
            st.unlink()

    def test_status_state_selection_rejects_invalid(self):
        tmpl = self._make_template()
        raised = False
        try:
            with self.env.cr.savepoint():
                self.Status.create({
                    'product_tmpl_id': tmpl.id,
                    'channel_id': self.etsy.id,
                    'state': 'bogus_state',
                })
        except (ValidationError, ValueError):
            raised = True
        self.assertTrue(raised, "Selection must reject invalid state value")
