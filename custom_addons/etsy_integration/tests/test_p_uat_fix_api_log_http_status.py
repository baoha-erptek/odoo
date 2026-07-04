"""P-UAT-FIX-API-LOG-HTTP-STATUS — Phase 1 + Phase 2 tests.

Class A defect surfaced by P-UAT-AUTOMATION-2FLOWS Phase D
(specs/006-master-plan/findings.md §"Residual #3"). Three of four
`etsy.api.log` writers omit `http_status` on success, so Flow-2 TC-003
(http_status in [200,299] AND error_message empty) can never converge.

Producers fixed by this slice:
- models/etsy_listing.py:_write_audit            (source='listing_pull')
- models/etsy_listing_product.py:_write_audit    (source='listing_pull')
- services/etsy_order_syncer.py:_audit_log       (source='audit')

The reference (correct) impl is
services/etsy_tracking_pusher.py:_audit, which threads http_status as a
parameter via the dedicated `client.push_tracking()` return tuple. The
3 broken writers route through `EtsyApiClient.get()`, which returns
`response.json()` and discards the status. Fix: expose
`EtsyApiClient.last_http_status` (set in `_request()` before
`raise_for_status()`, so both success and HTTP-failure paths capture);
adapters surface it via `adapter._client.last_http_status`.

The Phase 1 invariant test exercises all 3 writers in one transaction
and asserts no row violates the contract via raw SQL on the savepoint.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


def _raw_listing(listing_id, title='T', state='active'):
    return {
        'listing_id': listing_id,
        'title': title,
        'state': state,
        'description': 'desc',
        'url': 'https://www.etsy.com/listing/%s' % listing_id,
        'price': {'amount': 1000, 'divisor': 100, 'currency_code': 'USD'},
        'quantity': 1,
        'created_timestamp': 1600000000,
        'last_modified_tsz': 1700000000,
    }


class _FakeListingAdapter:
    """Stand-in for `EtsyListingAdapter`. Exposes a `_client` with the
    same `last_http_status` attribute the production code reads."""

    def __init__(self, pages, http_status=200):
        self._pages = pages
        self._client = MagicMock()
        self._client.last_http_status = http_status

    def fetch_listings(self, shop_id, since=None):
        for page in self._pages:
            for raw in page:
                yield raw


class _FakeInventoryAdapter:
    """Stand-in for `EtsyInventoryAdapter`."""

    def __init__(self, variants_per_listing, http_status=200):
        self._variants = variants_per_listing
        self._client = MagicMock()
        self._client.last_http_status = http_status

    def fetch_variants(self, listing_id):
        return self._variants.get(str(listing_id), [])


def _make_payload(etsy_order_id='recpt-1', amount=100.0, currency='USD'):
    """Mock an `EtsyOrderPayload` shape for audit-mode tests."""
    payload = MagicMock()
    payload.etsy_order_id = etsy_order_id
    payload.amount_total = amount
    payload.currency = currency
    payload.last_modified = datetime(2026, 1, 1)
    payload.order_date = datetime(2026, 1, 1)
    return payload


@tagged('post_install', '-at_install', 'p_uat_fix_api_log_http_status')
class TestT1_ListingPullHttpStatus(TransactionCase):
    """T1: `etsy.listing._write_audit` must populate `http_status`."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'UAT-FIX-API-LOG-T1',
            'active_source': 'api',
            'etsy_api_shop_id': '12345',
            'etsy_oauth_access_token': 'tok-access',
            'etsy_oauth_refresh_token': 'tok-refresh',
        })
        cls.Listing = cls.env['etsy.listing']

    def test_listing_pull_audit_row_has_http_status_on_success(self):
        adapter = _FakeListingAdapter(
            [[_raw_listing(1001)]], http_status=200)
        with patch.object(
            type(self.Listing), '_build_adapter', return_value=adapter,
        ):
            self.Listing._sync_shop_listings(self.shop)
        log = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
            ('source', '=', 'listing_pull'),
        ], order='id desc', limit=1)
        self.assertTrue(log, 'audit row must be written')
        self.assertEqual(
            log.http_status, 200,
            'success path must record http_status from '
            'client.last_http_status',
        )

    def test_listing_pull_audit_row_has_http_status_on_error(self):
        """Error path: even when post-fetch processing fails, the audit
        row records the last HTTP status the client saw — so operators
        can disambiguate upstream-failure from downstream-bug."""
        adapter = _FakeListingAdapter(
            [[_raw_listing(1002)]], http_status=200)
        with patch.object(
            type(self.Listing), '_build_adapter', return_value=adapter,
        ), patch.object(
            type(self.Listing), '_listing_vals_from_raw',
            side_effect=ValueError('bad vals'),
        ):
            self.Listing._cron_sync_listings()  # swallows per-shop error
        log = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
            ('source', '=', 'listing_pull'),
            ('error_message', 'ilike', 'bad vals'),
        ], order='id desc', limit=1)
        self.assertTrue(log, 'error-path audit row must persist')
        self.assertEqual(log.http_status, 200)


