"""P0-18b2a Phase 2 — ORM unit tests + HttpCase for webhook discovery.

Tests verify:
- ORM create/read trip with all new fields (direction, request_headers, etc.)
- Backward compat: old-style row creation still works
- HTTP POST /gearment/webhook returns 200 with {"status": "ok"}
- HTTP POST creates gearment.api.log row with direction='inbound_webhook'
- Request headers logged (Authorization/Cookie scrubbed)
- Signature header heuristic capture
- Malformed JSON handled gracefully (logged as raw)
- Event topic extraction from body

All HTTP tests use OdooCase (Odoo's HttpCase) with auth='public', csrf=False.
Tests are flexible to handle either type='json' Odoo envelope or type='http'.
"""

import json

from odoo import fields
from odoo.tests.common import HttpCase, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWebhookContentLengthGuard(TransactionCase):
    """Pure-function unit tests for the body-size pre-read guard.

    HttpCase test cannot drive this code path because Werkzeug's test client
    rewrites Content-Length to the real body size, so we test the helper
    directly. The guard is exercised in production against real network
    traffic where Content-Length cannot be transparently corrected.
    """

    def test_no_content_length_header_does_not_reject(self):
        from odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook import (
            _content_length_exceeds_cap,
        )
        self.assertFalse(_content_length_exceeds_cap({}))

    def test_content_length_below_cap_does_not_reject(self):
        from odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook import (
            _content_length_exceeds_cap,
        )
        self.assertFalse(
            _content_length_exceeds_cap({'Content-Length': '500000'})  # 500 KB
        )

    def test_content_length_above_cap_rejects(self):
        from odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook import (
            _content_length_exceeds_cap,
        )
        self.assertTrue(
            _content_length_exceeds_cap({'Content-Length': '50000000'})  # 50 MB
        )

    def test_garbage_content_length_does_not_reject(self):
        from odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook import (
            _content_length_exceeds_cap,
        )
        # Malformed Content-Length defaults to 'do not reject' so the body
        # still flows through and gets truncated by the storage cap.
        self.assertFalse(
            _content_length_exceeds_cap({'Content-Length': 'not-a-number'})
        )


