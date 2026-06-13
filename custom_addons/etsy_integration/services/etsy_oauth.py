"""Etsy OAuth2 PKCE helpers — pure functions, no Odoo, no live HTTP.

Implements RFC 7636 (PKCE) and Etsy's OAuth2 v3 endpoints. The Odoo
controller in `controllers/etsy_oauth.py` orchestrates these helpers and
persists the resulting tokens on `etsy.shop`.

Sandbox-mode notes (P0-14, 2026-04-27):
- Tokens are stored plaintext on `etsy.shop` with `groups='base.group_system'`
  for UI-level read restriction. Fernet-at-rest encryption is deferred to
  Phase 1 per Spec 005 findings Q2.
- `secrets/credentials.json` holds the registered Etsy app's `client_id`,
  `client_secret`, and one or more `redirect_uri` entries. The controller
  picks the redirect URI matching `web.base.url` at runtime.
"""
import base64
import hashlib
import secrets as _secrets
from urllib.parse import quote, urlencode

import requests

ETSY_AUTHORIZE_URL = 'https://www.etsy.com/oauth/connect'
ETSY_TOKEN_URL = 'https://api.etsy.com/v3/public/oauth/token'
DEFAULT_SCOPES = (
    'transactions_r',
    'transactions_w',
    'listings_r',
    'listings_w',
    'shops_r',
    # shops_w (P-LIST-SHIP-CREATE / ESTY-201): required to create/update
    # shop-level resources — shipping profiles, shop sections. Standard
    # self-serve Etsy scope; adding it forces every shop to re-authorize
    # (refresh tokens keep their original scope and cannot be upgraded).
    'shops_w',
    'email_r',
)
TOKEN_REQUEST_TIMEOUT_SECONDS = 30


def generate_code_verifier(num_bytes: int = 64) -> str:
    """Generate a PKCE code_verifier per RFC 7636 §4.1.

    Output is URL-safe base64 (no padding) of `num_bytes` random bytes.
    Length is `ceil(num_bytes * 4 / 3)` after stripping padding, e.g. 86
    chars for 64 bytes — comfortably inside the 43..128 range RFC requires.
    """
    raw = _secrets.token_bytes(num_bytes)
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def generate_code_challenge(code_verifier: str) -> str:
    """Derive a PKCE S256 code_challenge from a code_verifier per RFC 7636 §4.2."""
    digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


def build_authorize_url(
    client_id: str,
    redirect_uri: str,
    scopes,
    state: str,
    code_challenge: str,
) -> str:
    """Build the Etsy /oauth/connect URL with all required PKCE parameters."""
    if isinstance(scopes, str):
        scope_str = scopes
    else:
        scope_str = ' '.join(scopes)
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': scope_str,
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
    }
    # quote_via=quote escapes spaces as %20 (RFC 3986) rather than the
    # form-encoded `+`. Etsy's OAuth endpoint accepts both, but %20 is
    # what the test fixture and most OAuth2 clients expect.
    return f"{ETSY_AUTHORIZE_URL}?{urlencode(params, quote_via=quote)}"


def exchange_code_for_token(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict:
    """Exchange an authorization code for access + refresh tokens.

    Returns the parsed JSON response on success. Raises
    `requests.HTTPError` on non-2xx responses; the caller is responsible
    for translating into Odoo errors and for not logging the response
    body (it contains the access_token).
    """
    payload = {
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'code': code,
        'code_verifier': code_verifier,
    }
    response = requests.post(
        ETSY_TOKEN_URL,
        data=payload,
        timeout=TOKEN_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(client_id: str, refresh_token: str) -> dict:
    """Use a refresh_token to mint a new access_token (Etsy v3 OAuth2)."""
    payload = {
        'grant_type': 'refresh_token',
        'client_id': client_id,
        'refresh_token': refresh_token,
    }
    response = requests.post(
        ETSY_TOKEN_URL,
        data=payload,
        timeout=TOKEN_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()
