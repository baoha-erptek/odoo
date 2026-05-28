"""Pure-function PKCE tests for Etsy OAuth2 flow (no DB, no HTTP).

These tests verify the cryptographic correctness of the OAuth2 PKCE
implementation according to RFC 7636. No database or HTTP calls.

PHASE: RED (failing tests — implementation does not exist yet)
"""
import base64
import hashlib
import re

from odoo.tests.common import TransactionCase


class TestEtsyOAuthPKCE(TransactionCase):
    """Test PKCE helper functions — pure cryptography, no DB or HTTP."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def test_code_verifier_length_in_rfc7636_range(self):
        """Test that code_verifier length is between 43 and 128 chars per RFC 7636 §4.1."""
        from odoo.addons.etsy_integration.services.etsy_oauth import (
            generate_code_verifier,
        )

        verifier = generate_code_verifier()

        self.assertGreaterEqual(
            len(verifier), 43, "Verifier must be at least 43 chars per RFC 7636"
        )
        self.assertLessEqual(
            len(verifier), 128, "Verifier must be at most 128 chars per RFC 7636"
        )

    def test_code_verifier_charset_url_safe(self):
        """Test that code_verifier uses only URL-safe base64 alphabet per RFC 7636 §4.1.

        Allowed: A-Z, a-z, 0-9, hyphen (-), period (.), underscore (_), tilde (~)
        """
        from odoo.addons.etsy_integration.services.etsy_oauth import (
            generate_code_verifier,
        )

        # RFC 7636 §4.1 defines unreserved characters
        # unreserved = ALPHA / DIGIT / "-" / "." / "_" / "~"
        allowed_pattern = r'^[A-Za-z0-9\-._~]+$'

        for _ in range(10):
            verifier = generate_code_verifier()
            self.assertRegex(
                verifier,
                allowed_pattern,
                "Verifier must contain only unreserved chars [A-Za-z0-9\\-._~]",
            )

    def test_code_verifier_uniqueness_across_calls(self):
        """Test that 100 generated verifiers are all unique (randomness check)."""
        from odoo.addons.etsy_integration.services.etsy_oauth import (
            generate_code_verifier,
        )

        verifiers = [generate_code_verifier() for _ in range(100)]
        unique_verifiers = set(verifiers)

        self.assertEqual(
            len(unique_verifiers),
            100,
            "All 100 generated verifiers must be unique",
        )

    def test_code_challenge_is_sha256_base64url_of_verifier(self):
        """Test that code_challenge = base64url(sha256(verifier)) with no padding.

        Verified test vector: SHA256 of the ASCII bytes of 'hello' is
        2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824 (hex).
        Encoded base64url-no-pad, that becomes the challenge below.
        """
        from odoo.addons.etsy_integration.services.etsy_oauth import (
            generate_code_challenge,
        )

        test_verifier = 'hello'
        expected_challenge = 'LPJNul-wow4m6DsqxbninhsWHlwfp0JecwQzYpOLmCQ'

        challenge = generate_code_challenge(test_verifier)

        self.assertEqual(
            challenge,
            expected_challenge,
            "Code challenge must equal base64url(sha256(verifier)) without padding",
        )

        # Verify it's base64url without padding
        self.assertNotIn(
            '=', challenge, "Code challenge must not contain padding ('=')"
        )

    def test_code_challenge_base64url_properties(self):
        """Test that code_challenge uses base64url encoding (- and _ instead of + and /)."""
        from odoo.addons.etsy_integration.services.etsy_oauth import (
            generate_code_verifier,
            generate_code_challenge,
        )

        verifier = generate_code_verifier()
        challenge = generate_code_challenge(verifier)

        # base64url alphabet: A-Za-z0-9-_
        # Should NOT contain + or / (standard base64)
        self.assertNotIn('+', challenge, "Must use base64url (- not +)")
        self.assertNotIn('/', challenge, "Must use base64url (_ not /)")
        self.assertNotIn('=', challenge, "Must not contain padding")

    def test_build_authorize_url_includes_required_params(self):
        """Test that authorize URL contains all required PKCE parameters.

        Required per RFC 7636 §4.1 and Etsy API docs:
        - response_type=code
        - client_id
        - redirect_uri
        - scope (space-separated)
        - state
        - code_challenge
        - code_challenge_method=S256
        """
        from odoo.addons.etsy_integration.services.etsy_oauth import (
            build_authorize_url,
        )

        client_id = 'test_client_id_12345'
        redirect_uri = 'http://localhost:8069/etsy/oauth/callback'
        scopes = 'transactions_r transactions_w listings_r listings_w shops_r email_r'
        state = 'test_state_xyz_789'
        code_challenge = 'E9Mrozoa2owWoUeS_Z6OQ3OKN2iCHaEc292iNLsrgS8'

        url = build_authorize_url(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scopes=scopes,
            state=state,
            code_challenge=code_challenge,
        )

        # URL must start with Etsy authorization endpoint
        self.assertTrue(
            url.startswith('https://www.etsy.com/oauth/connect'),
            'URL must point to Etsy OAuth connect endpoint',
        )

        # Parse query params
        query_start = url.index('?') + 1
        query_string = url[query_start:]

        # All required params must be present
        self.assertIn('response_type=code', url)
        self.assertIn(f'client_id={client_id}', url)
        self.assertIn(f'redirect_uri=', url)  # will be URL-encoded
        self.assertIn('scope=', url)
        self.assertIn(f'state={state}', url)
        self.assertIn(f'code_challenge={code_challenge}', url)
        self.assertIn('code_challenge_method=S256', url)

    def test_build_authorize_url_scopes_space_separated(self):
        """Test that scopes are properly space-separated and URL-encoded.

        Input: "transactions_r transactions_w listings_r listings_w shops_r email_r"
        Expected in URL: scope=transactions_r%20transactions_w%20listings_r%20...
        """
        from odoo.addons.etsy_integration.services.etsy_oauth import (
            build_authorize_url,
        )

        scopes = 'transactions_r transactions_w listings_r listings_w shops_r email_r'
        url = build_authorize_url(
            client_id='test_id',
            redirect_uri='http://localhost:8069/etsy/oauth/callback',
            scopes=scopes,
            state='test_state',
            code_challenge='test_challenge',
        )

        # URL encoding: space becomes %20
        expected_scope_encoded = (
            'scope=transactions_r%20transactions_w%20listings_r%20'
            'listings_w%20shops_r%20email_r'
        )
        self.assertIn(
            expected_scope_encoded,
            url,
            'Scopes must be space-separated and URL-encoded',
        )

    def test_exchange_code_for_token_request_structure(self):
        """Test that exchange_code_for_token builds the correct POST request.

        This test verifies the function would POST the correct payload to Etsy.
        Actual HTTP is mocked by the caller.
        """
        # This test is a placeholder for Phase 2 (GREEN)
        # The implementation will POST to https://api.etsy.com/v3/oauth/token
        # with grant_type=authorization_code, code, client_id, client_secret, redirect_uri, code_verifier
        pass

    def test_refresh_access_token_request_structure(self):
        """Test that refresh_access_token builds the correct POST request.

        This test verifies the function would POST the correct payload to Etsy.
        Actual HTTP is mocked by the caller.
        """
        # This test is a placeholder for Phase 2 (GREEN)
        # The implementation will POST to https://api.etsy.com/v3/oauth/token
        # with grant_type=refresh_token, refresh_token, client_id, client_secret
        pass
