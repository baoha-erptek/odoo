"""Gearment webhook discovery-mode controller (P0-18b2a).

Public POST endpoint at /gearment/webhook. Logs full request headers + body
to gearment.api.log so HMAC signature header name + algorithm can be
discovered by inspecting the audit log after Gearment dashboard's
webhook simulator fires.

Out of scope (deferred to subsequent slices):
- HMAC signature verification → P0-18b2b
- Topic-to-handler routing + sale.order lookup → P0-18b2c
- Tracking write to sale.order.fulfillment → P0-18b2c
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Body truncation cap matches existing gearment.api.log convention (storage).
_MAX_BODY_CHARS = 4096

# Hard cap on bytes we consume off the wire.
# Defense-in-depth (security review HIGH #1): Werkzeug's get_data() buffers the
# entire Content-Length into memory before we can truncate. A reverse proxy
# typically enforces a body limit, but staging nginx config may not, and the
# dev container has no proxy at all. Pre-check Content-Length before reading.
_MAX_BODY_BYTES = 1_000_000  # 1 MB

# Headers that may carry secrets / PII; never written to audit log.
# Lower-cased for case-insensitive comparison.
_SCRUBBED_HEADERS = frozenset({
    'authorization',
    'cookie',
    'set-cookie',
    'proxy-authorization',
    'x-gearment-webhook-secret',
    'x-api-key',
})


def _scrub_headers(raw_headers):
    """Drop secret-bearing headers; keep names + values for everything else."""
    out = {}
    for name, value in raw_headers.items():
        lname = name.lower()
        if lname in _SCRUBBED_HEADERS or 'secret' in lname or 'password' in lname:
            continue
        out[name] = value
    return out


def _content_length_exceeds_cap(raw_headers, cap_bytes=_MAX_BODY_BYTES):
    """Return True if the Content-Length header advertises more than cap_bytes.

    Defense-in-depth helper: lets us refuse to read the body before
    Werkzeug buffers the whole thing into memory. Werkzeug's test client
    overwrites Content-Length, so this guard is most useful against real
    network traffic — the unit test below covers it directly.
    """
    try:
        content_length = int(raw_headers.get('Content-Length', '0') or '0')
    except (TypeError, ValueError):
        return False
    return content_length > cap_bytes


def _detect_signature_header(raw_headers):
    """Return name of first header whose name contains 'signature' (case-insensitive)."""
    for name in raw_headers.keys():
        if 'signature' in name.lower():
            return name
    return ''


def _detect_topic(body_dict, raw_headers):
    """Extract topic/event from body dict or X-Topic-style header."""
    if isinstance(body_dict, dict):
        topic = body_dict.get('event') or body_dict.get('topic')
        if topic:
            return str(topic)
    for name, value in raw_headers.items():
        if name.lower() in ('x-topic', 'x-event', 'x-gearment-topic', 'x-gearment-event'):
            return str(value)
    return ''


class GearmentWebhookController(http.Controller):
    """Discovery-mode webhook handler — log only, no validation, no routing."""

    @http.route(
        '/gearment/webhook',
        type='http',
        auth='public',
        csrf=False,
        methods=['POST'],
        save_session=False,
    )
    def webhook(self, **kwargs):
        """Accept any POST. Capture headers + body to gearment.api.log.

        Always returns 200 {"status": "ok"} so Gearment retry policy does
        not flood us during discovery.

        type='http' chosen over 'json' because Gearment may send malformed
        or non-JSON payloads during simulator tests; type='json' would
        return -32700 parse errors before our handler runs.
        """
        try:
            self._record_inbound()
        except Exception as exc:  # noqa: BLE001 — discovery resilience: never 500
            # Log only exception type + str(exc) at WARNING so we do not leak a
            # full traceback (security review HIGH #2). Full traceback at DEBUG
            # is fine when ops opt in to debug logging during a real probe.
            _logger.warning(
                "P0-18b2a: failed to log inbound Gearment webhook (%s: %s); "
                "still returning 200 to avoid retry storm",
                type(exc).__name__, exc,
            )
            _logger.debug(
                "P0-18b2a: full traceback for failed inbound logging",
                exc_info=True,
            )
        return request.make_response(
            json.dumps({'status': 'ok'}),
            headers=[('Content-Type', 'application/json')],
            status=200,
        )

    def _record_inbound(self):
        """Pull headers + body off the live request, write one audit row."""
        raw_headers = dict(request.httprequest.headers)

        # Pre-read body-size guard (security review HIGH #1).
        # If the sender advertised more than _MAX_BODY_BYTES, do not buffer it.
        # We still log a row so the probe is visible in the audit table.
        if _content_length_exceeds_cap(raw_headers):
            _logger.warning(
                "P0-18b2a: rejecting webhook body — Content-Length=%s exceeds %d",
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

        headers_scrubbed = _scrub_headers(raw_headers)
        signature_header = _detect_signature_header(raw_headers)
        topic = _detect_topic(body_dict, raw_headers)

        # sudo() justified inline: route is auth='public' so request.env.user
        # is the public user with no write access to gearment.api.log. The
        # controller itself is the trust boundary — only system-deployed code
        # can register the route, and the audit row is append-only.
        request.env['gearment.api.log'].sudo().create({
            'endpoint': 'POST /gearment/webhook',
            'http_status': 200,
            'source': 'inbound_webhook',
            'direction': 'inbound',
            'request_headers': json.dumps(headers_scrubbed, default=str),
            'request_body': body_text[:_MAX_BODY_CHARS],
            'signature_header_seen': signature_header,
            'topic_seen': topic,
        })
        _logger.debug(
            "P0-18b2a: logged inbound webhook (signature_header=%s topic=%s body_len=%d)",
            signature_header or '(none)', topic or '(none)', len(body_text),
        )
