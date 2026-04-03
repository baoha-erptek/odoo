import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class EtsyEmailLog(models.Model):
    _name = 'etsy.email.log'
    _description = 'Etsy Email Processing Log'
    _order = 'create_date desc'

    gmail_message_id = fields.Char(
        string='Gmail Message ID', required=True, index=True)
    subject = fields.Char(string='Email Subject')
    date_received = fields.Datetime(string='Date Received')
    raw_body_text = fields.Text(string='Raw Body (Text)')
    raw_body_html = fields.Text(string='Raw Body (HTML)')
    parse_status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped (Duplicate)'),
    ], string='Status', required=True, index=True, default='failed')
    error_message = fields.Text(string='Error Message')
    sale_order_id = fields.Many2one(
        'sale.order', string='Created Order', ondelete='set null')
    retry_count = fields.Integer(string='Retry Count', default=0)

    _sql_constraints = [
        ('gmail_message_id_unique', 'UNIQUE(gmail_message_id)',
         'Gmail Message ID must be unique!'),
    ]

    def action_view_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
        }

    def action_retry_parse(self):
        self.ensure_one()
        if self.parse_status != 'failed':
            return
        self.retry_count += 1
        from ..services.email_parser import parse_etsy_email, RawEmail
        raw = RawEmail(
            message_id=self.gmail_message_id,
            subject=self.subject or '',
            date=str(self.date_received or ''),
            text_body=self.raw_body_text or '',
            html_body=self.raw_body_html or '',
        )
        result = parse_etsy_email(raw)
        if hasattr(result, 'error'):
            self.error_message = result.error
            return
        from ..services.order_creator import OrderCreator
        creator = OrderCreator(self.env)
        order = creator.process_parse_result(result, self.id)
        if order:
            self.write({
                'parse_status': 'success',
                'sale_order_id': order.id,
                'error_message': False,
            })
