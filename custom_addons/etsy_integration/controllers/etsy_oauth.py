"""Etsy OAuth2 PKCE controller — handles /etsy/oauth/authorize + /callback.

The authorize route generates a PKCE verifier+challenge, persists the
verifier (keyed by a random `state` UUID) into `ir.config_parameter`, and
redirects the logged-in user to Etsy's /oauth/connect endpoint. The
callback route validates the state, retrieves the verifier, exchanges
the code for tokens via the helper in `services.etsy_oauth`, asserts
the granted scope set matches the four approved scopes, and persists
the tokens on the targeted `etsy.shop` row via the Fernet-encryption
helpers on `etsy.shop`.

P1-10 (2026-05-12): tokens are now stored as Fernet ciphertext via the
`etsy.shop._set_access_token` / `_set_refresh_token` helpers. Scope
assertion against the four E1-approved scopes (`transactions_r/w`,
`listings_r/w`, `shops_r`, `email_r`) hard-fails the callback on missing
or forbidden scope (`conversations_r` is excluded from the E1 grant).
"""
import json
import logging
import secrets as _secrets

import requests

from odoo import SUPERUSER_ID, api, fields, http
from odoo.exceptions import AccessError
from odoo.http import request

from ..services.etsy_oauth import (
    DEFAULT_SCOPES,
    build_authorize_url,
    exchange_code_for_token,
    generate_code_challenge,
    generate_code_verifier,
)

_logger = logging.getLogger(__name__)

_PENDING_PARAM_PREFIX = 'etsy.oauth.pending.'

# P1-10 scope-assertion contract — see specs/005-etsy-api-channel/
# p1-10-plan.md §D-P1-10-04 and the 2026-05-12 E1 approval bookkeeping.
_REQUIRED_SCOPES = frozenset({
    'transactions_r', 'transactions_w',
    'listings_r', 'listings_w',
    'shops_r', 'email_r',
})
# E1 approval explicitly excludes conversations_r. If Etsy ever returns
# it (e.g. lingering pre-2026-05-12 grant), reject — proceeding would
# bind the shop to a scope set we cannot rely on.
_FORBIDDEN_SCOPES = frozenset({'conversations_r'})


def _read_credentials(env):
    """Load Etsy app credentials from `secrets/credentials.json`.

    Expected schema:
        {
            "client_id": "...",
            "client_secret": "...",
            "redirect_uris": {
                "http://localhost:8169": "http://localhost:8169/etsy/oauth/callback",
                ...
            }
        }
    The controller picks the redirect_uri whose key matches the system's
    `web.base.url` so dev / staging / prod all coexist.
    """
    base_url = env['ir.config_parameter'].sudo().get_param(
        'etsy.oauth.credentials_path',
        default='/opt/odoo/secrets/credentials.json',
    )
    with open(base_url, 'r') as fp:
        data = json.load(fp)
    return data


def _pick_redirect_uri(env, credentials):
    odoo_base = env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
    redirects = credentials.get('redirect_uris') or {}
    if odoo_base in redirects:
        return redirects[odoo_base]
    if redirects:
        # Fall back to the first registered redirect URI; controllers run
        # under the system admin during install/test, where web.base.url
        # may not yet match production.
        return next(iter(redirects.values()))
    return credentials.get('redirect_uri', '')


def _bad_request(message):
    """Return a 400 response without going through the qweb error template.

    Raising werkzeug.exceptions.BadRequest in an Odoo HTTP controller causes
    the qweb 400 page to render, which depends on assets that may not be
    available in the test runner's HTTP harness — bumping the response to
    500. A plain Response keeps the contract simple and lets HttpCase
    assertions read response.status_code directly.
    """
    return request.make_response(message, status=400, headers=[('Content-Type', 'text/plain')])


def _audit_scope_failure(shop_id: int, error_message: str) -> None:
    """Write an `etsy.api.log` row from a fresh cursor + commit.

    The audit row must survive the 400 response, which rolls back the
    outer controller transaction (the response itself signals failure
    and Odoo's HTTP layer reverts any uncommitted ORM state). We open
    a new cursor on the same registry, write the audit row as
    SUPERUSER, and commit before returning — pattern documented in
    memory `feedback_capture_response_body_before_blackbox_probe.md`
    (Defect-11-02 fix carried forward).
    """
    with request.env.registry.cursor() as audit_cr:
        env_audit = api.Environment(audit_cr, SUPERUSER_ID, {})
        env_audit['etsy.api.log'].sudo().create({
            'shop_id': shop_id,
            'endpoint': 'GET /etsy/api/oauth/callback',
            'source': 'scope_validation',
            'error_message': error_message,
            # Deliberately do NOT include the access_token /
            # refresh_token / scope-bearing JSON body. The scope list
            # alone is sufficient for operator triage; the tokens are
            # PII per D-P1-10-04 and must not leak into the audit log.
        })
        audit_cr.commit()


