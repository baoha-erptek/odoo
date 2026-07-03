"""Settings toggle for the auto-create-design-order-on-confirm feature (ESTY-244)."""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    design_auto_create_on_confirm = fields.Boolean(
        string='Auto-create design order on sale confirmation',
        config_parameter='design.auto_create_on_confirm',
        default=True,
        help="When enabled, confirming a sale order automatically creates a "
             "design order and links the order's design files to it.",
    )
