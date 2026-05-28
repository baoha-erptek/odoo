import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

_SOURCE_SELECTION = [('api', 'Etsy API'), ('email', 'Email')]
_REASON_SELECTION = [
    ('bootstrap', 'Bootstrap (migration)'),
    ('manual', 'Manual toggle'),
    ('auto-failover', 'Automatic failover'),
    ('recovery-probe', 'Recovery probe'),
    ('scope-revoked', 'Scope revoked'),
]


class EtsyShopSourceChangeLog(models.Model):
    """Append-only audit of every `etsy.shop.active_source` switch.

    Spec 005 / ADR-008a §3. One row per transition (bootstrap on
    migration, manual UI toggle, auto-failover, recovery-probe,
    scope-revoked). Append-only: C-SCL-001 forbids unlink except
    `base.group_system`; no field is updatable post-create.
    """

    _name = 'etsy.shop.source.change.log'
    _description = 'Etsy Shop Source Change Log'
    _order = 'changed_at desc, id desc'

    shop_id = fields.Many2one(
        'etsy.shop', string='Shop', required=True,
        ondelete='cascade', index=True,
    )
    from_source = fields.Selection(
        selection=_SOURCE_SELECTION, string='From Source',
        help='NULL for the first (bootstrap) row of a shop.',
    )
    to_source = fields.Selection(
        selection=_SOURCE_SELECTION, string='To Source', required=True,
    )
    changed_at = fields.Datetime(
        string='Changed At', required=True,
        default=fields.Datetime.now, index=True,
    )
    reason = fields.Selection(
        selection=_REASON_SELECTION, string='Reason', required=True,
    )
    actor_user_id = fields.Many2one(
        'res.users', string='Actor',
        ondelete='set null',
        help='NULL for cron-driven (auto-failover / recovery-probe) changes.',
    )
    health_check_failures_at_change = fields.Integer(
        string='Health-Check Failures at Change',
        help='Snapshot of the shop consecutive-failure counter at switch time.',
    )
    notes = fields.Text(string='Notes')

    @api.constrains('reason', 'actor_user_id')
    def _check_system_reason_has_no_actor(self):
        """C-SCL-002: auto-failover / recovery-probe rows are cron-driven
        and MUST NOT carry an actor user.
        """
        for log in self:
            if log.reason in ('auto-failover', 'recovery-probe') and log.actor_user_id:
                raise ValidationError(
                    "Source-change rows with reason '%s' are cron-driven "
                    "and must not record an actor user." % log.reason
                )

    def unlink(self):
        """C-SCL-001: append-only — only system may delete audit rows."""
        if not self.env.su and not self.env.user._is_system():
            raise AccessError(
                "Etsy source-change log rows are append-only; only a "
                "system administrator may delete them (C-SCL-001)."
            )
        return super().unlink()