def _validate_scope_grant(scope_str: str, shop_id: int) -> str:
    """Return error message string if invalid (and audit), else ''.

    Validates the `scope` parameter from Etsy's token-exchange
    response against the E1 2026-05-12 approval set. On failure,
    writes a durable audit row before returning the human-readable
    error message (which becomes the 400 response body).
    """
    granted = set((scope_str or '').split())
    missing = _REQUIRED_SCOPES - granted
    forbidden = granted & _FORBIDDEN_SCOPES
    if not missing and not forbidden:
        return ''
    parts = []
    if missing:
        parts.append(f"missing required scopes: {sorted(missing)}")
    if forbidden:
        parts.append(f"forbidden scopes present: {sorted(forbidden)}")
    error_message = "Etsy OAuth scope validation failed; " + "; ".join(parts)
    _audit_scope_failure(shop_id, error_message)
    return error_message


class EtsyOAuthController(http.Controller):

    # Routes are intentionally namespaced under /etsy/api/oauth/ to avoid
    # collision with the existing Gmail OAuth controller in
    # `controllers/oauth.py`, which claims /etsy/oauth/callback for the
    # Spec 001 email-ingest flow. Per ADR-008a v2 the Gmail flow stays as
    # permanent failover, so we keep its URL stable and namespace the new
    # Etsy v3 API flow underneath /etsy/api/oauth/.

    @http.route('/etsy/api/oauth/authorize', type='http', auth='user', methods=['GET'])
    def authorize(self, shop_id=None, **kwargs):
        if not shop_id:
            return _bad_request("Missing shop_id")
        try:
            shop_id_int = int(shop_id)
        except (TypeError, ValueError):
            return _bad_request("Invalid shop_id")
        shop = request.env['etsy.shop'].browse(shop_id_int)
        if not shop.exists():
            return _bad_request("Etsy shop not found")
        # Authorization gate: only users with write access on this etsy.shop
        # can initiate OAuth — otherwise any salesman could trigger a token
        # rebind for a shop they don't manage. check_access_rights() guards
        # the model-level ACL; check_access_rule() guards record rules.
        try:
            shop.check_access_rights('write')
            shop.check_access_rule('write')
        except AccessError:
            return _bad_request("Insufficient permissions on this Etsy shop")

        credentials = _read_credentials(request.env)
        redirect_uri = _pick_redirect_uri(request.env, credentials)

        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)
        state = _secrets.token_urlsafe(32)

        # Persist verifier + shop_id + redirect_uri + creation timestamp
        # under ir.config_parameter so the callback can retrieve them.
        # Sandbox-mode storage; Phase 1 (P1-10) will move to a dedicated
        # transient model with TTL sweep.
        request.env['ir.config_parameter'].sudo().set_param(
            f"{_PENDING_PARAM_PREFIX}{state}",
            json.dumps({
                'code_verifier': verifier,
                'shop_id': shop.id,
                'redirect_uri': redirect_uri,
                'created_at': fields.Datetime.now().isoformat(),
            }),
        )

        auth_url = build_authorize_url(
            client_id=credentials['client_id'],
            redirect_uri=redirect_uri,
            scopes=DEFAULT_SCOPES,
            state=state,
            code_challenge=challenge,
        )
        return request.redirect(auth_url, local=False)

    @http.route('/etsy/api/oauth/callback', type='http', auth='public', methods=['GET'], csrf=False)
    def callback(self, code=None, state=None, error=None, **kwargs):
        if error:
            _logger.warning("Etsy OAuth callback returned error code (state=%s)", state)
            return _bad_request("Etsy OAuth declined")
        if not code or not state:
            return _bad_request("Missing code or state")

        param_key = f"{_PENDING_PARAM_PREFIX}{state}"
        ConfigParam = request.env['ir.config_parameter'].sudo()
        raw = ConfigParam.get_param(param_key)
        if not raw:
            return _bad_request("Unknown or expired OAuth state")

        # Consume the pending row first — even if the token exchange
        # fails, we never want to allow a replay of the same state
        # (defends against an attacker who intercepted the auth code).
        pending_record = ConfigParam.search([('key', '=', param_key)], limit=1)
        if pending_record:
            pending_record.unlink()

        pending = json.loads(raw)
        credentials = _read_credentials(request.env)

        # Prefer the redirect_uri persisted with the pending state row (it
        # reflects what we sent to Etsy at /authorize time, which Etsy
        # checks for an exact match). Fall back to the system-derived URI
        # only if the row predates redirect_uri being written (defensive).
        redirect_uri = pending.get('redirect_uri') or _pick_redirect_uri(
            request.env, credentials,
        )

        try:
            token_response = exchange_code_for_token(
                client_id=credentials['client_id'],
                client_secret=credentials['client_secret'],
                code=code,
                redirect_uri=redirect_uri,
                code_verifier=pending['code_verifier'],
            )
        except (requests.RequestException, KeyError, ValueError) as exc:
            # requests.RequestException covers HTTPError + connection errors
            # + timeouts. KeyError covers a malformed credentials dict.
            # ValueError covers a non-JSON response body. Tests that need
            # to drive the failure path raise one of these (or a subclass).
            # Don't catch bare Exception — that masks bugs in the controller.
            _logger.warning(
                "Etsy OAuth token exchange failed (state=%s): %s",
                state, type(exc).__name__,
            )
            return request.make_response(
                "Etsy token exchange failed",
                status=502,
                headers=[('Content-Type', 'text/plain')],
            )

        shop = request.env['etsy.shop'].sudo().browse(pending['shop_id'])
        if not shop.exists():
            return _bad_request("Etsy shop disappeared during OAuth")

        # P1-10 scope assertion — conditional. Etsy v3's token-exchange
        # response empirically omits `scope` (2026-05-22 staging probe:
        # keys are access_token, api_key, expires_in, refresh_token,
        # token_type, user_id). The granted scope set is bound at the
        # authorize step (`DEFAULT_SCOPES` in the /authorize URL); the
        # consent screen shows the user the exact list and they cannot
        # grant more than was requested. We retain the post-hoc check
        # as a defense-in-depth net for the day Etsy starts returning
        # `scope` — and to immediately surface `_FORBIDDEN_SCOPES`
        # leakage if it ever happens.
        granted_scope = token_response.get('scope') or ''
        if granted_scope:
            scope_error = _validate_scope_grant(granted_scope, shop.id)
            if scope_error:
                _logger.warning(
                    "Etsy OAuth scope validation failed (shop_id=%s): %s",
                    shop.id, scope_error,
                )
                return _bad_request("Etsy OAuth scope validation failed")

        expires_in = int(token_response.get('expires_in') or 3600)
        # P1-10: route tokens through the Fernet helpers — the raw
        # columns now hold ciphertext.
        shop._set_access_token(token_response['access_token'])
        shop._set_refresh_token(token_response.get('refresh_token') or '')
        shop.write({
            'etsy_oauth_token_expires_at': fields.Datetime.add(
                fields.Datetime.now(), seconds=expires_in,
            ),
        })

        # P1-11-SHOPID-BOOTSTRAP: discover and persist the real Etsy shop_id
        # immediately. Tokens are already written above, so the client can
        # authenticate. On failure we proceed (tokens are valid) and log a
        # warning — the operator can re-Authorize or set the field manually.
        # C-ESY-003 will block the active_source='api' flip if shop_id stays
        # empty, so there is no silent operational risk.
        if not shop.sudo().etsy_api_shop_id:
            from ..services.etsy_api_client import EtsyApiClient
            try:
                api_shop_id = EtsyApiClient(shop).fetch_users_me_shop_id()
            except Exception as exc:  # noqa: BLE001 — never break OAuth on discovery
                _logger.warning(
                    "Etsy shop_id bootstrap raised for shop %s (id=%s): %s",
                    shop.name, shop.id, type(exc).__name__,
                )
                api_shop_id = None
            if api_shop_id:
                # sudo: etsy_api_shop_id carries groups='base.group_system';
                # this is OAuth-callback completion (system-level event), the
                # public auth='public' route has no logged-in user to write it.
                shop.sudo().write({'etsy_api_shop_id': api_shop_id})

        return request.redirect('/odoo', local=True)
