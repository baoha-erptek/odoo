"""P-LIST-MODEL backfill — stub `multichannel.listing` per existing live template.

ADR-015 §6: non-destructive backfill. For every (product.template,
multichannel.sales.channel) pair where the template already has either
a corresponding ``product.channel.status`` row OR an ``etsy.listing`` row,
create one ``multichannel.listing`` stub with all override fields null so
the publisher's fallback chain reproduces today's behavior unchanged.

Importable Python package (sibling to the Odoo-discovery directory
``19.0.1.0.65/``) so the helper is unit-testable without engaging Odoo's
migration runner. Same pattern as etsy_integration ``_19_0_2_33_0`` /
``_19_0_2_34_0`` (see memory `feedback_etsy_inventory_property_name_and_noupdate_seed.md`
plus the etsy_integration test_p_bug_esty_188_phase2_orm_iter1.py tests).
"""

import logging

_logger = logging.getLogger(__name__)


def backfill_listings(env):
    """Create one stub ``multichannel.listing`` row per (tmpl, channel) pair
    derived from existing live rows. Idempotent — running twice yields the
    same set of rows because the PG UNIQUE index in
    ``multichannel.listing.init()`` collapses duplicate inserts.

    Returns ``(created, skipped)`` for caller logging.
    """
    Listing = env['multichannel.listing'].sudo()
    Status = env['product.channel.status'].sudo()

    # Source 1: every existing product.channel.status row implies operator
    # intent for that (template, channel) pair.
    pairs = set()
    for row in Status.search([]):
        if row.product_tmpl_id and row.channel_id:
            pairs.add((row.product_tmpl_id.id, row.channel_id.id))

    # Source 2: every etsy.listing → its product (via channel_status mirror).
    # Skipped when the etsy_integration module is absent; only the
    # status-row path runs then.
    EtsyListing = env.get('etsy.listing')
    if EtsyListing is not None:
        # etsy.listing is read-only mirror; the back-reference to a
        # product.template flows through product.channel.status.external_ref
        # (which already produced pairs above). No extra work needed.
        pass

    if not pairs:
        _logger.info(
            "P-LIST-MODEL backfill: no eligible (template, channel) pairs; "
            "nothing to backfill."
        )
        return 0, 0

    created = 0
    skipped = 0
    for tmpl_id, channel_id in sorted(pairs):
        existing = Listing.search([
            ('product_tmpl_id', '=', tmpl_id),
            ('channel_id', '=', channel_id),
            ('shop_ref', '=', False),
        ], limit=1)
        if existing:
            skipped += 1
            continue
        Listing.create({
            'product_tmpl_id': tmpl_id,
            'channel_id': channel_id,
            'state': 'draft',
        })
        created += 1
    _logger.info(
        "P-LIST-MODEL backfill: created %s stub rows; %s pairs already had "
        "a listing intent row.", created, skipped,
    )
    return created, skipped
