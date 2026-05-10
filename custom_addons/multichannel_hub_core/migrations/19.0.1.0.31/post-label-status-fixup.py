"""P1-LBL — combined fixup migration (.29 + .30 redo).

Earlier migrations at .29 and .30 used underscore-prefixed filenames
(`post_*.py`); Odoo 19's migration loader requires hyphen prefix
(`post-*.py`) — they were silently skipped. This .31 migration does
both jobs idempotently.

1. Default NULL `sale.order.fulfillment.label_status_id` rows → `cho_duyet`.
2. Refresh stale saved-filter `filter_operations_production_team` domain
   (legacy `('label_status', '!=', 'none')` survives because
   operations_dashboard_saved_filters.xml is `noupdate="1"`).
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Default NULL label_status_id rows.
    try:
        env['label.status.option']._post_migrate_default_null_rows()
    except Exception:
        _logger.exception(
            "P1-LBL fixup: failed to default NULL label_status_id rows")

    # 2. Refresh production-team saved filter.
    try:
        flt = env.ref(
            'multichannel_hub_core.filter_operations_production_team',
            raise_if_not_found=False,
        )
        new_domain = (
            "[('production_blocked', '=', False), "
            "('label_status_id', '!=', False)]"
        )
        if flt and flt.domain != new_domain:
            flt.domain = new_domain
            _logger.warning(
                "P1-LBL fixup: refreshed production-team saved-filter domain "
                "→ %s", new_domain)
    except Exception:
        _logger.exception(
            "P1-LBL fixup: failed to refresh production-team saved filter")
