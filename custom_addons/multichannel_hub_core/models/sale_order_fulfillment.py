from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrderFulfillment(models.Model):
    _name = 'sale.order.fulfillment'
    _description = 'Fulfillment lifecycle for a sale order'
    _inherit = ['mail.thread']
    _order = 'id desc'

    tracking_number = fields.Char(string='Tracking Number', index=True, tracking=True)
    shipping_date = fields.Date(string='Shipping Date', tracking=True)
    shipping_carrier_id = fields.Many2one(
        'shipping.carrier',
        string='Shipping Carrier',
        ondelete='set null',
        index=True,
        tracking=True,
    )
    label_status = fields.Selection(
        [
            ('none', 'None'),
            ('requested', 'Requested'),
            ('buying', 'Buying'),
            ('bought', 'Bought'),
            ('failed', 'Failed'),
        ],
        string='Label Status',
        default='none',
        required=True,
        tracking=True,
    )
    tracking_state = fields.Selection(
        [
            ('none', 'None'),
            ('label_requested', 'Label Requested'),
            ('label_ready', 'Label Ready'),
            ('shipped', 'Shipped'),
            ('in_transit', 'In Transit'),
            ('delivered', 'Delivered'),
            ('returned', 'Returned'),
        ],
        string='Tracking State',
        default='none',
        required=True,
        tracking=True,
    )
    mp_note = fields.Text(string='Marketing Note')
    pd_note = fields.Text(string='Production Note')
    pic_user_id = fields.Many2one(
        'res.users',
        string='Person In Charge',
        ondelete='set null',
        index=True,
        tracking=True,
    )
    order_priority = fields.Selection(
        [
            ('normal', 'Normal'),
            ('push', 'Push'),
            ('urgent', 'Urgent'),
        ],
        string='Order Priority',
        default='normal',
        required=True,
        tracking=True,
    )
    production_blocked = fields.Boolean(string='Production Blocked', default=False, tracking=True)
    block_reason = fields.Text(string='Block Reason', tracking=True)
    fulfillment_status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('produced', 'Produced'),
            ('shipped', 'Shipped'),
            ('delivered', 'Delivered'),
            ('cancelled', 'Cancelled'),
        ],
        string='Fulfillment Status',
        default='pending',
        required=True,
        tracking=True,
    )

    @api.constrains('production_blocked', 'block_reason')
    def _check_block_reason_when_blocked(self):
        for record in self:
            if record.production_blocked and not (record.block_reason and record.block_reason.strip()):
                raise ValidationError(_(
                    "A block reason is required when production is blocked."
                ))
