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

    # ---------------------------------------------------------------
    # P1-01b — Operations Dashboard line refactor (Owner directive D6).
    #
    # Excel-mapped Char fields (channel-agnostic; coexist with etsy_*
    # per p1-01b-plan.md DECISION 1).
    # ---------------------------------------------------------------
    image_url = fields.Char(
        string='Image URL',
        help='Channel-supplied product image URL; falls back to product image.')
    transaction_id = fields.Char(
        string='Transaction ID',
        index=True,
        help='Channel-agnostic transaction id. Coexists with etsy_transaction_id '
             'during operator UAT (P1-01b DECISION 1; cleanup deferred).')
    personalisation = fields.Text(
        string='Personalisation',
        help='Channel-agnostic personalisation text. Coexists with etsy_personalisation.')
    design_link_front = fields.Char(
        string='Design Link (Front)',
        help='Channel-agnostic; coexists with etsy_design_link_front during '
             'operator UAT (P1-01b DECISION 1; cleanup deferred).')
    design_link_back = fields.Char(
        string='Design Link (Back)',
        help='Channel-agnostic; coexists with etsy_design_link_back.')

    # Attribute-derived variant labels with manual-entry fallback. Each pair:
    #   <name>_manual = stored Char (operator override)
    #   <name>        = non-stored compute that prefers _manual when set,
    #                   else reads product_template_attribute_value_ids.
    # See p1-01b-plan.md DECISION 2 — non-stored compute + inverse + manual
    # sibling, mirroring the design-file approval pattern.
    option_label_manual = fields.Char(string='Option (manual override)')
    option_label = fields.Char(
        string='Option',
        compute='_compute_option_label',
        inverse='_inverse_option_label',
        store=False,
        help='Variant value for attribute "Option"; manual entry overrides '
             'the attribute-derived value.')

    color_manual = fields.Char(string='Color (manual override)')
    color = fields.Char(
        string='Color',
        compute='_compute_color',
        inverse='_inverse_color',
        store=False,
    )

    size_manual = fields.Char(string='Size (manual override)')
    size = fields.Char(
        string='Size',
        compute='_compute_size',
        inverse='_inverse_size',
        store=False,
    )

    side_manual = fields.Char(string='Side (manual override)')
    side = fields.Char(
        string='Side',
        compute='_compute_side',
        inverse='_inverse_side',
        store=False,
    )

    face_mask_size_manual = fields.Char(string='Face Mask Size (manual override)')
    face_mask_size = fields.Char(
        string='Face Mask Size',
        compute='_compute_face_mask_size',
        inverse='_inverse_face_mask_size',
        store=False,
    )

    # ---------------------------------------------------------------
    # Related-field shadows for the Operations Dashboard line list view
    # (P1-01b T-01b-04). All store=False, readonly=True per DECISION 3 —
    # canonical fields on parent models stay the source of truth.
    # ---------------------------------------------------------------
    # Product SKU (Excel col 8) — related from product variant default_code.
    sku = fields.Char(related='product_id.default_code', readonly=True, string='SKU')
    # Excel column 26: QUANTITY shadow (mirror of product_uom_qty).
    quantity = fields.Float(related='product_uom_qty', readonly=True, string='Quantity')

    # Order-level (Excel cols 4-6, 9-10, 29-31, 33)
    date_order = fields.Datetime(related='order_id.date_order', readonly=True)
    note = fields.Html(related='order_id.note', readonly=True, string='Note from Buyer')
    gift_message = fields.Char(related='order_id.gift_message', readonly=True)
    sales_channel = fields.Selection(related='order_id.sales_channel', readonly=True)
    channel_order_ref = fields.Char(related='order_id.channel_order_ref', readonly=True)
    shipping_carrier_id = fields.Many2one(related='order_id.shipping_carrier_id', readonly=True)
    shipping_service_label = fields.Char(related='order_id.shipping_service_label', readonly=True)
    processing_time = fields.Char(related='order_id.processing_time', readonly=True)
    # SHIPPING_COST column: delivery module not a dep, so we use a free-text
    # Char on sale.order (P1-01b T-01b-02 surprise — see findings.md).
    shipping_cost = fields.Char(related='order_id.shipping_cost', readonly=True)
    discount_code = fields.Char(related='order_id.discount_code', readonly=True)

    # Address fields (Excel cols 11-19) via order_id.partner_shipping_id
    partner_shipping_name = fields.Char(related='order_id.partner_shipping_id.name', readonly=True)
    partner_shipping_street = fields.Char(related='order_id.partner_shipping_id.street', readonly=True)
    partner_shipping_street2 = fields.Char(related='order_id.partner_shipping_id.street2', readonly=True)
    partner_shipping_city = fields.Char(related='order_id.partner_shipping_id.city', readonly=True)
    partner_shipping_state_id = fields.Many2one(related='order_id.partner_shipping_id.state_id', readonly=True)
    partner_shipping_zip = fields.Char(related='order_id.partner_shipping_id.zip', readonly=True)
    partner_shipping_country_id = fields.Many2one(related='order_id.partner_shipping_id.country_id', readonly=True)
    partner_shipping_phone = fields.Char(related='order_id.partner_shipping_id.phone', readonly=True)
    partner_shipping_email = fields.Char(related='order_id.partner_shipping_id.email', readonly=True)

    # Fulfillment / BA / PD / MP fields via order_id (P1-05 _inherits delegates
    # transparently — `order_id.label_status_id` resolves via fulfillment_id).
    label_status_id = fields.Many2one(related='order_id.label_status_id', readonly=True)
    pic_user_id = fields.Many2one(related='order_id.pic_user_id', readonly=True)
    pd_pic_user_id = fields.Many2one(related='order_id.pd_pic_user_id', readonly=True)
    mp_note = fields.Text(related='order_id.mp_note', readonly=True)
    order_priority = fields.Selection(related='order_id.order_priority', readonly=True)
    production_blocked = fields.Boolean(related='order_id.production_blocked', readonly=True)
    is_overdue_approval = fields.Boolean(related='order_id.is_overdue_approval', readonly=True)

    # Decoration drivers (P1-01a heritage, also via order_id)
    qty_total = fields.Float(related='order_id.qty_total', readonly=True)
    is_duplicate_buyer = fields.Boolean(related='order_id.is_duplicate_buyer', readonly=True)

    # Tracking columns (P1-03 + P1-DASH-MERGE heritage; via _inherits delegation).
    tracking_number = fields.Char(related='order_id.tracking_number', readonly=True)
    tracking_state = fields.Selection(related='order_id.tracking_state', readonly=True)
    shipping_date = fields.Date(related='order_id.shipping_date', readonly=True)
    warehouse_zone = fields.Selection(related='order_id.warehouse_zone', readonly=True)

    # ---------------------------------------------------------------
    # Compute methods for attribute-derived variant labels.
    # ---------------------------------------------------------------
    def _attribute_value_for(self, attribute_name):
        """Return the first product_template_attribute_value matching attribute name (case-insensitive)."""
        self.ensure_one()
        if not self.product_id:
            return ''
        target = attribute_name.lower().strip()
        for ptav in self.product_template_attribute_value_ids:
            attr = ptav.attribute_id
            if attr and attr.name and attr.name.lower().strip() == target:
                return ptav.name or ''
        return ''

    @api.depends('option_label_manual', 'product_template_attribute_value_ids')
    def _compute_option_label(self):
        for line in self:
            line.option_label = line.option_label_manual or line._attribute_value_for('Option')

    def _inverse_option_label(self):
        for line in self:
            line.option_label_manual = line.option_label

    @api.depends('color_manual', 'product_template_attribute_value_ids')
    def _compute_color(self):
        for line in self:
            line.color = line.color_manual or line._attribute_value_for('Color')

    def _inverse_color(self):
        for line in self:
            line.color_manual = line.color

    @api.depends('size_manual', 'product_template_attribute_value_ids')
    def _compute_size(self):
        for line in self:
            line.size = line.size_manual or line._attribute_value_for('Size')

    def _inverse_size(self):
        for line in self:
            line.size_manual = line.size

    @api.depends('side_manual', 'product_template_attribute_value_ids')
    def _compute_side(self):
        for line in self:
            line.side = line.side_manual or line._attribute_value_for('Side')

    def _inverse_side(self):
        for line in self:
            line.side_manual = line.side

    @api.depends('face_mask_size_manual', 'product_template_attribute_value_ids')
    def _compute_face_mask_size(self):
        for line in self:
            line.face_mask_size = line.face_mask_size_manual or line._attribute_value_for('Face Mask Size')

    def _inverse_face_mask_size(self):
        for line in self:
            line.face_mask_size_manual = line.face_mask_size

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
