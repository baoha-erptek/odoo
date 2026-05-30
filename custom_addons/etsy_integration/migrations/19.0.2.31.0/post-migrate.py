"""Post-migrate for P1-11-SHOPID-BOOTSTRAP.

Refuses to complete the module upgrade when any ``etsy.shop`` row has
``active_source='api'`` but a NULL or empty ``etsy_api_shop_id``. Such rows
predate the C-ESY-003 constraint and would 403 every Etsy API call (Etsy
returns ``"User does not own Shop {odoo_pk}"`` when the URL shop_id is wrong).

The fix path for the operator: re-Authorize the affected shop (auto-fetches
the field via ``EtsyApiClient.fetch_users_me_shop_id()`` introduced in this
slice) or manually populate the field from the Etsy admin UI, then re-run
``-u etsy_integration``.
"""


def migrate(cr, version):
    # Raw SQL justification: migrations run with a bare cursor (no Environment,
    # no Model classes loaded for the in-progress version). Direct SQL is the
    # only way to read shop state at upgrade time. The query is read-only,
    # parameterless, and operates on a known schema column.
    cr.execute(
        """
        SELECT id, name FROM etsy_shop
        WHERE active_source = 'api'
          AND (etsy_api_shop_id IS NULL OR etsy_api_shop_id = '')
        ORDER BY id
        """
    )
    rows = cr.fetchall()
    if not rows:
        return

    listing = '\n'.join('  - %s (id=%s)' % (name, sid) for sid, name in rows)
    raise Exception(
        "etsy_integration 19.0.2.31.0 cannot complete: %d Etsy shop(s) "
        "have active_source='api' but no etsy_api_shop_id (C-ESY-003). "
        "Affected:\n%s\n\nFix: re-Authorize the shop(s) from the Etsy Shop "
        "form (the OAuth callback now auto-populates the field) OR manually "
        "set etsy_api_shop_id in the form (admin, system group) OR flip "
        "active_source back to 'email' until the shop is ready. Then re-run "
        "`-u etsy_integration`." % (len(rows), listing)
    )
