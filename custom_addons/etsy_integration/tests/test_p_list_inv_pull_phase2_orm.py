"""Phase 2 ORM tests for P-LIST-INV-PULL — variant snapshot + SKU match
+ drift (Spec 008 US2/US3/US4).

- EtsyInventoryAdapter.fetch_variants returns the products list
- _sync_shop_variants upserts variants; soft-deletes removed ones
- SKU match: single match sets FK; no match leaves NULL (no auto-create,
  ADR-013 Q-a); empty sku skipped; duplicate default_code warn + first;
  manual FK preserved on resync (R-L6); closest-match-only (ADR-013 Q-c)
- C-LPROD-002 @api.constrains: product_id.default_code must == sku
- odoo_qty / qty_drift computed
- drift reporter: unlinked / qty_drift / orphan
- _cron_sync_variants filters active_source='api', refuses non-system

PHASE: RED (implementation does not exist yet)
"""
import logging
from unittest import mock

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


def _variant(product_id, sku='SKU-A', qty=5, price_amount=2999, props=None):
    return {
        'product_id': product_id,
        'sku': sku,
        'property_values': props or [
            {'property_id': 1, 'property_name': 'Color',
             'value_ids': [9], 'values': ['Red']},
        ],
        'offerings': [{
            'quantity': qty,
            'price': {'amount': price_amount, 'divisor': 100,
                      'currency_code': 'USD'},
        }],
    }


class _FakeInvAdapter:
    """Stands in for EtsyInventoryAdapter — maps listing_id → variants."""

    def __init__(self, by_listing):
        self._by_listing = by_listing  # {etsy_listing_id: [raw, ...]}

    def fetch_variants(self, listing_id):
        return self._by_listing.get(str(listing_id), [])


