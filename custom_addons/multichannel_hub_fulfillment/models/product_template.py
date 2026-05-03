"""product.template extension — Gearment SKU mapping (POD route).

Per ADR-003: Gearment-specific data lives in mhf, not mhc.

P1-DROP-SEED: when ``x_gearment_sku`` is set, the product is auto-routed
through the Dropship route and the Gearment vendor is added to
``seller_ids``. Clearing the SKU removes both (symmetric policy, owner-
confirmed 2026-05-03). FR-017 write-level defense: ``write()`` is the
canonical gate; ``@api.onchange`` is convenience for the form view.
"""
import logging

from odoo import Command, api, fields, models

_logger = logging.getLogger(__name__)

_GEARMENT_PARTNER_XMLID = 'multichannel_hub_fulfillment.partner_gearment_vendor'
_DROPSHIP_ROUTE_XMLID = 'stock_dropshipping.route_drop_shipping'


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_gearment_sku = fields.Char(
        string='Gearment SKU',
        index=True,
        tracking=True,
        help="Maps the product to a Gearment catalog SKU; required for "
             "any product that flows through the gearment_pod pipeline.",
    )

    # ----- helpers --------------------------------------------------------

    def _get_gearment_partner(self):
        return self.env.ref(_GEARMENT_PARTNER_XMLID, raise_if_not_found=False)

    def _get_dropship_route(self):
        return self.env.ref(_DROPSHIP_ROUTE_XMLID, raise_if_not_found=False)

    def _apply_gearment_mapping(self):
        """Sync route_ids + seller_ids with x_gearment_sku state.

        Idempotent by design — never duplicates seller_ids and never clobbers
        custom price/sequence on an existing Gearment supplier row.
        """
        partner = self._get_gearment_partner()
        route = self._get_dropship_route()
        if not partner or not route:
            _logger.warning(
                "P1-DROP-SEED: skipping Gearment SKU mapping for %s; "
                "partner_resolved=%s route_resolved=%s. Check that "
                "multichannel_hub_fulfillment seed loaded and "
                "stock_dropshipping is installed.",
                self, bool(partner), bool(route),
            )
            return

        for record in self:
            sku_set = bool(record.x_gearment_sku)
            existing_seller = record.seller_ids.filtered(
                lambda s, p=partner: s.partner_id.id == p.id
            )
            route_present = route in record.route_ids

            if sku_set:
                if not route_present:
                    record.route_ids = [Command.link(route.id)]
                if not existing_seller:
                    record.seller_ids = [Command.create({'partner_id': partner.id})]
            else:
                if route_present:
                    record.route_ids = [Command.unlink(route.id)]
                for sel in existing_seller:
                    record.seller_ids = [Command.unlink(sel.id)]

    # ----- onchange (UI convenience) --------------------------------------

    @api.onchange('x_gearment_sku')
    def _onchange_x_gearment_sku(self):
        """Apply mapping in form memory so the operator sees route/seller
        update immediately. Canonical persistence is via write()."""
        self._apply_gearment_mapping()

    # ----- CRUD overrides (FR-017 write-level defense) --------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered('x_gearment_sku')._apply_gearment_mapping()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'x_gearment_sku' in vals:
            self._apply_gearment_mapping()
        return result
