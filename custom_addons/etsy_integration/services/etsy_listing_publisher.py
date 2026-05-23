"""Etsy Outbound Publisher (Spec 011 P-PUB-DRAFT).

Initial slice scope: `create_draft(product, shop)` only. Image upload,
inventory PUT, and `publish()` orchestration land in subsequent slices.

Per ADR-014 §4 SKU resolution:
    use `x_sku_v2_suggested` when non-empty AND
    `x_sku_v2_status != 'ba_approved_legacy'`, else `default_code`.

Per Spec 011 §50: refuses to start when any of the 3 shop default IDs
(taxonomy / shipping_profile / return_policy) is NULL — they are required
by Etsy's createListing endpoint.
"""

import logging

from .etsy_api_client import EtsyApiClient

_logger = logging.getLogger(__name__)


class EtsyListingPublisher:
    """Orchestrates outbound publish to Etsy. Stateless; constructed
    per call with the Odoo environment.
    """

    def __init__(self, env):
        self.env = env

    # ------------------------------------------------------------------
    # SKU resolution (ADR-014 §4)
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_sku(tmpl):
        if (
            tmpl.x_sku_v2_suggested
            and tmpl.x_sku_v2_status != 'ba_approved_legacy'
        ):
            return tmpl.x_sku_v2_suggested
        return tmpl.default_code or ''

    # ------------------------------------------------------------------
    # Payload builder
    # ------------------------------------------------------------------
    def _build_create_draft_payload(self, tmpl, shop):
        return {
            'sku': self._resolve_sku(tmpl),
            'title': tmpl.name or '',
            'description': (tmpl.description_sale or tmpl.name or ''),
            'price': float(tmpl.x_listing_price or 0.0),
            'quantity': max(int(tmpl.qty_available or 0), 1),
            'who_made': shop.sudo().default_who_made or 'i_did',
            'when_made': shop.sudo().default_when_made or 'made_to_order',
            'is_supply': bool(shop.sudo().default_is_supply),
            'taxonomy_id': int(shop.sudo().default_taxonomy_id or 0),
            'shipping_profile_id': int(shop.sudo().default_shipping_profile_id or 0),
            'return_policy_id': int(shop.sudo().default_return_policy_id or 0),
            'state': 'draft',
        }

    # ------------------------------------------------------------------
    # Shop default validation
    # ------------------------------------------------------------------
    @staticmethod
    def _check_shop_defaults(shop):
        s = shop.sudo()
        missing = []
        if not s.default_taxonomy_id:
            missing.append('default_taxonomy_id')
        if not s.default_shipping_profile_id:
            missing.append('default_shipping_profile_id')
        if not s.default_return_policy_id:
            missing.append('default_return_policy_id')
        if missing:
            raise ValueError(
                "Etsy shop %r missing required publisher defaults: %s"
                % (shop.name, ', '.join(missing))
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create_draft(self, tmpl, shop):
        """POST /shops/{shop_id}/listings → returns Etsy listing payload.

        Writes `etsy.listing` (state='draft') + `product.channel.status`
        (state='draft', external_ref=str(listing_id)) on success.

        On 4xx, the caller's transaction rolls back via the raised
        ValueError; durable error audit lands in P-PUB-PUBLISH (slice
        T026 orchestrator owns the resumable state machine).
        """
        self._check_shop_defaults(shop)
        api_shop_id = shop.sudo().etsy_api_shop_id
        if not api_shop_id:
            raise ValueError(
                "Etsy shop %r missing etsy_api_shop_id; cannot publish."
                % shop.name
            )
        payload = self._build_create_draft_payload(tmpl, shop)
        client = EtsyApiClient(shop)
        path = "shops/%s/listings" % api_shop_id
        response = client.post(path, json=payload)
        listing_id = response.get('listing_id')
        if not listing_id:
            raise ValueError(
                "Etsy createListing returned no listing_id; payload=%r" % response
            )
        # Mirror locally
        Channel = self.env.ref('multichannel_hub_core.channel_etsy')
        self.env['etsy.listing'].sudo().create({
            'shop_id': shop.id,
            'etsy_listing_id': str(listing_id),
            'title': payload['title'],
            'description': payload['description'],
            'url': response.get('url') or '',
            'price': payload['price'],
            'quantity': payload['quantity'],
            'state': 'inactive',  # createDraft → Etsy state is 'draft'; we mirror as inactive until publish step
        })
        self.env['product.channel.status'].sudo().create({
            'product_tmpl_id': tmpl.id,
            'channel_id': Channel.id,
            'state': 'draft',
            'external_ref': str(listing_id),
        })
        return response

    # ------------------------------------------------------------------
    # Spec 011 P-PUB-INVENTORY — entire-array PUT (T018)
    # ------------------------------------------------------------------
    def push_inventory(self, tmpl, listing_id, shop):
        """PUT /listings/{listing_id}/inventory with the full products[] array.

        Builds one product entry per `product.product` variant of the template.
        Etsy requires the entire array on every write (no partial updates).
        SKU per ADR-014 §4 (resolved per-variant).

        On success, the local `etsy.listing.product` snapshot rows are updated
        from the response payload (T020).
        """
        if not listing_id:
            raise ValueError("push_inventory requires a non-empty listing_id")
        products_payload = []
        # Template-level SKU resolution wins (ADR-014 §4) — variant default_code
        # is typically auto-inherited from template and would defeat the v2 rule.
        # True per-variant overrides aren't in scope for this slice; revisit if
        # multi-variant publish surfaces a real divergence.
        sku = self._resolve_sku(tmpl)
        for variant in tmpl.product_variant_ids:
            products_payload.append({
                'sku': sku,
                'property_values': [],
                'offerings': [
                    {
                        'quantity': max(int(variant.qty_available or 0), 1),
                        'price': float(tmpl.x_listing_price or 0.0),
                        'is_enabled': True,
                    },
                ],
            })
        client = EtsyApiClient(shop)
        path = "listings/%s/inventory" % listing_id
        response = client.put(path, json={'products': products_payload})
        self._sync_inventory_snapshot(shop, listing_id, response)
        return response

    def _sync_inventory_snapshot(self, shop, listing_id, response):
        """Update etsy.listing.product rows from the PUT response (T020)."""
        if not isinstance(response, dict):
            return
        listing = self.env['etsy.listing'].sudo().search([
            ('shop_id', '=', shop.id),
            ('etsy_listing_id', '=', str(listing_id)),
        ], limit=1)
        if not listing:
            return
        ListingProduct = self.env['etsy.listing.product'].sudo()
        for entry in response.get('products') or []:
            etsy_product_id = entry.get('product_id')
            if not etsy_product_id:
                continue
            row = ListingProduct.search([
                ('listing_id', '=', listing.id),
                ('etsy_product_id', '=', str(etsy_product_id)),
            ], limit=1)
            qty = 0
            price = 0.0
            offerings = entry.get('offerings') or []
            if offerings:
                first = offerings[0]
                qty = int(first.get('quantity') or 0)
                price_obj = first.get('price') or {}
                amount = price_obj.get('amount')
                divisor = price_obj.get('divisor') or 100
                if amount is not None and divisor:
                    price = float(amount) / float(divisor)
            vals = {
                'sku': entry.get('sku') or '',
                'quantity': qty,
                'price': price,
            }
            if row:
                row.write(vals)
            else:
                vals.update({
                    'listing_id': listing.id,
                    'etsy_product_id': str(etsy_product_id),
                })
                ListingProduct.create(vals)
