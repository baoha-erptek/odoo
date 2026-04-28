"""P0-16c Phase 2 — ORM unit tests for EtsyOrderSyncer.

Drives the orchestrator that pages Etsy receipts, ingests via
`EtsyOrderIngestor`, and advances the per-shop watermark. HTTP is
patched at the `EtsyApiClient.get` boundary; the adapter, ingestor,
and `OrderCreator` run with their real implementations so the tests
exercise integration behavior, not isolated mocks.

OQ contracts verified:
- OQ1: audit branch logs each receipt via `_logger.warning`
- OQ2: status-only re-sync preserves operator fields (separate file)
- OQ3: cursor advances per-payload; mid-run failure pins cursor
- OQ4: `sync_audit_mode + sync_mode='api_only'` emits soft warning
- OQ5: cron filter skips `sync_mode != 'api_only'`
"""

import json
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services.etsy_order_syncer import EtsyOrderSyncer


_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'etsy_v3')


def _load(name):
    with open(os.path.join(_FIXTURE_DIR, name)) as f:
        return json.load(f)


def _patch_get(monkey_target, *responses):
    """Build a mock for `EtsyApiClient.get` returning successive
    fixtures. Used as the side_effect for `mock.patch.object`.
    """
    return MagicMock(side_effect=list(responses))


@tagged('post_install', '-at_install')
class TestEtsyOrderSyncer_FirstRun(TransactionCase):

    def setUp(self):
        super().setUp()
        self.shop = self.env['etsy.shop'].create({
            'name': 'FirstRunShop', 'sync_mode': 'api_only',
        })

    def test_first_run_passes_since_none_to_adapter(self):
        """NULL cursor → adapter receives `since=None`."""
        syncer = EtsyOrderSyncer(self.env)
        adapter = MagicMock()
        adapter.fetch_new_orders.return_value = iter([])
        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)
        adapter.fetch_new_orders.assert_called_once()
        args, kwargs = adapter.fetch_new_orders.call_args
        # adapter.fetch_new_orders(shop_id, since)
        self.assertIsNone(args[1] if len(args) > 1 else kwargs.get('since'))

    def test_first_run_advances_cursor_to_max_last_modified(self):
        """After successful batch, cursor = max(last_modified) of payloads."""
        syncer = EtsyOrderSyncer(self.env)
        with patch(
            'odoo.addons.etsy_integration.services.etsy_api_client.EtsyApiClient.get',
            _patch_get(None, _load('receipts_page1.json'), _load('receipts_page2.json')),
        ), patch(
            'odoo.addons.etsy_integration.services.etsy_order_syncer.EtsyApiClient',
            return_value=MagicMock(),
        ):
            # Real adapter w/ patched HTTP + fake EtsyApiClient instance
            from odoo.addons.etsy_integration.services.etsy_api_adapter import EtsyApiAdapter
            real_client = MagicMock()
            real_client.get.side_effect = [
                _load('receipts_page1.json'),
                _load('receipts_page2.json'),
            ]
            adapter = EtsyApiAdapter(real_client)
            with patch.object(syncer, '_build_adapter', return_value=adapter):
                syncer.sync_shop_orders(self.shop)
        self.shop.invalidate_recordset(['etsy_last_receipt_sync_at'])
        # page2 fixture max last_modified_tsz = 1704412800 (2024-01-05)
        # page1 max = 1704240000 (2024-01-03)
        self.assertIsNotNone(self.shop.etsy_last_receipt_sync_at)
        self.assertGreaterEqual(
            self.shop.etsy_last_receipt_sync_at,
            datetime(2024, 1, 3, 0, 0, 0),
        )


