"""Migration 19.0.1.0.3 — FR-025 sales_channel + channel_order_ref backfill.

Runs on `-u multichannel_hub_core` against any environment that already
has data. Mirrors `_backfill_sales_channel` from `__init__.py` (which
covers the fresh-install `-i` path) per memory gotcha #12.

Idempotent — only touches rows where `sales_channel IS NULL`.
"""

from odoo import api, SUPERUSER_ID

from odoo.addons.multichannel_hub_core import _backfill_sales_channel


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _backfill_sales_channel(env)
