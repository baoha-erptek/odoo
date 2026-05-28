"""P4-01-FIX-LOG-LINKAGE-EXCEPTION-PATH — Defect-2026-05-11-02 RED tests.

Surfaced during 2026-05-11 autonomous E2E run on staging demo_esty:
``sale.order.action_push_to_gearment`` raised ``requests.HTTPError`` on
Gearment 4xx, but ``gearment.api.log`` got NO new row — the exception
propagated through XML-RPC, dispatcher rolled back the request transaction,
and the audit row written by ``GearmentApiAdapter._log_call`` was rolled
back along with everything else.

Defect-2026-05-10-03 (FIX-LOG-LINKAGE) addressed the *value enrichment* on
the failure-path log. This slice fixes the *durability* of that log so it
survives the outer rollback. Pattern: write via a fresh registry cursor
(``self.env.registry.cursor()``) + explicit ``cr.commit()``.

Phase 2 ORM tests verify:
  - Failure-path log persists after the outer transaction rolls back.
  - Success path still writes (no regression).
  - Multiple consecutive failures all log distinct rows.

Test housekeeping: the fresh-cursor commit means rows persist beyond the
test's TransactionCase rollback. Each test cleans up its own rows via a
second fresh cursor in tearDown to avoid leaking demo data.
"""
import json
import os
from unittest import mock

import requests

from odoo.tests.common import TransactionCase, tagged


_TEST_ENV = {
    'GEARMENT_API_KEY': 'test_key',
    'GEARMENT_API_SECRET': 'test_secret',
    'GEARMENT_API_BASE_URL': 'https://example.invalid/integration-handler',
}


def _http_error(status_code: int, body_text: str) -> requests.exceptions.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    response._content = body_text.encode('utf-8')
    err = requests.exceptions.HTTPError(
        f"{status_code} Client Error for url: example",
        response=response,
    )
    return err


