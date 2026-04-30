"""Post-init setup for multichannel_hub_fulfillment.

Called after module loads to create ACL and cron records that depend on
the model being registered.
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_create_acl_and_cron(env):
    """Create ACL and cron records (idempotent).

    Args:
        env: Odoo environment (admin context, user=1)

    Note: This is called post-load by Odoo framework when noupdate=False.
          In Odoo 19, the signature is post_init_hook(env).
    """
    from odoo import api, fields
    from odoo.addons.base import models as base_models

    try:
        ir_model_access = env['ir.model.access']
        ir_model = env['ir.model']
        ir_cron = env['ir.cron']

        # Get the ir.model record for gearment.api.log
        model_id = ir_model.search([('model', '=', 'gearment.api.log')])
        if not model_id:
            _logger.debug("ir.model record not found for gearment.api.log")
            return

        # System admin group — full permissions
        system_group = env.ref('base.group_system')
        existing_system = ir_model_access.search([
            ('model_id', '=', model_id.id),
            ('group_id', '=', system_group.id),
        ])
        if not existing_system:
            ir_model_access.create({
                'name': 'gearment.api.log system',
                'model_id': model_id.id,
                'group_id': system_group.id,
                'perm_read': True,
                'perm_write': True,
                'perm_create': True,
                'perm_unlink': True,
            })

        # Sales manager group — read-only
        sale_manager_group = env.ref('sales_team.group_sale_manager')
        existing_sale_mgr = ir_model_access.search([
            ('model_id', '=', model_id.id),
            ('group_id', '=', sale_manager_group.id),
        ])
        if not existing_sale_mgr:
            ir_model_access.create({
                'name': 'gearment.api.log sale manager',
                'model_id': model_id.id,
                'group_id': sale_manager_group.id,
                'perm_read': True,
                'perm_write': False,
                'perm_create': False,
                'perm_unlink': False,
            })

        # Daily cleanup cron (idempotent)
        existing_cron = ir_cron.search([
            ('name', '=', 'Cleanup old Gearment API logs'),
        ])
        if not existing_cron:
            ir_cron.create({
                'name': 'Cleanup old Gearment API logs',
                'model_id': model_id.id,
                'state': 'code',
                'code': 'model._cron_cleanup_old_logs()',
                'user_id': env.ref('base.user_root').id,
                'interval_number': 1,
                'interval_type': 'days',
                'active': True,
            })
    except Exception as e:
        _logger.error(f"Failed to create ACL/cron for gearment.api.log: {e}")
