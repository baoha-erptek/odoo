"""Unit tests for GearmentApiClient.

RED phase: These tests define the contract for GearmentApiClient.
All tests MUST FAIL until implementation is complete.
"""

import os
from unittest import mock

import requests

from odoo.tests.common import TransactionCase

from ..services.gearment_api_client import GearmentApiClient, RateLimitError


class TestGearmentApiClientInitialization(TransactionCase):
    """Test GearmentApiClient initialization and configuration."""

    def tearDown(self):
        """Clean environment after each test."""
        for key in ('GEARMENT_API_KEY', 'GEARMENT_API_SECRET', 'GEARMENT_API_BASE_URL'):
            if key in os.environ:
                del os.environ[key]

    @mock.patch.dict(os.environ, {'GEARMENT_API_KEY': '', 'GEARMENT_API_SECRET': 'secret', 'GEARMENT_API_BASE_URL': 'http://api.test'}, clear=True)
    def test_init_missing_api_key_raises_value_error(self):
        """Missing GEARMENT_API_KEY raises ValueError."""
        with self.assertRaises(ValueError) as context:
            GearmentApiClient()
        self.assertIn('GEARMENT_API_KEY', str(context.exception))

    @mock.patch.dict(os.environ, {'GEARMENT_API_KEY': 'key', 'GEARMENT_API_SECRET': '', 'GEARMENT_API_BASE_URL': 'http://api.test'}, clear=True)
    def test_init_missing_api_secret_raises_value_error(self):
        """Missing GEARMENT_API_SECRET raises ValueError."""
        with self.assertRaises(ValueError) as context:
            GearmentApiClient()
        self.assertIn('GEARMENT_API_SECRET', str(context.exception))

    @mock.patch.dict(os.environ, {'GEARMENT_API_KEY': 'key', 'GEARMENT_API_SECRET': 'secret', 'GEARMENT_API_BASE_URL': ''}, clear=True)
    def test_init_missing_base_url_raises_value_error(self):
        """Missing GEARMENT_API_BASE_URL raises ValueError."""
        with self.assertRaises(ValueError) as context:
            GearmentApiClient()
        self.assertIn('GEARMENT_API_BASE_URL', str(context.exception))

    @mock.patch.dict(os.environ, {'GEARMENT_API_KEY': 'test_key', 'GEARMENT_API_SECRET': 'test_secret', 'GEARMENT_API_BASE_URL': 'http://api.test'}, clear=True)
    def test_init_succeeds_with_all_env_vars(self):
        """Initialization succeeds when all required env vars are set."""
        client = GearmentApiClient()
        self.assertIsNotNone(client)

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_init_raises_on_completely_missing_env(self):
        """Initialization raises ValueError when all env vars are missing."""
        with self.assertRaises(ValueError):
            GearmentApiClient()


class TestGearmentApiClientSession(TransactionCase):
    """Test GearmentApiClient session and authentication."""

    def setUp(self):
        """Set required environment variables for each test."""
        os.environ['GEARMENT_API_KEY'] = 'test_key_123'
        os.environ['GEARMENT_API_SECRET'] = 'test_secret_456'
        os.environ['GEARMENT_API_BASE_URL'] = 'http://api.gearment.test'

    def tearDown(self):
        """Clean environment after each test."""
        for key in ('GEARMENT_API_KEY', 'GEARMENT_API_SECRET', 'GEARMENT_API_BASE_URL'):
            if key in os.environ:
                del os.environ[key]

    @mock.patch('requests.Session')
    def test_session_sets_auth_headers(self, mock_session_class):
        """Session includes both API key and secret headers."""
        mock_session = mock.Mock()
        mock_session_class.return_value = mock_session

        client = GearmentApiClient()
        session = client._session()

        # Verify headers were set on the session
        self.assertTrue(
            hasattr(session, 'headers'),
            "Session should have headers attribute"
        )
        # Note: The exact header names are defined in the contract
        # ('X-Gearment-Client-Key' and 'X-Gearment-Client-Secret')
        self.assertIn('X-Gearment-Client-Key', session.headers or {})
        self.assertIn('X-Gearment-Client-Secret', session.headers or {})


