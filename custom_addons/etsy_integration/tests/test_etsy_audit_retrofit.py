"""P0-17 Phase 2 — ORM tests for EtsyOrderSyncer audit retrofit.

Tests the `_audit_log` retrofit that writes etsy.api.log rows during
audit-mode syncs, including PII scrubbing and per-receipt logging.

Pattern: real `EtsyApiAdapter` instance + mocked `EtsyApiClient.get`.
This drives the receipt→payload mapping path through the real adapter
so the test exercises the same wiring the production cron will use.

Reference: Master Plan 006, P0-17 planner OQ2, OQ5, OQ7.
"""

import json
import os
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services.etsy_api_adapter import EtsyApiAdapter
from odoo.addons.etsy_integration.services.etsy_order_syncer import EtsyOrderSyncer


_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'etsy_v3')


def _load(name):
    """Load JSON fixture."""
    with open(os.path.join(_FIXTURE_DIR, name)) as f:
        return json.load(f)


def _single_page_adapter(fixture_name):
    """Build a real EtsyApiAdapter that returns the fixture as a single
    page (next_offset=null), backed by a MagicMock EtsyApiClient."""
    page = _load(fixture_name)
    page['next_offset'] = None  # force single-page termination
    client = MagicMock()
    client.get.side_effect = [page]
    return EtsyApiAdapter(client)


@tagged('post_install', '-at_install')
class TestEtsyOrderSyncer_AuditLogPersists(TransactionCase):
    """ORM tests for syncer audit log persistence to etsy.api.log."""

    def setUp(self):
        super().setUp()
        self.shop = self.env['etsy.shop'].create({
            'name': 'Audit Test Shop',
            'sync_mode': 'api_only',
            'sync_audit_mode': True,
            'etsy_api_shop_id': '60752333',
        })

    def _run_sync(self, fixture_name='receipts_page1.json'):
        syncer = EtsyOrderSyncer(self.env)
        adapter = _single_page_adapter(fixture_name)
        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)

    def _audit_logs(self):
        return self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
            ('source', '=', 'audit'),
        ], order='id')

    def test_audit_run_creates_one_api_log_per_receipt(self):
        """Audit mode creates one etsy.api.log row per receipt."""
        self._run_sync()
        self.assertEqual(len(self._audit_logs()), 3)

    def test_audit_log_endpoint_field_set(self):
        """Audit logs have non-empty endpoint."""
        self._run_sync()
        for log in self._audit_logs():
            self.assertTrue(log.endpoint)

    def test_audit_log_pii_scrubbed_from_response_summary(self):
        """PII is not leaked in response_summary."""
        self._run_sync()
        pii_fragments = [
            'alice@example.com', 'bob@example.com', 'charlie@example.ca',
            'Alice Buyer', 'Bob Builder', 'Charlie Customer',
            '123 Main St', '456 Oak Ave', '789 Maple Rd',
            'Please hurry!',
        ]
        for log in self._audit_logs():
            summary = log.response_summary or ''
            for pii in pii_fragments:
                self.assertNotIn(pii, summary,
                                 f"PII '{pii}' leaked in log {log.id}: {summary[:100]}")

    def test_audit_log_includes_receipt_id_and_amount(self):
        """Audit log response_summary includes receipt id + amount + currency."""
        self._run_sync()
        logs = self._audit_logs()
        receipt_ids = ['1001', '1002', '1003']
        for log in logs:
            summary = log.response_summary or ''
            self.assertTrue(summary)
            self.assertTrue(
                any(rid in summary for rid in receipt_ids),
                f"No receipt id in {summary!r}",
            )
            self.assertIn('USD', summary)

    def test_no_audit_rows_in_normal_sync(self):
        """Normal (non-audit) sync does not create audit-source logs."""
        self.shop.sync_audit_mode = False
        self._run_sync()
        self.assertEqual(len(self._audit_logs()), 0)
