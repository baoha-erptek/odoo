"""Build a `GearmentOrderPayload` from a sale.order recordset.

Pure function — no ORM mutation, no I/O.

P4-01-B (2026-05-10) regen: legacy single-product schema replaced with the
real `/api/v3/orders/draft` schema. 2026-07-05: corrected to the proven-200
shape (singular `address`, `platform`, `variant_id`, METHOD_STANDARD) — see
`gearment_payload.py` for the wire example. `notes` is not part of the draft
schema, so it is no longer built.
"""
from __future__ import annotations

import logging

from odoo import _
from odoo.exceptions import UserError

from .gearment_payload import (
    GearmentAddress,
    GearmentLineItem,
    GearmentOrderPayload,
)

_logger = logging.getLogger(__name__)

# Gearment's draft validator wants the proto3 enum `PRINT_LOCATION_CODE_*`, NOT
# the bare human names (front/back/pocket/whole) it quotes in its 400 message —
# that mismatch was Defect-2026-05-10-05 (opaque 400 on every draft push). Wire
# values confirmed from the doc crawl 2026-07-05
# (docs/vendor/gearment/api_api.order.v1.vendororderapi.md, example
# PRINT_LOCATION_CODE_WHOLE).
# P-GEAR-PRINT-SIDES: `design.file.print_location` picks the side explicitly;
# unset files fall back to positional assignment in id-ASC order (oldest =
# front). NOTE: the QUOTE endpoint uses a different shape
# (`print_locations: ["front"]`, lowercase) — do not reuse these values there.
_SIDES = ('front', 'back')
_WIRE_LOCATION = {
    'front': 'PRINT_LOCATION_CODE_FRONT',
    'back': 'PRINT_LOCATION_CODE_BACK',
}

# Draft `platform` enum. Only Etsy flows through this pipeline today; the draft
# API 404s "marketplace not found" without it.
# ponytail: hard-coded ETSY — add a channel->platform map when a 2nd channel ships.
_PLATFORM_ETSY = 'MARKETPLACE_PLATFORM_ETSY'

# Draft `shipping_method` enum (proto MethodType). Only STANDARD is proven live
# (200 on 2026-07-05); the vendor doc crawl exposes no other MethodType values,
# so unverified METHOD_* constants would 400 the draft.
_SHIPPING_METHOD_DEFAULT = 'METHOD_STANDARD'

# FLW-04: Etsy shipping-service label (lowercased substring) -> Gearment
# MethodType. Grows once Gearment confirms its enum values; until then every
# service ships METHOD_STANDARD, but expedited buyer-paid services are flagged
# loudly (WARNING) instead of silently downgraded.
_SHIPPING_METHOD_MAP: dict[str, str] = {}
_EXPEDITED_HINTS = ('express', 'priority', 'expedited', 'rush', 'overnight')


def _resolve_shipping_method(order):
    """Map the order's channel shipping-service label to a Gearment method.

    Uses the channel-agnostic `sale.order.shipping_service_label` shadow
    (P1-01b, mhc) so this stays Etsy-independent.
    """
    label = (order.shipping_service_label or '').strip().lower()
    for needle, method in _SHIPPING_METHOD_MAP.items():
        if needle in label:
            return method
    if any(hint in label for hint in _EXPEDITED_HINTS):
        _logger.warning(
            "Gearment push %s: buyer paid for shipping service %r but only "
            "METHOD_STANDARD is available on the Gearment wire — shipping "
            "standard. Extend _SHIPPING_METHOD_MAP once Gearment confirms "
            "its MethodType enum values.",
            order.name, order.shipping_service_label,
        )
    return _SHIPPING_METHOD_DEFAULT

# The QUOTE endpoint (POST /api/v3/orders/price) uses a DIFFERENT, lowercase
# vocabulary than the draft: `order_platform: "etsy"`, `print_locations: ["front"]`,
# `shipping.address.method: "standard"`. Proven live 200 on 2026-07-05
# (order_total returned). Do NOT reuse the draft's proto-enum constants here.
_QUOTE_PLATFORM_ETSY = 'etsy'
_QUOTE_SHIPPING_METHOD = 'standard'