@tagged('post_install', '-at_install')
class TestEtsyOrderSyncer_Incremental(TransactionCase):

    def setUp(self):
        super().setUp()
        self.shop = self.env['etsy.shop'].create({
            'name': 'IncrementalShop', 'sync_mode': 'api_only',
        })
        self.shop.etsy_last_receipt_sync_at = datetime(2026, 1, 1, 0, 0, 0)

    def test_incremental_run_passes_existing_cursor_to_adapter(self):
        syncer = EtsyOrderSyncer(self.env)
        adapter = MagicMock()
        adapter.fetch_new_orders.return_value = iter([])
        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)
        args, kwargs = adapter.fetch_new_orders.call_args
        self.assertEqual(args[1] if len(args) > 1 else kwargs.get('since'),
                         datetime(2026, 1, 1, 0, 0, 0))

    def test_pagination_consumes_all_pages(self):
        """Two-page fixture → 5 sale.orders ingested."""
        syncer = EtsyOrderSyncer(self.env)
        from odoo.addons.etsy_integration.services.etsy_api_adapter import EtsyApiAdapter
        client = MagicMock()
        client.get.side_effect = [
            _load('receipts_page1.json'),
            _load('receipts_page2.json'),
        ]
        adapter = EtsyApiAdapter(client)
        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)
        orders = self.env['sale.order'].search([
            ('etsy_shop_id', '=', self.shop.id),
        ])
        self.assertEqual(len(orders), 5)


@tagged('post_install', '-at_install')
class TestEtsyOrderSyncer_Idempotency(TransactionCase):

    def setUp(self):
        super().setUp()
        self.shop = self.env['etsy.shop'].create({
            'name': 'IdempotencyShop', 'sync_mode': 'api_only',
        })

    def test_resync_same_receipt_does_not_create_duplicate(self):
        """Running the same receipt twice = exactly one sale.order."""
        syncer = EtsyOrderSyncer(self.env)
        from odoo.addons.etsy_integration.services.etsy_api_adapter import EtsyApiAdapter

        for _ in range(2):
            client = MagicMock()
            client.get.side_effect = [_load('receipts_single_paid.json')]
            adapter = EtsyApiAdapter(client)
            # Reset cursor between runs to force re-fetch
            self.shop.etsy_last_receipt_sync_at = False
            with patch.object(syncer, '_build_adapter', return_value=adapter):
                syncer.sync_shop_orders(self.shop)

        receipt_id = str(_load('receipts_single_paid.json')['results'][0]['receipt_id'])
        orders = self.env['sale.order'].search([
            ('etsy_order_id', '=', receipt_id),
        ])
        self.assertEqual(len(orders), 1)


@tagged('post_install', '-at_install')
class TestEtsyOrderSyncer_AuditMode(TransactionCase):

    def setUp(self):
        super().setUp()
        self.shop = self.env['etsy.shop'].create({
            'name': 'AuditModeShop',
            'sync_mode': 'email_only',
            'sync_audit_mode': True,
        })

    def _adapter_with_page1(self):
        from odoo.addons.etsy_integration.services.etsy_api_adapter import EtsyApiAdapter
        client = MagicMock()
        client.get.side_effect = [_load('receipts_page1.json')]
        # page1 has next_offset=3; provide a page2 with next_offset=null
        # to make the iterator terminate cleanly within a single test page
        page1 = _load('receipts_page1.json')
        page1['next_offset'] = None  # force single-page
        client.get.side_effect = [page1]
        return EtsyApiAdapter(client)

    def test_audit_mode_does_not_create_sale_order(self):
        syncer = EtsyOrderSyncer(self.env)
        adapter = self._adapter_with_page1()
        before = self.env['sale.order'].search_count([
            ('etsy_shop_id', '=', self.shop.id),
        ])
        with patch.object(syncer, '_build_adapter', return_value=adapter):
            result = syncer.sync_shop_orders(self.shop)
        after = self.env['sale.order'].search_count([
            ('etsy_shop_id', '=', self.shop.id),
        ])
        self.assertEqual(before, after, 'audit mode must not create orders')
        self.assertEqual(result['ingested'], 0)
        self.assertEqual(result['audited'], 3)

    def test_audit_mode_writes_api_log_per_receipt(self):
        """P0-17 retrofit: audit mode writes one etsy.api.log row per
        receipt with source='audit'. (Replaces the P0-16c version which
        asserted _logger.warning calls — that contract was a stopgap.)"""
        syncer = EtsyOrderSyncer(self.env)
        adapter = self._adapter_with_page1()
        before = self.env['etsy.api.log'].search_count([
            ('shop_id', '=', self.shop.id), ('source', '=', 'audit'),
        ])
        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)
        after = self.env['etsy.api.log'].search_count([
            ('shop_id', '=', self.shop.id), ('source', '=', 'audit'),
        ])
        self.assertEqual(after - before, 3)

    def test_audit_mode_advances_cursor_after_batch(self):
        syncer = EtsyOrderSyncer(self.env)
        adapter = self._adapter_with_page1()
        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)
        self.shop.invalidate_recordset(['etsy_last_receipt_sync_at'])
        # max last_modified_tsz in page1 = 1704240000 → 2024-01-03
        self.assertIsNotNone(self.shop.etsy_last_receipt_sync_at)
        self.assertGreaterEqual(
            self.shop.etsy_last_receipt_sync_at,
            datetime(2024, 1, 3, 0, 0, 0),
        )

    def test_audit_plus_api_only_logs_soft_warning(self):
        self.shop.sync_mode = 'api_only'  # nonsensical with audit
        syncer = EtsyOrderSyncer(self.env)
        adapter = MagicMock()
        adapter.fetch_new_orders.return_value = iter([])
        with patch(
            'odoo.addons.etsy_integration.services.etsy_order_syncer._logger',
        ) as mock_logger, patch.object(
            syncer, '_build_adapter', return_value=adapter,
        ):
            syncer.sync_shop_orders(self.shop)
        # OQ4 soft warning should fire before iteration starts
        warnings = [str(c) for c in mock_logger.warning.call_args_list]
        self.assertTrue(
            any('nonsensical' in w or 'audit' in w for w in warnings),
            f'expected soft warning about audit+api_only; got {warnings}',
        )


