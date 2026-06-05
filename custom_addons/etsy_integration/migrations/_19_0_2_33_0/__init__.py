"""P-BUG-ESTY-188 — bootstrap default_readiness_state_id on existing shops.

This module is the testable Python entry point. The Odoo standard discovery
path at ``migrations/19.0.2.33.0/post-migrate.py`` is a thin shim that
constructs an ``Environment`` and delegates here.

Why a separate package: Odoo migration directories are named with dots
(``19.0.2.33.0``) which are not valid Python identifiers, so the
auto-discovered file cannot be imported by tests. The underscore-prefixed
mirror gives us import-stability for Phase 2 ORM tests while preserving
Odoo's standard migration discovery.

Root cause being fixed (Jira ESTY-188 / Sub-phase 3h Wave 1):
``etsy.shop.default_readiness_state_id`` was added in 19.0.2.15.0 but never
bootstrapped on shops that pre-existed that release. Etsy's createListing
endpoint 400s with "A readiness_state_id is required for physical listings"
when the publisher payload omits the field, which it does whenever the shop
column is NULL.

Fix shape: for every ``active_source='api'`` shop missing the field, call
``GET /shops/{etsy_api_shop_id}/readiness-state-definitions`` and store the
first definition's id. Email-only shops and shops without an
``etsy_api_shop_id`` are skipped (no Etsy API surface).

Per-shop failures are logged and swallowed so that a single shop with an
expired OAuth token or a transient network blip does not block the upgrade
for the rest.
"""

import logging

_logger = logging.getLogger(__name__)


def post_migrate(cr, env):
    """Bootstrap ``etsy.shop.default_readiness_state_id`` on existing shops.

    Args:
        cr: Odoo database cursor (post-migrate phase; module fully loaded).
        env: ``odoo.api.Environment`` bound to ``cr`` with SUPERUSER_ID.

    Behaviour:
        - Iterate every ``etsy.shop`` where ``active_source = 'api'`` AND
          ``default_readiness_state_id`` is empty.
        - Skip rows missing ``etsy_api_shop_id`` (no URL to call).
        - For each, instantiate ``EtsyApiClient(shop)`` and call
          ``client.get("/shops/{shop_id}/readiness-state-definitions")``.
        - Persist the first definition's id (as ``Char`` since Etsy ids
          overflow XML-RPC int32 — see ``feedback_odoo19_test_gotchas`` 144).
        - Per-shop exceptions are caught + logged WARNING and do not re-raise.

    Returns:
        None.
    """
    shops = env["etsy.shop"].sudo().search(
        [
            ("active_source", "=", "api"),
            ("default_readiness_state_id", "in", (False, "")),
        ]
    )
    if not shops:
        _logger.debug(
            "P-BUG-ESTY-188 migration: no shops need readiness-state bootstrap"
        )
        return

    # Late import: the client lives in the same addon and is fully loaded by
    # the post-migrate phase. Top-level import would couple this migration
    # package to the services package import order.
    from odoo.addons.etsy_integration.services.etsy_api_client import (
        EtsyApiClient,
    )

    for shop in shops:
        if not shop.etsy_api_shop_id:
            _logger.warning(
                "P-BUG-ESTY-188: shop id=%s (%s) has active_source=api but no "
                "etsy_api_shop_id; skipping readiness-state bootstrap",
                shop.id,
                shop.name,
            )
            continue
        try:
            client = EtsyApiClient(shop)
            definitions = client.get(
                "/shops/%s/readiness-state-definitions" % shop.etsy_api_shop_id
            )
        except Exception as exc:  # noqa: BLE001 - per-shop swallow is intentional
            _logger.warning(
                "P-BUG-ESTY-188: failed to fetch readiness-state-definitions "
                "for shop id=%s (%s): %s",
                shop.id,
                shop.name,
                exc,
            )
            continue

        first_id = _first_definition_id(definitions)
        if not first_id:
            _logger.warning(
                "P-BUG-ESTY-188: shop id=%s (%s) returned no usable "
                "readiness-state definitions; left field empty",
                shop.id,
                shop.name,
            )
            continue

        shop.sudo().write({"default_readiness_state_id": str(first_id)})
        _logger.info(
            "P-BUG-ESTY-188: bootstrapped shop id=%s (%s) "
            "default_readiness_state_id=%s",
            shop.id,
            shop.name,
            first_id,
        )


def _first_definition_id(payload):
    """Pull the first readiness-state-definition id from an Etsy response.

    Etsy returns either a list of definitions or a ``{"results": [...]}``
    envelope depending on the endpoint version. Accept both shapes; the
    test fixture uses the bare-list form.
    """
    if isinstance(payload, dict):
        payload = payload.get("results") or payload.get("readiness_state_definitions") or []
    if not isinstance(payload, list) or not payload:
        return None
    first = payload[0]
    if not isinstance(first, dict):
        return None
    return first.get("readiness_state_definition_id") or first.get("id")
