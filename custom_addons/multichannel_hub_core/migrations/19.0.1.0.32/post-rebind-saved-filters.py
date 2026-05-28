"""P1-01b — rebind operations dashboard saved filters to sale.order.line.

operations_dashboard_saved_filters.xml is `noupdate="1"`, so existing
ir.filters rows installed under P1-DASH-MERGE keep their old
`sale.order` model_id + sale.order-flavored domains. This migration
rewrites them in-place so the dashboard refactor (model swap to
sale.order.line) takes effect on existing databases.

Idempotent: safe to re-run.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_FILTERS = [
    ('multichannel_hub_core.filter_operations_marketing_user',
     "[('order_id.state', '=', 'draft')]"),
    ('multichannel_hub_core.filter_operations_ba_lead',
     "[('order_id.state', 'in', ['draft', 'sale'])]"),
    ('multichannel_hub_core.filter_operations_production_team',
     "[('production_blocked', '=', False), ('label_status_id', '!=', False)]"),
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    rewritten = 0
    for xmlid, domain in _FILTERS:
        flt = env.ref(xmlid, raise_if_not_found=False)
        if not flt:
            continue
        if flt.model_id != 'sale.order.line' or flt.domain != domain:
            flt.write({'model_id': 'sale.order.line', 'domain': domain})
            rewritten += 1
    _logger.warning(
        "P1-01b migration: rebound %d operations-dashboard saved filter(s) "
        "to sale.order.line", rewritten)
