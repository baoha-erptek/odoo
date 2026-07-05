"""Build a `GearmentOrderPayload` from a sale.order recordset.

Pure function — no ORM mutation, no I/O.

P4-01-B (2026-05-10) regen: legacy single-product schema replaced with the
real `/api/v3/orders/draft` schema. 2026-07-05: corrected to the proven-200
shape (singular `address`, `platform`, `variant_id`, METHOD_STANDARD) — see
`gearment_payload.py` for the wire example. `notes` is not part of the draft
schema, so it is no longer built.
"""
from __future__ import annotations

from .gearment_payload import (
    GearmentAddress,
    GearmentLineItem,
    GearmentOrderPayload,
)

# Default location-code assignment when design.file lacks a per-record code.
# Gearment's draft validator wants the proto3 enum `PRINT_LOCATION_CODE_*`, NOT
# the bare human names (front/back/pocket/whole) it quotes in its 400 message —
# that mismatch was Defect-2026-05-10-05 (opaque 400 on every draft push). Wire
# values confirmed from the doc crawl 2026-07-05
# (docs/vendor/gearment/api_api.order.v1.vendororderapi.md, example
# PRINT_LOCATION_CODE_WHOLE). Two-sided print is the dominant Etsy POD pattern;
# positions beyond back are skipped until a per-design override field lands.
# NOTE: the QUOTE endpoint uses a different shape (`print_locations: ["front"]`,
# lowercase) — do not reuse these values there.
_PRINT_LOCATIONS_DEFAULT = ('PRINT_LOCATION_CODE_FRONT', 'PRINT_LOCATION_CODE_BACK')

# Draft `platform` enum. Only Etsy flows through this pipeline today; the draft
# API 404s "marketplace not found" without it.
# ponytail: hard-coded ETSY — add a channel->platform map when a 2nd channel ships.
_PLATFORM_ETSY = 'MARKETPLACE_PLATFORM_ETSY'

# Draft `shipping_method` enum (proto MethodType). Only STANDARD is proven live.
# ponytail: single value — map carrier.gearment_carrier_name -> METHOD_* when
# expedited/priority services are actually offered.
_SHIPPING_METHOD_DEFAULT = 'METHOD_STANDARD'

# The QUOTE endpoint (POST /api/v3/orders/price) uses a DIFFERENT, lowercase
# vocabulary than the draft: `order_platform: "etsy"`, `print_locations: ["front"]`,
# `shipping.address.method: "standard"`. Proven live 200 on 2026-07-05
# (order_total returned). Do NOT reuse the draft's proto-enum constants here.
_QUOTE_PLATFORM_ETSY = 'etsy'
_QUOTE_SHIPPING_METHOD = 'standard'
_PRINT_LOCATIONS_QUOTE = ('front', 'back')


def build_payload(order, design_files) -> GearmentOrderPayload:
    """Translate a sale.order into the Gearment outbound DTO (P4-01-B schema).

    `design_files` should be pre-filtered to states in
    `{'approved', 'proof_sent'}` by the caller.

    Each `sale.order.line` with a non-empty `x_gearment_sku` becomes a
    GearmentLineItem. Lines without the SKU are skipped (e.g. shipping line,
    or items on a non-Gearment fulfilment route).
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

    # Index design files by line so we can attach front/back URLs to the right
    # GearmentLineItem. design.file has order_line_id (P1-02a/b).
    designs_by_line: dict[int, list] = {}
    for df in design_files:
        line_id = df.order_line_id.id if df.order_line_id else None
        if line_id:
            designs_by_line.setdefault(line_id, []).append(df)

    line_items: list[GearmentLineItem] = []
    for line in order.order_line:
        sku = (line.product_id.product_tmpl_id.x_gearment_sku or '').strip()
        if not sku:
            continue
        line_designs = designs_by_line.get(line.id, [])
        # P4-01-FIX-PAYLOAD-SCHEMA: Gearment requires `printing_options[]` with
        # at least one entry per line. Build deterministically: first design.file
        # → PRINT_LOCATION_CODE_FRONT; second → PRINT_LOCATION_CODE_BACK.
        # Per-design `location_code` override is deferred to a future slice once
        # design.file gains the field. URL preference: file_url → gdrive_preview_url.
        printing_options = tuple(
            {
                'location_code': code,
                'url': df.file_url or df.gdrive_preview_url,
            }
            for code, df in zip(_PRINT_LOCATIONS_DEFAULT, line_designs)
            if (df.file_url or df.gdrive_preview_url)
        )
        if not printing_options:
            # Skip line entirely — Gearment rejects orders containing line_items
            # with empty printing_options. The operator sees the missing-design
            # gap on the dashboard's design_status indicator instead.
            continue
        line_items.append(GearmentLineItem(
            # x_gearment_sku holds the GM-prefixed catalog variant_id
            # (e.g. GM0249020374) — the draft's line-item key (Defect-05-10-02).
            variant_id=sku,
            quantity=int(line.product_uom_qty or 0),
            printing_options=printing_options,
            personalisation=getattr(line, 'etsy_personalisation', None) or None,
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
        shipping_method=_SHIPPING_METHOD_DEFAULT,
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

    designs_by_line: dict[int, int] = {}
    for df in design_files:
        line_id = df.order_line_id.id if df.order_line_id else None
        if line_id and (df.file_url or df.gdrive_preview_url):
            designs_by_line[line_id] = designs_by_line.get(line_id, 0) + 1

    line_items: list[dict] = []
    for line in order.order_line:
        sku = (line.product_id.product_tmpl_id.x_gearment_sku or '').strip()
        if not sku:
            continue
        design_count = min(designs_by_line.get(line.id, 0), len(_PRINT_LOCATIONS_QUOTE))
        if not design_count:
            continue
        line_items.append({
            'variant_id': sku,
            'quantity': int(line.product_uom_qty or 0),
            'print_locations': list(_PRINT_LOCATIONS_QUOTE[:design_count]),
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
