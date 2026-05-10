"""Post-migration for P1-LBL — default NULL label_status_id rows to 'Chờ duyệt'.

The actual logic lives on the model (label_status_option._post_migrate_default_null_rows)
so it can be reused from tests without going through the upgrade pipeline.

Slice: P1-LBL (Owner directive D2, 2026-05-10).
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Default NULL label_status_id rows + refresh stale saved-filter domain.

    Saved-filters XML is `noupdate="1"`, so the legacy domain
    `('label_status', '!=', 'none')` survives a -u upgrade and breaks
    sale.order search. This migration force-updates the existing row.

    Args:
        cr: Database cursor.
        version: Target manifest version (e.g. '19.0.1.0.29').
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Default NULL label_status_id rows to 'cho_duyet'.
    try:
        env['label.status.option']._post_migrate_default_null_rows()
    except Exception:
        _logger.exception(
            "P1-LBL migration: failed to default NULL label_status_id rows")

    # Refresh the production-team saved-filter domain (was stale due to
    # noupdate="1"). Idempotent — silently no-ops on fresh installs.
    try:
        flt = env.ref(
            'multichannel_hub_core.filter_operations_production_team',
            raise_if_not_found=False,
        )
        if flt:
            flt.domain = (
                "[('production_blocked', '=', False), "
                "('label_status_id', '!=', False)]"
            )
            _logger.warning(
                "P1-LBL migration: refreshed saved-filter "
                "filter_operations_production_team domain to label_status_id")
    except Exception:
        _logger.exception(
            "P1-LBL migration: failed to refresh production-team saved filter")