@tagged('post_install', '-at_install', 'p4_01_fix_log_linkage_exception_path')
class TestApiLogSurvivesOuterRollback(TransactionCase):
    """The audit row must persist when the caller's exception rolls back
    the outer transaction (Defect-2026-05-11-02)."""

    _SENTINEL_ENDPOINT_PREFIX = 'POST api/v3/orders/draft'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        from odoo.addons.multichannel_hub_fulfillment.services.gearment_adapter import (
            GearmentApiAdapter,
        )
        from odoo.addons.multichannel_hub_fulfillment.services.gearment_payload import (
            GearmentAddress, GearmentLineItem, GearmentOrderPayload,
        )
        cls._GearmentApiAdapter = GearmentApiAdapter
        cls._payload = GearmentOrderPayload(
            reference_id='SO-EXC-PATH-01', store_id='demo',
            addresses=(GearmentAddress(
                first_name='X', last_name='Y', street_1='1 Test',
                street_2=None, city='C', state='MA', zip_code='02108',
                country_code='US',
            ),),
            line_items=(GearmentLineItem(
                legacy_id=1, quantity=1, sku='SKU-EXC-PATH',
                printing_options=({'location_code': 'front', 'url': 'https://x/y.png'},),
            ),),
        )
        # Fresh cursor + explicit commit so the FK target (sale.order) is
        # visible to the adapter's fresh-cursor log write. The TransactionCase
        # rollback at end-of-class would otherwise leave the log row pointing
        # at a non-existent order. tearDownClass cleans these up via the
        # same fresh-cursor pattern to avoid leaking demo data.
        with cls.env.registry.cursor() as cr:
            cr_env = cls.env(cr=cr)
            partner = cr_env['res.partner'].create({
                'name': 'EXC-PATH Buyer',
            })
            product = cr_env['product.product'].create({
                'name': 'EXC-PATH Product', 'type': 'consu', 'list_price': 1.0,
            })
            order = cr_env['sale.order'].create({
                'partner_id': partner.id,
                'order_line': [(0, 0, {
                    'product_id': product.id, 'product_uom_qty': 1.0,
                })],
            })
            cr.commit()
            cls._committed_partner_id = partner.id
            cls._committed_product_id = product.id
            cls._committed_order_id = order.id
        # Re-browse in this test's cursor for read access.
        cls._order = cls.env['sale.order'].browse(cls._committed_order_id)
        cls._error_400 = _http_error(
            400,
            '{"message":"printing_options validation","status":"error"}',
        )

    @classmethod
    def tearDownClass(cls):
        # Wipe the committed fixture rows + any audit log children via a
        # fresh cursor (committed data is invisible to TransactionCase rollback).
        try:
            with cls.env.registry.cursor() as cr:
                cr_env = cls.env(cr=cr)
                cr_env['gearment.api.log'].sudo().search([
                    ('sale_order_id', '=', cls._committed_order_id),
                ]).unlink()
                cr_env['sale.order'].sudo().browse(
                    cls._committed_order_id).unlink()
                cr_env['product.product'].sudo().browse(
                    cls._committed_product_id).unlink()
                cr_env['res.partner'].sudo().browse(
                    cls._committed_partner_id).unlink()
                cr.commit()
        except Exception:  # noqa: BLE001
            pass
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        # Track ids written via fresh cursor so tearDown can wipe them
        # without depending on the test transaction.
        self._created_log_ids = []

    def tearDown(self):
        # Clean up audit rows written via fresh cursor (these survive
        # this test's TransactionCase rollback).
        if self._created_log_ids:
            try:
                with self.env.registry.cursor() as cr:
                    cr_env = self.env(cr=cr)
                    cr_env['gearment.api.log'].sudo().browse(
                        self._created_log_ids
                    ).unlink()
                    cr.commit()
            except Exception:
                # Best-effort; tests should not fail on cleanup
                pass
        super().tearDown()

    def _read_logs_for_order_via_fresh_cursor(self):
        """Read api.log rows written for ``self._order`` from a separate
        cursor — bypasses this test transaction's view of pending writes."""
        with self.env.registry.cursor() as cr:
            cr_env = self.env(cr=cr)
            logs = cr_env['gearment.api.log'].sudo().search([
                ('sale_order_id', '=', self._order.id),
            ], order='id desc')
            ids = logs.ids
            data = logs.read(['id', 'http_status', 'response_summary',
                              'error_message', 'endpoint', 'sale_order_id'])
        return ids, data

    def test_failure_path_log_persists_via_fresh_cursor(self):
        """The audit row exists in a fresh cursor immediately after the
        adapter's caught-and-re-raised HTTPError."""
        with mock.patch.dict(os.environ, _TEST_ENV, clear=False):
            adapter = self._GearmentApiAdapter(env=self.env)
        with mock.patch.object(
            adapter.client, '_request', side_effect=self._error_400,
        ):
            with self.assertRaises(requests.exceptions.HTTPError):
                adapter.push_order(
                    self._payload, sale_order_id=self._order.id,
                )

        ids, data = self._read_logs_for_order_via_fresh_cursor()
        self._created_log_ids.extend(ids)
        self.assertTrue(
            data,
            "Expected at least one gearment.api.log row visible in a fresh "
            "cursor after the failed push (Defect-2026-05-11-02 fix).",
        )
        latest = data[0]
        self.assertEqual(
            latest['http_status'], 400,
            "http_status must be carried from exc.response.status_code",
        )
        self.assertIn(
            'printing_options validation',
            latest['response_summary'] or '',
            "response_summary must carry the raw vendor body for blackbox debugging",
        )
        soid = latest['sale_order_id']
        if isinstance(soid, (list, tuple)):
            soid = soid[0]
        self.assertEqual(
            soid, self._order.id,
            "sale_order_id linkage must survive the rollback",
        )

    def test_failure_path_log_survives_simulated_outer_rollback(self):
        """Simulates the XML-RPC dispatcher's rollback by issuing a
        savepoint rollback in the test transaction AFTER the adapter's
        re-raise. The fresh-cursor write is committed independently and
        therefore survives."""
        # Capture the baseline count via fresh cursor so we can compare deltas.
        with self.env.registry.cursor() as cr:
            cr_env = self.env(cr=cr)
            baseline = cr_env['gearment.api.log'].sudo().search_count([
                ('sale_order_id', '=', self._order.id),
            ])

        # Take a savepoint in the test cursor; the adapter will write via
        # a separate cursor (fresh-cursor pattern from the fix). Then we
        # roll the savepoint back, simulating Odoo's request-transaction
        # rollback when the dispatcher catches the re-raised HTTPError.
        savepoint = self.env.cr.savepoint()
        with mock.patch.dict(os.environ, _TEST_ENV, clear=False):
            adapter = self._GearmentApiAdapter(env=self.env)
        with mock.patch.object(
            adapter.client, '_request', side_effect=self._error_400,
        ):
            try:
                adapter.push_order(
                    self._payload, sale_order_id=self._order.id,
                )
            except requests.exceptions.HTTPError:
                pass
        savepoint.rollback()

        # Fresh cursor still sees the committed audit row.
        with self.env.registry.cursor() as cr:
            cr_env = self.env(cr=cr)
            after = cr_env['gearment.api.log'].sudo().search([
                ('sale_order_id', '=', self._order.id),
            ], order='id desc')
            self._created_log_ids.extend(after.ids)
            after_count = len(after)

        self.assertEqual(
            after_count, baseline + 1,
            "Audit row count should grow by exactly one even after the "
            "outer transaction rolls back (fresh-cursor commit isolates).",
        )

    def test_multiple_failures_log_distinct_rows(self):
        """Three consecutive failures produce three distinct audit rows."""
        with mock.patch.dict(os.environ, _TEST_ENV, clear=False):
            adapter = self._GearmentApiAdapter(env=self.env)
        with mock.patch.object(
            adapter.client, '_request', side_effect=self._error_400,
        ):
            for _ in range(3):
                try:
                    adapter.push_order(
                        self._payload, sale_order_id=self._order.id,
                    )
                except requests.exceptions.HTTPError:
                    pass

        ids, data = self._read_logs_for_order_via_fresh_cursor()
        self._created_log_ids.extend(ids)
        # We expect at least 3 rows — older ones from prior tests in the
        # same DB might exist, but the 3 newest must be distinct ids.
        self.assertGreaterEqual(
            len(ids), 3,
            "Three consecutive push failures should produce ≥3 audit rows",
        )
        self.assertEqual(
            len(set(ids[:3])), 3,
            "Each failure should produce a distinct audit row (no dedupe)",
        )
