import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class EtsyEmailLog(models.Model):
    _name = 'etsy.email.log'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Etsy Email Processing Log'
    _order = 'create_date desc'

    gmail_message_id = fields.Char(
        string='Gmail Message ID', required=True, index=True)
    subject = fields.Char(string='Email Subject')
    date_received = fields.Datetime(string='Date Received')
    raw_body_text = fields.Text(
        string='Raw Body (Text)',
        groups='sales_team.group_sale_manager')
    raw_body_html = fields.Text(
        string='Raw Body (HTML)',
        groups='sales_team.group_sale_manager')
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

    def _check_parse_failures(self):
        """Check for consecutive parse failures and alert admin if threshold exceeded."""
        recent_logs = self.search([], order='create_date desc', limit=20)
        consecutive_failures = 0
        for log in recent_logs:
            if log.parse_status == 'failed':
                consecutive_failures += 1
            else:
                break

        if consecutive_failures >= 5:
            first_failed = self.search(
                [('parse_status', '=', 'failed')],
                order='create_date desc',
                limit=1,
            )
            if first_failed:
                existing_activity = self.env['mail.activity'].search([
                    ('res_model', '=', self._name),
                    ('res_id', '=', first_failed.id),
                    ('activity_type_id', '=',
                     self.env.ref('mail.mail_activity_data_warning').id),
                    ('summary', '=', 'Etsy parse failures detected'),
                ], limit=1)
                if not existing_activity:
                    admin = self.env.ref(
                        'base.user_admin', raise_if_not_found=False)
                    first_failed.activity_schedule(
                        'mail.mail_activity_data_warning',
                        user_id=admin.id if admin else self.env.uid,
                        summary='Etsy parse failures detected',
                        note=(
                            f'{consecutive_failures} consecutive parse failures. '
                            'Etsy email format may have changed.'
                        ),
                    )

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
