"""sale.order.line extension — design_file_ids inverse + design_status rollup.

T023: design_status rolls up the lowest state of all design.file children
on the line. Ordering: rejected < pending < approved < none. Stored +
indexed so the Order / Process Dashboards can filter on it without
heavy joins.

T074 (P1-02b): Extended to be route-aware. If all files are approved but
any route is pending/failed, design_status='approved-pending-route' instead
of 'approved' to show routing is in progress.

P1-IMG-LINE-WIDGET: product_image_thumb non-stored Binary computed from
product_id.product_tmpl_id.image_128. Async-only fallback — the existing
image_downloader cron populates upstream image_1920 from etsy_image_url;
Odoo's stock image-resize pipeline auto-derives image_128. P1-IMG-BACKFILL
amends the cron predicate for any uncovered cases.
"""
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    design_file_ids = fields.One2many(
        'design.file',
        'order_line_id',
        string='Design Files',
    )

    product_image_thumb = fields.Binary(
        string='Image',
        compute='_compute_product_image_thumb',
        store=False,
        attachment=False,
    )

    @api.depends('product_id.product_tmpl_id.image_128')
    def _compute_product_image_thumb(self):
        for line in self:
            line.product_image_thumb = line.product_id.product_tmpl_id.image_128 or False

    design_status = fields.Selection(
        [
            ('none', 'No design'),
            ('rejected', 'Needs revision'),
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('approved-pending-route', 'Approved (route pending)'),
        ],
        compute='_compute_design_status',
        store=True,
        index=True,
        default='none',
    )

    @api.depends('design_file_ids.state', 'design_file_ids.route_ids.state')
    def _compute_design_status(self):
        """Compute design_status: rollup of file states + route state awareness.

        Logic:
        1. If no files → 'none'
        2. If any file rejected → 'rejected'
        3. If any file pending → 'pending'
        4. If all files approved:
           a. If any route pending/failed → 'approved-pending-route'
           b. Otherwise → 'approved'

        This ensures the dashboard shows file approval state as primary, with
        routing-in-progress as a secondary status.
        """
        for line in self:
            file_states = set(line.design_file_ids.mapped('state'))

            if not file_states:
                line.design_status = 'none'
            elif 'rejected' in file_states:
                line.design_status = 'rejected'
            elif 'pending' in file_states:
                line.design_status = 'pending'
            else:
                # All files are approved; check routes
                routes = line.design_file_ids.route_ids
                if routes and any(r.state in ('pending', 'failed') for r in routes):
                    line.design_status = 'approved-pending-route'
                else:
                    line.design_status = 'approved'
