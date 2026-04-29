"""P1-03 — backfill sale.order.fulfillment.order_id for existing rows.

The reverse pointer is needed by the Tracking Dashboard view + the
bulk-shipped action. Existing fulfillments created before this slice
have order_id IS NULL; backfill once via UPDATE FROM. Idempotent.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE sale_order_fulfillment f
           SET order_id = o.id
          FROM sale_order o
         WHERE o.fulfillment_id = f.id
           AND f.order_id IS NULL
    """)
    _logger.info(
        "P1-03 backfill: stamped order_id on %s fulfillment rows",
        cr.rowcount,
    )
