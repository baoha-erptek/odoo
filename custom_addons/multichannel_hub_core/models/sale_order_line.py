"""sale.order.line extension — design_file_ids inverse + design_status rollup.

T023: design_status rolls up the lowest state of all design.file children
on the line. Ordering: rejected < pending < approved < none. Stored +
indexed so the Order / Process Dashboards can filter on it without
heavy joins.
"""
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    design_file_ids = fields.One2many(
        'design.file',
        'order_line_id',
        string='Design Files',
    )

    design_status = fields.Selection(
        [
            ('none', 'No design'),
            ('rejected', 'Needs revision'),
            ('pending', 'Pending'),
            ('approved', 'Approved'),
        ],
        compute='_compute_design_status',
        store=True,
        index=True,
        default='none',
    )

    @api.depends('design_file_ids.state')
    def _compute_design_status(self):
        for line in self:
            states = set(line.design_file_ids.mapped('state'))
            if not states:
                line.design_status = 'none'
            elif 'rejected' in states:
                line.design_status = 'rejected'
            elif 'pending' in states:
                line.design_status = 'pending'
            else:
                line.design_status = 'approved'