@tagged('post_install', '-at_install', 'p_uat_fix_api_log_http_status')
class TestT2_VariantPullHttpStatus(TransactionCase):
    """T2: `etsy.listing.product._write_audit` must populate
    `http_status`."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'UAT-FIX-API-LOG-T2',
            'active_source': 'api',
            'etsy_api_shop_id': '67890',
            'etsy_oauth_access_token': 'tok-access',
            'etsy_oauth_refresh_token': 'tok-refresh',
        })
        cls.listing = cls.env['etsy.listing'].create({
            'shop_id': cls.shop.id,
            'etsy_listing_id': '5001',
            'title': 'T2 Listing',
            'state': 'active',
            'is_active': True,
        })
        cls.LP = cls.env['etsy.listing.product']

    def test_variant_pull_audit_row_has_http_status_on_success(self):
        variant = {
            'product_id': '999',
            'sku': '',  # empty SKU avoids product matching path
            'property_values': [],
            'offerings': [
                {'quantity': 5, 'price': {'amount': 2000, 'divisor': 100}}],
        }
        adapter = _FakeInventoryAdapter(
            {'5001': [variant]}, http_status=200)
        with patch.object(
            type(self.LP), '_build_adapter', return_value=adapter,
        ):
            self.LP._sync_shop_variants(self.shop)
        log = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
            ('source', '=', 'listing_pull'),
            ('endpoint', 'ilike', 'inventory'),
        ], order='id desc', limit=1)
        self.assertTrue(log, 'variant-pull audit row must be written')
        self.assertEqual(log.http_status, 200)


@tagged('post_install', '-at_install', 'p_uat_fix_api_log_http_status')
class TestT3_OrderSyncerAuditLogHttpStatus(TransactionCase):
    """T3: `_audit_log` in `etsy_order_syncer` writes `http_status=200`.

    Audit rows only fire AFTER `adapter.fetch_new_orders` has yielded a
    payload — the upstream page fetch has already succeeded — so 200 is
    the only correct value at this call site."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'UAT-FIX-API-LOG-T3',
            'sync_mode': 'email_only',
            'sync_audit_mode': True,
            'etsy_api_shop_id': '12345',
        })

    def test_audit_log_row_has_http_status_200(self):
        from odoo.addons.etsy_integration.services.etsy_order_syncer \
            import EtsyOrderSyncer
        adapter = MagicMock()
        adapter.fetch_new_orders.return_value = iter([_make_payload()])
        syncer = EtsyOrderSyncer(self.env)
        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)
        log = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
            ('source', '=', 'audit'),
        ], order='id desc', limit=1)
        self.assertTrue(log, 'audit row must be written')
        self.assertEqual(log.http_status, 200)


@tagged('post_install', '-at_install', 'p_uat_fix_api_log_http_status')
class TestPhase1_HttpStatusInvariant(TransactionCase):
    """Phase 1 (DB-level): exercise all 3 writers in one transaction and
    query directly to assert the invariant. This is the regression test
    explicitly called out in findings.md §"Residual #3"."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'UAT-FIX-API-LOG-INVARIANT',
            'active_source': 'api',
            'sync_mode': 'email_only',
            'sync_audit_mode': True,
            'etsy_api_shop_id': '54321',
            'etsy_oauth_access_token': 'tok-access',
            'etsy_oauth_refresh_token': 'tok-refresh',
        })

    def test_invariant_listing_pull_audit_no_zero_http_status(self):
        # T1 — listing pull
        Listing = self.env['etsy.listing']
        with patch.object(
            type(Listing), '_build_adapter',
            return_value=_FakeListingAdapter(
                [[_raw_listing(7001)]], http_status=200),
        ):
            Listing._sync_shop_listings(self.shop)
        # T2 — variant pull
        Listing.create({
            'shop_id': self.shop.id,
            'etsy_listing_id': '7002',
            'title': 'X',
            'state': 'active',
            'is_active': True,
        })
        LP = self.env['etsy.listing.product']
        variant = {
            'product_id': '111',
            'sku': '',
            'property_values': [],
            'offerings': [
                {'quantity': 1, 'price': {'amount': 100, 'divisor': 100}}],
        }
        with patch.object(
            type(LP), '_build_adapter',
            return_value=_FakeInventoryAdapter(
                {'7002': [variant]}, http_status=200),
        ):
            LP._sync_shop_variants(self.shop)
        # T3 — audit-mode order sync
        from odoo.addons.etsy_integration.services.etsy_order_syncer \
            import EtsyOrderSyncer
        adapter = MagicMock()
        adapter.fetch_new_orders.return_value = iter(
            [_make_payload(etsy_order_id='recpt-inv')])
        syncer = EtsyOrderSyncer(self.env)
        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)
        # Invariant: query directly (Phase 1 style — bypasses ORM cache).
        self.env.flush_all()
        # Invariant query: `fields.Integer()` without explicit default
        # writes NULL on omitted-key creates (ORM read coerces NULL→0),
        # so the filter must catch BOTH NULL and 0/negative. Similarly
        # `error_message` may store as NULL or empty string depending on
        # field-config + write path; treat both as "empty".
        self.env.cr.execute(
            """
            SELECT id, source, http_status, error_message
              FROM etsy_api_log
             WHERE shop_id = %s
               AND source IN ('listing_pull', 'audit')
               AND (error_message IS NULL OR error_message = '')
               AND (http_status IS NULL OR http_status <= 0)
            """,
            (self.shop.id,),
        )
        violations = self.env.cr.fetchall()
        self.assertEqual(
            violations, [],
            'No listing_pull/audit row with empty error_message may '
            'have NULL or non-positive http_status. Violations: %r'
            % (violations,),
        )
