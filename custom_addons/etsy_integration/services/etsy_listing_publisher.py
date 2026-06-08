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

from odoo import _, fields
from odoo.exceptions import UserError

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
    # P-BUG-ESTY-188 iter3 — per-variant SKU / starting price (ADR-014 §4.a)
    # ------------------------------------------------------------------

    # Etsy SKU max length per /v3/application/listings/.../inventory contract.
    ETSY_SKU_MAX_LEN = 32

    @staticmethod
    def _slugify_value_name(name):
        """Etsy-safe slug: uppercase, alnum only, ``"`` → ``IN`` (inch glyph).

        Empty input returns an empty string — caller decides whether that's
        fatal (UserError) or a fallback to template SKU.
        """
        if not name:
            return ''
        # Inch glyphs (straight and curly) → 'IN' so e.g. ``6"`` slugs to
        # ``6IN`` rather than disappearing entirely.
        cleaned = name.replace('"', 'IN').replace('”', 'IN').replace("''", 'IN')
        cleaned = re.sub(r'[^A-Za-z0-9]+', '', cleaned).upper()
        return cleaned

    @classmethod
    def _synthesize_variant_sku(cls, base, value_names):
        """Compose ``{base}-{slug1}{slug2}...`` clamped to ``ETSY_SKU_MAX_LEN``.

        Raises ``UserError`` when both ``base`` and every slug are empty —
        Etsy 400s on empty SKU and the operator needs a clear hint to set
        ``default_code`` on the template or a per-variant SKU.

        When truncation kicks in, the suffix end is dropped (preserves the
        base + most-significant first axis) and a WARNING is logged.
        """
        slugs = [cls._slugify_value_name(v) for v in (value_names or [])]
        slug = ''.join(s for s in slugs if s)
        base = (base or '').strip()
        if not base and not slug:
            raise UserError(_(
                "Etsy publish: cannot synthesize a variant SKU — template has "
                "no default_code AND the variant has no attribute values to "
                "derive a suffix from. Set default_code on the product or on "
                "at least one variant."
            ))
        if not base:
            sku = slug
        elif not slug:
            sku = base
        else:
            sku = '%s-%s' % (base, slug)
        if len(sku) > cls.ETSY_SKU_MAX_LEN:
            _logger.warning(
                "Etsy SKU %r exceeds %d chars; truncating from the suffix end.",
                sku, cls.ETSY_SKU_MAX_LEN,
            )
            sku = sku[:cls.ETSY_SKU_MAX_LEN]
        return sku

    def _resolve_variant_sku(self, tmpl, variant):
        """Per-variant SKU: ``variant.default_code`` wins; else synthesize.

        For dynamic-variant axes the matching ``product.product`` does not
        exist; pass an empty recordset and the caller has already passed
        ``value_names`` separately via ``_synthesize_variant_sku``.
        """
        if variant and variant.default_code:
            return variant.default_code
        base = self._resolve_sku(tmpl)
        if variant:
            value_names = variant.product_template_attribute_value_ids.mapped(
                lambda ptav: ptav.product_attribute_value_id.name
            )
        else:
            value_names = []
        return self._synthesize_variant_sku(base, value_names)

    def _resolve_starting_price(self, tmpl, shop):
        """Listing ``price`` for createListing — minimum positive variant price.

        Strategy:
          1. Collect positive ``variant.lst_price`` across materialized variants
             (``product.product``).  ``lst_price`` already includes
             ``price_extra`` on top of the template ``list_price``.
          2. If any positives → return min(positives) converted to shop currency.
          3. Else fall back to the template ``list_price`` converted.
          4. If the resulting value is still ``0`` → ``UserError``.  Etsy 400s
             with ``/price: empty`` otherwise; the operator needs to set
             ``list_price`` on the template or ``price_extra`` on at least one
             variant.
        """
        t = tmpl.sudo()
        positives = [
            float(v.lst_price)
            for v in t.product_variant_ids
            if v.lst_price and v.lst_price > 0
        ]
        raw = min(positives) if positives else float(t.list_price or 0.0)
        if raw <= 0:
            raise UserError(_(
                "Etsy publish: cannot resolve a positive starting price for "
                "%r. Set list_price on the product or price_extra on at least "
                "one variant before publishing."
            ) % t.name)
        return self._convert_to_shop_currency(raw, shop)

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
    def _property_value_for(axis, value_name, intent=None, shop=None):
        """Build one Etsy property_values[] entry for an (axis, value) pair.

        Returns ``{property_id, property_name, values}`` or ``None`` when the
        axis is not publishable or is missing its Etsy property id/name.

        **3-tier resolution chain (UX review HIGH #4 — spec 012 §US6)**:
          1. ``intent.attribute_mapping_ids`` per-listing override (P-LIST-ATTRIBUTES)
          2. ``shop.default_attribute_mapping_ids`` shop-wide default (P-LIST-ATTR-CONFIG)
          3. ``product.attribute.x_etsy_property_id`` product global

        Empty override at any tier falls through to the next. Returns
        ``None`` + WARNING when no tier carries a numeric id (Etsy 400s on
        an empty property_id).
        """
        if not axis.x_publish_as_property:
            return None
        raw = None
        name = None
        # Tier 1 — per-listing override
        if intent and intent.attribute_mapping_ids:
            for row in intent.attribute_mapping_ids:
                if row.product_attribute_id.id != axis.id:
                    continue
                if row.etsy_property_id_override:
                    raw = row.etsy_property_id_override
                if row.etsy_property_name_override:
                    name = row.etsy_property_name_override
                break
        # Tier 2 — shop default mapping
        if (not raw or not name) and shop and shop.default_attribute_mapping_ids:
            for row in shop.default_attribute_mapping_ids:
                if row.product_attribute_id.id != axis.id:
                    continue
                if not raw and row.etsy_property_id_override:
                    raw = row.etsy_property_id_override
                if not name and row.etsy_property_name_override:
                    name = row.etsy_property_name_override
                break
        # Tier 3 — product.attribute global
        if not raw:
            raw = axis.x_etsy_property_id
        if not name:
            name = axis.x_etsy_property_name
        if not raw or not name:
            _logger.warning(
                "product.attribute id=%s name=%r missing x_etsy_property_id "
                "or x_etsy_property_name across all 3 tiers; skipping it as "
                "an Etsy variation property.", axis.id, axis.name,
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
    # P-LIST-HOW-ITS-MADE who_made/when_made/is_supply (ADR-015 / spec 012)
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_who_made(tmpl, shop, intent):
        if intent and intent.etsy_who_made:
            return intent.etsy_who_made
        return tmpl.x_who_made or shop.default_who_made or 'i_did'

    @staticmethod
    def _resolve_when_made(tmpl, shop, intent):
        if intent and intent.etsy_when_made:
            return intent.etsy_when_made
        return tmpl.x_when_made or shop.default_when_made or 'made_to_order'

    @staticmethod
    def _resolve_is_supply(tmpl, shop, intent):
        # is_supply has no per-product surface; intent override wins,
        # otherwise shop default. Defaults False when neither set.
        if intent and intent.etsy_is_supply:
            return True
        return bool(shop.default_is_supply)

    # ------------------------------------------------------------------
    # P-LIST-SHIPPING shipping-profile resolver (ADR-015 / spec 012)
    # ------------------------------------------------------------------
    def _resolve_shipping_profile_id(self, tmpl, shop):
        """listing override → shop default → soft 0 (consistent with the
        P-LIST-CATEGORY pre-hardening behaviour)."""
        intent = self._resolve_listing_intent(tmpl, shop)
        if intent and intent.etsy_shipping_profile_id:
            raw = intent.etsy_shipping_profile_id.etsy_profile_id
            if raw and raw.isdigit():
                return int(raw)
        try:
            return int(shop.default_shipping_profile_id or 0)
        except (TypeError, ValueError):
            return 0

    # ------------------------------------------------------------------
    # P-LIST-CATEGORY taxonomy resolver (ADR-015 / spec 012)
    # ------------------------------------------------------------------
    def _resolve_taxonomy_id(self, tmpl, shop):
        """Etsy createListing requires a numeric ``taxonomy_id``.

        Resolution order (per ADR-015 §3 fallback chain):
          1. ``multichannel.listing.etsy_taxonomy_id`` (per-listing override)
          2. ``product.template.x_taxonomy_id`` (per-product fallback,
             pre-iter3 site)
          3. ``etsy.shop.default_taxonomy_id`` (shop default)
          4. ``0`` — matches the pre-slice behavior. Etsy 400s with a
             missing-field error in that case; a future hardening slice
             will raise ``UserError`` here once every production shop is
             guaranteed to carry a default.
        """
        intent = self._resolve_listing_intent(tmpl, shop)
        if intent and intent.etsy_taxonomy_id:
            raw = intent.etsy_taxonomy_id.etsy_id
            if raw and raw.isdigit():
                return int(raw)
        per_product = tmpl.x_taxonomy_id if hasattr(tmpl, 'x_taxonomy_id') else None
        if per_product:
            try:
                return int(per_product)
            except (TypeError, ValueError):
                pass
        shop_default = shop.default_taxonomy_id
        if shop_default:
            try:
                return int(shop_default)
            except (TypeError, ValueError):
                pass
        return 0

    # ------------------------------------------------------------------
    # P-ENH-ESTY-190 / ADR-017 — 3-tier title/description/image fallback
    # (listing intent → product template → shop default).
    # ------------------------------------------------------------------
    def _resolve_title_with_fallback(self, intent, tmpl, shop_sudo):
        """Resolve listing title across the 3-tier chain.

        ``intent`` may be an empty recordset when no per-shop listing row
        exists. ``shop_sudo`` is the sudo'd ``etsy.shop`` recordset
        already used by the payload builder. Returns '' when every tier
        is empty so the publisher never emits None.
        """
        listing_val = intent.title if intent else ''
        if listing_val:
            return listing_val
        product_val = tmpl.name or ''
        if product_val:
            return product_val
        shop_default = shop_sudo.default_title or ''
        if shop_default:
            _logger.debug(
                "P-ENH-ESTY-190: title resolved from shop default; "
                "shop=%s template=%s",
                shop_sudo.name, tmpl.id,
            )
            return shop_default
        return ''

    def _resolve_description_with_fallback(self, intent, tmpl, shop_sudo):
        """Resolve listing description across the 3-tier chain.

        Mirrors title resolution. Preserves the legacy double-fallback to
        ``tmpl.name`` after ``description_sale`` for compatibility with
        templates that lack a sales description — shop-default sits
        between description_sale and that final name-as-description
        rescue.
        """
        listing_val = (intent.description if intent else '') or ''
        if listing_val:
            return listing_val
        product_val = tmpl.description_sale or ''
        if product_val:
            return product_val
        shop_default = shop_sudo.default_description or ''
        if shop_default:
            _logger.debug(
                "P-ENH-ESTY-190: description resolved from shop default; "
                "shop=%s template=%s",
                shop_sudo.name, tmpl.id,
            )
            return shop_default
        return tmpl.name or ''

    def _resolve_image_with_fallback(self, tmpl, shop_sudo):
        """Resolve listing hero image across the 3-tier chain.

        Used by ``upload_images`` when neither the template main image
        nor any gallery row carries binary data. Returns False when every
        tier is empty so callers can short-circuit before any POST.
        """
        if tmpl.image_1920:
            return tmpl.image_1920
        shop_default = shop_sudo.default_image_1920
        if shop_default:
            _logger.debug(
                "P-ENH-ESTY-190: hero image resolved from shop default; "
                "shop=%s template=%s",
                shop_sudo.name, tmpl.id,
            )
            return shop_default
        return False

    # ------------------------------------------------------------------
    # Listing intent resolver (P-LIST-MODEL — ADR-015)
    # ------------------------------------------------------------------
    def _resolve_listing_intent(self, tmpl, shop):
        """Locate the ``multichannel.listing`` row that drives marketing
        overrides for this (template, etsy channel, shop) tuple.

        Resolution order:
          1. row matching shop.name (per-shop intent)
          2. row with shop_ref NULL/empty (template-wide intent — backfill stub)
          3. nothing → empty recordset; callers fall back to template fields
        """
        Listing = self.env['multichannel.listing'].sudo()
        Channel = self.env.ref(
            'multichannel_hub_core.channel_etsy',
            raise_if_not_found=False,
        )
        if not Channel:
            return Listing.browse([])
        shop_name = (shop.sudo().name or '').strip()
        if shop_name:
            # P-PUB-RESOLVER-CASING-BUG (2026-06-08): etsy.shop.name is CamelCase
            # operator-entered (e.g. 'JaHandmadeArt'); multichannel.listing.shop_ref
            # stores the Etsy URL slug form ('jahandmadeart'). Use case-insensitive
            # `=ilike` with literal `_` / `%` escaped so the LIKE wildcards don't
            # leak from shop_name into the SQL pattern. Backslash is also escaped
            # because Odoo's =ilike emits `ESCAPE '\\'`.
            escaped = shop_name.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            specific = Listing.search([
                ('product_tmpl_id', '=', tmpl.id),
                ('channel_id', '=', Channel.id),
                ('shop_ref', '=ilike', escaped),
            ], limit=1)
            if specific:
                return specific
        return Listing.search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', Channel.id),
            '|', ('shop_ref', '=', False), ('shop_ref', '=', ''),
        ], limit=1)

    def _resolve_shop_specific_listing(self, tmpl, shop):
        """Return the shop-specific ``multichannel.listing`` row (no NULL-shop
        fallback). Used by ``run()`` to write the post-publish state back to
        the exact row that corresponds to (template, shop) — never the
        template-wide stub. Mirrors ``_resolve_listing_intent`` step 1 only.

        P-LIST-PUBLISH-STATE-SYNC (2026-06-08): the read-side resolver falls
        through to the NULL-shop stub on cache miss, which is correct for
        field-fallback semantics but wrong for writeback (would tag the
        wrong row as published / errored).
        """
        Listing = self.env['multichannel.listing'].sudo()
        Channel = self.env.ref(
            'multichannel_hub_core.channel_etsy',
            raise_if_not_found=False,
        )
        if not Channel:
            return Listing.browse([])
        shop_name = (shop.sudo().name or '').strip()
        if not shop_name:
            return Listing.browse([])
        # Same escape pattern as _resolve_listing_intent — see comments there.
        # KEEP IN SYNC with the read-side resolver: if the escape rule changes
        # there (e.g. Unicode handling), update both helpers in the same commit.
        escaped = shop_name.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        return Listing.search([
            ('product_tmpl_id', '=', tmpl.id),
            ('channel_id', '=', Channel.id),
            ('shop_ref', '=ilike', escaped),
        ], limit=1)

    # ------------------------------------------------------------------
    # Payload builder
    # ------------------------------------------------------------------
    def _build_create_draft_payload(self, tmpl, shop):
        # tmpl.sudo() — read attributes regardless of caller's stock-read ACL;
        # the wizard's FR-017 gate proved BA membership upstream.
        s = tmpl.sudo()
        sh = shop.sudo()
        # P-LIST-MODEL: marketing overrides (title/description) read from the
        # multichannel.listing intent layer; empty fields fall back to template.
        # Single lookup shared by every resolver in the payload builder.
        # P-ENH-ESTY-190 / ADR-017: extend 2-tier chain to 3-tier by adding
        # shop-level brand-voice defaults (etsy.shop.default_title /
        # .default_description) as the final fallback before the empty
        # string. Resolution helpers log DEBUG when shop default fires so
        # operators can audit which tier supplied the final value.
        intent = self._resolve_listing_intent(s, shop)
        title = self._resolve_title_with_fallback(intent, s, sh)
        description = self._resolve_description_with_fallback(intent, s, sh)
        payload = {
            'sku': self._resolve_sku(s),
            'title': title,
            'description': description,
            # P-BUG-ESTY-188 iter3: `price` is the listing "starts at" value;
            # derive from the minimum positive variant lst_price (which already
            # includes per-variant price_extra) and convert to shop currency.
            # iter2 currency conversion is encapsulated inside the helper.
            'price': self._resolve_starting_price(s, shop),
            'quantity': max(int(s.qty_available or 0), 1),
            # Spec 011 P-PUB-PER-PRODUCT-DEFAULTS — per-product override wins
            # over shop default; falls back to hardcoded legacy default when
            # both are blank. is_supply stays shop-wide (not in override scope).
            'who_made': self._resolve_who_made(s, sh, intent),
            'when_made': self._resolve_when_made(s, sh, intent),
            'is_supply': self._resolve_is_supply(s, sh, intent),
            'taxonomy_id': self._resolve_taxonomy_id(s, sh),
            'shipping_profile_id': self._resolve_shipping_profile_id(s, sh),
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

    def _variant_for_combo(self, tmpl, combo_value_ids):
        """Materialized ``product.product`` matching the value combination.

        Returns an empty recordset when no variant matches (typical for
        dynamic-variant axes — variants only materialize on first sale).
        Caller MUST check truthiness (``if variant:``) before accessing
        fields; every call site has a template-level fallback strategy.
        """
        variants = tmpl.product_variant_ids
        # Prefetch the M2M + indirect attribute-value ids in one batch so
        # the per-variant loop does not trigger an N+1.
        variants.mapped('product_template_attribute_value_ids.product_attribute_value_id')
        for variant in variants:
            vids = set(variant.product_template_attribute_value_ids
                       .mapped('product_attribute_value_id').ids)
            if vids and vids.issubset(combo_value_ids):
                return variant
        return variants.browse([])

    def _variant_qty_for_combo(self, tmpl, combo_value_ids):
        """Quantity for a value combination (set of ``product.attribute.value``
        ids), preferring a matching materialized variant's on-hand qty; falls
        back to the template's ``qty_available`` when no ``product.product``
        matches.
        """
        variant = self._variant_for_combo(tmpl, combo_value_ids)
        if variant:
            return variant.qty_available
        return tmpl.qty_available

    def push_inventory(self, tmpl, listing_id, shop):
        """PUT /listings/{listing_id}/inventory with the full products[] array.

        Per ADR-014 §4.a (2026-06-06 P-BUG-ESTY-188 iter3 amendment), Etsy's
        native model is per-variant: each ``products[]`` entry carries its own
        ``sku`` + ``offerings[].quantity/price``. The sibling
        ``sku_on_property[]`` / ``quantity_on_property[]`` / ``price_on_property[]``
        arrays list the varying axes whose values drive distinct SKUs / qty /
        prices — Etsy rejects mixed dimensions unless the corresponding axis is
        declared in the sibling list.

        R-PUB-VARIANT-MATERIALIZE (2026-05-28) still applies: variations come
        from the cartesian product of publishable variant-creating attribute
        lines, NOT from ``product.product`` records. Per-variant SKU / price
        derive from the matching ``product.product`` when materialized; from
        the synthesized slug + ``list_price`` when not.
        """
        if not listing_id:
            raise ValueError("push_inventory requires a non-empty listing_id")
        t = tmpl.sudo()
        base_sku = self._resolve_sku(t)
        readiness = shop.sudo().default_readiness_state_id
        # iter2 currency conversion is invoked per offering inside the loop;
        # we still pre-compute the template-level fallback price once.
        template_price = self._convert_to_shop_currency(t.list_price, shop)
        # P-LIST-ATTRIBUTES — resolve the listing intent ONCE so the
        # per-axis property_value_for lookup can read the per-listing
        # mapping overrides.
        intent = self._resolve_listing_intent(t, shop)

        def _offering(qty, price):
            o = {'quantity': max(int(qty or 0), 1), 'price': float(price), 'is_enabled': True}
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
        sh = shop.sudo()
        fixed_props = []
        for line in fixed:
            pv = self._property_value_for(
                line.attribute_id, line.value_ids[0].name,
                intent=intent, shop=sh,
            )
            if pv:
                fixed_props.append(pv)

        products_payload = []
        if varying:
            for combo in itertools.product(*[list(line.value_ids) for line in varying]):
                props = list(fixed_props)
                for line, value in zip(varying, combo):
                    pv = self._property_value_for(
                        line.attribute_id, value.name,
                        intent=intent, shop=sh,
                    )
                    if pv:
                        props.append(pv)
                combo_ids = {v.id for v in combo}
                combo_ids.update(line.value_ids[0].id for line in fixed)
                variant = self._variant_for_combo(t, combo_ids)
                if variant and variant.default_code:
                    sku = variant.default_code
                else:
                    value_names = [v.name for v in combo]
                    sku = self._synthesize_variant_sku(base_sku, value_names)
                if variant and variant.lst_price and variant.lst_price > 0:
                    price = self._convert_to_shop_currency(variant.lst_price, shop)
                else:
                    price = template_price
                qty = variant.qty_available if variant else t.qty_available
                products_payload.append({
                    'sku': sku,
                    'property_values': props,
                    'offerings': [_offering(qty, price)],
                })
        else:
            # No varying axis → a single product (with any fixed properties).
            products_payload.append({
                'sku': base_sku,
                'property_values': fixed_props,
                'offerings': [_offering(t.qty_available, template_price)],
            })

        # SKU collision guard (code-reviewer iter3 HIGH): if synthesized or
        # truncated SKUs collide across distinct variants, surface a clear
        # UserError BEFORE Etsy 400s on duplicate SKUs within products[].
        if len(products_payload) > 1:
            seen_skus = {}
            for p in products_payload:
                key = p['sku']
                if key in seen_skus and p['property_values'] != seen_skus[key]:
                    raise UserError(_(
                        "Etsy publish: SKU %r is shared by two variants with "
                        "different attribute values. This usually means the "
                        "base SKU is too long and synthesized SKUs collided "
                        "after the %d-char Etsy truncation. Shorten the "
                        "template's default_code or set explicit per-variant "
                        "default_code values."
                    ) % (key, self.ETSY_SKU_MAX_LEN))
                seen_skus[key] = p['property_values']

        # Sibling arrays — Etsy requires them when SKU / qty / price differ
        # across products. Compute by looking at distinct dimension values.
        body = {'products': products_payload}
        if varying and len(products_payload) > 1:
            distinct_skus = {p['sku'] for p in products_payload}
            distinct_qty = {p['offerings'][0]['quantity'] for p in products_payload}
            distinct_price = {p['offerings'][0]['price'] for p in products_payload}
            varying_prop_ids = []
            for line in varying:
                raw = line.attribute_id.x_etsy_property_id
                if not raw:
                    continue
                varying_prop_ids.append(int(raw) if raw.isdigit() else raw)
            if varying_prop_ids:
                if len(distinct_skus) > 1:
                    body['sku_on_property'] = list(varying_prop_ids)
                if len(distinct_qty) > 1:
                    body['quantity_on_property'] = list(varying_prop_ids)
                if len(distinct_price) > 1:
                    body['price_on_property'] = list(varying_prop_ids)

        client = EtsyApiClient(shop)
        path = "listings/%s/inventory" % listing_id
        response = client.put(path, json=body)
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
        sh = shop.sudo()
        candidates = []
        if t.image_1920:
            candidates.append(('main', t.image_1920))
        for row in t.x_extra_image_ids.sorted('sequence'):
            if row.image_1920:
                candidates.append(('gallery', row.image_1920))
        # P-ENH-ESTY-190 / ADR-017 — when neither template main image nor
        # gallery has anything, fall back to shop-level default. Keeps the
        # listing publishable even for products waiting on Marketing's
        # photoshoot; the shop default is the brand-voice rescue.
        if not candidates and sh.default_image_1920:
            _logger.debug(
                "P-ENH-ESTY-190: hero image resolved from shop default; "
                "shop=%s template=%s listing=%s",
                sh.name, tmpl.id, listing_id,
            )
            candidates.append(('shop_default', sh.default_image_1920))
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
    # P-LIST-VIDEO — uploadListingVideo (Etsy: 1 video per listing)
    # ------------------------------------------------------------------
    # OAS contract:
    #   POST /v3/application/shops/{shop_id}/listings/{listing_id}/videos
    #   multipart/form-data: { name: <filename>, video: <binary> }
    # The intent record's ir.attachment carries both: ``datas`` is base64
    # binary content; ``name`` is the original filename. Empty intent or
    # no attachment → no-op (returns {}).
    def push_video(self, tmpl, listing_id, shop):
        """Upload one video per listing to Etsy via uploadListingVideo.

        Reads the multichannel.listing intent attachment for this shop
        (per ADR-015 layer). No intent / no video → returns {} silently.
        Failures raise — caller (``run()``) treats them as non-fatal.
        """
        if not listing_id:
            raise ValueError("push_video requires a non-empty listing_id")
        intent = self._resolve_listing_intent(tmpl, shop)
        if not intent or not intent.video_attachment_id:
            return {}
        # Sudo required: service-layer publisher reads the attachment binary;
        # the marketing-user ACL on multichannel.listing already proved write
        # authority to attach the video, so the read at this boundary mirrors
        # the FR-017 service-layer defense pattern used by upload_images.
        attachment = intent.video_attachment_id.sudo()
        raw = attachment.datas
        if not raw:
            _logger.warning(
                "multichannel.listing %s video attachment %s has empty "
                "datas; skipping push_video for listing %s.",
                intent.id, attachment.id, listing_id,
            )
            return {}
        api_shop_id = shop.sudo().etsy_api_shop_id
        if not api_shop_id:
            raise ValueError(
                "Etsy shop %r missing etsy_api_shop_id; cannot push video."
                % shop.name
            )
        try:
            payload_bytes = base64.b64decode(raw)
        except Exception as exc:  # noqa: BLE001 — defensive only
            _logger.warning(
                "Failed to b64-decode video attachment id=%s for listing %s: %s",
                attachment.id, listing_id, exc,
            )
            return {}
        filename = attachment.name or 'video.mp4'
        mimetype = attachment.mimetype or 'video/mp4'
        client = EtsyApiClient(shop)
        path = "shops/%s/listings/%s/videos" % (api_shop_id, listing_id)
        files = {
            'video': (filename, payload_bytes, mimetype),
        }
        data = {'name': filename}
        return client.post_multipart(path, files=files, data=data)

    # ------------------------------------------------------------------
    # P-BUG-ESTY-188 iter3 — Variation images (ADR-014 §4.a)
    # ------------------------------------------------------------------
    # Per Etsy OAS:
    #   POST /v3/application/shops/{shop_id}/listings/{listing_id}/variation-images
    #   body: {"variation_images": [{"property_id": int, "value_id": int,
    #                                "image_id": int}]}
    # Each entry binds ONE image to ONE (property_id × value_id) pair — not per
    # combo. ``image_id`` is the ``listing_image_id`` returned by a prior
    # ``uploadListingImage`` call.
    def push_variation_images(self, tmpl, listing_id, shop):
        """Upload each variant's ``image_variant_1920`` then bind via
        ``updateVariationImages``.

        Best-effort: per-variant upload failure logs WARNING and skips that
        variant; the overall listing publish must not be blocked. Returns the
        list of bindings actually POSTed (empty when no variant carries an
        image or every upload failed).
        """
        if not listing_id:
            raise ValueError(
                "push_variation_images requires a non-empty listing_id"
            )
        t = tmpl.sudo()
        api_shop_id = shop.sudo().etsy_api_shop_id
        if not api_shop_id:
            raise ValueError(
                "Etsy shop %r missing etsy_api_shop_id; cannot push "
                "variation images." % shop.name
            )

        # Only variants whose attribute belongs to a *publishable* variation
        # axis can be bound — otherwise Etsy can't render the variation.
        publishable_attr_ids = {
            line.attribute_id.id
            for line in t.attribute_line_ids
            if line.attribute_id.create_variant != 'no_variant'
            and line.attribute_id.x_publish_as_property
            and line.attribute_id.x_etsy_property_id
        }
        if not publishable_attr_ids:
            return []

        client = EtsyApiClient(shop)
        upload_path = "shops/%s/listings/%s/images" % (api_shop_id, listing_id)
        sku_base = t.default_code or 'variant'

        bindings = []
        for variant in t.product_variant_ids:
            if not variant.image_variant_1920:
                continue
            try:
                payload_bytes = base64.b64decode(variant.image_variant_1920)
            except Exception as exc:  # noqa: BLE001 — defensive only
                _logger.warning(
                    "Skipping variation image for variant id=%s on listing %s "
                    "— decode failed: %s",
                    variant.id, listing_id, exc,
                )
                continue
            files = {
                'image': (
                    '%s_v%s.jpg' % (sku_base, variant.id),
                    payload_bytes,
                    'image/jpeg',
                ),
            }
            try:
                upload_response = client.post_multipart(upload_path, files=files)
            except Exception as exc:  # noqa: BLE001 — partial-failure resilience
                _logger.warning(
                    "Variation image upload failed for variant id=%s on "
                    "listing %s: %s", variant.id, listing_id, exc,
                )
                continue
            image_id_raw = (upload_response or {}).get('listing_image_id')
            if not image_id_raw:
                _logger.warning(
                    "uploadListingImage returned no listing_image_id for "
                    "variant id=%s on listing %s; skipping binding.",
                    variant.id, listing_id,
                )
                continue
            try:
                image_id = int(image_id_raw)
            except (TypeError, ValueError):
                _logger.warning(
                    "uploadListingImage returned non-integer listing_image_id="
                    "%r for variant id=%s on listing %s; skipping binding.",
                    image_id_raw, variant.id, listing_id,
                )
                continue
            for ptav in variant.product_template_attribute_value_ids:
                if ptav.attribute_id.id not in publishable_attr_ids:
                    continue
                raw_prop = ptav.attribute_id.x_etsy_property_id
                prop_id = int(raw_prop) if str(raw_prop).isdigit() else raw_prop
                bindings.append({
                    'property_id': prop_id,
                    'value_id': ptav.product_attribute_value_id.id,
                    'image_id': image_id,
                })

        if not bindings:
            return []
        # ``listing_id`` originates from Etsy's createListing response, not
        # operator input — path-injection is semantically impossible in the
        # integer namespace Etsy emits. ``api_shop_id`` is shop-config-only
        # and group_system-gated upstream.
        bind_path = "shops/%s/listings/%s/variation-images" % (
            api_shop_id, listing_id,
        )
        client.post(bind_path, json={'variation_images': bindings})
        return bindings

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
            # P-BUG-ESTY-188 iter3 — bind per-variant images. Best-effort:
            # partial / total failure of variation-images must not block
            # the listing from publishing.
            try:
                self.push_variation_images(tmpl, listing_id, shop)
            except Exception as exc:  # noqa: BLE001 — non-fatal
                _logger.warning(
                    "Etsy push_variation_images failed for listing %s: %s; "
                    "continuing with publish chain", listing_id, exc,
                )
            # P-LIST-VIDEO — push the per-listing video when intent carries
            # one. Best-effort: video failures must not block publish (the
            # listing is still viable without video; operator can retry
            # via the wizard).
            try:
                self.push_video(tmpl, listing_id, shop)
            except Exception as exc:  # noqa: BLE001 — non-fatal
                _logger.warning(
                    "Etsy push_video failed for listing %s: %s; continuing "
                    "with publish chain", listing_id, exc,
                )
            self.publish(listing_id, shop)
            existing.write({
                'state': 'published',
                'last_sync_error': False,
            })
            # P-LIST-PUBLISH-STATE-SYNC (2026-06-08): mirror the success state
            # onto the shop-specific multichannel.listing row so the marketing
            # statusbar reflects what's live on Etsy. sudo() because BA-role
            # publish must write to the Marketing-owned model. Empty
            # recordset (no shop-specific listing row, or no shop name) is a
            # no-op — product.channel.status above stays as the source of truth.
            listing_row = self._resolve_shop_specific_listing(tmpl, shop)
            if listing_row:
                listing_row.write({'state': 'published'})
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
            # P-LIST-PUBLISH-STATE-SYNC (2026-06-08): mirror error state onto
            # the shop-specific multichannel.listing row. Wrapped in try/except
            # so a listing-state write failure cannot mask the original publish
            # exception that we are about to re-raise.
            try:
                listing_row = self._resolve_shop_specific_listing(tmpl, shop)
                if listing_row:
                    listing_row.write({'state': 'error'})
            except Exception as state_exc:  # noqa: BLE001 — best-effort
                _logger.warning(
                    "Failed to mirror error state onto multichannel.listing "
                    "for tmpl=%s shop=%s: %s", tmpl.id, shop.id, state_exc,
                )
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
