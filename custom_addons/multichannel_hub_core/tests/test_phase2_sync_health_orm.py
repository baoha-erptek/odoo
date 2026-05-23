"""Phase 2 ORM tests for P0-11 multichannel.sync.health."""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.multichannel_hub_core.models.multichannel_sync_health import (
    MultichannelSyncHealth,
)


@tagged('post_install', '-at_install')
class TestSyncHealthORM(TransactionCase):

    def test_record_creates_row(self):
        row = MultichannelSyncHealth.record(
            self.env, 'etsy', 'order_sync', status='ok', delta_rows=10,
        )
        self.assertTrue(row)
        self.assertEqual(row.metric_key, 'order_sync')
        self.assertEqual(row.status, 'ok')
        self.assertEqual(row.rows_processed, 10)
        self.assertTrue(row.last_run_at)
        self.assertTrue(row.last_success_at)

    def test_record_upserts_existing(self):
        row = MultichannelSyncHealth.record(
            self.env, 'etsy', 'upsert_test', status='ok', delta_rows=5,
        )
        row2 = MultichannelSyncHealth.record(
            self.env, 'etsy', 'upsert_test', status='warning',
            message='slow', delta_rows=3, delta_failed=1,
        )
        self.assertEqual(row.id, row2.id, "second call must upsert, not create")
        self.assertEqual(row2.status, 'warning')
        self.assertEqual(row2.rows_processed, 8)
        self.assertEqual(row2.rows_failed, 1)

    def test_record_with_error_status_sets_last_error_at(self):
        row = MultichannelSyncHealth.record(
            self.env, 'etsy', 'error_test', status='error',
            message='boom', delta_failed=1,
        )
        self.assertEqual(row.status, 'error')
        self.assertTrue(row.last_error_at)
        self.assertEqual(row.last_error_message, 'boom')

    def test_record_missing_channel_returns_empty(self):
        result = MultichannelSyncHealth.record(
            self.env, 'nonexistent_channel_code', 'whatever',
        )
        self.assertFalse(result)
