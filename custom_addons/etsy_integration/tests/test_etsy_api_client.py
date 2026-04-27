"""Unit tests for EtsyApiClient.

RED phase: These tests define the contract for EtsyApiClient.
All tests MUST FAIL until implementation is complete.
"""

import os
from datetime import datetime, timedelta
from unittest import mock

import requests

from odoo.tests.common import TransactionCase, tagged

from ..services.etsy_api_client import EtsyApiClient, RateLimitError


@tagged('post_install', '-at_install')
class TestEtsyApiClientInitialization(TransactionCase):
    """Test EtsyApiClient initialization with etsy.shop record."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test API Shop',
        })
        # Tokens written via sudo() because the fields have group_system ACL
        cls.shop.sudo().write({
            'etsy_oauth_access_token': 'access_abc123',
            'etsy_oauth_refresh_token': 'refresh_xyz789',
            'etsy_oauth_token_expires_at': datetime(2099, 1, 1, 0, 0, 0),
        })
        # Mock _read_credentials so we don't need secrets/credentials.json
        cls._creds_patcher = mock.patch(
            'odoo.addons.etsy_integration.services.etsy_api_client._read_credentials',
            return_value={'client_id': 'test_client_id', 'client_secret': 'test_secret'},
        )
        cls._creds_patcher.start()
        cls.addClassCleanup(cls._creds_patcher.stop)

    def test_init_succeeds_with_valid_shop(self):
        """Initialization succeeds when shop has all three OAuth fields populated."""
        client = EtsyApiClient(self.shop)
        self.assertIsNotNone(client)

    def test_init_missing_access_token_raises(self):
        """Missing etsy_oauth_access_token raises ValueError."""
        shop_no_access = self.env['etsy.shop'].create({
            'name': 'No Access Token Shop',
        })
        shop_no_access.sudo().write({
            'etsy_oauth_access_token': '',
            'etsy_oauth_refresh_token': 'refresh_xyz789',
            'etsy_oauth_token_expires_at': datetime(2099, 1, 1, 0, 0, 0),
        })
        with self.assertRaises(ValueError) as context:
            EtsyApiClient(shop_no_access)
        self.assertIn('access_token', str(context.exception))

    def test_init_missing_refresh_token_raises(self):
        """Missing etsy_oauth_refresh_token raises ValueError."""
        shop_no_refresh = self.env['etsy.shop'].create({
            'name': 'No Refresh Token Shop',
        })
        shop_no_refresh.sudo().write({
            'etsy_oauth_access_token': 'access_abc123',
            'etsy_oauth_refresh_token': '',
            'etsy_oauth_token_expires_at': datetime(2099, 1, 1, 0, 0, 0),
        })
        with self.assertRaises(ValueError) as context:
            EtsyApiClient(shop_no_refresh)
        self.assertIn('refresh_token', str(context.exception))

    def test_init_missing_credentials_file_raises(self):
        """Missing credentials file surfaces ValueError (FileNotFoundError wrapped)."""
        with mock.patch(
            'odoo.addons.etsy_integration.services.etsy_api_client._read_credentials',
            side_effect=FileNotFoundError('secrets/credentials.json not found'),
        ):
            with self.assertRaises(ValueError):
                EtsyApiClient(self.shop)


@tagged('post_install', '-at_install')
class TestEtsyApiClientSession(TransactionCase):
    """Test EtsyApiClient session and authentication headers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Session Shop',
        })
        cls.shop.sudo().write({
            'etsy_oauth_access_token': 'access_abc123',
            'etsy_oauth_refresh_token': 'refresh_xyz789',
            'etsy_oauth_token_expires_at': datetime(2099, 1, 1, 0, 0, 0),
        })
        cls._creds_patcher = mock.patch(
            'odoo.addons.etsy_integration.services.etsy_api_client._read_credentials',
            return_value={'client_id': 'test_client_id', 'client_secret': 'test_secret'},
        )
        cls._creds_patcher.start()
        cls.addClassCleanup(cls._creds_patcher.stop)

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    def test_session_sets_bearer_authorization_header(self, mock_session_class):
        """Session includes Authorization: Bearer <access_token> header."""
        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session

        client = EtsyApiClient(self.shop)
        session = client._session()

        self.assertIn('Authorization', session.headers)
        self.assertTrue(session.headers['Authorization'].startswith('Bearer '))
        self.assertIn('access_abc123', session.headers['Authorization'])

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    def test_session_sets_x_api_key_header(self, mock_session_class):
        """Session includes x-api-key header with client_id."""
        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session

        client = EtsyApiClient(self.shop)
        session = client._session()

        self.assertIn('x-api-key', session.headers)
        self.assertEqual(session.headers['x-api-key'], 'test_client_id')