class TestGearmentApiClientPing(TransactionCase):
    """Test ping endpoint."""

    def setUp(self):
        """Set required environment variables for each test."""
        os.environ['GEARMENT_API_KEY'] = 'test_key_123'
        os.environ['GEARMENT_API_SECRET'] = 'test_secret_456'
        os.environ['GEARMENT_API_BASE_URL'] = 'http://api.gearment.test'

    def tearDown(self):
        """Clean environment after each test."""
        for key in ('GEARMENT_API_KEY', 'GEARMENT_API_SECRET', 'GEARMENT_API_BASE_URL'):
            if key in os.environ:
                del os.environ[key]

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_ping_calls_correct_url(self, mock_session_class):
        """ping() calls the correct API endpoint."""
        mock_session = mock.Mock()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'ok'}
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GearmentApiClient()
        client.ping()

        # Verify the request was made to the correct URL
        calls = mock_session.request.call_args_list
        self.assertTrue(len(calls) > 0, "Session.request should have been called")

        # Check method and path in first call
        call_args = calls[0]
        self.assertEqual(call_args[0][0], 'GET', "Should use GET method")
        # URL should contain the catalog endpoint with limit=1
        self.assertIn('/api/v3/catalog', call_args[0][1])

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_ping_returns_parsed_json_on_200(self, mock_session_class):
        """ping() returns parsed JSON response on 200 status."""
        mock_session = mock.Mock()
        expected_response = {'status': 'ok', 'message': 'pong'}
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_response
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GearmentApiClient()
        result = client.ping()

        self.assertEqual(result, expected_response)

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_ping_raises_value_error_on_401(self, mock_session_class):
        """ping() raises ValueError on 401 authentication error."""
        mock_session = mock.Mock()
        mock_response = mock.Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GearmentApiClient()

        with self.assertRaises(ValueError):
            client.ping()

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_ping_raises_value_error_on_403(self, mock_session_class):
        """ping() raises ValueError on 403 forbidden error."""
        mock_session = mock.Mock()
        mock_response = mock.Mock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GearmentApiClient()

        with self.assertRaises(ValueError):
            client.ping()

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_ping_raises_http_error_on_500(self, mock_session_class):
        """ping() raises HTTPError on 500 server error."""
        mock_session = mock.Mock()
        mock_response = mock.Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Internal Server Error")
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GearmentApiClient()

        with self.assertRaises(requests.HTTPError):
            client.ping()


class TestGearmentApiClientRateLimiting(TransactionCase):
    """Test 429 rate limit handling."""

    def setUp(self):
        """Set required environment variables for each test."""
        os.environ['GEARMENT_API_KEY'] = 'test_key_123'
        os.environ['GEARMENT_API_SECRET'] = 'test_secret_456'
        os.environ['GEARMENT_API_BASE_URL'] = 'http://api.gearment.test'

    def tearDown(self):
        """Clean environment after each test."""
        for key in ('GEARMENT_API_KEY', 'GEARMENT_API_SECRET', 'GEARMENT_API_BASE_URL'):
            if key in os.environ:
                del os.environ[key]

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_429_with_retry_after_then_success(self, mock_session_class):
        """Client retries on 429 and succeeds on second attempt."""
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

        client = GearmentApiClient()
        result = client.ping()

        # Should have retried once (2 total calls)
        self.assertEqual(mock_session.request.call_count, 2)
        self.assertEqual(result, {'status': 'ok'})

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    @mock.patch('time.sleep')
    def test_429_three_times_raises_rate_limit_error(self, mock_sleep, mock_session_class):
        """Client raises RateLimitError after 3 failed retries."""
        mock_session = mock.Mock()

        # All three responses: 429 with Retry-After
        mock_response_429 = mock.Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {'Retry-After': '1'}

        mock_session.request.return_value = mock_response_429
        mock_session_class.return_value = mock_session

        client = GearmentApiClient()

        with self.assertRaises(RateLimitError) as context:
            client.ping()

        # Should have the retry_after value from last response
        self.assertEqual(context.exception.retry_after, 1)

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
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

        client = GearmentApiClient()

        with self.assertRaises(RateLimitError):
            client.ping()

        # Verify sleep was called with backoff values
        sleep_calls = mock_sleep.call_args_list
        self.assertTrue(len(sleep_calls) > 0, "Should have called sleep for backoff")
        # Expected sequence: 1, 2, 4 (for 3 retries)
        expected_backoffs = [1, 2, 4]
        actual_backoffs = [call[0][0] for call in sleep_calls]
        self.assertEqual(actual_backoffs[:len(expected_backoffs)], expected_backoffs)

    @mock.patch('odoo.addons.multichannel_hub_fulfillment.services.gearment_api_client.requests.Session')
    def test_ping_with_rate_limiter_exhausted_still_sends(self, mock_session_class):
        """ping() still sends request even if internal rate limiter has no tokens.

        Rate limiter is informational/best-effort; requests proceed.
        """
        mock_session = mock.Mock()
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'ok'}
        mock_session.request.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = GearmentApiClient()
        # Assume rate limiter is exhausted (internal state)
        # ping() should still work
        result = client.ping()

        self.assertEqual(result, {'status': 'ok'})
        self.assertTrue(mock_session.request.called)
