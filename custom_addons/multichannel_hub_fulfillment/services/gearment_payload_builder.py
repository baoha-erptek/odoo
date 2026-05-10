"""Build a `GearmentOrderPayload` from a sale.order recordset.

Pure function — no ORM mutation, no I/O.

P4-01-B (2026-05-10) regen: legacy single-product schema replaced with the
real `/api/v3/orders/draft` schema (reference_id + addresses[] + line_items[]).
Buyer-supplied notes are HTML-escaped before going into the payload so the
downstream Gearment API response cannot smuggle HTML/script content back into
chatter rendering on the dashboard.
"""
from __future__ import annotations

from html import escape

from .gearment_payload import (
    GearmentAddress,
    GearmentLineItem,
    GearmentOrderPayload,
)


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
        state=(partner.state_id.code or partner.state_id.name) if partner.state_id else None,
        zip_code=partner.zip or '',
        country_code=(partner.country_id.code or '') if partner.country_id else '',
        phone=partner.phone or getattr(partner, 'mobile', None) or None,
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
        url_front = next(
            (
                (df.file_url or df.gdrive_preview_url)
                for df in line_designs
                if (df.file_url or df.gdrive_preview_url)
            ),
            None,
        )
        url_back = next(
            (
                (df.file_url or df.gdrive_preview_url)
                for df in line_designs[1:]
                if (df.file_url or df.gdrive_preview_url)
            ),
            None,
        )
        line_items.append(GearmentLineItem(
            product_id=_safe_int(sku),
            quantity=int(line.product_uom_qty or 0),
            sku=sku,
            design_url_front=url_front,
            design_url_back=url_back,
            personalisation=getattr(line, 'etsy_personalisation', None) or None,
        ))

    notes = escape((order.note or '').strip())[:1024] if order.note else None

    carrier = order.fulfillment_id.shipping_carrier_id if order.fulfillment_id else None
    shipping_method = (carrier.gearment_carrier_name if carrier else '') or 'standard'

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
        addresses=(address,),
        line_items=tuple(line_items),
        shipping_method=shipping_method,
        notes=notes,
    )


def _safe_int(sku: str) -> int:
    """Gearment's `line_items[].product_id` is an integer (catalog legacy_product_id).

    The merchant's x_gearment_sku is sometimes the raw int, sometimes a stringy
    code. Coerce best-effort; non-numeric SKUs fall back to 0 which Gearment
    will reject — the operator sees the validation error in chatter and fixes
    the product master.
    """
    try:
        return int(sku)
    except (TypeError, ValueError):
        return 0