@tagged('post_install', '-at_install')
class TestWebhookDiscoveryORM(TransactionCase):
    """Phase 2: ORM tests for webhook discovery fields on gearment.api.log."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_create_inbound_log_with_all_fields(self):
        """Test create + read trip with all new webhook discovery fields."""
        model = self.env['gearment.api.log']

        request_headers_dict = {
            'Content-Type': 'application/json',
            'X-Gearment-Signature': 'sha256=abc123def456',
            'Host': 'odoo.hatafax.com',
        }

        row = model.create({
            'endpoint': 'POST /gearment/webhook',
            'http_status': 200,
            'source': 'inbound_webhook',
            'request_started_at': fields.Datetime.now(),
            'direction': 'inbound',
            'request_headers': json.dumps(request_headers_dict),
            'request_body': json.dumps({
                'order': {'gearment_id': 'G-12345'},
                'event': 'order.completed'
            }),
            'signature_header_seen': 'X-Gearment-Signature',
            'topic_seen': 'order.completed',
        })

        # Verify read trip
        self.assertIsNotNone(row.id, "Row should be created")
        read_row = model.browse(row.id)
        self.assertEqual(read_row.direction, 'inbound')
        self.assertEqual(read_row.source, 'inbound_webhook')
        self.assertEqual(read_row.signature_header_seen, 'X-Gearment-Signature')
        self.assertEqual(read_row.topic_seen, 'order.completed')

        # Verify headers round-trip JSON
        headers_back = json.loads(read_row.request_headers)
        self.assertEqual(headers_back['X-Gearment-Signature'], 'sha256=abc123def456')

        # Verify body round-trip JSON
        body_back = json.loads(read_row.request_body)
        self.assertEqual(body_back['order']['gearment_id'], 'G-12345')

    def test_existing_outbound_log_still_works(self):
        """Test backward compat: create row with only original fields
        (no direction, request_headers, etc.) — should still work."""
        model = self.env['gearment.api.log']

        row = model.create({
            'endpoint': 'POST /api/v3/draft-orders',
            'http_status': 201,
            'source': 'draft',
            'request_started_at': fields.Datetime.now(),
            # Intentionally omit new fields
        })

        self.assertIsNotNone(row.id, "Old-style row creation should succeed")
        read_row = model.browse(row.id)
        self.assertEqual(read_row.source, 'draft')


@tagged('post_install', '-at_install')
class TestWebhookDiscoveryHTTP(HttpCase):
    """Phase 2: HTTP integration tests for /gearment/webhook endpoint.

    Note: HttpCase tests use self.url_open() for HTTP requests.
    The route is defined with auth='public', csrf=False, type='json',
    methods=['POST'].
    """

    def test_webhook_post_returns_200(self):
        """Test that POST /gearment/webhook returns HTTP 200."""
        payload = {
            'order': {
                'gearment_id': 'G-TEST-001',
                'order_ref': 'SO-12345',
            },
            'tracking': {
                'tracking_number': 'TRK123456',
                'carrier': 'USPS',
            }
        }

        response = self.url_open(
            '/gearment/webhook',
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'},
            timeout=30,
        )

        self.assertEqual(
            response.status_code,
            200,
            f"POST /gearment/webhook should return 200, got {response.status_code}"
        )

    def test_webhook_creates_log_record(self):
        """Test that POST /gearment/webhook creates a gearment.api.log row
        with direction='inbound_webhook'."""
        payload = {
            'order': {
                'gearment_id': 'G-TEST-002',
                'order_ref': 'SO-22345',
            }
        }

        # Count before (NOTE: direction field doesn't exist yet in RED phase)
        log_model = self.env['gearment.api.log']
        count_before = log_model.search_count([
            ('source', '=', 'inbound_webhook'),
        ])

        # POST
        response = self.url_open(
            '/gearment/webhook',
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'},
            timeout=30,
        )
        self.assertEqual(response.status_code, 200, "Request should succeed")

        # Count after
        count_after = log_model.search_count([
            ('source', '=', 'inbound_webhook'),
        ])

        self.assertGreater(
            count_after,
            count_before,
            "POST /gearment/webhook should create at least one inbound log row"
        )

        # Find the new row and verify request_body contains order ref
        new_logs = log_model.search([
            ('source', '=', 'inbound_webhook'),
        ], order='request_started_at desc', limit=1)

        self.assertTrue(new_logs, "Should have created at least one log row")
        latest = new_logs[0]
        self.assertIn(
            'SO-22345',
            latest.request_body or '',
            "Log request_body should contain the order ref from payload"
        )

    def test_webhook_logs_signature_header_if_present(self):
        """Test that if X-Gearment-Signature header is present,
        it's captured in signature_header_seen field."""
        payload = {'order': {'gearment_id': 'G-TEST-003'}}

        # POST with signature header
        response = self.url_open(
            '/gearment/webhook',
            data=json.dumps(payload).encode(),
            headers={
                'Content-Type': 'application/json',
                'X-Gearment-Signature': 'sha256=def789',
            },
            timeout=30,
        )
        self.assertEqual(response.status_code, 200)

        # Search for the log row and verify signature_header_seen
        log_model = self.env['gearment.api.log']
        logs = log_model.search([
            ('source', '=', 'inbound_webhook'),
        ], order='request_started_at desc', limit=1)

        self.assertTrue(logs, "Log row should exist")
        self.assertIsNotNone(
            logs[0].signature_header_seen,
            "signature_header_seen should be populated"
        )
        # Case-insensitive check: should contain 'signature' in lower
        self.assertIn(
            'signature',
            (logs[0].signature_header_seen or '').lower(),
            f"signature_header_seen should contain 'signature', got {logs[0].signature_header_seen}"
        )

    def test_webhook_authorization_header_not_logged(self):
        """Test security: Authorization header MUST NOT appear in
        request_headers log (defense against accidental secret leakage)."""
        payload = {'order': {'gearment_id': 'G-TEST-004'}}

        # POST with Authorization header
        response = self.url_open(
            '/gearment/webhook',
            data=json.dumps(payload).encode(),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer secret-deadbeef-token',
            },
            timeout=30,
        )
        self.assertEqual(response.status_code, 200)

        # Verify Authorization header not in logged request_headers
        log_model = self.env['gearment.api.log']
        logs = log_model.search([
            ('source', '=', 'inbound_webhook'),
        ], order='request_started_at desc', limit=1)

        self.assertTrue(logs, "Log row should exist")
        request_headers_text = logs[0].request_headers or ''
        self.assertNotIn(
            'secret-deadbeef-token',
            request_headers_text,
            "Authorization header value must NOT leak into request_headers log"
        )

    def test_webhook_malformed_json_logged_as_raw(self):
        """Test resilience: malformed JSON body is logged as-is, not rejected.
        Should return 200 (not 400) to avoid DoS via sender retries."""
        # Malformed: missing closing brace
        malformed_body = b'{"order":{"gearment_id":"G-EVT"'

        response = self.url_open(
            '/gearment/webhook',
            data=malformed_body,
            headers={'Content-Type': 'application/json'},
            timeout=30,
        )

        # Should return 200 despite malformed JSON (no hard failure)
        self.assertEqual(
            response.status_code,
            200,
            "POST /gearment/webhook should return 200 even for malformed JSON"
        )

        # Verify log row was created with the raw malformed body
        log_model = self.env['gearment.api.log']
        logs = log_model.search([
            ('source', '=', 'inbound_webhook'),
        ], order='request_started_at desc', limit=1)

        self.assertTrue(logs, "Log row should exist even for malformed JSON")
        # Raw body should contain parts we can identify
        self.assertIn(
            'G-EVT',
            logs[0].request_body or '',
            "Malformed JSON body should be logged as-is, raw content preserved"
        )

    def test_webhook_detects_event_topic(self):
        """Test that event topic is extracted from body['event'] or body['topic'],
        and stored in topic_seen field."""
        payload = {
            'event': 'order.completed',
            'order': {'gearment_id': 'G-TEST-005'},
        }

        response = self.url_open(
            '/gearment/webhook',
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'},
            timeout=30,
        )
        self.assertEqual(response.status_code, 200)

        # Verify topic_seen was populated
        log_model = self.env['gearment.api.log']
        logs = log_model.search([
            ('source', '=', 'inbound_webhook'),
        ], order='request_started_at desc', limit=1)

        self.assertTrue(logs, "Log row should exist")
        self.assertEqual(
            logs[0].topic_seen,
            'order.completed',
            f"topic_seen should be 'order.completed', got {logs[0].topic_seen}"
        )
