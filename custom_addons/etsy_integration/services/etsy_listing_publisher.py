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
import itertools
import logging
import re

from odoo import fields

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
    # Spec 011 P-PUB-VARIANT-PROPERTIES — variant attribute axes →
    # products[].property_values[] per push_inventory offering
    # ------------------------------------------------------------------
    # Per-axis gated by product.attribute.x_publish_as_property (default
    # True). property_id comes from product.attribute.x_etsy_property_id;
    # when empty, falls back to the attribute name and logs WARNING so
    # the BA can spot un-mapped axes in the Odoo log.
    #
    # Walks variant.product_template_attribute_value_ids (per-variant
    # M2M). For dynamic-variant axes (e.g. Color in our seed), the M2M
    # stays empty until a buyer picks a combination — return [] in that
    # case, which Etsy already accepts at line 247's prior baseline.
    @staticmethod
    def _property_value_for(axis, value_name):
        """Build one Etsy property_values[] entry for an (axis, value) pair.

        Returns {property_id, property_name, values} or None when the axis is
        not publishable or is missing its Etsy property id/name. Etsy REQUIRES
        both a numeric property_id AND a non-null property_name string (the
        inventory PUT 400s "Expected string value for property_name" without
        it — verified live 2026-05-28), so an axis lacking either is skipped
        entirely rather than sent malformed (which would 400 the whole PUT).
        """
        if not axis.x_publish_as_property:
            return None
        raw = axis.x_etsy_property_id
        name = axis.x_etsy_property_name
        if not raw or not name:
            _logger.warning(
                "product.attribute id=%s name=%r missing x_etsy_property_id "
                "or x_etsy_property_name; skipping it as an Etsy variation "
                "property (Etsy rejects property_values without both).",
                axis.id, axis.name,
            )
            return None
        return {
            'property_id': int(raw) if raw.isdigit() else raw,
            'property_name': name,
            'values': [value_name],
        }

    @staticmethod
    def _collect_property_values(variant):
        properties = []
        for ptav in variant.product_template_attribute_value_ids:
            pv = EtsyListingPublisher._property_value_for(
                ptav.attribute_id, ptav.product_attribute_value_id.name,
            )
            if pv:
                properties.append(pv)
        return properties

    # ------------------------------------------------------------------
    # Spec 011 P-PUB-WEIGHT-DIMENSIONS — template weight + Size axis →
    # createListing item_weight + item_*dimensions
    # ------------------------------------------------------------------
    # Weight: read standard product.template.weight (kg base unit per
    # Odoo); convert to oz or g per shop.weight_unit_pref. Omit weight
    # keys when weight <= 0 (Etsy treats absence as "no weight").
    #
    # Dimensions: parse the template's Size attribute value name for a
    # rectangular pattern ("R30X18" or "12X18" or "12 × 18"). Mug-family
    # Size values like "11 oz" do not match the regex → dimensions
    # omitted (correct: Mugs publish without item_*dimensions). Emits
    # length+width+unit together or none at all (Etsy rejects partial).
    # Tracker row 339; LOC ~110.
    # Rect dimensions from a Size value name: "R30X18" (2D) or "R30X18X2" (3D).
    # The optional 3rd group yields item_height (Etsy createListing field).
    _RECT_PATTERN = re.compile(
        r'^[Rr]?\s*(\d+)\s*[xX×]\s*(\d+)(?:\s*[xX×]\s*(\d+))?'
    )

    @staticmethod
    def _collect_weight_and_dimensions(tmpl, shop):
        """Build Etsy weight + dimension payload keys.

        tmpl/shop should already be sudo'd (matches _collect_materials
        call-site convention; safe to re-sudo).

        Returns dict that may contain any of:
            item_weight, item_weight_unit  (when tmpl.weight > 0)
            item_length, item_width, [item_height,] item_dimensions_unit
                (when template's Size value matches rect pattern; height only
                 when the value carries a 3rd dimension, e.g. "R30X18X2")

        Empty dict when weight <= 0 AND no parseable Size value.
        """
        result = {}

        weight_kg = tmpl.weight or 0.0
        if weight_kg > 0:
            unit_pref = shop.weight_unit_pref or 'oz'
            if unit_pref == 'oz':
                # kg → oz: 1 kg = 35.274 oz
                result['item_weight'] = round(weight_kg * 35.274, 2)
            else:
                # kg → g
                result['item_weight'] = round(weight_kg * 1000.0, 2)
            result['item_weight_unit'] = unit_pref

        try:
            size_value_name = ''
            for line in tmpl.attribute_line_ids:
                if line.attribute_id.name == 'Size' and line.value_ids:
                    size_value_name = line.value_ids[0].name or ''
                    break
            if size_value_name:
                match = EtsyListingPublisher._RECT_PATTERN.match(size_value_name)
                if match:
                    result['item_length'] = int(match.group(1))
                    result['item_width'] = int(match.group(2))
                    if match.group(3):
                        result['item_height'] = int(match.group(3))
                    result['item_dimensions_unit'] = shop.dimensions_unit_pref or 'cm'
        except Exception as exc:  # noqa: BLE001 — parse failure must not block publish
            _logger.warning(
                "Failed to extract dimensions for product.template id=%s: %s",
                tmpl.id, exc,
            )

        return result

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
            # P-BUG-ESTY-188 iter2: convert from company currency to shop
            # listing currency. Without this, USD-priced templates land at
            # the same numeric value in a VND shop, well below Etsy's
            # per-currency minimum, and createListing 400s "price_too_low".
            'price': self._convert_to_shop_currency(s.list_price, shop),
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
        # Spec 011 personalization is NOT emitted on createListing — Etsy
        # deprecated the four inline fields in 2026 (they now 400). It is sent
        # as a separate orchestrator step via push_personalization() against
        # the dedicated /personalization endpoint (R-PUB-PERSONALIZATION-
        # ENDPOINTS), the same way inventory and images are separate steps.
        # Spec 011 P-PUB-MATERIALS — emit materials only when the variant
        # carries Material attribute values. Matches tags-block "empty
        # omitted" pattern; Etsy treats absence as "no materials".
        materials = self._collect_materials(s)
        if materials:
            payload['materials'] = materials
        # Spec 011 P-PUB-WEIGHT-DIMENSIONS — weight + dimension keys
        payload.update(self._collect_weight_and_dimensions(s, sh))
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
        # listing_currency_id is enforced inside _convert_to_shop_currency
        # rather than here: the helper is reached on every payload build, and
        # adding it to this list would break every shop fixture that doesn't
        # need to publish (orders pull, tracking push, etc).
        if missing:
            raise ValueError(
                "Etsy shop %r missing required publisher defaults: %s"
                % (shop.name, ', '.join(missing))
            )

    # ------------------------------------------------------------------
    # Currency conversion (P-BUG-ESTY-188 iter2)
    # ------------------------------------------------------------------
    def _convert_to_shop_currency(self, amount, shop):
        """Convert ``amount`` from company currency to shop listing currency.

        Etsy requires listing prices in the shop's listing currency. Without
        conversion, a USD-priced Odoo template silently lands at the same
        numeric value in a VND shop — 24,000x too low — and Etsy 400s with
        ``price_too_low``.

        When ``shop.listing_currency_id`` is NULL the helper falls through
        with the raw amount and logs a WARNING. Hard-failing here would
        break every shop fixture that doesn't go through the OAuth /
        migration bootstrap path. Production shops always have the field
        populated; if a 400 reaches Etsy because the shop slipped through,
        the WARNING in the log + Etsy's own response body identify the
        misconfiguration. The migration ``19.0.2.34.0`` covers the
        bootstrap on install; OAuth callback covers fresh shops.
        """
        sh = shop.sudo()
        if not sh.listing_currency_id:
            _logger.warning(
                "Etsy shop %r missing listing_currency_id; emitting raw "
                "list_price=%s. If shop currency differs from company "
                "currency=%s, Etsy will 400 with 'price_too_low'. Run "
                "migration 19.0.2.34.0 or set the field on etsy.shop.",
                shop.name, amount, self.env.company.currency_id.name,
            )
            return float(amount or 0.0)
        company = self.env.company
        if sh.listing_currency_id == company.currency_id:
            return float(amount or 0.0)
        # Standard Odoo CE multi-currency: rate at today's date, company
        # context for per-company rate selection. _convert raises UserError
        # when no rate is configured — owner sees a clear error instead of a
        # silent zero.
        converted = company.currency_id._convert(
            amount or 0.0,
            sh.listing_currency_id,
            company,
            fields.Date.context_today(self),
        )
        return float(converted)

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
    # Etsy allows at most 2 *varying* variation properties per listing.
    ETSY_MAX_VARIATIONS = 2

    def _variant_qty_for_combo(self, tmpl, combo_value_ids):
        """Quantity for a value combination (set of product.attribute.value ids),
        preferring a matching materialized variant's on-hand qty; falls back to
        the template's qty_available when no product.product matches (dynamic
        axes carry no materialized variant).
        """
        for variant in tmpl.product_variant_ids:
            vids = set(variant.product_template_attribute_value_ids
                       .mapped('product_attribute_value_id').ids)
            if vids and vids.issubset(combo_value_ids):
                return variant.qty_available
        return tmpl.qty_available

    def push_inventory(self, tmpl, listing_id, shop):
        """PUT /listings/{listing_id}/inventory with the full products[] array.

        R-PUB-VARIANT-MATERIALIZE (2026-05-28): Etsy variations are built from
        the cartesian product of the publishable variant-creating attribute
        lines, NOT from `product.product` records — so dynamic-variant axes
        (e.g. Color, create_variant='dynamic', which materialize no variants)
        still produce real Etsy variations instead of the prior empty fallback.

        - Varying axes (>1 value) form the product grid; Etsy caps these at 2.
        - Single-value publishable axes ride along as fixed property_values.
        - SKU is template-level (ADR-014 §4) and consistent across products
          (Etsy rejects mixed SKUs: "sku must be consistent across all products").
        - Quantity prefers a matching materialized variant's on-hand, else the
          template qty.

        On success, the local `etsy.listing.product` snapshot rows are updated.
        """
        if not listing_id:
            raise ValueError("push_inventory requires a non-empty listing_id")
        t = tmpl.sudo()
        sku = self._resolve_sku(t)
        readiness = shop.sudo().default_readiness_state_id
        # P-BUG-ESTY-188 iter2: convert per offering — push_inventory writes
        # each variant offering at this price, so the same FX hop applies.
        price = self._convert_to_shop_currency(t.list_price, shop)

        def _offering(qty):
            o = {'quantity': max(int(qty or 0), 1), 'price': price, 'is_enabled': True}
            if readiness:
                o['readiness_state_id'] = int(readiness)
            return o

        # Publishable variant-creating axes (Material is materials[]-only, not a
        # variation property — see etsy_attribute_defaults.xml).
        pub_lines = [
            line for line in t.attribute_line_ids
            if line.value_ids
            and line.attribute_id.create_variant != 'no_variant'
            and line.attribute_id.x_publish_as_property
        ]
        varying = [line for line in pub_lines if len(line.value_ids) > 1]
        fixed = [line for line in pub_lines if len(line.value_ids) == 1]
        if len(varying) > self.ETSY_MAX_VARIATIONS:
            raise ValueError(
                "Etsy allows at most %d variation properties, but %r has %d "
                "varying publishable axes: %s"
                % (self.ETSY_MAX_VARIATIONS, t.name, len(varying),
                   ', '.join(line.attribute_id.name for line in varying))
            )

        # Fixed (single-value) properties are identical on every product.
        fixed_props = []
        for line in fixed:
            pv = self._property_value_for(line.attribute_id, line.value_ids[0].name)
            if pv:
                fixed_props.append(pv)

        products_payload = []
        if varying:
            for combo in itertools.product(*[list(line.value_ids) for line in varying]):
                props = list(fixed_props)
                for line, value in zip(varying, combo):
                    pv = self._property_value_for(line.attribute_id, value.name)
                    if pv:
                        props.append(pv)
                combo_ids = {v.id for v in combo}
                combo_ids.update(line.value_ids[0].id for line in fixed)
                products_payload.append({
                    'sku': sku,
                    'property_values': props,
                    'offerings': [_offering(self._variant_qty_for_combo(t, combo_ids))],
                })
        else:
            # No varying axis → a single product (with any fixed properties).
            products_payload.append({
                'sku': sku,
                'property_values': fixed_props,
                'offerings': [_offering(t.qty_available)],
            })

        client = EtsyApiClient(shop)
        path = "listings/%s/inventory" % listing_id
        response = client.put(path, json={'products': products_payload})
        self._sync_inventory_snapshot(shop, listing_id, response)
        return response

    # ------------------------------------------------------------------
    # Spec 011 R-PUB-PERSONALIZATION-ENDPOINTS — dedicated personalization
    # endpoint (inline createListing fields deprecated by Etsy 2026).
    # ------------------------------------------------------------------
    # Etsy's 2026 migration-period contract accepts exactly ONE text_input
    # question per listing. `x_personalization_char_count` is already pinned
    # to 1-1024 by the mhc `_check_personalization_char_count` constraint, so
    # it passes straight through. `x_personalization_instructions` is an
    # unbounded Text field, so it is truncated here to Etsy's 256-char ceiling
    # (API-boundary validation, not an impossible-state guard).
    ETSY_PERSONALIZATION_INSTRUCTIONS_MAX = 256

    def push_personalization(self, tmpl, listing_id, shop):
        """POST /shops/{shop_id}/listings/{listing_id}/personalization.

        No-op (returns {}) when the template is not personalizable. Builds a
        single text_input question from the preserved product.template fields.
        """
        if not listing_id:
            raise ValueError(
                "push_personalization requires a non-empty listing_id"
            )
        # sudo: read personalization fields regardless of the caller's
        # stock/product-read ACL; the wizard's FR-017 gate proved BA upstream.
        t = tmpl.sudo()
        if not t.x_is_personalizable:
            return {}
        api_shop_id = shop.sudo().etsy_api_shop_id
        if not api_shop_id:
            raise ValueError(
                "Etsy shop %r missing etsy_api_shop_id; cannot push "
                "personalization." % shop.name
            )
        instructions = (t.x_personalization_instructions or '')[
            :self.ETSY_PERSONALIZATION_INSTRUCTIONS_MAX
        ]
        payload = {
            'personalization_questions': [{
                'question_type': 'text_input',
                'question_text': 'Personalization',
                'instructions': instructions,
                'required': bool(t.x_personalization_required),
                'max_allowed_characters': int(t.x_personalization_char_count or 256),
            }],
        }
        client = EtsyApiClient(shop)
        path = "shops/%s/listings/%s/personalization" % (api_shop_id, listing_id)
        return client.post(path, json=payload)

    # ------------------------------------------------------------------
    # Spec 011 P-PUB-IMAGES + P-PUB-MULTI-IMAGE (MP006 2026-05-27)
    # ------------------------------------------------------------------
    # Original MVP: single image_1920. Multi-image pivot 2026-05-27:
    # iterate main image_1920 first, then multichannel.product.image
    # gallery rows sorted by sequence; cap at Etsy's 10-image limit;
    # per-image upload failure logs WARNING and continues to the next.
    ETSY_MAX_IMAGES = 10

    def upload_images(self, tmpl, listing_id, shop):
        """POST /shops/{shop_id}/listings/{listing_id}/images for main + gallery.

        Etsy's uploadListingImage endpoint is shop-scoped; the bare
        listings/{id}/images path 404s (surfaced by the real-product UAT
        2026-05-28 — every upload silently failed via the per-image WARNING).

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
        api_shop_id = shop.sudo().etsy_api_shop_id
        if not api_shop_id:
            raise ValueError(
                "Etsy shop %r missing etsy_api_shop_id; cannot upload images."
                % shop.name
            )
        client = EtsyApiClient(shop)
        path = "shops/%s/listings/%s/images" % (api_shop_id, listing_id)
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

            # R-PUB-PERSONALIZATION-ENDPOINTS: set personalization via the
            # dedicated endpoint (inline createListing fields deprecated by
            # Etsy 2026). Best-effort — a personalization failure must not
            # block the listing from publishing; log and continue.
            try:
                self.push_personalization(tmpl, listing_id, shop)
            except Exception as exc:  # noqa: BLE001 — personalization is non-fatal
                _logger.warning(
                    "Etsy personalization push failed for listing %s: %s; "
                    "continuing with publish chain", listing_id, exc,
                )

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
