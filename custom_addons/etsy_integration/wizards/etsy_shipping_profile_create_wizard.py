"""Create-Etsy-shipping-profile wizard (P-LIST-SHIP-CREATE / ESTY-201).

Lets a BA user build a NEW manual flat-rate shipping profile and push it
to Etsy, instead of only selecting from profiles created in Etsy's web UI.
Reachable from the ``etsy.shop`` form (Publisher Defaults) and inline from
the listing form, next to the shipping-profile selector.

The wizard validates the Etsy ``createShopShippingProfile`` contract
*before* any network call, builds the form-ready payload, delegates the
POST + cache upsert to ``create_profile``, then optionally wires the new
profile as the shop default or the listing override.
"""

import logging

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from ..services.etsy_shipping_profile_creator import create_profile

_logger = logging.getLogger(__name__)

_BA_GROUP_XMLID = 'multichannel_hub_core.group_ba_user'


class EtsyShippingProfileCreateWizard(models.TransientModel):
    _name = 'etsy.shipping.profile.create.wizard'
    _description = 'Create Etsy Shipping Profile'

    shop_id = fields.Many2one(
        'etsy.shop', string='Etsy Shop', required=True, ondelete='cascade',
    )
    set_on_listing_id = fields.Many2one(
        'multichannel.listing', string='Apply To Listing', ondelete='cascade',
        help='When launched from a listing, the new profile becomes that '
             "listing's shipping-profile override on success.",
    )

    title = fields.Char(string='Profile Name', required=True)
    origin_country_id = fields.Many2one(
        'res.country', string='Ships From', required=True,
    )
    origin_postal_code = fields.Char(
        string='Origin Postal Code',
        help='Required by Etsy for countries that use postal codes (US, etc.).',
    )
    primary_cost = fields.Float(
        string='Shipping Cost', required=True, digits=(16, 2),
        help='Cost to ship this item alone, in the shop currency.',
    )
    secondary_cost = fields.Float(
        string='Cost With Another Item', required=True, digits=(16, 2),
        help='Cost to ship this item alongside another, in the shop currency.',
    )
    min_delivery_days = fields.Integer(string='Min Delivery Days')
    max_delivery_days = fields.Integer(string='Max Delivery Days')
    min_processing_time = fields.Integer(string='Min Processing Time')
    max_processing_time = fields.Integer(string='Max Processing Time')
    processing_time_unit = fields.Selection(
        [('business_days', 'Business days'), ('weeks', 'Weeks')],
        string='Processing Unit', default='business_days',
    )
    destination_kind = fields.Selection(
        [('everywhere', 'Everywhere'),
         ('country', 'Specific country'),
         ('region', 'Region (EU / non-EU)')],
        string='Ships To', default='everywhere', required=True,
    )
    destination_country_id = fields.Many2one(
        'res.country', string='Destination Country',
    )
    destination_region = fields.Selection(
        [('eu', 'European Union'), ('non_eu', 'Non-EU Europe')],
        string='Destination Region',
    )
    set_as_shop_default = fields.Boolean(
        string='Set As Shop Default',
        help='Also store this profile as the shop default shipping profile.',
    )

    def _check_ba_or_raise(self):
        # FR-017 write-level defense: mirror the view group at the method
        # before any side effect (network POST / cache write).
        if not self.env.user.has_group(_BA_GROUP_XMLID):
            raise AccessError(_(
                "Only BA users can create Etsy shipping profiles.",
            ))

    def _build_payload(self):
        """Validate the Etsy contract and return the form-ready dict."""
        self.ensure_one()
        if not self.title:
            raise UserError(_("Profile name is required."))
        if not self.origin_country_id.code:
            raise UserError(_("Origin country has no ISO code."))
        # Etsy requires the full delivery-days pair (v1 does not support the
        # carrier + mail_class alternative). Both present or the call 400s.
        if not (self.min_delivery_days and self.max_delivery_days):
            raise UserError(_(
                "Both minimum and maximum delivery days are required.",
            ))
        if self.min_delivery_days > self.max_delivery_days:
            raise UserError(_(
                "Minimum delivery days cannot exceed maximum delivery days.",
            ))
        # Etsy allows 0 cost (free shipping) but rejects negatives; catch the
        # typo here so the operator gets a clear message, not an opaque 400.
        if self.primary_cost < 0 or self.secondary_cost < 0:
            raise UserError(_("Shipping costs cannot be negative."))

        payload = {
            'title': self.title,
            'origin_country_iso': self.origin_country_id.code,
            'primary_cost': '%.2f' % self.primary_cost,
            'secondary_cost': '%.2f' % self.secondary_cost,
            'min_delivery_days': self.min_delivery_days,
            'max_delivery_days': self.max_delivery_days,
        }
        if self.origin_postal_code:
            payload['origin_postal_code'] = self.origin_postal_code
        if self.min_processing_time and self.max_processing_time:
            payload['min_processing_time'] = self.min_processing_time
            payload['max_processing_time'] = self.max_processing_time
            payload['processing_time_unit'] = (
                self.processing_time_unit or 'business_days')

        # destination_country_iso XOR destination_region; neither = everywhere.
        if self.destination_kind == 'country':
            if not self.destination_country_id.code:
                raise UserError(_("Select a destination country."))
            payload['destination_country_iso'] = self.destination_country_id.code
        elif self.destination_kind == 'region':
            if not self.destination_region:
                raise UserError(_("Select a destination region."))
            payload['destination_region'] = self.destination_region
        return payload

    def action_create_profile(self):
        self._check_ba_or_raise()  # FR-017
        self.ensure_one()
        payload = self._build_payload()
        profile = create_profile(self.env, self.shop_id, payload)
        if self.set_as_shop_default:
            # sudo: default_shipping_profile_id is gated to base.group_system
            # (field-level groups on etsy.shop). The actor here is a BA (gated
            # above by _check_ba_or_raise), who has read but not write on that
            # system field, so the privileged action writes it via sudo.
            # It is a Char (int64-safe) holding the numeric profile id.
            self.shop_id.sudo().default_shipping_profile_id = (
                profile.etsy_profile_id)
        if self.set_on_listing_id:
            # sudo: the wizard may be launched against a listing the BA can
            # read but not independently write (cross-company / curated). The
            # override write is an intended side effect of this BA-gated
            # action, so it runs privileged.
            self.set_on_listing_id.sudo().etsy_shipping_profile_id = profile.id
        return {'type': 'ir.actions.act_window_close'}