def _printable_designs_by_line(design_files):
    """Index design files by order-line id, keeping only files with a URL."""
    by_line: dict[int, list] = {}
    for df in design_files:
        if not df.order_line_id:
            continue
        if not (df.file_url or df.gdrive_preview_url):
            continue
        by_line.setdefault(df.order_line_id.id, []).append(df)
    return by_line


def _assign_sides(line_designs, line_label):
    """Return [(side, design.file)] front-first for one order line.

    Explicit `print_location` wins. Unset files fill the remaining free
    sides in id-ASC order — oldest file prints front. (The old positional
    zip iterated the recordset in its natural `create_date DESC` order,
    which put the NEWEST file on the front.) Duplicate explicit sides
    raise; unset files beyond the free sides are dropped (legacy 2-file cap).
    """
    designs = sorted(line_designs, key=lambda d: d.id or 0)
    explicit = [d.print_location for d in designs if d.print_location]
    duplicated = sorted({s for s in explicit if explicit.count(s) > 1})
    if duplicated:
        raise UserError(_(
            "Cannot build the Gearment order: product '%(product)s' has "
            "more than one approved design file on the same print side "
            "(%(sides)s). Set a distinct Print Location on each file.",
            product=line_label, sides=', '.join(duplicated),
        ))
    free = [s for s in _SIDES if s not in explicit]
    assigned = []
    for d in designs:
        if d.print_location:
            assigned.append((d.print_location, d))
        elif free:
            assigned.append((free.pop(0), d))
    return sorted(assigned, key=lambda pair: _SIDES.index(pair[0]))


def build_payload(order, design_files) -> GearmentOrderPayload:
    """Translate a sale.order into the Gearment outbound DTO (P4-01-B schema).

    `design_files` should be pre-filtered to states in
    `{'approved', 'proof_sent'}` by the caller.

    Each `sale.order.line` with a resolvable GM variant id becomes a
    GearmentLineItem (FLW-01: variant-level supplierinfo `product_code`
    first, template `x_gearment_sku` fallback). Lines without one are
    skipped (e.g. shipping line, or items on a non-Gearment route);
    multi-variant products without a variant-specific code raise.
    """
    order.ensure_one()
    partner = order.partner_shipping_id or order.partner_id

    # Split free-form name into first/last for the Gearment schema. The split
    # is best-effort: if the partner only has a single token, last_name gets
    # an empty string. Gearment's validator rejects fully empty fields.
    full_name = (partner.name or '').strip()
    if ' ' in full_name:
        first_name, last_name = full_name.split(' ', 1)
    else:
        first_name, last_name = (full_name, full_name) if full_name else ('-', '-')

    address = GearmentAddress(
        first_name=first_name,
        last_name=last_name,
        street_1=partner.street or '',
        street_2=partner.street2 or None,
        city=partner.city or '',
        state_code=(partner.state_id.code or partner.state_id.name) if partner.state_id else None,
        zip_code=partner.zip or '',
        country_code=(partner.country_id.code or '') if partner.country_id else '',
        phone_no=partner.phone or getattr(partner, 'mobile', None) or None,
        email=partner.email or None,
    )

    # Index design files by line so we can attach per-side URLs to the right
    # GearmentLineItem. design.file has order_line_id (P1-02a/b).
    designs_by_line = _printable_designs_by_line(design_files)

    line_items: list[GearmentLineItem] = []
    for line in order.order_line:
        product = line.product_id
        # FLW-01: per-variant GM id (Gearment vendor supplierinfo.product_code)
        # first, template x_gearment_sku fallback (single-variant products).
        sku = product._gearment_resolved_sku()
        if not sku:
            continue
        product_label = product.display_name or line.name or sku
        if (product.product_tmpl_id.product_variant_count > 1
                and not product._gearment_variant_code()):
            # Template fallback on a multi-variant product would push the
            # SAME GM variant for every size/color — the FLW-01 bug. Push
            # is the hard gate; fail loudly so the operator maps variants.
            raise UserError(_(
                "Cannot push to Gearment: product '%(product)s' has "
                "variants, but this variant has no Gearment variant code. "
                "On the product's Purchase tab, add the Gearment vendor "
                "line for this exact variant with its GM variant id as "
                "Vendor Product Code.",
                product=product_label,
            ))
        line_designs = designs_by_line.get(line.id, [])
        if not line_designs:
            # P-GEAR-PRINT-SIDES: was a silent `continue` that shipped the
            # order WITHOUT this line (findings 2026-07-05 (C)). Fail loudly
            # so the operator fixes the design gap before pushing.
            raise UserError(_(
                "Cannot push to Gearment: product '%(product)s' has no "
                "approved design file with a usable URL. Upload and approve "
                "a design for it first.",
                product=product_label,
            ))
        # P4-01-FIX-PAYLOAD-SCHEMA: Gearment requires `printing_options[]`
        # with at least one entry per line. URL preference:
        # file_url → gdrive_preview_url.
        printing_options = tuple(
            {
                'location_code': _WIRE_LOCATION[side],
                'url': df.file_url or df.gdrive_preview_url,
            }
            for side, df in _assign_sides(line_designs, product_label)
        )
        line_items.append(GearmentLineItem(
            # sku is the GM-prefixed catalog variant_id (e.g. GM0249020374)
            # — the draft's line-item key (Defect-05-10-02); per-variant
            # resolution since FLW-01.
            variant_id=sku,
            quantity=int(line.product_uom_qty or 0),
            printing_options=printing_options,
        ))

    store_id = ''
    if 'etsy_shop_id' in order._fields and order.etsy_shop_id:
        store_id = (
            str(getattr(order.etsy_shop_id, 'etsy_shop_id', ''))
            or order.etsy_shop_id.display_name
            or ''
        )

    return GearmentOrderPayload(
        reference_id=order.channel_order_ref or order.name,
        store_id=store_id,
        platform=_PLATFORM_ETSY,
        addresses=(address,),
        line_items=tuple(line_items),
        shipping_method=_resolve_shipping_method(order),
        # FLW-05: documented draft field; buyer already paid the gift fee
        # on Etsy. mhc shadow field (P1-01b), so no ei dependency.
        gift_message_body=(order.gift_message or '').strip() or None,
    )


