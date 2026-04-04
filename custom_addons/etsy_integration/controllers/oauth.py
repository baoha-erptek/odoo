"""OAuth2 callback controller for Gmail authorization flow.

Handles the redirect from Google's OAuth2 consent screen, exchanges
the authorization code for tokens, and stores the refresh token in
Odoo's system parameters.
"""
import logging

import requests

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

_TOKEN_URL = 'https://oauth2.googleapis.com/token'
_REQUEST_TIMEOUT = 15

# Config parameter key used to store the OAuth state nonce
_STATE_PARAM_KEY = 'etsy_integration.oauth_state'


class EtsyOAuthController(http.Controller):
    """Controller for Google OAuth2 callback during Gmail authorization."""

    @http.route(
        '/etsy/oauth/callback',
        type='http',
        auth='user',
        methods=['GET'],
        csrf=False,
    )
    def oauth_callback(self, code=None, error=None, state=None, **kw):
        """Handle the OAuth2 redirect from Google.

        Validates the state parameter to prevent CSRF, exchanges the
        authorization code for tokens, and stores the refresh_token.
        """
        if error:
            _logger.warning('OAuth callback received error: %s', error)
            return request.render(
                'etsy_integration.oauth_error_page',
                {'error_message': _('Authorization was denied: %s', error)},
            )

        if not code:
            _logger.warning('OAuth callback called without code or error')
            return request.render(
                'etsy_integration.oauth_error_page',
                {'error_message': _('No authorization code received.')},
            )

        # Sudo required: reading system config parameters (oauth state nonce,
        # gmail credentials) not accessible to regular users via ACLs
        icp = request.env['ir.config_parameter'].sudo()

        # Validate OAuth state parameter to prevent CSRF attacks
        expected_state = icp.get_param(_STATE_PARAM_KEY, '')
        if not expected_state or state != expected_state:
            _logger.warning('OAuth callback: state mismatch (CSRF protection)')
            return request.render(
                'etsy_integration.oauth_error_page',
                {'error_message': _(
                    'Invalid state parameter. Please restart the '
                    'authorization flow from Settings.'
                )},
            )
        # Clear the state nonce after validation (single use)
        icp.set_param(_STATE_PARAM_KEY, '')

        client_id = icp.get_param('etsy_integration.gmail_client_id', '')
        client_secret = icp.get_param('etsy_integration.gmail_client_secret', '')
        base_url = icp.get_param('web.base.url', '')
        redirect_uri = base_url + '/etsy/oauth/callback'

        if not client_id or not client_secret:
            _logger.error('OAuth callback: missing client_id or client_secret in config')
            return request.render(
                'etsy_integration.oauth_error_page',
                {'error_message': _(
                    'Gmail Client ID or Client Secret is not configured. '
                    'Please set them in Settings before authorizing.'
                )},
            )

        try:
            response = requests.post(
                _TOKEN_URL,
                data={
                    'code': code,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri,
                    'grant_type': 'authorization_code',
                },
                timeout=_REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            _logger.exception('OAuth token exchange request failed')
            return request.render(
                'etsy_integration.oauth_error_page',
                {'error_message': _('Token exchange request failed: %s', str(exc))},
            )

        if not response.ok:
            _logger.error(
                'OAuth token exchange failed (%s): %s',
                response.status_code,
                response.text[:500],
            )
            return request.render(
                'etsy_integration.oauth_error_page',
                {'error_message': _(
                    'Token exchange failed (HTTP %s). '
                    'Please verify your credentials and try again.',
                    response.status_code,
                )},
            )

        token_data = response.json()
        refresh_token = token_data.get('refresh_token')

        if not refresh_token:
            _logger.error(
                'OAuth token response missing refresh_token. '
                'Ensure access_type=offline and prompt=consent were used.'
            )
            return request.render(
                'etsy_integration.oauth_error_page',
                {'error_message': _(
                    'No refresh token received from Google. '
                    'Please revoke access at https://myaccount.google.com/permissions '
                    'and try again.'
                )},
            )

        icp.set_param('etsy_integration.gmail_refresh_token', refresh_token)
        _logger.debug('Gmail OAuth2 refresh token stored successfully')

        return request.redirect(
            '/odoo/settings?searchTerms=Etsy#etsy_integration'
        )
