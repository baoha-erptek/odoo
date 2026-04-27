from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ShippingCarrier(models.Model):
    _name = 'shipping.carrier'
    _description = 'Carrier identity for tracking + Etsy/Gearment push'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(
        string='Code',
        required=True,
        index=True,
        help='Stable machine identifier (lowercase, e.g. "usps"). Unique across active rows.',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    is_active = fields.Boolean(string='Active', default=True)
    tracking_url_template = fields.Char(
        string='Tracking URL Template',
        help='URL template with `{tracking_number}` placeholder.',
    )
    tracking_prefix_regex = fields.Char(
        string='Tracking Prefix Regex',
        help='Regex used by carrier auto-detection (Spec 004a).',
    )
    # NOTE: Etsy carrier enum kept conservative for now (usps/ups/fedex/dhl/4px/other).
    # Expand once Etsy app scope review is approved and we can confirm the live
    # API contract at https://developers.etsy.com/documentation/reference#operation/createReceiptShipment
    etsy_carrier_name = fields.Selection(
        [
            ('usps', 'USPS'),
            ('ups', 'UPS'),
            ('fedex', 'FedEx'),
            ('dhl', 'DHL'),
            ('4px', '4PX'),
            ('other', 'Other'),
        ],
        string='Etsy Carrier Name',
        help='Maps to the Etsy v3 API carrier enum used for tracking push.',
    )
    gearment_carrier_name = fields.Char(
        string='Gearment Carrier Name',
        help='Mapping for Gearment partner sync (Spec 004b).',
    )
    notes = fields.Text(string='Notes')

    @api.constrains('name', 'code')
    def _check_name_code_not_empty(self):
        for record in self:
            if not (record.name and record.name.strip()):
                raise ValidationError(_("Shipping carrier name cannot be empty."))
            if not (record.code and record.code.strip()):
                raise ValidationError(_("Shipping carrier code cannot be empty."))

    @api.constrains('code')
    def _check_code_unique(self):
        for record in self:
            if not record.code:
                continue
            duplicates = self.search([
                ('code', '=', record.code),
                ('id', '!=', record.id),
            ])
            if duplicates:
                raise ValidationError(_(
                    "Shipping carrier code %(code)s is already used by %(other)s.",
                    code=record.code,
                    other=duplicates[0].name,
                ))
