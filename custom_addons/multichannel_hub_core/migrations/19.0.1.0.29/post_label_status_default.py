"""
Post-migration script for P1-LBL label_status field swap (19.0.1.0.29).

This migration defaults existing fulfillment rows with NULL label_status_id
to 'cho_duyet' (the orange-bucket "pending approval" safe-default state).
Existing rows with value already set are left untouched.

Rationale: When the label_status Selection field is dropped and replaced
with a Many2one to label.status.option, pre-existing fulfillment records
will have NULL in the new label_status_id column until defaulted.
This migration ensures no fulfillment is left in a NULL state.

References: P1-LBL plan §2 (Migrations), §4 risk #5 (backward-compat).
"""

import logging

from odoo import api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Default NULL label_status_id rows to 'cho_duyet' during module upgrade.

    Args:
        cr: Database cursor (psycopg2 connection)
        version: Target module version (e.g., '19.0.1.0.29')
    """
    if version != '19.0.1.0.29':
        # This migration is only for the 19.0.1.0.29 upgrade
        return

    # Create environment with SUPERUSER_ID to access full ORM
    env = api.Environment(cr, api.SUPERUSER_ID, {})

    # Fetch the default label status 'cho_duyet'
    try:
        target = env.ref('multichannel_hub_core.label_status_cho_duyet', raise_if_not_found=True)
    except ValueError:
        _logger.error(
            "P1-LBL migration: label_status_cho_duyet XML ID not found; "
            "ensure seed data is loaded before migration runs"
        )
        return

    # Find all fulfillment rows with NULL label_status_id
    cr.execute(
        "SELECT id FROM sale_order_fulfillment WHERE label_status_id IS NULL"
    )
    null_ids = [row[0] for row in cr.fetchall()]

    if not null_ids:
        _logger.debug("P1-LBL migration: no NULL label_status_id rows found")
        return

    # Update them to the default safe value
    cr.execute(
        "UPDATE sale_order_fulfillment SET label_status_id = %s WHERE label_status_id IS NULL",
        (target.id,)
    )

    # Audit log
    _logger.warning(
        "P1-LBL migration: rewrote %d sale.order.fulfillment rows to default "
        "'Chờ duyệt' (id=%s); audit list: %s",
        len(null_ids),
        target.id,
        null_ids,
    )