def build_quote_body(order, design_files) -> dict:
    """Build the `POST /api/v3/orders/price` body (pure, no I/O).

    The price-quote endpoint is separate from the draft and uses a lowercase
    vocabulary: `order_platform: "etsy"`, `shipping.address.{method,state_code,
    country_code}`, and per-line `print_locations: ["front", ...]`. Only lines
    with `x_gearment_sku` (the GM variant_id) and at least one design file are
    quoted — mirroring `build_payload`. Proven live 200 on 2026-07-05.
    """
    order.ensure_one()
    partner = order.partner_shipping_id or order.partner_id

    designs_by_line = _printable_designs_by_line(design_files)

    line_items: list[dict] = []
    for line in order.order_line:
        # FLW-01: same per-variant resolution as build_payload, but no
        # multi-variant strictness — the quote is advisory; push is the gate.
        sku = line.product_id._gearment_resolved_sku()
        if not sku:
            continue
        line_designs = designs_by_line.get(line.id, [])
        if not line_designs:
            # Quote is advisory — skip the line instead of raising; the
            # push path (`build_payload`) is the hard gate.
            continue
        product_label = line.product_id.display_name or line.name or sku
        line_items.append({
            'variant_id': sku,
            'quantity': int(line.product_uom_qty or 0),
            'print_locations': [
                side for side, _df in _assign_sides(line_designs, product_label)
            ],
        })

    return {
        'order_platform': _QUOTE_PLATFORM_ETSY,
        'shipping': {
            'address': {
                'method': _QUOTE_SHIPPING_METHOD,
                'state_code': (partner.state_id.code or None) if partner.state_id else None,
                'country_code': (partner.country_id.code or '') if partner.country_id else '',
            },
        },
        'line_items': line_items,
    }