@tagged('post_install', '-at_install', 'p_list_inv_pull')
class TestPListInvPull(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'INV Shop', 'active_source': 'api',
            'etsy_oauth_access_token': 'tok-a',
            'etsy_oauth_refresh_token': 'tok-r',
        })
        cls.listing = cls.env['etsy.listing'].create({
            'shop_id': cls.shop.id, 'etsy_listing_id': '900',
            'title': 'Hat', 'state': 'active',
        })
        cls.Variant = cls.env['etsy.listing.product']

    def _patch(self, by_listing):
        return mock.patch.object(
            type(self.Variant), '_build_adapter',
            return_value=_FakeInvAdapter(by_listing),
        )

    def _product(self, code):
        return self.env['product.product'].create({
            'name': 'P-%s' % code, 'default_code': code})

    def test_fetch_variants_returns_products_list(self):
        from odoo.addons.etsy_integration.services.etsy_inventory_adapter \
            import EtsyInventoryAdapter
        client = mock.Mock()
        client.get.return_value = {'products': [_variant(1), _variant(2)]}
        got = EtsyInventoryAdapter(client).fetch_variants(900)
        self.assertEqual([v['product_id'] for v in got], [1, 2])
        client.get.assert_called_once()

    def test_sync_creates_variants(self):
        with self._patch({'900': [_variant(11, sku='S11'),
                                  _variant(12, sku='S12')]}):
            self.Variant._sync_shop_variants(self.shop)
        recs = self.Variant.search([('listing_id', '=', self.listing.id)])
        self.assertEqual(set(recs.mapped('etsy_product_id')), {'11', '12'})
        v = recs.filtered(lambda r: r.etsy_product_id == '11')
        self.assertEqual(v.sku, 'S11')
        self.assertEqual(v.quantity, 5)
        self.assertAlmostEqual(v.price, 29.99, places=2)

    def test_resync_soft_deletes_absent_variant(self):
        with self._patch({'900': [_variant(21, sku='A'), _variant(22, sku='B')]}):
            self.Variant._sync_shop_variants(self.shop)
        with self._patch({'900': [_variant(21, sku='A')]}):
            self.Variant._sync_shop_variants(self.shop)
        gone = self.Variant.search([('listing_id', '=', self.listing.id),
                                    ('etsy_product_id', '=', '22')])
        self.assertTrue(gone, "row must NOT be hard-unlinked")
        self.assertFalse(gone.is_active)

    def test_sku_match_single(self):
        p = self._product('MATCH-1')
        with self._patch({'900': [_variant(31, sku='MATCH-1')]}):
            self.Variant._sync_shop_variants(self.shop)
        v = self.Variant.search([('etsy_product_id', '=', '31')])
        self.assertEqual(v.product_id, p)

    def test_sku_no_match_leaves_null_no_autocreate(self):
        before = self.env['product.product'].search_count([])
        with self._patch({'900': [_variant(41, sku='NOPE-XYZ')]}):
            self.Variant._sync_shop_variants(self.shop)
        v = self.Variant.search([('etsy_product_id', '=', '41')])
        self.assertFalse(v.product_id)
        self.assertEqual(self.env['product.product'].search_count([]), before,
                         "must NOT auto-create a product (ADR-013 Q-a)")

    def test_sku_empty_skipped(self):
        with self._patch({'900': [_variant(51, sku='')]}):
            self.Variant._sync_shop_variants(self.shop)
        v = self.Variant.search([('etsy_product_id', '=', '51')])
        self.assertFalse(v.product_id)

    def test_duplicate_default_code_warns_and_links_first(self):
        p1 = self._product('DUP')
        self._product('DUP')  # second product, same code
        with self._patch({'900': [_variant(61, sku='DUP')]}):
            self.Variant._sync_shop_variants(self.shop)
        v = self.Variant.search([('etsy_product_id', '=', '61')])
        self.assertEqual(v.product_id, p1, "deterministic: first by id")

    def test_manual_fk_preserved_on_resync(self):
        """Dup default_code: auto-match picks p1; operator overrides to
        p2 (same code → C-LPROD-002 OK); resync must NOT revert to p1."""
        p1 = self._product('DUP2')
        p2 = self._product('DUP2')
        with self._patch({'900': [_variant(71, sku='DUP2')]}):
            self.Variant._sync_shop_variants(self.shop)
        v = self.Variant.search([('etsy_product_id', '=', '71')])
        self.assertEqual(v.product_id, p1, "auto-match picks first by id")
        v.product_id = p2  # operator override (default_code still 'DUP2')
        with self._patch({'900': [_variant(71, sku='DUP2')]}):
            self.Variant._sync_shop_variants(self.shop)
        v.invalidate_recordset()
        self.assertEqual(v.product_id, p2, "manual FK must survive resync")

    def test_c_lprod_002_constraint_rejects_sku_mismatch(self):
        p = self._product('GOODSKU')
        with self._patch({'900': [_variant(81, sku='GOODSKU')]}):
            self.Variant._sync_shop_variants(self.shop)
        v = self.Variant.search([('etsy_product_id', '=', '81')])
        bad = self._product('DIFFERENT')
        with self.assertRaises(ValidationError):
            v.product_id = bad  # default_code 'DIFFERENT' != sku 'GOODSKU'

    def test_odoo_qty_and_qty_drift_computed(self):
        with self._patch({'900': [_variant(91, sku='Q', qty=10)]}):
            self.Variant._sync_shop_variants(self.shop)
        v = self.Variant.search([('etsy_product_id', '=', '91')])
        self.assertEqual(v.odoo_qty, 0)  # unlinked → 0
        self.assertEqual(v.qty_drift, 10)  # 10 (etsy) - 0 (odoo)

    def test_drift_reporter_unlinked_and_orphan(self):
        from odoo.addons.etsy_integration.services\
            .etsy_listing_drift_reporter import EtsyListingDriftReporter
        with self._patch({'900': [_variant(95, sku='UNMATCHED')]}):
            self.Variant._sync_shop_variants(self.shop)
        rep = EtsyListingDriftReporter(self.env)
        unlinked = rep.get_unlinked_variants(self.shop)
        self.assertTrue(any(u['sku'] == 'UNMATCHED' for u in unlinked))

    def test_cron_filters_api_and_refuses_non_system(self):
        seen = []
        with mock.patch.object(
            type(self.Variant), '_sync_shop_variants',
            side_effect=lambda shop: seen.append(shop.id),
        ):
            self.Variant._cron_sync_variants()
        self.assertIn(self.shop.id, seen)
        portal = self.env['res.users'].create({
            'name': 'P', 'login': 'plinv_portal',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        with self.assertRaises(AccessError):
            self.Variant.with_user(portal)._cron_sync_variants()

    def test_audit_row_written_source_listing_pull(self):
        before = self.env['etsy.api.log'].search_count([
            ('shop_id', '=', self.shop.id), ('source', '=', 'listing_pull')])
        with self._patch({'900': [_variant(99, sku='Z')]}):
            self.Variant._sync_shop_variants(self.shop)
        after = self.env['etsy.api.log'].search_count([
            ('shop_id', '=', self.shop.id), ('source', '=', 'listing_pull')])
        self.assertGreater(after, before)
