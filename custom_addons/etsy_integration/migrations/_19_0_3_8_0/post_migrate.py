"""Backfill multichannel.listing.etsy_shop_id from shop_ref name-lookup."""

import logging

_logger = logging.getLogger(__name__)


def post_migrate(cr, env):
    """Match every listing with NULL etsy_shop_id by ``shop_ref`` name.

    WARNING is logged when the name has no match or matches multiple
    shops. The migration never raises — a partial backfill is acceptable;
    the computed price-display widget SOFT-FAILs to 0.0 when the FK
    remains NULL.
    """
    Listing = env['multichannel.listing']
    Shop = env['etsy.shop']
    listings = Listing.search([
        ('etsy_shop_id', '=', False),
        ('shop_ref', '!=', False),
    ])
    if not listings:
        _logger.info(
            "P-ENH-ESTY-195: no listings need etsy_shop_id backfill.",
        )
        return
    backfilled = 0
    skipped = 0
    for listing in listings:
        matches = Shop.search([('name', '=', listing.shop_ref)])
        if len(matches) == 1:
            listing.etsy_shop_id = matches
            backfilled += 1
        else:
            skipped += 1
            _logger.warning(
                "P-ENH-ESTY-195: listing %s shop_ref=%r matched %s shops "
                "by name — leaving etsy_shop_id NULL.",
                listing.id, listing.shop_ref, len(matches),
            )
    _logger.info(
        "P-ENH-ESTY-195: backfilled etsy_shop_id on %s listings, "
        "%s skipped (no match or ambiguous).",
        backfilled, skipped,
    )