@tagged('post_install', '-at_install')
class TestEtsyApiClientPing(TransactionCase):
    """Test ping endpoint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Ping Shop',
        })
        cls.shop.sudo().write({
            'etsy_oauth_access_token': 'access_abc123',
            'etsy_oauth_refresh_token': 'refresh_xyz789',
            'etsy_oauth_token_expires_at': datetime(2099, 1, 1, 0, 0, 0),
        })
        cls._creds_patcher = mock.patch(
            'odoo.addons.etsy_integration.services.etsy_api_client._read_credentials',
            return_value={'client_id': 'test_client_id', 'client_secret': 'test_secret'},
        )
        cls._creds_patcher.start()
        cls.addClassCleanup(cls._creds_patcher.stop)

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    def test_ping_calls_users_me_endpoint(self, mock_session_class):
        """ping() calls the /users/me endpoint with GET method."""
        mock_session = mock.Mock()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'user_id': 12345}
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = EtsyApiClient(self.shop)
        client.ping()

        # Verify the request was made to the correct endpoint
        calls = mock_session.request.call_args_list
        self.assertTrue(len(calls) > 0, "Session.request should have been called")

        call_args = calls[0]
        self.assertEqual(call_args[0][0], 'GET', "Should use GET method")
        self.assertIn('/users/me', call_args[0][1])

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    def test_ping_returns_parsed_json_on_200(self, mock_session_class):
        """ping() returns parsed JSON response on 200 status."""
        mock_session = mock.Mock()
        expected_response = {'user_id': 12345, 'login_name': 'test_shop'}
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = EtsyApiClient(self.shop)
        result = client.ping()

        self.assertEqual(result, expected_response)

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    def test_ping_raises_value_error_on_403(self, mock_session_class):
        """ping() raises ValueError on 403 forbidden error."""
        mock_session = mock.Mock()
        mock_response = mock.Mock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = EtsyApiClient(self.shop)

        with self.assertRaises(ValueError):
            client.ping()

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    def test_ping_raises_http_error_on_500(self, mock_session_class):
        """ping() raises HTTPError on 500 server error."""
        mock_session = mock.Mock()
        mock_response = mock.Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Internal Server Error")
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = EtsyApiClient(self.shop)

        with self.assertRaises(requests.HTTPError):
            client.ping()


@tagged('post_install', '-at_install')
class TestEtsyApiClientRateLimiting(TransactionCase):
    """Test 429 rate limit handling."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Rate Limit Shop',
        })
        cls.shop.sudo().write({
            'etsy_oauth_access_token': 'access_abc123',
            'etsy_oauth_refresh_token': 'refresh_xyz789',
            'etsy_oauth_token_expires_at': datetime(2099, 1, 1, 0, 0, 0),
        })
        cls._creds_patcher = mock.patch(
            'odoo.addons.etsy_integration.services.etsy_api_client._read_credentials',
            return_value={'client_id': 'test_client_id', 'client_secret': 'test_secret'},
        )
        cls._creds_patcher.start()
        cls.addClassCleanup(cls._creds_patcher.stop)

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    def test_429_with_retry_after_then_success(self, mock_session_class):
        """Client retries on 429 with Retry-After and succeeds on second attempt."""
        mock_session = mock.Mock()

        # First response: 429 with Retry-After header
        mock_response_429 = mock.Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {'Retry-After': '0'}

        # Second response: 200 success
        mock_response_200 = mock.Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'status': 'ok'}

        mock_session.request.side_effect = [mock_response_429, mock_response_200]
        mock_session_class.return_value = mock_session

        client = EtsyApiClient(self.shop)
        result = client.ping()

        # Should have retried once (2 total calls)
        self.assertEqual(mock_session.request.call_count, 2)
        self.assertEqual(result, {'status': 'ok'})

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    @mock.patch('time.sleep')
    def test_429_three_times_raises_rate_limit_error(self, mock_sleep, mock_session_class):
        """Client raises RateLimitError after 3 failed retries."""
        mock_session = mock.Mock()

        # All responses: 429 with Retry-After
        mock_response_429 = mock.Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {'Retry-After': '1'}

        mock_session.request.return_value = mock_response_429
        mock_session_class.return_value = mock_session

        client = EtsyApiClient(self.shop)

        with self.assertRaises(RateLimitError) as context:
            client.ping()

        # Should have the retry_after value from last response
        self.assertEqual(context.exception.retry_after, 1)

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    @mock.patch('time.sleep')
    def test_429_without_retry_after_uses_backoff(self, mock_sleep, mock_session_class):
        """Client uses exponential backoff (1, 2, 4 seconds) when Retry-After is missing."""
        mock_session = mock.Mock()

        # All responses: 429 without Retry-After header
        mock_response_429 = mock.Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {}

        mock_session.request.return_value = mock_response_429
        mock_session_class.return_value = mock_session

        client = EtsyApiClient(self.shop)

        with self.assertRaises(RateLimitError):
            client.ping()

        # Verify sleep was called with backoff values
        sleep_calls = mock_sleep.call_args_list
        self.assertTrue(len(sleep_calls) > 0, "Should have called sleep for backoff")
        # Expected sequence: 1, 2, 4 (for 3 retries)
        expected_backoffs = [1, 2, 4]
        actual_backoffs = [call[0][0] for call in sleep_calls]
        self.assertEqual(actual_backoffs[:len(expected_backoffs)], expected_backoffs)

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    def test_retry_after_capped_at_60_seconds(self, mock_session_class):
        """Retry-After header is capped at 60 seconds."""
        mock_session = mock.Mock()

        # First response: 429 with excessive Retry-After
        mock_response_429 = mock.Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {'Retry-After': '999999'}

        # Second response: 200 success
        mock_response_200 = mock.Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'status': 'ok'}

        mock_session.request.side_effect = [mock_response_429, mock_response_200]
        mock_session_class.return_value = mock_session

        with mock.patch('time.sleep') as mock_sleep:
            client = EtsyApiClient(self.shop)
            result = client.ping()

            # Verify sleep was called with capped value
            self.assertEqual(result, {'status': 'ok'})
            sleep_calls = mock_sleep.call_args_list
            # First call should be with 60 (the cap)
            self.assertEqual(sleep_calls[0][0][0], 60)


