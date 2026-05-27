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
import re

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
    # Spec 011 P-PUB-MATERIALS — template Material values → materials[]
    # ------------------------------------------------------------------
    # Etsy materials[] is listing-level (one array per listing), not
    # per-variant — so we walk the template's attribute lines, not a
    # specific variant. This also sidesteps the `create_variant='dynamic'`
    # case where `variant.product_template_attribute_value_ids` is empty
    # until a buyer picks a combination. Reuses existing product.attribute
    # seed data; no new model, no new field.
    ETSY_MAX_MATERIALS = 13

    @staticmethod
    def _collect_materials(tmpl):
        """Pick Material attribute values off the template's attribute lines.

        Selects values whose attribute is named `Material` OR whose value
        carries `x_namespace='MAT2'` (future-proofing for namespace-based
        families). Each value name is charset-cleaned per Etsy's letters/
        numbers/whitespace whitelist, deduplicated preserving order, and
        capped at 13.

        Returns: list[str]. Empty when no Material values found or all
        clean to empty strings.
        """
        seen = []
        for line in tmpl.attribute_line_ids:
            line_is_material = (
                line.attribute_id.name == 'Material'
                or any(v.x_namespace == 'MAT2' for v in line.value_ids)
            )
            if not line_is_material:
                continue
            for v in line.value_ids:
                cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', v.name or '')
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                if cleaned and cleaned not in seen:
                    seen.append(cleaned)
                if len(seen) >= EtsyListingPublisher.ETSY_MAX_MATERIALS:
                    return seen
        return seen

    # ------------------------------------------------------------------
    # Payload builder
    # ------------------------------------------------------------------
    def _build_create_draft_payload(self, tmpl, shop):
        # tmpl.sudo() — read attributes regardless of caller's stock-read ACL;
        # the wizard's FR-017 gate proved BA membership upstream.
        s = tmpl.sudo()
        sh = shop.sudo()
        payload = {
            'sku': self._resolve_sku(s),
            'title': s.name or '',
            'description': (s.description_sale or s.name or ''),
            'price': float(s.list_price or 0.0),
            'quantity': max(int(s.qty_available or 0), 1),
            # Spec 011 P-PUB-PER-PRODUCT-DEFAULTS — per-product override wins
            # over shop default; falls back to hardcoded legacy default when
            # both are blank. is_supply stays shop-wide (not in override scope).
            'who_made': s.x_who_made or sh.default_who_made or 'i_did',
            'when_made': s.x_when_made or sh.default_when_made or 'made_to_order',
            'is_supply': bool(sh.default_is_supply),
            'taxonomy_id': int(s.x_taxonomy_id or sh.default_taxonomy_id or 0),
            'shipping_profile_id': int(sh.default_shipping_profile_id or 0),
            'return_policy_id': int(sh.default_return_policy_id or 0),
            'state': 'draft',
        }
        # Etsy 2025 API update requires readiness_state_id on physical listings.
        # Include only when set on the shop; older sandbox shops without it would
        # otherwise 400 the legacy 'processing_min/max' path which is gone.
        if sh.default_readiness_state_id:
            payload['readiness_state_id'] = int(sh.default_readiness_state_id)
        tag_names = s.product_tag_ids.mapped('name')[:13]
        if tag_names:
            payload['tags'] = tag_names
        # Spec 011 P-PUB-PERSONALIZATION — emit personalization keys only when
        # the feature is enabled. Etsy treats absence as "feature off"; do NOT
        # send is_personalizable=False (matches tags-block "empty omitted" pattern).
        if s.x_is_personalizable:
            payload['is_personalizable'] = True
            payload['personalization_is_required'] = bool(s.x_personalization_required)
            payload['personalization_char_count_max'] = int(s.x_personalization_char_count or 256)
            payload['personalization_instructions'] = s.x_personalization_instructions or ''
        # Spec 011 P-PUB-MATERIALS — emit materials only when the variant
        # carries Material attribute values. Matches tags-block "empty
        # omitted" pattern; Etsy treats absence as "no materials".
        materials = self._collect_materials(s)
        if materials:
            payload['materials'] = materials
        return payload

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
        # The wizard (product.creation.wizard.action_create) seeds the status row
        # at draft / no external_ref. Update-or-create so re-publish after wizard
        # creation doesn't collide on the (product_tmpl_id, channel_id) UNIQUE
        # constraint.
        Status = self.env['product.channel.status'].sudo()
        existing_status = Status.search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', Channel.id),
        ], limit=1)
        status_vals = {'state': 'draft', 'external_ref': str(listing_id)}
        if existing_status:
            existing_status.write(status_vals)
        else:
            Status.create(dict(
                status_vals,
                product_tmpl_id=tmpl.id,
                channel_id=Channel.id,
            ))
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
        # Etsy 2025 API requires readiness_state_id on every offering.
        readiness = shop.sudo().default_readiness_state_id
        for variant in tmpl.sudo().product_variant_ids:
            offering = {
                'quantity': max(int(variant.sudo().qty_available or 0), 1),
                'price': float(tmpl.sudo().list_price or 0.0),
                'is_enabled': True,
            }
            if readiness:
                offering['readiness_state_id'] = int(readiness)
            products_payload.append({
                'sku': sku,
                'property_values': [],
                'offerings': [offering],
            })
        client = EtsyApiClient(shop)
        path = "listings/%s/inventory" % listing_id
        response = client.put(path, json={'products': products_payload})
        self._sync_inventory_snapshot(shop, listing_id, response)
        return response

    # ------------------------------------------------------------------
    # Spec 011 P-PUB-IMAGES + P-PUB-MULTI-IMAGE (MP006 2026-05-27)
    # ------------------------------------------------------------------
    # Original MVP: single image_1920. Multi-image pivot 2026-05-27:
    # iterate main image_1920 first, then multichannel.product.image
    # gallery rows sorted by sequence; cap at Etsy's 10-image limit;
    # per-image upload failure logs WARNING and continues to the next.
    ETSY_MAX_IMAGES = 10

    def upload_images(self, tmpl, listing_id, shop):
        """POST /listings/{listing_id}/images for main + gallery images.

        Returns the list of response payloads (one per successful upload).
        Returns [] if neither main image nor gallery rows are present.
        """
        if not listing_id:
            raise ValueError("upload_images requires a non-empty listing_id")
        t = tmpl.sudo()
        candidates = []
        if t.image_1920:
            candidates.append(('main', t.image_1920))
        for row in t.x_extra_image_ids.sorted('sequence'):
            if row.image_1920:
                candidates.append(('gallery', row.image_1920))
        if not candidates:
            return []
        client = EtsyApiClient(shop)
        path = "listings/%s/images" % listing_id
        sku = tmpl.default_code or 'image'
        results = []
        for idx, (origin, raw) in enumerate(candidates, start=1):
            if idx > self.ETSY_MAX_IMAGES:
                _logger.warning(
                    "Skipping image %d for listing %s: Etsy cap at %d",
                    idx, listing_id, self.ETSY_MAX_IMAGES,
                )
                continue
            try:
                payload_bytes = base64.b64decode(raw)
            except Exception as exc:  # noqa: BLE001 — defensive only
                _logger.warning(
                    "Skipping %s image %d for listing %s — decode failed: %s",
                    origin, idx, listing_id, exc,
                )
                continue
            files = {
                'image': (
                    '%s_%d.jpg' % (sku, idx),
                    payload_bytes,
                    'image/jpeg',
                ),
            }
            try:
                response = client.post_multipart(path, files=files)
            except Exception as exc:  # noqa: BLE001 — partial-failure resilience
                _logger.warning(
                    "Etsy image upload failed for listing %s image %d: %s",
                    listing_id, idx, exc,
                )
                continue
            if response:
                results.append(response)
        return results

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
