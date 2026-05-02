"""Build a `GearmentOrderPayload` from a sale.order recordset.

Pure function — no ORM mutation, no I/O.

Buyer-supplied notes are markup-escaped before going into the payload
so the downstream Gearment API response cannot smuggle HTML/script
content back into chatter rendering on the dashboard.
"""
from __future__ import annotations

from html import escape

from .gearment_payload import GearmentOrderPayload


def build_payload(order, design_files) -> GearmentOrderPayload:
    """Translate a sale.order into the Gearment outbound DTO.

    `design_files` should be pre-filtered to states in
    `{'approved', 'proof_sent'}` by the caller.

    The current adapter contract (P0-18b1) takes a single product +
    quantity per payload. For multi-line orders we use the first line
    that has a Gearment SKU and sum its quantity. Multi-item splitting
    is a follow-up (P4-01b).
    """
    order.ensure_one()
    partner = order.partner_shipping_id or order.partner_id

    address = {
        'name': partner.name or '',
        'street': partner.street or '',
        'street2': partner.street2 or '',
        'city': partner.city or '',
        'state': (partner.state_id.code or partner.state_id.name) if partner.state_id else '',
        'zip': partner.zip or '',
        'country': partner.country_id.code or '',
        'phone': partner.phone or getattr(partner, 'mobile', None) or '',
        'email': partner.email or '',
    }

    primary_sku = ''
    primary_qty = 0
    for line in order.order_line:
        sku = (line.product_id.product_tmpl_id.x_gearment_sku or '').strip()
        if sku:
            primary_sku = sku
            primary_qty = int(line.product_uom_qty or 0)
            break

    designs = [
        {
            'name': df.name or '',
            'url': df.file_url or df.gdrive_preview_url or '',
            'state': df.state,
        }
        for df in design_files
        if (df.file_url or df.gdrive_preview_url)
    ]

    notes = escape((order.note or '').strip())[:1024] if order.note else None

    carrier = order.fulfillment_id.shipping_carrier_id if order.fulfillment_id else None
    shipping_method = (carrier.gearment_carrier_name if carrier else '') or 'standard'

    store_id = ''
    if 'etsy_shop_id' in order._fields and order.etsy_shop_id:
        store_id = str(getattr(order.etsy_shop_id, 'etsy_shop_id', '')) \
            or order.etsy_shop_id.display_name or ''

    return GearmentOrderPayload(
        external_order_id=order.channel_order_ref or order.name,
        platform=order.sales_channel or 'other',
        store_id=store_id,
        quantity=primary_qty,
        product_id=primary_sku,
        address=address,
        shipping_method=shipping_method,
        design_files=designs,
        notes=notes,
    )
