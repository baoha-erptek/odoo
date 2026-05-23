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

import base64
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
        # tmpl.sudo() — read attributes regardless of caller's stock-read ACL;
        # the wizard's FR-017 gate proved BA membership upstream.
        s = tmpl.sudo()
        return {
            'sku': self._resolve_sku(s),
            'title': s.name or '',
            'description': (s.description_sale or s.name or ''),
            'price': float(s.x_listing_price or 0.0),
            'quantity': max(int(s.qty_available or 0), 1),
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
        sku = self._resolve_sku(tmpl.sudo())
        for variant in tmpl.sudo().product_variant_ids:
            products_payload.append({
                'sku': sku,
                'property_values': [],
                'offerings': [
                    {
                        'quantity': max(int(variant.sudo().qty_available or 0), 1),
                        'price': float(tmpl.sudo().x_listing_price or 0.0),
                        'is_enabled': True,
                    },
                ],
            })
        client = EtsyApiClient(shop)
        path = "listings/%s/inventory" % listing_id
        response = client.put(path, json={'products': products_payload})
        self._sync_inventory_snapshot(shop, listing_id, response)
        return response

    # ------------------------------------------------------------------
    # Spec 011 P-PUB-IMAGES (option B / MVP) — single-image, no diff (T015)
    # ------------------------------------------------------------------
    # Odoo 19 CE has no `product.image` model (Enterprise-only). MVP scope:
    # upload the template's `image_1920` per publish, no manifest diff, no
    # DELETE path. Multi-image-per-listing + diff is a follow-up slice.
    def upload_images(self, tmpl, listing_id, shop):
        """POST /listings/{listing_id}/images for the template's main image.

        Returns the list of response payloads (one per successful upload).
        Templates with no `image_1920` set are a no-op (returns []).
        """
        if not listing_id:
            raise ValueError("upload_images requires a non-empty listing_id")
        if not tmpl.sudo().image_1920:
            return []
        # `image_1920` is stored base64-encoded; decode for the multipart body.
        try:
            payload_bytes = base64.b64decode(tmpl.sudo().image_1920)
        except Exception as exc:  # noqa: BLE001 — defensive only
            raise ValueError(
                "Could not decode product image for template %r: %s"
                % (tmpl.name, exc)
            ) from exc
        client = EtsyApiClient(shop)
        path = "listings/%s/images" % listing_id
        files = {
            'image': (
                (tmpl.default_code or 'image') + '.jpg',
                payload_bytes,
                'image/jpeg',
            ),
        }
        response = client.post_multipart(path, files=files)
        return [response] if response else []

    # ------------------------------------------------------------------
    # Spec 011 P-PUB-PUBLISH T025 — PATCH /listings/{id} state='active'
    # ------------------------------------------------------------------
    def publish(self, listing_id, shop):
        if not listing_id:
            raise ValueError("publish requires a non-empty listing_id")
        client = EtsyApiClient(shop)
        return client.patch(
            "listings/%s" % listing_id, json={'state': 'active'},
        )

    # ------------------------------------------------------------------
    # Spec 011 P-PUB-PUBLISH T026 — orchestrator
    # ------------------------------------------------------------------
    def run(self, tmpl, shop):
        """Run the full publish chain: create_draft → upload_images →
        push_inventory → publish.

        Resumable: if a `product.channel.status` row already exists with an
        `external_ref`, skip `create_draft` and reuse that listing_id.

        On failure: write `product.channel.status.state='error'` +
        `last_sync_error` and re-raise. Caller is responsible for transaction
        boundary; the durable error write happens via the standard ORM (the
        orchestrator's invoker — wizard — runs in its own savepoint and the
        wizard's UI surfaces last_sync_error to the operator).
        """
        Channel = self.env.ref('multichannel_hub_core.channel_etsy')
        Status = self.env['product.channel.status'].sudo()
        existing = Status.search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', Channel.id),
        ], limit=1)
        listing_id = existing.external_ref if existing else None
        result = {}
        try:
            if not listing_id:
                draft_response = self.create_draft(tmpl, shop)
                listing_id = draft_response.get('listing_id')
                if not listing_id:
                    raise ValueError("create_draft returned no listing_id")
                # create_draft just wrote the status row; refresh
                existing = Status.search([
                    ('product_tmpl_id', '=', tmpl.id),
                    ('channel_id', '=', Channel.id),
                ], limit=1)
                result['listing_id'] = listing_id
            else:
                result['listing_id'] = int(listing_id) if str(listing_id).isdigit() else listing_id

            self.upload_images(tmpl, listing_id, shop)
            self.push_inventory(tmpl, listing_id, shop)
            self.publish(listing_id, shop)
            existing.write({
                'state': 'published',
                'last_sync_error': False,
            })
            return result
        except Exception as exc:
            # Best-effort durable error capture on the status row. If the
            # status row doesn't exist yet (create_draft failed before
            # writing one), there's nothing to update.
            if existing:
                existing.write({
                    'state': 'error',
                    'last_sync_error': (str(exc) or '')[:4000],
                })
            raise

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
