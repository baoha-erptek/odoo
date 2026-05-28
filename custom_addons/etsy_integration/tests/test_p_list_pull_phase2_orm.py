"""Phase 2 ORM tests for P-LIST-PULL — Etsy listing metadata ingest (Spec 008 US1).

Business logic / ORM behaviour:
- EtsyListingAdapter.fetch_listings paginates (next_offset until None)
- _sync_shop_listings upserts: create new, update mutable fields
- url / created_at are immutable after first ingest
- listing absent from a fresh fetch is soft-deleted (is_active=False,
  state='deleted') — never hard unlink
- _cron_sync_listings filters to active_source='api' shops only
- _cron_sync_listings refuses non-system callers (AccessError)
- one etsy.api.log row written per shop sync, source='listing_pull'

PHASE: RED (implementation does not exist yet)
"""
import logging
from unittest import mock

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


def _raw(listing_id, title='T', state='active', price_amount=2999,
         qty=5, url=None, created_ts=1600000000, modified_ts=1700000000):
    """A raw Etsy v3 listing dict (money as {amount,divisor,currency_code})."""
    return {
        'listing_id': listing_id,
        'title': title,
        'state': state,
        'description': 'desc-%s' % listing_id,
        'url': url or 'https://www.etsy.com/listing/%s' % listing_id,
        'price': {'amount': price_amount, 'divisor': 100, 'currency_code': 'USD'},
        'quantity': qty,
        'created_timestamp': created_ts,
        'last_modified_tsz': modified_ts,
    }


class _FakeAdapter:
    """Stands in for EtsyListingAdapter — yields canned raw dicts."""

    def __init__(self, pages):
        self._pages = pages  # list of lists of raw dicts

    def fetch_listings(self, shop_id, since=None):
        for page in self._pages:
            for raw in page:
                yield raw


@tagged('post_install', '-at_install', 'p_list_pull')
class TestPListPullIngest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'P-LIST-PULL Shop',
            'active_source': 'api',
            'etsy_oauth_access_token': 'tok-access',
            'etsy_oauth_refresh_token': 'tok-refresh',
        })
        cls.Listing = cls.env['etsy.listing']

    def _patch_adapter(self, pages):
        return mock.patch.object(
            type(self.Listing), '_build_adapter',
            return_value=_FakeAdapter(pages),
        )

    def test_fetch_listings_paginates_until_no_next_offset(self):
        """Adapter pages with limit/offset and stops on falsy next_offset."""
        from odoo.addons.etsy_integration.services.etsy_listing_adapter import (
            EtsyListingAdapter,
        )
        responses = [
            {'results': [_raw(1), _raw(2)], 'next_offset': 2},
            {'results': [_raw(3)], 'next_offset': None},
        ]
        client = mock.Mock()
        client.get.side_effect = responses
        adapter = EtsyListingAdapter(client)
        got = list(adapter.fetch_listings(self.shop.id, None))
        self.assertEqual([r['listing_id'] for r in got], [1, 2, 3])
        self.assertEqual(client.get.call_count, 2)

    def test_sync_creates_new_listings(self):
        with self._patch_adapter([[_raw(101), _raw(102)]]):
            self.Listing._sync_shop_listings(self.shop)
        recs = self.Listing.search([('shop_id', '=', self.shop.id)])
        self.assertEqual(set(recs.mapped('etsy_listing_id')), {'101', '102'})
        r = recs.filtered(lambda x: x.etsy_listing_id == '101')
        self.assertEqual(r.state, 'active')
        self.assertAlmostEqual(r.price, 29.99, places=2)
        self.assertEqual(r.quantity, 5)
        self.assertTrue(r.is_active)

    def test_resync_updates_mutable_but_not_url_or_created_at(self):
        with self._patch_adapter([[_raw(200, title='Old', state='active',
                                        price_amount=1000)]]):
            self.Listing._sync_shop_listings(self.shop)
        rec = self.Listing.search([('shop_id', '=', self.shop.id),
                                    ('etsy_listing_id', '=', '200')])
        original_url, original_created = rec.url, rec.created_at
        with self._patch_adapter([[_raw(200, title='New', state='inactive',
                                        price_amount=4200,
                                        url='https://evil/override',
                                        created_ts=999)]]):
            self.Listing._sync_shop_listings(self.shop)
        rec.invalidate_recordset()
        self.assertEqual(rec.title, 'New')
        self.assertEqual(rec.state, 'inactive')
        self.assertAlmostEqual(rec.price, 42.00, places=2)
        self.assertEqual(rec.url, original_url, "url must be immutable")
        self.assertEqual(rec.created_at, original_created,
                         "created_at must be immutable")

    def test_listing_absent_from_fetch_is_soft_deleted(self):
        with self._patch_adapter([[_raw(301), _raw(302)]]):
            self.Listing._sync_shop_listings(self.shop)
        with self._patch_adapter([[_raw(301)]]):  # 302 gone upstream
            self.Listing._sync_shop_listings(self.shop)
        gone = self.Listing.search([('shop_id', '=', self.shop.id),
                                     ('etsy_listing_id', '=', '302')])
        self.assertTrue(gone, "row must NOT be hard-unlinked")
        self.assertFalse(gone.is_active)
        self.assertEqual(gone.state, 'deleted')

    def test_audit_row_written_source_listing_pull(self):
        before = self.env['etsy.api.log'].search_count([
            ('shop_id', '=', self.shop.id), ('source', '=', 'listing_pull')])
        with self._patch_adapter([[_raw(401)]]):
            self.Listing._sync_shop_listings(self.shop)
        after = self.env['etsy.api.log'].search_count([
            ('shop_id', '=', self.shop.id), ('source', '=', 'listing_pull')])
        self.assertEqual(after, before + 1)

    def test_cron_swallows_shop_error_and_writes_error_audit(self):
        """Production path: a per-shop failure is swallowed by
        _cron_sync_listings (no re-raise) and a listing_pull audit row
        with error_message persists on the cron's commit."""
        with self._patch_adapter([[_raw(501)]]), mock.patch.object(
            type(self.Listing), '_listing_vals_from_raw',
            side_effect=ValueError('bad listing data'),
        ):
            # Cron must NOT propagate the per-shop error.
            self.Listing._cron_sync_listings()
        log = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
            ('source', '=', 'listing_pull'),
            ('error_message', 'ilike', 'bad listing data'),
        ])
        self.assertTrue(log, "error-path audit row must persist")

    def test_cron_filters_active_source_api_only(self):
        email_shop = self.env['etsy.shop'].create({
            'name': 'Email Shop', 'active_source': 'email'})
        seen = []
        with mock.patch.object(
            type(self.Listing), '_sync_shop_listings',
            side_effect=lambda shop: seen.append(shop.id),
        ):
            self.Listing._cron_sync_listings()
        self.assertIn(self.shop.id, seen)
        self.assertNotIn(email_shop.id, seen)

    def test_cron_refuses_non_system_caller(self):
        portal = self.env['res.users'].create({
            'name': 'Portal U', 'login': 'plistpull_portal',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        with self.assertRaises(AccessError):
            self.Listing.with_user(portal)._cron_sync_listings()
