import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ShippingCarrier(models.Model):
    _name = 'shipping.carrier'
    _description = 'Carrier identity for tracking + Etsy/Gearment push'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True, tracking=True)
    code = fields.Char(
        string='Code',
        required=True,
        index=True,
        tracking=True,
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
        help='Regex used by carrier auto-detection (Spec 004a). Anchored '
             'at start (re.match). Avoid nested quantifiers like (a+)+ '
             'or (a*)* — Python `re` has no timeout and a poorly-written '
             'pattern can hang the worker on adversarial input. Empty-match '
             'patterns (e.g. .*) are rejected by C-SC-002.',
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
        tracking=True,
        help='Maps to the Etsy v3 API carrier enum used for tracking push.',
    )
    gearment_carrier_name = fields.Char(
        string='Gearment Carrier Name',
        tracking=True,
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

    @api.constrains('tracking_prefix_regex')
    def _check_tracking_prefix_regex_safe(self):
        """P2-02: reject regexes that compile-fail or match the empty string.

        A regex matching '' (e.g., `.*`, `(a*)*`, `(?:)`) would tag every
        tracking number with this carrier and short-circuit detection.
        """
        for record in self:
            pattern = record.tracking_prefix_regex
            if not pattern:
                continue
            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                raise ValidationError(_(
                    "Invalid regex on carrier %(name)s: %(err)s",
                    name=record.name, err=exc,
                )) from exc
            if compiled.match(''):
                raise ValidationError(_(
                    "Carrier %(name)s regex matches the empty string and "
                    "would tag every tracking number — refine it.",
                    name=record.name,
                ))

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
