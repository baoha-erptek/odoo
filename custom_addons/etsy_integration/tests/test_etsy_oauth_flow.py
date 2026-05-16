"""HttpCase tests for EtsyOAuthController routes.

Tests the OAuth callback flow via HTTP, including:
- GET /etsy/api/oauth/authorize (login required, issues state, stores verifier)
- GET /etsy/api/oauth/callback (validates state, exchanges code, stores tokens)

State is stored as ir.config_parameter during authorize, retrieved + consumed
during callback.

PHASE: RED (failing tests — controller and service methods do not exist yet)
"""
import json
from unittest import mock

from odoo.exceptions import ValidationError
from odoo.tests.common import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestEtsyOAuthControllerFlow(HttpCase):
    """Test Etsy OAuth controller routes via HTTP."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Create a test admin user for authorization tests
        cls.admin_user = cls.env.ref('base.user_admin')

        # Create a test etsy.shop
        cls.etsy_shop = cls.env['etsy.shop'].create({
            'name': 'Test OAuth Shop',
        })

        # The real `secrets/credentials.json` is not bind-mounted into the
        # test container, so `_read_credentials()` would fail with
        # FileNotFoundError. Mock it once for the whole class — every test
        # that issues an HTTP call to /etsy/oauth/* needs this.
        cls._creds_patcher = mock.patch(
            'odoo.addons.etsy_integration.controllers.etsy_oauth._read_credentials',
            return_value={
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret',
                'redirect_uris': {
                    'http://localhost:8169':
                        'http://localhost:8169/etsy/api/oauth/callback',
                },
            },
        )
        cls._creds_patcher.start()
        cls.addClassCleanup(cls._creds_patcher.stop)

    def test_authorize_route_requires_login(self):
        """Test that /etsy/api/oauth/authorize requires authentication.

        Anonymous request should redirect to /web/login.
        """
        # GET /etsy/api/oauth/authorize without being logged in
        response = self.url_open(
            '/etsy/api/oauth/authorize?shop_id=%s' % self.etsy_shop.id,
            timeout=10,
            allow_redirects=False,
        )

        # Should redirect to login (303 or 302)
        self.assertIn(
            response.status_code,
            [302, 303],
            'Anonymous access to /etsy/api/oauth/authorize must redirect',
        )

        # Redirect target should be /web/login or similar
        location = response.headers.get('Location', '')
        self.assertIn(
            '/web/login',
            location,
            'Redirect must point to login page',
        )

    def test_authorize_route_returns_302_to_etsy(self):
        """Test that logged-in user GET /etsy/api/oauth/authorize redirects to Etsy.

        Response should be 302 with Location header pointing to
        https://www.etsy.com/oauth/connect with code_challenge, code_challenge_method,
        state, etc.
        """
        self.authenticate(self.admin_user.login, self.admin_user.login)

        response = self.url_open(
            '/etsy/api/oauth/authorize?shop_id=%s' % self.etsy_shop.id,
            timeout=10,
            allow_redirects=False,
        )

        # Should be 303 (or 302) redirect — Odoo's request.redirect() emits
        # 303 by default in Odoo 19; older versions used 302.
        self.assertIn(
            response.status_code,
            [302, 303],
            'Authorized /etsy/api/oauth/authorize must return 3xx redirect',
        )

        location = response.headers.get('Location', '')

        # Redirect must be to Etsy OAuth endpoint
        self.assertTrue(
            location.startswith('https://www.etsy.com/oauth/connect'),
            'Redirect must point to Etsy OAuth endpoint',
        )

        # Query parameters must include PKCE challenge
        self.assertIn('code_challenge=', location)
        self.assertIn('code_challenge_method=S256', location)
        self.assertIn('state=', location)
        self.assertIn('response_type=code', location)
        self.assertIn('client_id=', location)

    def test_authorize_route_persists_state_to_config_parameter(self):
        """Test that authorize route stores state+verifier in ir.config_parameter.

        After calling authorize, ir.config_parameter must have a row keyed
        'etsy.oauth.pending.<state>' containing code_verifier and shop_id.
        """
        self.authenticate(self.admin_user.login, self.admin_user.login)

        response = self.url_open(
            '/etsy/api/oauth/authorize?shop_id=%s' % self.etsy_shop.id,
            timeout=10,
            allow_redirects=False,
        )

        # Extract state from redirect URL
        location = response.headers.get('Location', '')
        self.assertIn('state=', location)

        # Parse state value from URL
        state_start = location.index('state=') + 6
        state_end = location.index('&', state_start) if '&' in location[state_start:] else len(location)
        state_value = location[state_start:state_end]

        # Verify state was stored in config_parameter
        stored_value = self.env['ir.config_parameter'].sudo().get_param(
            f'etsy.oauth.pending.{state_value}',
            default=None,
        )

        self.assertIsNotNone(
            stored_value,
            f'State row etsy.oauth.pending.{state_value} must exist in ir.config_parameter',
        )

        # Stored value should be JSON with code_verifier and shop_id
        try:
            state_data = json.loads(stored_value)
        except (json.JSONDecodeError, TypeError):
            self.fail(f'Stored state value must be valid JSON: {stored_value}')

        self.assertIn(
            'code_verifier',
            state_data,
            'Stored state must contain code_verifier',
        )
        self.assertEqual(
            state_data.get('shop_id'),
            self.etsy_shop.id,
            'Stored state must contain matching shop_id',
        )

    def test_callback_with_invalid_state_rejected(self):
        """Test that callback with invalid state is rejected.

        GET /etsy/api/oauth/callback?code=abc&state=does-not-exist should return
        400 or redirect with error, and should NOT create tokens.
        """
        self.authenticate(self.admin_user.login, self.admin_user.login)

        response = self.url_open(
            '/etsy/api/oauth/callback?code=test_auth_code_123&state=invalid_state_xyz',
            timeout=10,
        )

        # Should return 400 or redirect with error
        self.assertIn(
            response.status_code,
            [400, 303, 302],
            'Invalid state should result in error response',
        )

        # etsy_shop should NOT have tokens
        self.etsy_shop.invalidate_recordset()
        self.assertFalse(
            self.etsy_shop.etsy_oauth_access_token,
            'No tokens should be written for invalid state',
        )

    def test_callback_with_valid_state_exchanges_token(self):
        """Test that callback with valid state exchanges code for tokens.

        1. Pre-seed an etsy.oauth.pending.<state> config row
        2. Mock requests.post to return access token response
        3. GET /etsy/api/oauth/callback?code=xxx&state=yyy
        4. Verify:
           - State row is consumed (deleted)
           - etsy.shop has access_token, refresh_token, token_expires_at
           - User is redirected to success page
        """
        # First, manually create a state row (simulating authorize route)
        import secrets
        state = secrets.token_urlsafe(32)
        code_verifier = 'test_verifier_' + 'A' * 50  # RFC 7636 compliant
        shop_id = self.etsy_shop.id

        self.env['ir.config_parameter'].sudo().set_param(
            f'etsy.oauth.pending.{state}',
            json.dumps({
                'code_verifier': code_verifier,
                'shop_id': shop_id,
            }),
        )

        # Mock the token exchange response from Etsy. Include the
        # four E1-approved scopes (P1-10 scope assertion) — without
        # them the callback hard-fails the grant.
        token_response = {
            'access_token': 'test_access_token_abc123',
            'refresh_token': 'test_refresh_token_xyz789',
            'expires_in': 3600,
            'token_type': 'bearer',
            'scope': 'transactions_r transactions_w listings_r '
                     'listings_w shops_r email_r',
        }

        with mock.patch(
            'odoo.addons.etsy_integration.controllers.etsy_oauth.exchange_code_for_token',
        ) as mock_exchange:
            mock_exchange.return_value = token_response

            self.authenticate(self.admin_user.login, self.admin_user.login)

            response = self.url_open(
                f'/etsy/api/oauth/callback?code=test_auth_code_abc&state={state}',
                timeout=10,
            )

        # Verify state row was consumed
        state_after = self.env['ir.config_parameter'].sudo().get_param(
            f'etsy.oauth.pending.{state}',
            default=None,
        )
        self.assertIsNone(
            state_after,
            f'State row etsy.oauth.pending.{state} must be consumed after callback',
        )

        # Verify tokens were written to etsy.shop. P1-10: raw
        # columns hold Fernet ciphertext now, so verify via the
        # decrypt helpers.
        self.etsy_shop.invalidate_recordset()
        self.assertEqual(
            self.etsy_shop._get_access_token(),
            'test_access_token_abc123',
            'Access token (decrypted) must match the value Etsy returned',
        )
        self.assertEqual(
            self.etsy_shop._get_refresh_token(),
            'test_refresh_token_xyz789',
            'Refresh token (decrypted) must match the value Etsy returned',
        )
        self.assertIsNotNone(
            self.etsy_shop.etsy_oauth_token_expires_at,
            'Token expiry must be set to ~now + expires_in seconds',
        )

    def test_callback_state_row_consumed_even_on_token_exchange_failure(self):
        """Test that state row is consumed even if token exchange fails.

        This prevents replay attacks. If Etsy returns 400 on token exchange,
        the state row should still be deleted so the auth code cannot be
        reused.
        """
        import secrets
        state = secrets.token_urlsafe(32)
        code_verifier = 'test_verifier_' + 'A' * 50

        self.env['ir.config_parameter'].sudo().set_param(
            f'etsy.oauth.pending.{state}',
            json.dumps({
                'code_verifier': code_verifier,
                'shop_id': self.etsy_shop.id,
            }),
        )

        # Mock token exchange to fail with a requests.RequestException
        # (matches the controller's narrow except clause — bare Exception
        # would not be caught and would surface as a 500 instead).
        import requests
        with mock.patch(
            'odoo.addons.etsy_integration.controllers.etsy_oauth.exchange_code_for_token',
        ) as mock_exchange:
            mock_exchange.side_effect = requests.HTTPError('Invalid grant')

            self.authenticate(self.admin_user.login, self.admin_user.login)

            response = self.url_open(
                f'/etsy/api/oauth/callback?code=bad_code&state={state}',
                timeout=10,
            )

        # State row MUST still be consumed (even though exchange failed)
        state_after = self.env['ir.config_parameter'].sudo().get_param(
            f'etsy.oauth.pending.{state}',
            default=None,
        )
        self.assertIsNone(
            state_after,
            'State row must be consumed even on token exchange failure (prevent replay)',
        )

        # Shop should NOT have tokens (exchange failed)
        self.etsy_shop.invalidate_recordset()
        self.assertFalse(
            self.etsy_shop.etsy_oauth_access_token,
            'No tokens should be written if exchange fails',
        )

    def test_callback_requires_code_and_state_params(self):
        """Test that callback rejects requests missing code or state.

        GET /etsy/api/oauth/callback without code or state should return 400.
        """
        self.authenticate(self.admin_user.login, self.admin_user.login)

        # Missing state
        response = self.url_open(
            '/etsy/api/oauth/callback?code=test_code',
            timeout=10,
        )
        self.assertEqual(
            response.status_code,
            400,
            'Missing state should return 400',
        )

        # Missing code
        response = self.url_open(
            '/etsy/api/oauth/callback?state=test_state',
            timeout=10,
        )
        self.assertEqual(
            response.status_code,
            400,
            'Missing code should return 400',
        )