@tagged('post_install', '-at_install')
class TestEtsyApiClient401Refresh(TransactionCase):
    """Test 401 authentication refresh behavior."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shop = cls.env['etsy.shop'].create({
            'name': 'Test Refresh Shop',
        })
        cls.shop.sudo().write({
            'etsy_oauth_access_token': 'access_abc123',
            'etsy_oauth_refresh_token': 'refresh_xyz789',
            'etsy_oauth_token_expires_at': datetime(2099, 1, 1, 0, 0, 0),
        })
        cls._creds_patcher = mock.patch(
            'odoo.addons.etsy_integration.services.etsy_api_client._read_credentials',
            return_value={'client_id': 'test_client_id', 'client_secret': 'test_secret'},
        )
        cls._creds_patcher.start()
        cls.addClassCleanup(cls._creds_patcher.stop)

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.etsy_oauth.refresh_access_token')
    def test_401_triggers_refresh_then_retry(self, mock_refresh, mock_session_class):
        """Client refreshes token on 401 and retries the original request."""
        mock_session = mock.Mock()

        # First response: 401 Unauthorized
        mock_response_401 = mock.Mock()
        mock_response_401.status_code = 401

        # Second response: 200 success after refresh
        mock_response_200 = mock.Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'user_id': 12345}

        mock_session.request.side_effect = [mock_response_401, mock_response_200]
        mock_session_class.return_value = mock_session

        # Mock the refresh response
        mock_refresh.return_value = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_in': 3600,
        }

        client = EtsyApiClient(self.shop)
        result = client.ping()

        # Verify refresh was called
        self.assertTrue(mock_refresh.called)
        # Verify shop record was updated (Odoo 19: invalidate_recordset, no .refresh())
        self.shop.invalidate_recordset()
        self.assertEqual(self.shop.sudo().etsy_oauth_access_token, 'new_access_token')
        self.assertEqual(self.shop.sudo().etsy_oauth_refresh_token, 'new_refresh_token')
        # Verify ping succeeded
        self.assertEqual(result, {'user_id': 12345})

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.etsy_oauth.refresh_access_token')
    def test_401_then_refresh_fails_raises_value_error(self, mock_refresh, mock_session_class):
        """If refresh fails, client raises ValueError."""
        mock_session = mock.Mock()

        # First response: 401 Unauthorized
        mock_response_401 = mock.Mock()
        mock_response_401.status_code = 401

        mock_session.request.return_value = mock_response_401
        mock_session_class.return_value = mock_session

        # Mock refresh failure
        mock_refresh.side_effect = requests.HTTPError("Refresh token expired")

        client = EtsyApiClient(self.shop)

        with self.assertRaises(ValueError) as context:
            client.ping()

        self.assertIn('Etsy token refresh failed', str(context.exception))

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.etsy_oauth.refresh_access_token')
    def test_401_only_one_refresh_attempt_per_request(self, mock_refresh, mock_session_class):
        """After one refresh, if 401 occurs again, do not loop infinitely."""
        mock_session = mock.Mock()

        # Both responses: 401 Unauthorized
        mock_response_401 = mock.Mock()
        mock_response_401.status_code = 401

        mock_session.request.return_value = mock_response_401
        mock_session_class.return_value = mock_session

        # Mock successful refresh
        mock_refresh.return_value = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_in': 3600,
        }

        client = EtsyApiClient(self.shop)

        with self.assertRaises(ValueError):
            client.ping()

        # Verify refresh was called exactly once (not looping)
        self.assertEqual(mock_refresh.call_count, 1)

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.etsy_oauth.refresh_access_token')
    def test_proactive_refresh_when_token_expires_within_60s(self, mock_refresh, mock_session_class):
        """Token is refreshed proactively if expiration is within 60 seconds."""
        # Set token to expire in 30 seconds
        self.shop.sudo().write({
            'etsy_oauth_token_expires_at': datetime.now() + timedelta(seconds=30),
        })

        mock_session = mock.Mock()
        mock_response_200 = mock.Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'user_id': 12345}
        mock_session.request.return_value = mock_response_200
        mock_session_class.return_value = mock_session

        # Mock successful refresh
        mock_refresh.return_value = {
            'access_token': 'proactive_access_token',
            'refresh_token': 'proactive_refresh_token',
            'expires_in': 3600,
        }

        client = EtsyApiClient(self.shop)
        result = client.ping()

        # Verify refresh was called BEFORE the request
        self.assertTrue(mock_refresh.called)
        # Verify the new token was used in request
        call_args = mock_session.request.call_args_list
        self.assertTrue(len(call_args) > 0)

    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.requests.Session')
    @mock.patch('odoo.addons.etsy_integration.services.etsy_api_client.etsy_oauth.refresh_access_token')
    def test_no_proactive_refresh_when_token_valid_for_long_time(self, mock_refresh, mock_session_class):
        """Token is NOT refreshed if expiration is far in the future."""
        # Set token to expire in 1 hour
        self.shop.sudo().write({
            'etsy_oauth_token_expires_at': datetime.now() + timedelta(hours=1),
        })

        mock_session = mock.Mock()
        mock_response_200 = mock.Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {'user_id': 12345}
        mock_session.request.return_value = mock_response_200
        mock_session_class.return_value = mock_session

        client = EtsyApiClient(self.shop)
        result = client.ping()

        # Verify refresh was NOT called
        self.assertFalse(mock_refresh.called)
        # Verify ping still succeeded
        self.assertEqual(result, {'user_id': 12345})