@tagged('post_install', '-at_install')
class TestEtsyOrderSyncer_PartialFailure(TransactionCase):

    def setUp(self):
        super().setUp()
        self.shop = self.env['etsy.shop'].create({
            'name': 'PartialFailureShop', 'sync_mode': 'api_only',
        })

    def test_cursor_advances_only_through_successful_payloads(self):
        """If ingest raises on payload #2, cursor pins at payload #1's
        last_modified, and payloads #3+ are never attempted."""
        syncer = EtsyOrderSyncer(self.env)
        from odoo.addons.etsy_integration.services.etsy_api_adapter import EtsyApiAdapter
        client = MagicMock()
        page1 = _load('receipts_page1.json')
        page1['next_offset'] = None
        client.get.side_effect = [page1]
        adapter = EtsyApiAdapter(client)

        call_count = {'n': 0}

        def fake_ingest(payload, shop):
            call_count['n'] += 1
            if call_count['n'] == 2:
                raise RuntimeError('simulated ingest failure')
            # Real path for #1: just write a sale.order placeholder.
            # We don't need the full ingest behavior — just succeed.
            from odoo.addons.etsy_integration.services.etsy_order_ingestor import (
                EtsyOrderIngestor,
            )
            return EtsyOrderIngestor(self.env)._creator.process_etsy_payload(
                payload, shop,
            )

        with patch.object(syncer, '_build_adapter', return_value=adapter), patch(
            'odoo.addons.etsy_integration.services.etsy_order_syncer.EtsyOrderIngestor',
        ) as mock_cls:
            mock_cls.return_value.ingest.side_effect = fake_ingest
            syncer.sync_shop_orders(self.shop)

        self.shop.invalidate_recordset(['etsy_last_receipt_sync_at'])
        # Receipt #1 last_modified_tsz = 1704067200 → 2024-01-01
        # Cursor must be at receipt #1 (succeeded), not #2 (failed) or #3.
        self.assertEqual(
            self.shop.etsy_last_receipt_sync_at,
            datetime(2024, 1, 1, 0, 0, 0),
        )
        # Only payload #1 + the failed #2 attempt → call_count == 2; #3 never tried.
        self.assertEqual(call_count['n'], 2)


@tagged('post_install', '-at_install')
class TestEtsyOrderSyncer_CronFilter(TransactionCase):

    def test_cron_method_skips_email_only_shops(self):
        api_shop = self.env['etsy.shop'].create({
            'name': 'ApiOnlyShop', 'sync_mode': 'api_only',
        })
        self.env['etsy.shop'].create({
            'name': 'EmailOnlyShop', 'sync_mode': 'email_only',
        })
        with patch.object(EtsyOrderSyncer, 'sync_shop_orders') as mock_sync:
            self.env['etsy.shop']._cron_sync_orders()
        # Only the api_only shop should be processed
        called_shops = [c.args[0] for c in mock_sync.call_args_list]
        self.assertEqual(len(called_shops), 1)
        self.assertEqual(called_shops[0].id, api_shop.id)
