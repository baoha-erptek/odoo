"""P1-MTO-SEED migration — activate MTO route + Manufacture product_selectable.

Mirrors `_enable_mto_seed_routes` from `multichannel_hub_core/__init__.py` so
the route configuration is applied on the upgrade path (`-u`) as well as the
fresh-install path (`-i`).

Idempotent: only writes when the desired state is missing.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):  # noqa: ARG001
    from odoo import api, SUPERUSER_ID  # local import — Odoo migration convention

    env = api.Environment(cr, SUPERUSER_ID, {})

    # System-wide side effect: activating these standard Odoo routes makes
    # them assignable to any product by users who already have product write
    # rights. No new privilege is granted (route assignment was already gated
    # by product write ACL); the change only removes a UI-level domain filter
    # so the wizard can attach the routes. ADR-010 amendment 2026-05-03
    # authorizes this as part of the hybrid dropship + MTO architecture.
    mto_route = env.ref('stock.route_warehouse0_mto', raise_if_not_found=False)
    if mto_route and not mto_route.active:
        mto_route.active = True
        _logger.info("P1-MTO-SEED: activated stock.route_warehouse0_mto")

    manufacture_route = env.ref(
        'mrp.route_warehouse0_manufacture', raise_if_not_found=False,
    )
    if manufacture_route and not manufacture_route.product_selectable:
        manufacture_route.product_selectable = True
        _logger.info(
            "P1-MTO-SEED: enabled product_selectable on "
            "mrp.route_warehouse0_manufacture"
        )
