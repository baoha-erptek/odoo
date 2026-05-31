"""HMAC-signed Gearment webhook simulator for Flow-3 TC-DROP-005.

Mirrors the canonical signing scheme implemented in
``multichannel_hub_fulfillment/controllers/gearment_webhook.py::_compute_signature``:

    signing_string = url_path + nonce + timestamp + base64url(body)
    sig            = base64url(HMAC-SHA256(secret, signing_string))

The controller accepts the signature under any header whose name contains
``signature``; we use the documented ``X-Connect-Signature``.

Secret comes from the environment variable ``GEARMENT_API_SECRET`` (preferred)
or ``GEARMENT_WEBHOOK_HMAC_SECRET`` (legacy alias). NEVER hard-code secrets in
this file or in fixtures — the test that uses this helper must inject the
secret via environment, the same way the Odoo controller reads it from
``ir.config_parameter``.

Usage (from a Playwright test or ad-hoc python):

    from fixtures.gearment_webhook_post import post_webhook
    rc, body = post_webhook(
        base_url='https://odoo.hatafax.com',
        secret=os.environ['GEARMENT_API_SECRET'],
        payload={'type': 'tracking.updated', 'order_id': 'GEAR-UAT-001', ...},
    )
    assert rc == 200, f'webhook rejected: {body!r}'
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets as _secrets
import time
from typing import Any

try:
    import requests  # noqa: WPS433 — fixture-only dependency
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "gearment_webhook_post.py requires the 'requests' library. "
        "Install with: pip install requests"
    ) from exc

WEBHOOK_PATH = "/gearment/webhook"
SIGNATURE_HEADER = "X-Connect-Signature"
DEFAULT_TIMEOUT = 15


def compute_signature(
    body_bytes: bytes,
    nonce: str,
    timestamp_str: str,
    secret: str,
    url_path: str = WEBHOOK_PATH,
) -> str:
    """Exact mirror of ``_compute_signature`` in the production controller.

    ``body_bytes`` MUST be the same bytes that the client POSTs. The function
    is deterministic — passing the same args yields the same signature.
    """
    body_b64 = base64.urlsafe_b64encode(body_bytes).decode("ascii")
    signing_string = (url_path + nonce + timestamp_str + body_b64).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signing_string, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def post_webhook(
    base_url: str,
    secret: str,
    payload: dict[str, Any],
    *,
    nonce: str | None = None,
    timestamp_str: str | None = None,
    url_path: str = WEBHOOK_PATH,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[int, str]:
    """Sign + POST `payload` to Gearment's webhook endpoint on `base_url`.

    Returns ``(status_code, response_text)``. Raises on transport errors
    (DNS, connection refused) so callers can fail loudly.

    Defensive against operator mistakes:
      - ``secret`` must be non-empty (refuses to POST with empty secret).
      - ``nonce``/``timestamp_str`` are auto-generated when not provided so
        each call satisfies the controller's replay-window + nonce-dedup
        defenses without the caller juggling clock skew.
    """
    if not secret:
        raise ValueError(
            "Empty webhook secret. Set GEARMENT_API_SECRET in your environment "
            "before invoking post_webhook; the controller will reject any "
            "request signed with an empty key."
        )
    body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    nonce = nonce or _secrets.token_hex(8)
    timestamp_str = timestamp_str or str(int(time.time()))
    sig = compute_signature(body_bytes, nonce, timestamp_str, secret, url_path=url_path)
    headers = {
        "Content-Type": "application/json",
        SIGNATURE_HEADER: sig,
        "X-Connect-Nonce": nonce,
        "X-Connect-Timestamp": timestamp_str,
    }
    full_url = base_url.rstrip("/") + url_path
    response = requests.post(full_url, data=body_bytes, headers=headers, timeout=timeout)
    return response.status_code, response.text
