"""P-BUG-ESTY-188 iter2 — bootstrap listing_currency_id on existing shops.

Testable Python entry point. Odoo's standard discovery path at
``migrations/19.0.2.34.0/post-migrate.py`` is a thin shim that constructs
an ``Environment`` and delegates here. The underscore-prefixed mirror gives
us import-stability for Phase 2 ORM tests (dotted dir is not a valid Python
identifier).

Root cause being fixed (Jira ESTY-188 / Sub-phase 3h Wave 1, iter2):
``etsy.shop.listing_currency_id`` is a new Many2one field added in
19.0.2.34.0. Existing shops created before this release have NULL; the
publisher cannot convert outbound list_price from company currency to shop
currency, so Etsy 400s with ``price_too_low`` when the company currency
differs from the shop's listing currency (e.g. USD company publishing to a
VND Etsy shop).

Fix shape: for every ``active_source='api'`` shop missing the field, call
``GET /shops/{etsy_api_shop_id}`` (Etsy's shop-metadata endpoint), read
``currency_code`` from the response, resolve to ``res.currency`` and write
the Many2one. Email-only shops and shops without an ``etsy_api_shop_id``
are skipped. Per-shop failures are logged WARNING and swallowed so a
single shop's expired token or transient blip does not block the upgrade.

``EtsyApiClient`` is imported at MODULE scope (not inside the function)
because Phase 2 tests patch ``...migrations._19_0_2_34_0.EtsyApiClient``
and a late-import inside the function would defeat that patch.
"""

import logging

from odoo.addons.etsy_integration.services.etsy_api_client import EtsyApiClient

_logger = logging.getLogger(__name__)


def post_migrate(cr, env):
    """Bootstrap ``etsy.shop.listing_currency_id`` on existing shops.

    Args:
        cr: Odoo database cursor (post-migrate phase; module fully loaded).
        env: ``odoo.api.Environment`` bound to ``cr`` with SUPERUSER_ID.

    Behaviour:
        - Iterate every ``etsy.shop`` where ``active_source = 'api'`` AND
          ``listing_currency_id`` is empty.
        - Skip rows missing ``etsy_api_shop_id`` (no URL to call).
        - For each, instantiate ``EtsyApiClient(shop)`` and call
          ``client.get("/shops/{etsy_api_shop_id}")``.
        - Read ``currency_code`` from the response.
        - Resolve to ``res.currency`` (search by name, active_test=False so
          dormant currencies like VND are eligible); skip + WARNING if no
          match.
        - Per-shop exceptions are caught + logged WARNING and do not
          re-raise.

    Returns:
        None.
    """
    # active_test=False so archived shops are also bootstrapped — owner may
    # un-archive later and the field should already be populated. This also
    # covers raw-SQL-inserted fixtures in tests where ``active`` is NULL.
    shops = env["etsy.shop"].sudo().with_context(active_test=False).search(
        [
            ("active_source", "=", "api"),
            ("listing_currency_id", "=", False),
        ]
    )
    if not shops:
        _logger.debug(
            "P-BUG-ESTY-188 iter2: no shops need listing_currency_id bootstrap"
        )
        return

    Currency = env["res.currency"].sudo().with_context(active_test=False)

    for shop in shops:
        if not shop.etsy_api_shop_id:
            _logger.warning(
                "P-BUG-ESTY-188 iter2: shop id=%s (%s) has active_source=api but "
                "no etsy_api_shop_id; skipping listing_currency_id bootstrap",
                shop.id,
                shop.name,
            )
            continue

        try:
            client = EtsyApiClient(shop)
            shop_data = client.get("/shops/%s" % shop.etsy_api_shop_id)
        except Exception as exc:  # noqa: BLE001 - per-shop swallow is intentional
            # Log exception TYPE only; the exception's string form can
            # carry response-body context from Etsy which (defensively) we
            # don't want flowing into install logs.
            _logger.warning(
                "P-BUG-ESTY-188 iter2: failed to fetch shop metadata for "
                "shop id=%s (%s): %s",
                shop.id,
                shop.name,
                type(exc).__name__,
            )
            continue

        currency_code = (shop_data or {}).get("currency_code")
        if not currency_code:
            _logger.warning(
                "P-BUG-ESTY-188 iter2: shop id=%s (%s) returned no currency_code; "
                "left listing_currency_id empty",
                shop.id,
                shop.name,
            )
            continue

        currency = Currency.search([("name", "=", currency_code)], limit=1)
        if not currency:
            _logger.warning(
                "P-BUG-ESTY-188 iter2: shop id=%s (%s) has currency_code=%r but "
                "no matching res.currency record; left listing_currency_id empty",
                shop.id,
                shop.name,
                currency_code,
            )
            continue

        # We do NOT activate the currency here even if dormant (VND ships
        # active=False in 19 CE). Activating a global res.currency row from
        # an install-time migration would silently change currency-selector
        # dropdowns everywhere in the database. Operator must manually
        # enable the currency in Settings > Currencies if their Odoo
        # workflow needs it visible; ``_convert`` works on inactive
        # currencies because it only reads the rate row.
        shop.sudo().write({"listing_currency_id": currency.id})
        _logger.info(
            "P-BUG-ESTY-188 iter2: bootstrapped shop id=%s (%s) "
            "listing_currency_id=%s (currency_code=%s)",
            shop.id,
            shop.name,
            currency.id,
            currency_code,
        )
