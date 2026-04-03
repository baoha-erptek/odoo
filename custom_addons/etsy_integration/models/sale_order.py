import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    etsy_order_id = fields.Char(
        string='Etsy Order ID', index=True, copy=False,
        help='Unique Etsy order identifier from the notification email')
    etsy_shop_id = fields.Many2one(
        'etsy.shop', string='Etsy Shop', index=True, ondelete='restrict')
    etsy_note_from_buyer = fields.Text(string='Note from Buyer')
    etsy_gift_message = fields.Text(string='Gift Message')
    etsy_shipping_service = fields.Char(string='Shipping Service')
    etsy_processing_time = fields.Char(string='Processing Time')
    etsy_shipping_cost = fields.Float(string='Etsy Shipping Cost', digits=(12, 2))
    etsy_discount_code = fields.Char(string='Discount Code')
    etsy_subtotal = fields.Float(string='Etsy Subtotal', digits=(12, 2))
    etsy_email_log_id = fields.Many2one(
        'etsy.email.log', string='Source Email', ondelete='set null')
    is_etsy_order = fields.Boolean(
        string='Is Etsy Order', compute='_compute_is_etsy_order', store=True)

    _sql_constraints = [
        ('etsy_order_id_unique', 'UNIQUE(etsy_order_id)',
         'Etsy Order ID must be unique!'),
    ]

    @api.depends('etsy_order_id')
    def _compute_is_etsy_order(self):
        for order in self:
            order.is_etsy_order = bool(order.etsy_order_id)

    @api.model
    def _cron_fetch_etsy_emails(self):
        """Scheduled action: fetch and process Etsy order emails."""
        from ..services.gmail_client import GmailClient
        from ..services.email_parser import parse_etsy_email
        from ..services.order_creator import OrderCreator

        ICP = self.env['ir.config_parameter'].sudo()
        client_id = ICP.get_param('etsy_integration.gmail_client_id', '')
        client_secret = ICP.get_param('etsy_integration.gmail_client_secret', '')
        refresh_token = ICP.get_param('etsy_integration.gmail_refresh_token', '')
        label = ICP.get_param('etsy_integration.gmail_label', 'ordertest2')

        if not all([client_id, client_secret, refresh_token]):
            _logger.warning(
                'Etsy Integration: Gmail credentials not configured. '
                'Go to Settings > Etsy Integration to set them up.')
            return

        gmail = GmailClient(client_id, client_secret, refresh_token)
        if not gmail.authenticate():
            _logger.error('Etsy Integration: Gmail authentication failed.')
            return

        raw_emails = gmail.fetch_labeled_emails(label)
        if not raw_emails:
            _logger.info('Etsy Integration: No new emails found.')
            return

        _logger.info('Etsy Integration: Processing %d emails.', len(raw_emails))
        creator = OrderCreator(self.env)
        processed_ids = []

        for raw_email in raw_emails:
            EmailLog = self.env['etsy.email.log']
            existing_log = EmailLog.search(
                [('gmail_message_id', '=', raw_email.message_id)], limit=1)
            if existing_log:
                _logger.info('Skipping already-processed email %s', raw_email.message_id)
                processed_ids.append(raw_email.message_id)
                continue

            log_vals = {
                'gmail_message_id': raw_email.message_id,
                'subject': raw_email.subject,
                'date_received': fields.Datetime.now(),
                'raw_body_text': raw_email.text_body,
                'raw_body_html': raw_email.html_body,
                'parse_status': 'failed',
            }

            result = parse_etsy_email(raw_email)

            if hasattr(result, 'error'):
                log_vals['error_message'] = result.error
                EmailLog.create(log_vals)
                _logger.warning(
                    'Etsy Integration: Parse failed for %s: %s',
                    raw_email.message_id, result.error)
                continue

            if creator.is_duplicate_order(result.order_id):
                log_vals['parse_status'] = 'skipped'
                log_vals['error_message'] = (
                    f'Duplicate order: {result.order_id}')
                EmailLog.create(log_vals)
                processed_ids.append(raw_email.message_id)
                continue

            email_log = EmailLog.create(log_vals)
            try:
                order = creator.process_parse_result(result, email_log.id)
                if order:
                    email_log.write({
                        'parse_status': 'success',
                        'sale_order_id': order.id,
                    })
                    processed_ids.append(raw_email.message_id)
                    _logger.info(
                        'Etsy Integration: Created order %s from email %s',
                        order.name, raw_email.message_id)
                else:
                    email_log.write({
                        'parse_status': 'skipped',
                        'error_message': 'Order already exists',
                    })
                    processed_ids.append(raw_email.message_id)
            except Exception as e:
                email_log.write({'error_message': str(e)})
                _logger.exception(
                    'Etsy Integration: Failed to create order from %s',
                    raw_email.message_id)

        if processed_ids:
            try:
                gmail.remove_label(processed_ids, label)
                _logger.info(
                    'Etsy Integration: Removed label from %d emails.',
                    len(processed_ids))
            except Exception:
                _logger.exception(
                    'Etsy Integration: Failed to remove label from emails.')

        _logger.info(
            'Etsy Integration: Cycle complete. %d/%d emails processed.',
            len(processed_ids), len(raw_emails))
