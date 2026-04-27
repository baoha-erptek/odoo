import logging

from . import models
from . import services
from . import tests

_logger = logging.getLogger(__name__)

_BACKFILL_BATCH_SIZE = 1000


def post_init_hook(env):
    """Backfill `fulfillment_id` on every existing `sale.order` row.

    When `multichannel_hub_core` installs onto a database that already
    contains `sale.order` data (e.g., the etsy_integration test fixtures
    or production orders), the newly added `fulfillment_id` column is
    populated as NULL. The ORM then refuses to write to those rows
    because `fulfillment_id` is `required=True`. We create a fresh
    `sale.order.fulfillment` sibling for each orphan and assign it.

    Batched to avoid a single 17K-row UPDATE on the existing Etsy
    backlog.
    """
    SaleOrder = env['sale.order']
    Fulfillment = env['sale.order.fulfillment']

    orphan_ids = SaleOrder.search([('fulfillment_id', '=', False)]).ids
    if not orphan_ids:
        return

    _logger.info(
        "multichannel_hub_core: backfilling fulfillment_id for %s sale.order rows",
        len(orphan_ids),
    )
    for offset in range(0, len(orphan_ids), _BACKFILL_BATCH_SIZE):
        batch_ids = orphan_ids[offset:offset + _BACKFILL_BATCH_SIZE]
        siblings = Fulfillment.create([{} for _ in batch_ids])
        for order, sibling in zip(SaleOrder.browse(batch_ids), siblings):
            order.fulfillment_id = sibling.id
        env.cr.commit()
