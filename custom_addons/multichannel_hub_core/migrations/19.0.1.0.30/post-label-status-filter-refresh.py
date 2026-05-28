"""Refresh saved-filter domains broken by P1-LBL label_status → label_status_id swap.

The saved_filters XML is `noupdate="1"` so the legacy domain
`('label_status', '!=', 'none')` survives -u upgrades. This is a separate
migration step from .29 (which handled NULL fulfillment row defaulting)
because the NULL-row migration only fires on the .29 boundary; environments
that already took .29 still need this filter-refresh.

Slice: P1-LBL.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    flt = env.ref(
        'multichannel_hub_core.filter_operations_production_team',
        raise_if_not_found=False,
    )
    if not flt:
        _logger.debug(
            "P1-LBL filter refresh: production-team saved filter not found")
        return
    new_domain = (
        "[('production_blocked', '=', False), "
        "('label_status_id', '!=', False)]"
    )
    if flt.domain == new_domain:
        return
    flt.domain = new_domain
    _logger.warning(
        "P1-LBL filter refresh: rewrote saved filter "
        "filter_operations_production_team domain → %s",
        new_domain,
    )
