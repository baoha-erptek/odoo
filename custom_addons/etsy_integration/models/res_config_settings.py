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
