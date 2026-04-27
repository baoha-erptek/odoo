"""Backfill `sale.order.fulfillment_id` for existing rows on upgrade.

Runs once on upgrade from 19.0.1.0.0 (empty skeleton landed in P0-20) to
19.0.1.0.1 (sale.order.fulfillment mixin landed in P1-05). Mirrors the
post_init_hook used at fresh-install time so the upgrade path produces
the same end state.
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)
_BACKFILL_BATCH_SIZE = 1000


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    SaleOrder = env['sale.order']
    Fulfillment = env['sale.order.fulfillment']

    orphan_ids = SaleOrder.search([('fulfillment_id', '=', False)]).ids
    if not orphan_ids:
        return

    _logger.info(
        "multichannel_hub_core %s: backfilling fulfillment_id for %s sale.order rows",
        version, len(orphan_ids),
    )
    for offset in range(0, len(orphan_ids), _BACKFILL_BATCH_SIZE):
        batch_ids = orphan_ids[offset:offset + _BACKFILL_BATCH_SIZE]
        siblings = Fulfillment.create([{} for _ in batch_ids])
        for order, sibling in zip(SaleOrder.browse(batch_ids), siblings):
            order.fulfillment_id = sibling.id
        cr.commit()
