"""Etsy shipping profile syncer (P-LIST-SHIPPING).

Per-shop pull from ``GET /shops/{shop_id}/shipping-profiles``. Each
profile is keyed on ``(shop_id, shipping_profile_id)``. Soft-deletes
(``is_deleted=true`` from Etsy) are kept in the cache and surfaced as
``active=False`` so historical listings still resolve their label.
"""

import logging

from odoo import fields as odoo_fields

from .etsy_api_client import EtsyApiClient

_logger = logging.getLogger(__name__)


def sync_shipping_profiles(env, shop, client=None):
    """Pull + upsert. Returns ``(created, updated)``."""
    if client is None:
        client = EtsyApiClient(shop)
    api_shop_id = shop.sudo().etsy_api_shop_id
    if not api_shop_id:
        _logger.warning(
            "Etsy shipping profile sync: shop %r has no etsy_api_shop_id; "
            "skipping.", shop.name,
        )
        return 0, 0
    path = 'shops/%s/shipping-profiles' % api_shop_id
    response = client.get(path)
    rows = (response or {}).get('results') or []
    if not rows:
        _logger.info(
            "Etsy shipping profile sync (shop %r): empty list.", shop.name,
        )
        return 0, 0

    Profile = env['etsy.shipping.profile'].sudo()
    now = odoo_fields.Datetime.now()
    created = 0
    updated = 0
    for row in rows:
        etsy_id = row.get('shipping_profile_id')
        if etsy_id is None:
            continue
        vals = {
            'title': row.get('title') or '',
            'origin_country_iso': (row.get('origin_country_iso') or '')[:2],
            'is_deleted': bool(row.get('is_deleted')),
            'active': not bool(row.get('is_deleted')),
            'last_synced_at': now,
        }
        existing = Profile.search([
            ('shop_id', '=', shop.id),
            ('etsy_profile_id', '=', str(etsy_id)),
        ], limit=1)
        if existing:
            existing.write(vals)
            updated += 1
        else:
            Profile.create(dict(
                vals, shop_id=shop.id, etsy_profile_id=str(etsy_id),
            ))
            created += 1
    _logger.info(
        "Etsy shipping profile sync (shop %r): %s created, %s updated, %s total.",
        shop.name, created, updated, len(rows),
    )
    return created, updated
