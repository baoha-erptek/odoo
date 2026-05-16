"""System-group gate on sensitive Etsy `ir.config_parameter` keys (P1-10).

Stock `ir.config_parameter.get_param` checks model-level read access
only — any logged-in user can read any key. P1-10 introduces a
sensitive key (`etsy.oauth.fernet_key`) that decryption keys depend on;
leaking it would unlock every stored OAuth token. We gate read access
to that key — and any future sensitive Etsy keys — to
`base.group_system`.

Decision **D-P1-10-02** in `specs/005-etsy-api-channel/p1-10-plan.md`.

Extending `_SENSITIVE_KEYS` is the supported extension point; the
surrounding code never needs to change.
"""

from odoo import _, api, models
from odoo.exceptions import AccessError


# Read access to these keys requires base.group_system. Non-system
# callers receive AccessError even on sudo()-less `with_user(...)`
# code paths.
_SENSITIVE_KEYS = frozenset([
    'etsy.oauth.fernet_key',
])


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.model
    def get_param(self, key, default=False):
        # Gate sensitive keys to admin-equivalent contexts. In Odoo
        # 19 `sudo()` sets `env.su=True` without changing `env.uid`,
        # so `env.user._is_system()` alone would reject any
        # sudo()-with-non-admin-user call (e.g. controllers running
        # under `auth='public'` then sudo'ing for ORM writes). Treat
        # `env.su` as the "we're inside a trust boundary" marker on
        # par with admin/system-group membership.
        if (
            key in _SENSITIVE_KEYS
            and not self.env.su
            and not self.env.user._is_system()
        ):
            raise AccessError(
                _("System parameter %r is restricted to administrators.") % key
            )
        return super().get_param(key, default)
