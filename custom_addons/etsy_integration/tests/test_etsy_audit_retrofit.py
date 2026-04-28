"""P0-17 Phase 2 — ORM tests for EtsyOrderSyncer audit retrofit.

Tests the `_audit_log` retrofit that writes etsy.api.log rows during
audit-mode syncs, including PII scrubbing and per-receipt logging.

This file tests the integration between the syncer and the new model.

Reference: Master Plan 006, P0-17 planner OQ2, OQ5, OQ7.
"""

import json
import os
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.etsy_integration.services.etsy_order_syncer import EtsyOrderSyncer


_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'etsy_v3')


def _load(name):
    """Load JSON fixture."""
    with open(os.path.join(_FIXTURE_DIR, name)) as f:
        return json.load(f)


@tagged('post_install', '-at_install')
class TestEtsyOrderSyncer_AuditLogPersists(TransactionCase):
    """ORM tests for syncer audit log persistence to etsy.api.log."""

    @classmethod
    def setUpClass(cls):
        """Set up test shop."""
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def setUp(self):
        """Create a fresh shop for each test."""
        super().setUp()
        self.shop = self.env['etsy.shop'].create({
            'name': 'Audit Test Shop',
            'sync_mode': 'api_only',
        })

    def test_audit_run_creates_one_api_log_per_receipt(self):
        """Syncer audit mode creates one etsy.api.log row per receipt."""
        self.shop.sync_audit_mode = True

        syncer = EtsyOrderSyncer(self.env)

        # Mock the adapter to return the fixture with 3 receipts
        adapter = MagicMock()
        fixture_data = _load('receipts_page1.json')
        # Simulate paginated adapter behavior
        adapter.fetch_new_orders.return_value = iter([fixture_data])

        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)

        # Verify 3 audit logs were created (one per receipt in fixture)
        audit_logs = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
            ('source', '=', 'audit'),
        ])

        self.assertEqual(
            len(audit_logs), 3,
            f"Expected 3 audit logs for 3 receipts, got {len(audit_logs)}"
        )

    def test_audit_log_endpoint_field_set(self):
        """Audit logs have endpoint field populated."""
        self.shop.sync_audit_mode = True

        syncer = EtsyOrderSyncer(self.env)
        adapter = MagicMock()
        adapter.fetch_new_orders.return_value = iter([_load('receipts_page1.json')])

        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)

        audit_logs = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
            ('source', '=', 'audit'),
        ])

        for log in audit_logs:
            self.assertIsNotNone(
                log.endpoint,
                f"Log {log.id} should have endpoint populated"
            )
            self.assertTrue(
                len(log.endpoint) > 0,
                f"Log {log.id} endpoint should not be empty"
            )

    def test_audit_log_pii_scrubbed_from_response_summary(self):
        """PII is not leaked in response_summary field."""
        self.shop.sync_audit_mode = True

        syncer = EtsyOrderSyncer(self.env)
        adapter = MagicMock()
        adapter.fetch_new_orders.return_value = iter([_load('receipts_page1.json')])

        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)

        audit_logs = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
            ('source', '=', 'audit'),
        ])

        # PII fragments to check
        pii_fragments = [
            'alice@example.com', 'bob@example.com', 'charlie@example.ca',
            'Alice Buyer', 'Bob Builder', 'Charlie Customer',
            '123 Main St', '456 Oak Ave', '789 Maple Rd',
            'Please hurry!',  # message_from_buyer
        ]

        for log in audit_logs:
            response_summary = log.response_summary or ''
            for pii in pii_fragments:
                self.assertNotIn(
                    pii, response_summary,
                    f"PII '{pii}' found in log {log.id} response_summary: "
                    f"{response_summary[:100]}"
                )

    def test_audit_log_includes_receipt_id_and_amount(self):
        """Audit log response_summary includes receipt ID and amount tokens."""
        self.shop.sync_audit_mode = True

        syncer = EtsyOrderSyncer(self.env)
        adapter = MagicMock()
        adapter.fetch_new_orders.return_value = iter([_load('receipts_page1.json')])

        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)

        audit_logs = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
            ('source', '=', 'audit'),
        ], order='id')

        # Fixture has receipt IDs: 1001, 1002, 1003 with amounts 110, 55, 75 USD
        expected_receipt_ids = ['1001', '1002', '1003']
        expected_amounts = ['110', '55', '75']

        for i, log in enumerate(audit_logs):
            response_summary = log.response_summary or ''
            self.assertTrue(
                len(response_summary) > 0,
                f"Log {log.id} should have non-empty response_summary"
            )
            # At least one receipt ID should be mentioned
            self.assertTrue(
                any(receipt_id in response_summary
                    for receipt_id in expected_receipt_ids),
                f"No receipt ID found in log {log.id} response_summary: "
                f"{response_summary}"
            )
            # Currency code should be present
            self.assertIn(
                'USD', response_summary,
                f"Currency code 'USD' not found in log {log.id} "
                f"response_summary: {response_summary}"
            )

    def test_no_audit_rows_in_normal_sync(self):
        """Normal (non-audit) sync does not create audit-source logs."""
        # Shop with audit mode OFF
        self.shop.sync_audit_mode = False

        syncer = EtsyOrderSyncer(self.env)
        adapter = MagicMock()
        adapter.fetch_new_orders.return_value = iter([_load('receipts_page1.json')])

        with patch.object(syncer, '_build_adapter', return_value=adapter):
            syncer.sync_shop_orders(self.shop)

        # Verify NO audit-source logs were created
        audit_logs = self.env['etsy.api.log'].search([
            ('shop_id', '=', self.shop.id),
            ('source', '=', 'audit'),
        ])

        self.assertEqual(
            len(audit_logs), 0,
            f"Normal sync should not create audit logs, "
            f"but found {len(audit_logs)}"
        )
