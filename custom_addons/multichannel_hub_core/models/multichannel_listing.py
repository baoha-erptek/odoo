"""Per-channel/per-shop listing intent (pre-publish source of truth).

ADR-015 §1: separate listing-intent layer between ``product.template``
(the product itself) and ``etsy.listing`` (the read-only mirror of what's
on Etsy). Marketing edits these rows to express *what we want to list*;
the publisher reads listing intent first, then falls back to the template
or shop default.

Three-layer field resolution chain (publisher honors):

    multichannel.listing.<field>   -- per-listing override
    product.template.x_<field>     -- per-product fallback (when defined)
    etsy.shop.default_<field>      -- per-shop default

Empty override → fallback. Wave-2 slices each add one or more Etsy-specific
fields here (taxonomy, shipping profile, who_made, video, attribute
mapping). This foundational slice (``P-LIST-MODEL``) only ships the model
+ marketing overrides (title/description/image) + state machine.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MultichannelListing(models.Model):
    _name = 'multichannel.listing'
    _description = 'Multichannel Listing Intent (per-channel / per-shop)'
    _order = 'product_tmpl_id, channel_id, sequence, id'
    _rec_name = 'display_name'

    # ------------------------------------------------------------------
    # Anchor + scope
    # ------------------------------------------------------------------
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        ondelete='cascade',
        index=True,
        help='Product master this listing intent belongs to.',
    )
    channel_id = fields.Many2one(
        'multichannel.sales.channel',
        string='Channel',
        required=True,
        ondelete='restrict',
        index=True,
        help='Sales channel (etsy / amazon / website / ...).',
    )
    shop_ref = fields.Char(
        string='Shop',
        index=True,
        help='Free-text shop identifier scoped to the channel (e.g. '
             '"jahandmadeart" / "namcohome" for Etsy). Empty when the '
             'channel itself is the scope (e.g. company website).',
    )
    sequence = fields.Integer(default=10, help='Per-template ordering.')

    # ------------------------------------------------------------------
    # Marketing overrides (empty → product.template fallback at publish)
    # ------------------------------------------------------------------
    title = fields.Char(
        help='Per-listing marketing title; empty → product.template.name.',
    )
    description = fields.Text(
        help='Per-listing marketing description; empty → '
             'product.template.description_sale.',
    )
    image_1920 = fields.Image(
        max_width=1920,
        max_height=1920,
        help='Per-listing hero image; empty → product.template.image_1920.',
    )

    # P-LIST-VIDEO (ADR-015 / spec 012 §US7) — 1 video per listing.
    # Etsy ``uploadListingVideo`` accepts ``video`` (binary) + ``name``
    # multipart fields. We hold both via a single ir.attachment so the
    # operator can drop the file once and the publisher picks up the
    # binary + filename at push time. Domain restricts to private
    # attachments to keep the file out of the website front-end.
    video_attachment_id = fields.Many2one(
        'ir.attachment',
        string='Video',
        domain="[('public', '=', False)]",
        ondelete='set null',
        help='Per-listing video file (Etsy caps at one video per listing). '
             'Empty → no video pushed.',
    )

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('ready', 'Ready for Publish'),
            ('published', 'Published'),
            ('error', 'Error'),
        ],
        default='draft',
        required=True,
        help='Lifecycle of the listing intent.',
    )
    external_ref = fields.Char(
        string='External Reference',
        index=True,
        copy=False,
        help='Channel-side ID assigned after first successful publish. '
             'For Etsy this is the etsy_listing_id (Char to avoid XML-RPC '
             'int32 overflow on large Etsy IDs).',
    )
    last_synced_at = fields.Datetime(
        copy=False,
        help='Last successful publish / sync timestamp.',
    )

    display_name = fields.Char(
        compute='_compute_display_name', store=True,
    )

    # ------------------------------------------------------------------
    # PG-level UNIQUE — see project_sql_constraints_drift memory
    # ------------------------------------------------------------------
    def init(self):
        """Mirror UNIQUE(product_tmpl_id, channel_id, shop_ref) at PG.

        Odoo 19 dropped declarative ``_sql_constraints`` enforcement; the
        raw-SQL mirror in init() is the sole enforcement path. NULL
        ``shop_ref`` collates as DISTINCT per PostgreSQL semantics; the
        intent is "one listing per (product × channel) when shop_ref is
        empty", so we use COALESCE to fold NULL into ''.
        """
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                uniq_multichannel_listing_tmpl_channel_shop
            ON multichannel_listing (
                product_tmpl_id, channel_id, COALESCE(shop_ref, '')
            )
        """)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('product_tmpl_id.name', 'channel_id.code', 'shop_ref')
    def _compute_display_name(self):
        for rec in self:
            tmpl = rec.product_tmpl_id.name or '?'
            ch = rec.channel_id.code or '?'
            if rec.shop_ref:
                rec.display_name = '%s @ %s/%s' % (tmpl, ch, rec.shop_ref)
            else:
                rec.display_name = '%s @ %s' % (tmpl, ch)

    # ------------------------------------------------------------------
    # Resolver helpers — read by publisher (and by future channels)
    # ------------------------------------------------------------------
    def resolve_title(self):
        self.ensure_one()
        return self.title or self.product_tmpl_id.name or ''

    def resolve_description(self):
        self.ensure_one()
        return (
            self.description
            or self.product_tmpl_id.description_sale
            or self.product_tmpl_id.name
            or ''
        )

    def resolve_image_1920(self):
        self.ensure_one()
        return self.image_1920 or self.product_tmpl_id.image_1920

    # ------------------------------------------------------------------
    # P-LIST-UX-FIXES R1 — Open in Etsy Shop Manager (action_url)
    # ------------------------------------------------------------------
    def action_open_in_etsy_shop_manager(self):
        """Return an act_url to the Etsy Shop Manager edit screen for
        this listing. The button is gated in the view to state='published'
        AND external_ref non-null, so we don't expect to be called in any
        other state — but defensively redirect to the shop dashboard if
        either is missing.
        """
        self.ensure_one()
        if self.external_ref and str(self.external_ref).isdigit():
            url = (
                'https://www.etsy.com/your/shops/me/tools/listings/%s/edit'
                % self.external_ref
            )
        else:
            url = 'https://www.etsy.com/your/shops/me/tools/listings'
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
