import logging

from . import models
from . import services
from . import tests

_logger = logging.getLogger(__name__)

_BACKFILL_BATCH_SIZE = 1000


def _backfill_fulfillment_id(env):
    """P1-05: ensure every existing sale.order has a fulfillment_id sibling."""
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


def _backfill_sales_channel(env):
    """P1-01a (FR-025): set sales_channel + channel_order_ref on existing
    sale.order rows. Idempotent — only touches rows where
    sales_channel IS NULL. Etsy orders detected via etsy_order_id IS NOT
    NULL (column lives in the etsy_integration extension; safe to read
    via raw SQL since this helper runs only when both modules are
    installed against the same DB).
    """
    cr = env.cr
    # Only run if etsy_order_id column exists (etsy_integration installed).
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'sale_order'
          AND column_name = 'etsy_order_id'
    """)
    has_etsy_col = bool(cr.fetchone())

    if has_etsy_col:
        cr.execute("""
            UPDATE sale_order
               SET sales_channel = 'etsy',
                   channel_order_ref = etsy_order_id
             WHERE sales_channel IS NULL
               AND etsy_order_id IS NOT NULL
               AND etsy_order_id <> ''
        """)
        etsy_rows = cr.rowcount
    else:
        etsy_rows = 0

    cr.execute("""
        UPDATE sale_order
           SET sales_channel = 'other'
         WHERE sales_channel IS NULL
    """)
    other_rows = cr.rowcount

    if etsy_rows or other_rows:
        _logger.info(
            "multichannel_hub_core: FR-025 backfill — %s etsy rows, %s other rows",
            etsy_rows, other_rows,
        )


def _enable_mto_seed_routes(env):
    """P1-MTO-SEED: activate MTO route + make Manufacture product-selectable.

    Odoo ships `stock.route_warehouse0_mto` inactive and
    `mrp.route_warehouse0_manufacture` with `product_selectable=False`. The
    pass-through BOM wizard relies on both being usable on
    vn_internal_production products. XML overrides on cross-module records
    are blocked by `noupdate` flags, so we set them programmatically.
    """
    mto_route = env.ref('stock.route_warehouse0_mto', raise_if_not_found=False)
    if mto_route and not mto_route.active:
        mto_route.active = True

    manufacture_route = env.ref(
        'mrp.route_warehouse0_manufacture', raise_if_not_found=False,
    )
    if manufacture_route and not manufacture_route.product_selectable:
        manufacture_route.product_selectable = True


def post_init_hook(env):
    """Backfill fulfillment_id (P1-05) and sales_channel (P1-01a / FR-025);
    activate MTO + Manufacture routes for P1-MTO-SEED.

    Backfill helpers fire only on fresh install (`-i`); the upgrade path
    (`-u`) runs the matching `migrations/19.0.1.0.3/post-fr025-backfill.py`
    script per memory gotcha #12. Route activation is idempotent and runs
    on every install/upgrade via the matching migration in 19.0.1.0.17.
    """
    _backfill_fulfillment_id(env)
    _backfill_sales_channel(env)
    _enable_mto_seed_routes(env)
