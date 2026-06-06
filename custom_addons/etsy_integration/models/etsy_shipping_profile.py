"""Etsy shipping profile cache (P-LIST-SHIPPING / ADR-015).

Unlike ``etsy.taxonomy.node`` (global catalog), shipping profiles are
per-shop — each Etsy shop owns its own profiles. The cache model
carries an ``etsy.shop`` FK + the Etsy profile id; UNIQUE composite
on (shop_id, etsy_profile_id) at PG.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class EtsyShippingProfile(models.Model):
    _name = 'etsy.shipping.profile'
    _description = 'Etsy Shop Shipping Profile (cache)'
    _order = 'shop_id, title'
    _rec_name = 'display_name'

    shop_id = fields.Many2one(
        'etsy.shop',
        string='Shop',
        required=True,
        ondelete='cascade',
        index=True,
    )
    etsy_profile_id = fields.Char(
        string='Etsy Profile ID',
        required=True,
        index=True,
        copy=False,
        help='Numeric shipping_profile_id from Etsy (stored as string to '
             'avoid XML-RPC int32 overflow).',
    )
    title = fields.Char(string='Title')
    origin_country_iso = fields.Char(
        string='Origin Country',
        size=2,
        help='ISO 3166-1 alpha-2 country code from which the listing ships.',
    )
    is_deleted = fields.Boolean(
        default=False,
        help='True when the profile has been deleted on Etsy. Soft-keep so '
             'historical listings still resolve.',
    )
    active = fields.Boolean(default=True)
    last_synced_at = fields.Datetime(copy=False)
    display_name = fields.Char(
        compute='_compute_display_name', store=True,
    )

    def init(self):
        """Mirror UNIQUE(shop_id, etsy_profile_id) at PG."""
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                uniq_etsy_shipping_profile_shop_etsy_id
            ON etsy_shipping_profile (shop_id, etsy_profile_id)
        """)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s [#%s]' % (
                rec.title or 'Untitled', rec.etsy_profile_id or '?',
            )
