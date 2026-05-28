"""etsy_integration extension to sale.order.fulfillment.

Adds Etsy-specific fields that the multichannel_hub_core foundation
cannot host (mhc CLAUDE.md prohibits Etsy-named code).

P1-03 — `etsy_ship_notified_at` is stamped by Spec 005's
EtsyTrackingPusher when the Etsy /receipts/{id}/tracking call
returns 200, recording when the buyer was last notified.
"""

from odoo import fields, models


class SaleOrderFulfillment(models.Model):
    _inherit = 'sale.order.fulfillment'

    etsy_ship_notified_at = fields.Datetime(
        string='Etsy Ship Notified At',
        copy=False,
        groups='base.group_system',
        help="UTC timestamp of the last successful Etsy buyer-shipping "
             "notification (set by Spec 005 EtsyTrackingPusher on 200 OK). "
             "System-only writes — operators cannot fake notification times.",
    )
