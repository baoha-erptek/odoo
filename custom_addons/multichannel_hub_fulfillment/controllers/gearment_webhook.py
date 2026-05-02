"""Gearment webhook controller — HMAC verify + replay defense (P0-18b2b).

Public POST endpoint at /gearment/webhook. P0-18b2a discovery established
the audit log; P0-18b2b adds HMAC-SHA256 verify against GEARMENT_API_SECRET
plus replay-window + nonce-dedup defenses. Verified payloads return 200;
unverified return 401 with truncated body and `verify_failure_reason`.

Topic-to-handler routing + sale.order writes deferred to P0-18b2c.

Signing string contract (cracked from Gearment OpenAPI yaml + verified
against captured probe row 3):

    signing_string = url_path + nonce + timestamp + base64url(body)
    sig            = base64url(hmac_sha256(secret, signing_string))
    header         = X-Connect-Signature
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import time

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_URL_PATH = '/gearment/webhook'
_MAX_BODY_CHARS = 4096
_MAX_BODY_BYTES = 1_000_000  # pre-read guard
_FAIL_BODY_CAP = 256  # on verify failure, truncate stored body further

# Replay window
_TIMESTAMP_PAST_TOLERANCE = 300   # accept up to 5 min behind
_TIMESTAMP_FUTURE_SKEW = 60       # accept up to 1 min ahead
_NONCE_DEDUP_WINDOW = 600         # nonce can't repeat within 10 min

_SCRUBBED_HEADERS = frozenset({
    'authorization',
    'cookie',
    'set-cookie',
    'proxy-authorization',
    'x-gearment-webhook-secret',
    'x-api-key',
})


def _scrub_headers(raw_headers):
    out = {}
    for name, value in raw_headers.items():
        lname = name.lower()
        if lname in _SCRUBBED_HEADERS or 'secret' in lname or 'password' in lname:
            continue
        out[name] = value
    return out


def _content_length_exceeds_cap(raw_headers, cap_bytes=_MAX_BODY_BYTES):
    try:
        content_length = int(raw_headers.get('Content-Length', '0') or '0')
    except (TypeError, ValueError):
        return False
    return content_length > cap_bytes


def _detect_signature_header(raw_headers):
    """Heuristic capture of the first header whose name contains 'signature'."""
    for name in raw_headers.keys():
        if 'signature' in name.lower():
            return name
    return ''


def _detect_topic(body_dict, raw_headers):
    """Extract topic/event. Real Gearment payloads use body['type']; we also
    accept body['event']/body['topic'] and X-Topic-style headers as fallback.
    """
    if isinstance(body_dict, dict):
        topic = body_dict.get('type') or body_dict.get('event') or body_dict.get('topic')
        if topic:
            return str(topic)
    for name, value in raw_headers.items():
        if name.lower() in ('x-topic', 'x-event', 'x-gearment-topic', 'x-gearment-event'):
            return str(value)
    return ''


def _compute_signature(body_bytes, nonce, timestamp_str, secret, url_path=_URL_PATH):
    """Compute the canonical Gearment HMAC-SHA256 signature.

    signing_string = url_path + nonce + timestamp + base64url(body)
    sig            = base64url(HMAC-SHA256(secret, signing_string))

    All values UTF-8 encoded. Body base64-urlsafe with '=' padding (Go
    base64.URLEncoding default). Returns the urlsafe-base64 string.
    """
    body_b64 = base64.urlsafe_b64encode(body_bytes).decode('ascii')
    signing_string = (url_path + nonce + timestamp_str + body_b64).encode('utf-8')
    digest = hmac.new(secret.encode('utf-8'), signing_string, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode('ascii')


def _verify_signature(raw_headers, body_bytes, env_for_dedup,
                       request_path=None, now_provider=None):
    """Verify Gearment webhook authenticity.

    Returns (is_valid: bool, failure_reason: str). reason='' on success.

    raw_headers: dict (case-sensitive keys; we resolve case-insensitively).
    body_bytes:  exact bytes the sender posted; HMAC'd verbatim.
    env_for_dedup: an Odoo Environment used only to search gearment.api.log
        for prior nonce within the dedup window.
    request_path: HTTP path the request hit, used as the signing-string
        prefix. Default `_URL_PATH` (`/gearment/webhook`). The caller passes
        `request.httprequest.path` so a future `/v2` route cannot be
        impersonated by replaying a `/v1` signature against it
        (security review M2).
    now_provider: callable returning unix epoch seconds. Default `time.time`
        (re-resolved at call time so test mocks of the module-level `time`
        attribute take effect; using a default-arg callable would freeze
        the original `time.time` at definition).
        Tests inject `lambda: 1777735761` for deterministic windows.
    """
    if now_provider is None:
        now_provider = time.time
    if request_path is None:
        request_path = _URL_PATH
    headers_ci = {k.lower(): v for k, v in raw_headers.items()}
    sig_header = headers_ci.get('x-connect-signature', '')
    ts_header = headers_ci.get('x-connect-timestamp', '')
    nonce_header = headers_ci.get('x-connect-nonce', '')
    client_key = headers_ci.get('x-connect-client-key', '')

    if not sig_header:
        return False, 'missing_signature_header'
    if not ts_header:
        return False, 'missing_timestamp_header'
    if not nonce_header:
        return False, 'missing_nonce_header'
    if not client_key:
        return False, 'missing_client_key_header'

    expected_client_key = os.environ.get('GEARMENT_API_KEY', '')
    if not expected_client_key or client_key != expected_client_key:
        return False, 'client_key_mismatch'

    try:
        ts_int = int(ts_header)
    except (TypeError, ValueError):
        return False, 'timestamp_invalid'

    now = int(now_provider())
    if ts_int < now - _TIMESTAMP_PAST_TOLERANCE or ts_int > now + _TIMESTAMP_FUTURE_SKEW:
        return False, 'timestamp_outside_window'

    cutoff = now - _NONCE_DEDUP_WINDOW
    prior = env_for_dedup['gearment.api.log'].sudo().search([
        ('nonce_value', '=', nonce_header),
        ('request_timestamp', '>=', cutoff),
    ], limit=1)
    if prior:
        return False, 'nonce_replay'

    secret = os.environ.get('GEARMENT_API_SECRET', '')
    if not secret:
        # Refuse to "succeed" without a configured secret — fail closed.
        return False, 'signature_mismatch'
    expected_sig = _compute_signature(
        body_bytes, nonce_header, ts_header, secret, url_path=request_path,
    )
    if not hmac.compare_digest(expected_sig, sig_header):
        return False, 'signature_mismatch'

    return True, ''


class GearmentWebhookController(http.Controller):
    """HMAC-verified webhook handler. Audit-logs every request."""

    @http.route(
        '/gearment/webhook',
        type='http',
        auth='public',
        csrf=False,
        methods=['POST'],
        save_session=False,
    )
    def webhook(self, **kwargs):
        """POST /gearment/webhook.

        On verify success → 200 {"status":"ok"} + audit row signature_verified=True.
        On verify failure → 401 {"error":"unauthorized"} + audit row with
        signature_verified=False, verify_failure_reason set, body truncated to
        256 chars (defense — don't store full hostile payloads).

        type='http' (not 'json') so Gearment's malformed-JSON simulator probes
        don't 400 with -32700 before our handler runs.
        """
        status = 200
        try:
            verified = self._record_inbound()
            if not verified:
                status = 401
        except Exception as exc:  # noqa: BLE001 — log path resilience
            _logger.warning(
                "P0-18b2b: failed to log inbound Gearment webhook (%s: %s); "
                "returning 200 to avoid retry storm",
                type(exc).__name__, exc,
            )
            _logger.debug(
                "P0-18b2b: full traceback for failed inbound logging",
                exc_info=True,
            )
            status = 200

        response_body = (
            json.dumps({'status': 'ok'}) if status == 200
            else json.dumps({'error': 'unauthorized'})
        )
        return request.make_response(
            response_body,
            headers=[('Content-Type', 'application/json')],
            status=status,
        )

    def _record_inbound(self):
        """Verify signature, write one audit row, return True on verified."""
        raw_headers = dict(request.httprequest.headers)

        if _content_length_exceeds_cap(raw_headers):
            _logger.warning(
                "P0-18b2b: rejecting webhook body — Content-Length=%s exceeds %d",
                raw_headers.get('Content-Length'), _MAX_BODY_BYTES,
            )
            body_bytes = b''
            body_text = ''
        else:
            body_bytes = request.httprequest.get_data() or b''
            body_text = body_bytes.decode('utf-8', errors='replace')

        try:
            body_dict = json.loads(body_text) if body_text else {}
        except (ValueError, TypeError):
            body_dict = {}

        verified, failure_reason = _verify_signature(
            raw_headers, body_bytes, request.env,
            request_path=request.httprequest.path,
        )

        headers_scrubbed = _scrub_headers(raw_headers)
        signature_header = _detect_signature_header(raw_headers)
        topic = _detect_topic(body_dict, raw_headers)

        # On verify failure, store at most _FAIL_BODY_CAP bytes of the body
        # so we keep enough for forensics but don't archive hostile payloads
        # at full length.
        body_to_store = (
            body_text[:_MAX_BODY_CHARS] if verified
            else body_text[:_FAIL_BODY_CAP]
        )

        # Parse Gearment's timestamp header into the indexed integer column
        # for nonce-dedup queries; coerce to 0 on parse failure rather than
        # raising (we still want the audit row even on verify failure).
        try:
            ts_int = int(raw_headers.get('X-Connect-Timestamp') or 0)
        except (TypeError, ValueError):
            ts_int = 0

        # sudo() justified inline: route is auth='public' so request.env.user
        # is the public user with no write access to gearment.api.log. The
        # controller itself is the trust boundary; the audit row is append-only.
        request.env['gearment.api.log'].sudo().create({
            'endpoint': 'POST /gearment/webhook',
            'http_status': 200 if verified else 401,
            'source': 'inbound_webhook',
            'direction': 'inbound',
            'request_headers': json.dumps(headers_scrubbed, default=str),
            'request_body': body_to_store,
            'signature_header_seen': signature_header,
            'topic_seen': topic,
            'nonce_value': raw_headers.get('X-Connect-Nonce') or '',
            'request_timestamp': ts_int,
            'signature_verified': verified,
            'verify_failure_reason': failure_reason,
        })
        _logger.debug(
            "P0-18b2b: logged webhook (verified=%s reason=%s topic=%s body_len=%d)",
            verified, failure_reason or '(none)', topic or '(none)', len(body_text),
        )
        return verified
