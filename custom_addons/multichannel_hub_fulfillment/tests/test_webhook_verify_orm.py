"""P0-18b2b Phase 2 — Webhook HMAC verification + replay defense tests.

Tests verify:
- HMAC-SHA256 signature verification via _verify_signature helper
- Captured probe signature validates correctly
- Invalid signatures rejected with proper failure reasons
- Missing required headers rejected
- Client key validation (X-Connect-Client-Key vs GEARMENT_API_KEY)
- Timestamp validation (within ±300/+60 second window)
- Nonce deduplication (reject replays within 10 min window)
- HTTP 401 on verification failure
- Audit log fields populated (nonce_value, request_timestamp, signature_verified, verify_failure_reason)
- Request body truncation to 256 chars on verification failure
- Topic extraction from body['type'] key

All HTTP tests use HttpCase with auth='public', csrf=False.
Unit tests import _verify_signature directly and test pure verification logic.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from unittest import mock

from odoo import fields
from odoo.tests.common import HttpCase, TransactionCase, tagged


# Test vectors. Body / nonce / timestamp are taken verbatim from the real
# Gearment dashboard probe (gearment.api.log row 3 per findings.md) — they
# are not secret. The CLIENT_KEY and SECRET are SYNTHETIC, generated only
# for these tests, so the real `.env` Gearment credentials never land in
# source control. The CAPTURED_SIGNATURE was recomputed against the
# synthetic SECRET so this whole vector is internally consistent and runs
# with no live secret material. The original real-Gearment signature
# (nNqkvTj5v9Qg4rwaKYhlAjQS-3N_gMc-whSGp-VypVE=) was verified locally
# during P0-18b2a debugging — see specs/004-fulfillment-routing/findings.md.
CAPTURED_BODY = b'{"order":{"gearment_id":"string","gearment_name":"string","reference":"string","status":"shipped","vendor_id":"string"},"tracking":{"company":"string","number":"string","url":"string"},"type":"order_completed"}'
CAPTURED_NONCE = 'j2jXmLHWOJtJuQ=='
CAPTURED_TIMESTAMP = '1777735761'
CAPTURED_CLIENT_KEY = 'TEST_KEY_DO_NOT_USE'
CAPTURED_SECRET = 'TEST_SECRET_DO_NOT_USE_IN_PROD_64chars_padded_xxxxxxxxxxxxxxxxxx'
CAPTURED_SIGNATURE = 'huUS5udBX-bu7UIhc0Bd3Gug0vJO12_k0dp-oEYB-Lw='

# URL path for signing
_WEBHOOK_PATH = '/gearment/webhook'


def _compute_signature(nonce: str, timestamp: str, body: bytes, secret: str,
                        url_path: str = _WEBHOOK_PATH) -> str:
    """Helper to compute HMAC-SHA256 signature matching Gearment scheme.

    Returns base64url-encoded signature with '=' padding.
    """
    body_b64 = base64.urlsafe_b64encode(body).decode('ascii')
    signing_string = url_path + nonce + timestamp + body_b64
    digest = hmac.new(
        secret.encode('utf-8'),
        signing_string.encode('utf-8'),
        hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).decode('ascii')


@tagged('post_install', '-at_install')
class TestVerifySignatureUnit(TransactionCase):
    """Pure helper unit tests for _verify_signature verification logic.

    These tests exercise the verification function directly without HTTP,
    using mock.patch for environment variables and time.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _import_verifier(self):
        """Lazy import to avoid collection-time failures if function doesn't exist yet.

        During RED phase, import failure appears as test failure (AssertionError: expected function)
        rather than ImportError at module load time.
        """
        try:
            from odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook import \
                _verify_signature
            return _verify_signature
        except ImportError as e:
            self.fail(f"_verify_signature not found; expected in GREEN phase: {e}")

    def test_captured_probe_signature_verifies_true(self):
        """Test that captured probe signature verifies successfully.

        Uses CAPTURED_* values + now_provider pinned to captured timestamp.
        Should return (True, '').
        """
        _verify_signature = self._import_verifier()

        headers = {
            'X-Connect-Signature': CAPTURED_SIGNATURE,
            'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
            'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertTrue(is_valid, f"Captured signature should verify; got reason={reason}")
        self.assertEqual(reason, '', f"Success should have empty reason; got {reason}")

    def test_invalid_signature_rejected(self):
        """Test that flipping one char of signature causes rejection."""
        _verify_signature = self._import_verifier()

        # Flip first char of signature
        bad_sig = 'X' + CAPTURED_SIGNATURE[1:]

        headers = {
            'X-Connect-Signature': bad_sig,
            'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
            'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertFalse(is_valid, "Invalid signature should not verify")
        self.assertEqual(reason, 'signature_mismatch', f"Expected 'signature_mismatch'; got {reason}")

    def test_missing_signature_header(self):
        """Test that missing X-Connect-Signature returns 'missing_signature_header'."""
        _verify_signature = self._import_verifier()

        headers = {
            'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
            'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertFalse(is_valid)
        self.assertEqual(reason, 'missing_signature_header')

    def test_missing_timestamp_header(self):
        """Test that missing X-Connect-Timestamp returns 'missing_timestamp_header'."""
        _verify_signature = self._import_verifier()

        headers = {
            'X-Connect-Signature': CAPTURED_SIGNATURE,
            'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertFalse(is_valid)
        self.assertEqual(reason, 'missing_timestamp_header')

    def test_missing_nonce_header(self):
        """Test that missing X-Connect-Nonce returns 'missing_nonce_header'."""
        _verify_signature = self._import_verifier()

        headers = {
            'X-Connect-Signature': CAPTURED_SIGNATURE,
            'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
            'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertFalse(is_valid)
        self.assertEqual(reason, 'missing_nonce_header')

    def test_missing_client_key_header(self):
        """Test that missing X-Connect-Client-Key returns 'missing_client_key_header'."""
        _verify_signature = self._import_verifier()

        headers = {
            'X-Connect-Signature': CAPTURED_SIGNATURE,
            'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertFalse(is_valid)
        self.assertEqual(reason, 'missing_client_key_header')

    def test_wrong_client_key(self):
        """Test that client key mismatch returns 'client_key_mismatch'."""
        _verify_signature = self._import_verifier()

        headers = {
            'X-Connect-Signature': CAPTURED_SIGNATURE,
            'X-Connect-Client-Key': 'WRONG_KEY',
            'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertFalse(is_valid)
        self.assertEqual(reason, 'client_key_mismatch')

    def test_timestamp_too_old(self):
        """Test that timestamp outside window (too old) returns 'timestamp_outside_window'."""
        _verify_signature = self._import_verifier()

        # Use timestamp 600 seconds (10 min) in the past; now is CAPTURED_TIMESTAMP
        old_ts = str(int(CAPTURED_TIMESTAMP) - 600)

        # Recompute signature for the old timestamp
        sig = _compute_signature(CAPTURED_NONCE, old_ts, CAPTURED_BODY, CAPTURED_SECRET)

        headers = {
            'X-Connect-Signature': sig,
            'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
            'X-Connect-Timestamp': old_ts,
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertFalse(is_valid)
        self.assertEqual(reason, 'timestamp_outside_window')

    def test_timestamp_too_far_future(self):
        """Test that timestamp too far in future (>60s skew) returns 'timestamp_outside_window'."""
        _verify_signature = self._import_verifier()

        # Use timestamp 120 seconds in the future; now is CAPTURED_TIMESTAMP; window is +60s
        future_ts = str(int(CAPTURED_TIMESTAMP) + 120)

        # Recompute signature for the future timestamp
        sig = _compute_signature(CAPTURED_NONCE, future_ts, CAPTURED_BODY, CAPTURED_SECRET)

        headers = {
            'X-Connect-Signature': sig,
            'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
            'X-Connect-Timestamp': future_ts,
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertFalse(is_valid)
        self.assertEqual(reason, 'timestamp_outside_window')

    def test_timestamp_within_window_skew_60s(self):
        """Test that timestamp at boundary (now + 60s skew) verifies successfully."""
        _verify_signature = self._import_verifier()

        # Use timestamp exactly 60 seconds in the future (boundary of acceptable window)
        future_ts = str(int(CAPTURED_TIMESTAMP) + 60)

        # Recompute signature for the boundary timestamp
        sig = _compute_signature(CAPTURED_NONCE, future_ts, CAPTURED_BODY, CAPTURED_SECRET)

        headers = {
            'X-Connect-Signature': sig,
            'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
            'X-Connect-Timestamp': future_ts,
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertTrue(is_valid, f"Timestamp at +60s boundary should be accepted; got reason={reason}")
        self.assertEqual(reason, '')

    def test_timestamp_invalid_format(self):
        """Test that non-numeric timestamp returns 'timestamp_invalid'."""
        _verify_signature = self._import_verifier()

        headers = {
            'X-Connect-Signature': CAPTURED_SIGNATURE,
            'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
            'X-Connect-Timestamp': 'not-a-number',
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertFalse(is_valid)
        self.assertEqual(reason, 'timestamp_invalid')

    def test_duplicate_nonce_rejected(self):
        """Test that duplicate nonce (seen in last 10 min) is rejected.

        Pre-creates a gearment.api.log row with same nonce + timestamp;
        second verify call should return 'nonce_replay'.
        """
        _verify_signature = self._import_verifier()

        # Pre-create a log row with this nonce to simulate prior request
        self.env['gearment.api.log'].sudo().create({
            'endpoint': 'POST /gearment/webhook',
            'http_status': 200,
            'source': 'inbound_webhook',
            'direction': 'inbound',
            'request_started_at': fields.Datetime.now(),
            'nonce_value': CAPTURED_NONCE,
            'request_timestamp': int(CAPTURED_TIMESTAMP),
        })

        headers = {
            'X-Connect-Signature': CAPTURED_SIGNATURE,
            'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
            'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertFalse(is_valid)
        self.assertEqual(reason, 'nonce_replay')

    def test_old_nonce_outside_dedup_window_does_not_block(self):
        """Test that nonce outside the 10-min dedup window is not blocked.

        Pre-creates a log row with same nonce but request_started_at
        > 10 min in the past; second verify call should succeed.
        """
        _verify_signature = self._import_verifier()

        # Pre-create a log row with this nonce, but 700 seconds (11+ min) ago
        now_dt = fields.Datetime.now()
        old_time = fields.Datetime.subtract(now_dt, timedelta(seconds=700))

        self.env['gearment.api.log'].sudo().create({
            'endpoint': 'POST /gearment/webhook',
            'http_status': 200,
            'source': 'inbound_webhook',
            'direction': 'inbound',
            'request_started_at': old_time,
            'nonce_value': CAPTURED_NONCE,
            'request_timestamp': int(CAPTURED_TIMESTAMP) - 700,
        })

        headers = {
            'X-Connect-Signature': CAPTURED_SIGNATURE,
            'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
            'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        with mock.patch.dict(os.environ, {
            'GEARMENT_API_SECRET': CAPTURED_SECRET,
            'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
        }, clear=False):
            is_valid, reason = _verify_signature(
                headers,
                CAPTURED_BODY,
                self.env,
                now_provider=lambda: float(CAPTURED_TIMESTAMP),
            )

        self.assertTrue(
            is_valid,
            f"Nonce outside 10-min window should be allowed; got reason={reason}"
        )
        self.assertEqual(reason, '')


@tagged('post_install', '-at_install')
class TestWebhookVerifyHTTP(HttpCase):
    """End-to-end HTTP integration tests for webhook verification.

    Tests verify the full request/response cycle: POST /gearment/webhook
    with valid/invalid signatures, and audit log state transitions.
    """

    def _compute_sig(self, nonce: str, ts: str, body: bytes, secret: str,
                      url_path: str = _WEBHOOK_PATH) -> str:
        """Helper to compute HMAC-SHA256 signature (same as module-level function)."""
        return _compute_signature(nonce, ts, body, secret, url_path)

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': CAPTURED_SECRET,
        'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
    }, clear=False)
    @mock.patch('odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook.time.time',
                return_value=float(CAPTURED_TIMESTAMP))
    def test_valid_signature_returns_200_and_logs_verified_true(self, mock_time):
        """Test that valid signature returns 200 and audit row has signature_verified=True."""
        payload = CAPTURED_BODY

        response = self.url_open(
            '/gearment/webhook',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': CAPTURED_SIGNATURE,
                'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
                'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
                'X-Connect-Nonce': CAPTURED_NONCE,
            },
            timeout=30,
        )

        self.assertEqual(response.status_code, 200)
        resp_json = json.loads(response.text)
        self.assertEqual(resp_json.get('status'), 'ok')

        # Verify audit row
        log_model = self.env['gearment.api.log']
        logs = log_model.search([
            ('source', '=', 'inbound_webhook'),
        ], order='request_started_at desc', limit=1)

        self.assertTrue(logs, "Audit row should exist")
        latest = logs[0]
        self.assertTrue(latest.signature_verified, "signature_verified should be True")
        self.assertEqual(latest.verify_failure_reason, '', "verify_failure_reason should be empty")
        self.assertEqual(latest.nonce_value, CAPTURED_NONCE, "nonce_value should be captured")
        self.assertEqual(
            latest.request_timestamp,
            int(CAPTURED_TIMESTAMP),
            "request_timestamp should match header"
        )

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': CAPTURED_SECRET,
        'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
    }, clear=False)
    @mock.patch('odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook.time.time',
                return_value=float(CAPTURED_TIMESTAMP))
    def test_invalid_signature_returns_401_and_logs_verified_false(self, mock_time):
        """Test that invalid signature returns 401 and audit row has signature_verified=False."""
        payload = CAPTURED_BODY
        bad_sig = 'X' + CAPTURED_SIGNATURE[1:]  # Flip first char

        response = self.url_open(
            '/gearment/webhook',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': bad_sig,
                'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
                'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
                'X-Connect-Nonce': CAPTURED_NONCE,
            },
            timeout=30,
        )

        self.assertEqual(response.status_code, 401)
        resp_json = json.loads(response.text)
        self.assertEqual(resp_json.get('error'), 'unauthorized')

        # Verify audit row
        log_model = self.env['gearment.api.log']
        logs = log_model.search([
            ('source', '=', 'inbound_webhook'),
        ], order='request_started_at desc', limit=1)

        self.assertTrue(logs, "Audit row should exist")
        latest = logs[0]
        self.assertFalse(latest.signature_verified, "signature_verified should be False")
        self.assertEqual(latest.verify_failure_reason, 'signature_mismatch')

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': CAPTURED_SECRET,
        'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
    }, clear=False)
    @mock.patch('odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook.time.time',
                return_value=float(CAPTURED_TIMESTAMP))
    def test_missing_signature_header_returns_401(self, mock_time):
        """Test that missing X-Connect-Signature returns 401."""
        payload = CAPTURED_BODY

        response = self.url_open(
            '/gearment/webhook',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
                'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
                'X-Connect-Nonce': CAPTURED_NONCE,
            },
            timeout=30,
        )

        self.assertEqual(response.status_code, 401)
        resp_json = json.loads(response.text)
        self.assertEqual(resp_json.get('error'), 'unauthorized')

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': CAPTURED_SECRET,
        'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
    }, clear=False)
    @mock.patch('odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook.time.time',
                return_value=float(CAPTURED_TIMESTAMP))
    def test_missing_timestamp_header_returns_401(self, mock_time):
        """Test that missing X-Connect-Timestamp returns 401."""
        payload = CAPTURED_BODY

        response = self.url_open(
            '/gearment/webhook',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': CAPTURED_SIGNATURE,
                'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
                'X-Connect-Nonce': CAPTURED_NONCE,
            },
            timeout=30,
        )

        self.assertEqual(response.status_code, 401)

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': CAPTURED_SECRET,
        'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
    }, clear=False)
    @mock.patch('odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook.time.time',
                return_value=float(CAPTURED_TIMESTAMP))
    def test_missing_nonce_header_returns_401(self, mock_time):
        """Test that missing X-Connect-Nonce returns 401."""
        payload = CAPTURED_BODY

        response = self.url_open(
            '/gearment/webhook',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': CAPTURED_SIGNATURE,
                'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
                'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
            },
            timeout=30,
        )

        self.assertEqual(response.status_code, 401)

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': CAPTURED_SECRET,
        'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
    }, clear=False)
    @mock.patch('odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook.time.time',
                return_value=float(CAPTURED_TIMESTAMP))
    def test_missing_client_key_header_returns_401(self, mock_time):
        """Test that missing X-Connect-Client-Key returns 401."""
        payload = CAPTURED_BODY

        response = self.url_open(
            '/gearment/webhook',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': CAPTURED_SIGNATURE,
                'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
                'X-Connect-Nonce': CAPTURED_NONCE,
            },
            timeout=30,
        )

        self.assertEqual(response.status_code, 401)

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': CAPTURED_SECRET,
        'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
    }, clear=False)
    @mock.patch('odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook.time.time',
                return_value=float(CAPTURED_TIMESTAMP))
    def test_wrong_client_key_returns_401(self, mock_time):
        """Test that wrong X-Connect-Client-Key returns 401 with 'client_key_mismatch'."""
        payload = CAPTURED_BODY

        response = self.url_open(
            '/gearment/webhook',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': CAPTURED_SIGNATURE,
                'X-Connect-Client-Key': 'WRONG_KEY',
                'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
                'X-Connect-Nonce': CAPTURED_NONCE,
            },
            timeout=30,
        )

        self.assertEqual(response.status_code, 401)

        # Verify failure reason in audit log
        log_model = self.env['gearment.api.log']
        logs = log_model.search([
            ('source', '=', 'inbound_webhook'),
        ], order='request_started_at desc', limit=1)
        self.assertTrue(logs, "Audit row should exist")
        self.assertEqual(logs[0].verify_failure_reason, 'client_key_mismatch')

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': CAPTURED_SECRET,
        'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
    }, clear=False)
    @mock.patch('odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook.time.time',
                return_value=float(CAPTURED_TIMESTAMP))
    def test_expired_timestamp_returns_401(self, mock_time):
        """Test that timestamp > 300s old is rejected."""
        payload = CAPTURED_BODY
        old_ts = str(int(CAPTURED_TIMESTAMP) - 600)
        old_sig = self._compute_sig(CAPTURED_NONCE, old_ts, payload, CAPTURED_SECRET)

        response = self.url_open(
            '/gearment/webhook',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': old_sig,
                'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
                'X-Connect-Timestamp': old_ts,
                'X-Connect-Nonce': CAPTURED_NONCE,
            },
            timeout=30,
        )

        self.assertEqual(response.status_code, 401)

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': CAPTURED_SECRET,
        'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
    }, clear=False)
    @mock.patch('odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook.time.time',
                return_value=float(CAPTURED_TIMESTAMP))
    def test_future_timestamp_beyond_skew_returns_401(self, mock_time):
        """Test that timestamp > 60s in future is rejected."""
        payload = CAPTURED_BODY
        future_ts = str(int(CAPTURED_TIMESTAMP) + 120)
        future_sig = self._compute_sig(CAPTURED_NONCE, future_ts, payload, CAPTURED_SECRET)

        response = self.url_open(
            '/gearment/webhook',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': future_sig,
                'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
                'X-Connect-Timestamp': future_ts,
                'X-Connect-Nonce': CAPTURED_NONCE,
            },
            timeout=30,
        )

        self.assertEqual(response.status_code, 401)

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': CAPTURED_SECRET,
        'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
    }, clear=False)
    @mock.patch('odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook.time.time',
                return_value=float(CAPTURED_TIMESTAMP))
    def test_duplicate_nonce_returns_401(self, mock_time):
        """Test that duplicate nonce (seen in last 10 min) is rejected.

        HttpCase request runs in its own DB connection, so test-side rows
        committed via the test transaction are not visible to the
        controller's env. Instead we drive the dedup against the
        controller's own audit-row writes: fire the same valid request
        twice — the second call sees the first call's audit row and must
        return 401 with reason 'nonce_replay'.
        """
        payload = CAPTURED_BODY
        headers = {
            'Content-Type': 'application/json',
            'X-Connect-Signature': CAPTURED_SIGNATURE,
            'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
            'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
            'X-Connect-Nonce': CAPTURED_NONCE,
        }

        # 1st hit: should succeed (200, signature_verified=True)
        first = self.url_open('/gearment/webhook', data=payload, headers=headers, timeout=30)
        self.assertEqual(first.status_code, 200)

        # 2nd hit with same nonce: dedup triggers 401
        second = self.url_open('/gearment/webhook', data=payload, headers=headers, timeout=30)
        self.assertEqual(second.status_code, 401)

        # Find the failure row by reason directly. Same-second
        # request_started_at on both rows can make `desc, id desc` pick
        # whichever row got the larger id; safer to filter on the field
        # we're asserting.
        log_model = self.env['gearment.api.log']
        failed_rows = log_model.search([
            ('source', '=', 'inbound_webhook'),
            ('verify_failure_reason', '=', 'nonce_replay'),
        ])
        self.assertTrue(failed_rows, "A nonce_replay audit row must exist for the 2nd hit")

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': CAPTURED_SECRET,
        'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
    }, clear=False)
    @mock.patch('odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook.time.time',
                return_value=float(CAPTURED_TIMESTAMP))
    def test_topic_extracted_from_body_type_key(self, mock_time):
        """Test that topic is extracted from body['type'] key."""
        # Body with 'type' key
        payload = b'{"type":"order_completed","order":{"gearment_id":"G-123"}}'
        sig = self._compute_sig(CAPTURED_NONCE, CAPTURED_TIMESTAMP, payload, CAPTURED_SECRET)

        response = self.url_open(
            '/gearment/webhook',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': sig,
                'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
                'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
                'X-Connect-Nonce': CAPTURED_NONCE,
            },
            timeout=30,
        )

        self.assertEqual(response.status_code, 200)

        # Verify topic_seen captures 'order_completed'
        log_model = self.env['gearment.api.log']
        logs = log_model.search([
            ('source', '=', 'inbound_webhook'),
        ], order='request_started_at desc', limit=1)
        self.assertTrue(logs, "Audit row should exist")
        self.assertEqual(logs[0].topic_seen, 'order_completed')

    @mock.patch.dict(os.environ, {
        'GEARMENT_API_SECRET': CAPTURED_SECRET,
        'GEARMENT_API_KEY': CAPTURED_CLIENT_KEY,
    }, clear=False)
    @mock.patch('odoo.addons.multichannel_hub_fulfillment.controllers.gearment_webhook.time.time',
                return_value=float(CAPTURED_TIMESTAMP))
    def test_failure_drops_request_body_to_256(self, mock_time):
        """Test that on verification failure, request_body is truncated to 256 chars."""
        # Create a very long body
        long_body = b'{"order":{"gearment_id":"' + b'x' * 1000 + b'"}}'
        bad_sig = 'INVALID_SIGNATURE'

        response = self.url_open(
            '/gearment/webhook',
            data=long_body,
            headers={
                'Content-Type': 'application/json',
                'X-Connect-Signature': bad_sig,
                'X-Connect-Client-Key': CAPTURED_CLIENT_KEY,
                'X-Connect-Timestamp': CAPTURED_TIMESTAMP,
                'X-Connect-Nonce': CAPTURED_NONCE,
            },
            timeout=30,
        )

        self.assertEqual(response.status_code, 401)

        # Verify body truncation
        log_model = self.env['gearment.api.log']
        logs = log_model.search([
            ('source', '=', 'inbound_webhook'),
        ], order='request_started_at desc', limit=1)
        self.assertTrue(logs, "Audit row should exist")
        # Body should be truncated to 256 chars or less
        body_len = len(logs[0].request_body or '')
        self.assertLessEqual(body_len, 256, f"request_body should be ≤256 chars; got {body_len}")


# Import datetime for test_old_nonce_outside_dedup_window_does_not_block
from datetime import timedelta
