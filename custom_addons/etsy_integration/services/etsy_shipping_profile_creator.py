"""Etsy shipping profile creator (P-LIST-SHIP-CREATE / Jira ESTY-201).

Pushes a NEW manual flat-rate shipping profile to Etsy via
``POST /shops/{shop_id}/shipping-profiles`` and upserts the result into
the ``etsy.shipping.profile`` cache (mirroring the read-only syncer's
write shape). The created row carries ``source='odoo_create'`` so it is
distinguishable from synced profiles yet still resolved by the publisher.

Calculated/carrier-rate profiles are *not* creatable through the Etsy
API — only manual profiles — so this service is intentionally limited to
the manual flat-rate shape. See ``createShopShippingProfile`` in the Etsy
v3 reference.
"""

import logging

from odoo import _
from odoo import fields as odoo_fields
from odoo.exceptions import UserError

from .etsy_api_client import EtsyApiClient

_logger = logging.getLogger(__name__)


def create_profile(env, shop, payload, client=None):
    """Create one shipping profile on Etsy and cache it.

    ``payload`` is the already-validated, Etsy-ready form dict (built by
    the wizard): ``title``, ``origin_country_iso``, ``primary_cost``,
    ``secondary_cost``, the delivery-day pair, and exactly one of
    ``destination_country_iso`` / ``destination_region`` (or neither).

    Returns the created ``etsy.shipping.profile`` record. Raises
    ``UserError`` on any Etsy failure so the wizard surfaces a clean
    message and the whole transaction rolls back (no orphan cache row).
    """
    api_shop_id = shop.sudo().etsy_api_shop_id
    if not api_shop_id:
        raise UserError(_(
            "Shop %s has no Etsy shop id; authorize the shop before "
            "creating shipping profiles.", shop.display_name,
        ))
    path = 'shops/%s/shipping-profiles' % api_shop_id

    # Etsy createShopShippingProfile is application/x-www-form-urlencoded,
    # so send via the client's form ``data=`` path (not ``json=``).
    if client is None:
        client = EtsyApiClient(shop)
    try:
        response = client.post(path, data=payload)
    except UserError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface any vendor/transport error
        # EtsyApiClient already WARNING-logs the 4xx/403 body; re-wrap as a
        # user-facing message. str(exc) on a 4xx carries the captured body.
        raise UserError(_(
            "Etsy rejected the shipping profile: %s", exc,
        )) from exc

    etsy_id = (response or {}).get('shipping_profile_id')
    if etsy_id is None:
        raise UserError(_(
            "Etsy did not return a shipping_profile_id; profile not created.",
        ))

    Profile = env['etsy.shipping.profile'].sudo()
    now = odoo_fields.Datetime.now()
    # etsy_id cast to str — Etsy ids can exceed XML-RPC int32 (gotcha #144).
    profile = Profile.create({
        'shop_id': shop.id,
        'etsy_profile_id': str(etsy_id),
        'title': response.get('title') or payload.get('title') or '',
        'origin_country_iso': (
            response.get('origin_country_iso')
            or payload.get('origin_country_iso') or '')[:2],
        'is_deleted': bool(response.get('is_deleted')),
        'active': not bool(response.get('is_deleted')),
        'source': 'odoo_create',
        'created_at': now,
        'last_synced_at': now,
    })

    # Success audit row (same txn — commits with the profile). The api
    # client already logs failures via its 4xx body-capture WARNING.
    env['etsy.api.log'].sudo().create({
        'shop_id': shop.id,
        'endpoint': 'POST /v3/application/%s' % path,
        'http_status': 200,
        'source': 'shipping_profile_create',
        'request_payload_summary': 'title=%s origin=%s' % (
            payload.get('title'), payload.get('origin_country_iso'),
        ),
        'response_summary': 'shipping_profile_id=%s' % etsy_id,
    })
    return profile
