"""P0-18b2c Phase 1 — DB schema verification for dispatcher slice.

Tests cover:
- gearment.api.log: business_handled, business_summary fields exist
- sale.order.fulfillment: tracking_url field exists
- gearment.api.log: UNIQUE partial index on (nonce_value, request_timestamp)
- UNIQUE constraint blocks concurrent same-(nonce, ts) inserts
- Partial WHERE clause keeps outbound rows free to insert with empty nonce
"""
import psycopg2

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWebhookDispatcherDB(TransactionCase):
    """Phase 1: DB-schema verification for P0-18b2c."""

    def test_business_handled_column_exists(self):
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'gearment_api_log'
              AND column_name IN ('business_handled', 'business_summary')
        """)
        cols = {row[0] for row in self.env.cr.fetchall()}
        self.assertEqual(cols, {'business_handled', 'business_summary'})

    def test_tracking_url_column_on_fulfillment(self):
        self.env.cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'sale_order_fulfillment'
              AND column_name = 'tracking_url'
        """)
        self.assertTrue(self.env.cr.fetchone(),
                         "tracking_url column missing on sale_order_fulfillment")

    def test_unique_partial_index_exists(self):
        self.env.cr.execute("""
            SELECT indexname, indexdef FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'gearment_api_log'
              AND indexname = 'gearment_api_log_nonce_ts_unique'
        """)
        row = self.env.cr.fetchone()
        self.assertIsNotNone(row, "UNIQUE partial index missing")
        indexdef = row[1].lower()
        self.assertIn('unique', indexdef)
        self.assertIn('nonce_value', indexdef)
        self.assertIn('request_timestamp', indexdef)
        self.assertIn('where', indexdef, "Index must be PARTIAL (WHERE clause)")

    def test_unique_constraint_blocks_duplicate_insert(self):
        """Two concurrent inserts with same (nonce, ts) → second raises."""
        log = self.env['gearment.api.log']
        nonce = 'p0_18b2c_unique_test_nonce'
        ts = 1777735900
        log.sudo().create({
            'endpoint': 'POST /test',
            'source': 'inbound_webhook',
            'direction': 'inbound',
            'nonce_value': nonce,
            'request_timestamp': ts,
            'request_started_at': fields.Datetime.now(),
            'signature_verified': True,  # partial index only enforces verified rows
        })
        # Use a savepoint so the IntegrityError doesn't poison the outer
        # test cursor. Catch the low-level psycopg2 error directly.
        with self.assertRaises(psycopg2.IntegrityError):
            with self.env.cr.savepoint():
                log.sudo().create({
                    'endpoint': 'POST /test',
                    'source': 'inbound_webhook',
                    'direction': 'inbound',
                    'nonce_value': nonce,
                    'request_timestamp': ts,
                    'request_started_at': fields.Datetime.now(),
                    'signature_verified': True,
                })

    def test_null_nonce_allows_multiple_outbound_rows(self):
        """Partial index excludes empty nonce; outbound rows can repeat."""
        log = self.env['gearment.api.log']
        for _i in range(3):
            log.sudo().create({
                'endpoint': 'GET /api/v3/catalog',
                'source': 'probe',
                'direction': 'outbound',
                'nonce_value': '',
                'request_timestamp': 0,
                'request_started_at': fields.Datetime.now(),
            })
        rows = log.sudo().search([
            ('endpoint', '=', 'GET /api/v3/catalog'),
            ('direction', '=', 'outbound'),
        ])
        self.assertGreaterEqual(len(rows), 3)

    def test_unverified_rows_with_same_nonce_allowed(self):
        """Partial WHERE clause requires signature_verified=True;
        verify-failure rows with matching (nonce, ts) must coexist."""
        log = self.env['gearment.api.log']
        nonce = 'p0_18b2c_unverified_test'
        ts = 1777735901
        for _i in range(2):
            log.sudo().create({
                'endpoint': 'POST /gearment/webhook',
                'source': 'inbound_webhook',
                'direction': 'inbound',
                'nonce_value': nonce,
                'request_timestamp': ts,
                'request_started_at': fields.Datetime.now(),
                'signature_verified': False,
                'verify_failure_reason': 'signature_mismatch',
            })
        rows = log.sudo().search([
            ('nonce_value', '=', nonce),
            ('signature_verified', '=', False),
        ])
        self.assertGreaterEqual(len(rows), 2)
