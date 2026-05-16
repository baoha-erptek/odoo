"""P1-11a post-migration — ADR-008a §2 / data-model.md §1.

Maps the legacy `etsy.shop.sync_mode` enum onto the new
`active_source` selector and bootstraps the append-only
`etsy.shop.source.change.log` audit with one `reason='bootstrap'`
row per existing shop. `sync_mode` is intentionally NOT dropped
(dual-column transition window); a later slice retires it.

Raw SQL justification: migrations run before the ORM registry for
the upgraded module is fully usable for these tables; the mapping is
a single set-based UPDATE and the bootstrap is an idempotent
NOT EXISTS INSERT — both are clearer and safer in SQL.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Map every shop from its authoritative legacy sync_mode. Idempotent:
    # re-running yields the same deterministic mapping.
    cr.execute("""
        UPDATE etsy_shop
        SET active_source = CASE
            WHEN sync_mode = 'api_only' THEN 'api'
            WHEN sync_mode = 'email_only' THEN 'email'
            ELSE 'email'
        END
    """)
    _logger.info(
        "P1-11a: mapped sync_mode -> active_source for %s shop(s).",
        cr.rowcount,
    )

    # The audit table is created in the schema phase of this same
    # upgrade; guard defensively in case ordering ever changes.
    cr.execute("SELECT to_regclass('etsy_shop_source_change_log')")
    if not cr.fetchone()[0]:
        _logger.warning(
            "P1-11a: etsy_shop_source_change_log table absent at "
            "post-migration; skipping bootstrap (T047 model missing)."
        )
        return

    # One bootstrap row per shop that has none yet (NOT EXISTS keeps
    # this idempotent across repeated upgrades).
    cr.execute("""
        INSERT INTO etsy_shop_source_change_log
            (shop_id, from_source, to_source, reason, changed_at,
             create_uid, write_uid, create_date, write_date)
        SELECT s.id, NULL, s.active_source, 'bootstrap', now(),
               1, 1, now(), now()
        FROM etsy_shop s
        WHERE NOT EXISTS (
            SELECT 1 FROM etsy_shop_source_change_log l
            WHERE l.shop_id = s.id
        )
    """)
    _logger.info(
        "P1-11a: inserted %s bootstrap source-change row(s).",
        cr.rowcount,
    )
