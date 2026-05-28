"""P1-DROP-CALLSITE: drop the orphaned Gearment retry cron + ICP.

The cron `ir_cron_gearment_retry_stalled` and ICP
`multichannel_hub_fulfillment.gearment_auto_push_enabled` lived in the now-deleted
`data/ir_cron_gearment_retry.xml`. The XML used `noupdate="1"`, which blocks
Odoo's automatic cleanup on module upgrade. This script removes them
explicitly so the upgrade leaves no orphan rows.

Cron records auto-create a paired `ir.actions.server` record, which has its
own `ir_model_data` entry suffixed `_ir_actions_server`; both must be cleared.

Security: PostgreSQL does not support parameter-bound table names, so the
DELETE statement interpolates `table` into the SQL string. To prevent any
chance of injection via a corrupted `ir_model_data.model` value, the script
hard-whitelists the set of tables it is willing to write to. Any model not
on the allow-list is logged and skipped.
"""
import logging

_logger = logging.getLogger(__name__)

ORPHAN_XMLIDS = (
    'multichannel_hub_fulfillment.ir_cron_gearment_retry_stalled',
    'multichannel_hub_fulfillment.ir_cron_gearment_retry_stalled_ir_actions_server',
    'multichannel_hub_fulfillment.icp_gearment_auto_push_enabled',
)

# model name -> (db table, allow-listed)
MODEL_TO_TABLE = {
    'ir.cron': 'ir_cron',
    'ir.actions.server': 'ir_act_server',
    'ir.config_parameter': 'ir_config_parameter',
}


def migrate(cr, version):
    for xmlid in ORPHAN_XMLIDS:
        module, name = xmlid.split('.', 1)
        cr.execute(
            "SELECT res_id, model FROM ir_model_data "
            "WHERE module = %s AND name = %s",
            (module, name),
        )
        row = cr.fetchone()
        if not row:
            continue
        res_id, model = row
        table = MODEL_TO_TABLE.get(model)
        if not table:
            _logger.warning(
                "P1-DROP-CALLSITE migration: model %r not in allow-list; "
                "skipping orphan cleanup for %s", model, xmlid)
            continue
        cr.execute(
            "DELETE FROM " + table + " WHERE id = %s", (res_id,))
        cr.execute(
            "DELETE FROM ir_model_data WHERE module = %s AND name = %s",
            (module, name),
        )
