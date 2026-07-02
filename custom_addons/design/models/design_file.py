"""design.file extension — link each file to its parent design.order.

ESTY-244: design.file itself stays defined in multichannel_hub_core (ADR-018);
here we only add the parent document link so a design.order can own its files.
"""
from odoo import fields, models


class DesignFile(models.Model):
    _inherit = 'design.file'

    design_order_id = fields.Many2one(
        'design.order', string='Design Order',
        ondelete='set null', index=True,
        help="Parent design order document (ESTY-244).",
    )
