import secrets
from urllib.parse import urlencode

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    etsy_gmail_label = fields.Char(
        string='Gmail Label',
        config_parameter='etsy_integration.gmail_label',
        default='ordertest2',
        help='Gmail label used to filter Etsy order emails')
    etsy_gmail_client_id = fields.Char(
        string='Gmail Client ID',
        config_parameter='etsy_integration.gmail_client_id')
    etsy_gmail_client_secret = fields.Char(
        string='Gmail Client Secret',
        config_parameter='etsy_integration.gmail_client_secret')
    etsy_gmail_refresh_token = fields.Char(
        string='Gmail Refresh Token',
        config_parameter='etsy_integration.gmail_refresh_token')
    etsy_cron_interval = fields.Integer(
        string='Fetch Interval (minutes)',
        config_parameter='etsy_integration.cron_interval',
        default=10)
    etsy_auto_confirm_email = fields.Boolean(
        string='Auto-confirm cron-imported orders',
        config_parameter='etsy_integration.auto_confirm_email',
        default=False,
        help='When enabled, orders created by the email cron are immediately '
             'confirmed, their pickings validated, and marked as invoiced '
             '(see R5). Default off — operators may want to review first.')

    def action_start_oauth_flow(self):
        """Initiate the Google OAuth2 authorization flow.

        Builds the authorization URL with the required parameters and
        redirects the user to Google's consent screen. On approval,
        Google redirects back to /etsy/oauth/callback with the code.

        Returns:
            An ir.actions.act_url action that opens the Google consent page.
        """
        self.ensure_one()
        # Sudo required: reading system config parameters (gmail credentials)
        # not accessible to regular users via ACLs
        icp = self.env['ir.config_parameter'].sudo()
        client_id = icp.get_param('etsy_integration.gmail_client_id', '')

        if not client_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'OAuth Setup Incomplete',
                    'message': (
                        'Please configure the Gmail Client ID first, '
                        'then save the settings before authorizing.'
                    ),
                    'type': 'danger',
                },
            }

        base_url = icp.get_param('web.base.url', '')
        redirect_uri = base_url + '/etsy/oauth/callback'

        # Generate and store a cryptographic nonce to prevent CSRF
        state = secrets.token_urlsafe(32)
        icp.set_param('etsy_integration.oauth_state', state)

        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'https://www.googleapis.com/auth/gmail.modify',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state,
        }
        auth_url = 'https://accounts.google.com/o/oauth2/auth?' + urlencode(params)

        return {
            'type': 'ir.actions.act_url',
            'url': auth_url,
            'target': 'self',
        }

    def action_test_gmail_connection(self):
        self.ensure_one()
        from ..services.gmail_client import GmailClient
        client_id = self.etsy_gmail_client_id or ''
        client_secret = self.etsy_gmail_client_secret or ''
        refresh_token = self.etsy_gmail_refresh_token or ''

        if not all([client_id, client_secret, refresh_token]):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Failed',
                    'message': 'Please fill in all Gmail credentials first.',
                    'type': 'danger',
                },
            }

        gmail = GmailClient(client_id, client_secret, refresh_token)
        success, message = gmail.test_connection()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Connection Test',
                'message': message,
                'type': 'success' if success else 'danger',
            },
        }
