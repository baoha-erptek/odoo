"""P-LIST-CATEGORY (ADR-015 §3 / spec 012 §US4) — Etsy taxonomy extension.

mhc cannot depend on etsy_integration (ADR-003 keeps the dependency
graph one-way). Etsy-specific listing fields therefore live here, as
classic ``_inherit`` extensions of ``multichannel.listing``.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MultichannelListingEtsy(models.Model):
    _inherit = 'multichannel.listing'

    # P-ENH-ESTY-195 (ADR-016) — typed FK from listing to etsy.shop.
    # Backfilled in migration 19.0.3.8.0 from the legacy ``shop_ref`` Char
    # by name-lookup. NULL when no match or ambiguous.
    etsy_shop_id = fields.Many2one(
        'etsy.shop',
        string='Etsy Shop',
        ondelete='set null',
        index=True,
        help='Shop this listing pushes to. Drives the price-display widget '
             'and per-channel-shop overrides.',
    )

    # P-ENH-ESTY-195 — sibling field driving the Monetary widget on the
    # form. Mirrors ``etsy_shop_id.listing_currency_id`` (or False).
    display_currency_id = fields.Many2one(
        'res.currency',
        string='Display Currency',
        compute='_compute_display_currency_id',
        help='Listing currency derived from the Etsy shop. Used to drive '
             'the ``display_price_in_shop_currency`` Monetary widget.',
    )

    # P-ENH-ESTY-195 — read-only conversion preview. SOFT-FAIL: returns
    # 0.0 + WARNING when shop / currency / rate is missing. Does NOT
    # raise — the form must load gracefully (US3 acceptance).
    display_price_in_shop_currency = fields.Monetary(
        string='Price (shop currency)',
        compute='_compute_display_price_in_shop_currency',
        currency_field='display_currency_id',
        help='Preview of the list price converted to the shop currency '
             'using today\'s ``res.currency.rate``. 0.0 means the shop, '
             'currency, or rate is not configured.',
    )

    @api.depends('etsy_shop_id', 'etsy_shop_id.listing_currency_id')
    def _compute_display_currency_id(self):
        for rec in self:
            shop = rec.etsy_shop_id
            rec.display_currency_id = shop.listing_currency_id if shop else False

    @api.depends(
        'product_tmpl_id.list_price',
        'etsy_shop_id',
        'etsy_shop_id.listing_currency_id',
    )
    def _compute_display_price_in_shop_currency(self):
        company = self.env.company
        from_currency = company.currency_id
        today = fields.Date.context_today(self)
        for rec in self:
            shop = rec.etsy_shop_id
            if not shop:
                _logger.warning(
                    "multichannel.listing %s: no etsy_shop_id — "
                    "display_price_in_shop_currency=0.0",
                    rec.id,
                )
                rec.display_price_in_shop_currency = 0.0
                continue
            # sudo: ``listing_currency_id`` carries ``groups='base.group_system'``
            # so Marketing reading the listing form lacks direct access. The
            # currency selector itself is not sensitive — only its identifier
            # is needed to drive the Monetary widget.
            to_currency = shop.sudo().listing_currency_id
            if not to_currency:
                _logger.warning(
                    "multichannel.listing %s: etsy_shop_id=%s has no "
                    "listing_currency_id — display_price_in_shop_currency=0.0",
                    rec.id, shop.id,
                )
                rec.display_price_in_shop_currency = 0.0
                continue
            amount = rec.product_tmpl_id.list_price or 0.0
            if to_currency == from_currency:
                rec.display_price_in_shop_currency = float(amount)
                continue
            # Odoo silently falls back to rate=1 when no ``res.currency.rate``
            # row exists, which would silently mis-price the listing. Detect
            # the missing-rate case explicitly so US3 SOFT-FAIL fires.
            # sudo: ``res.currency.rate`` ACL restricts to accountants. The
            # widget only needs existence of a rate row for today to decide
            # whether to render a converted price or fall back to 0.0. No
            # cross-company data leaks: domain pins ``company_id`` to the
            # current company (or shared rates with NULL company).
            rate_row = self.env['res.currency.rate'].sudo().search([
                ('currency_id', '=', to_currency.id),
                ('company_id', 'in', [company.id, False]),
                ('name', '<=', today),
            ], order='name desc', limit=1)
            if not rate_row:
                _logger.warning(
                    "multichannel.listing %s: no res.currency.rate for "
                    "%s on or before %s — display_price_in_shop_currency=0.0",
                    rec.id, to_currency.name, today,
                )
                rec.display_price_in_shop_currency = 0.0
                continue
            try:
                rec.display_price_in_shop_currency = from_currency._convert(
                    amount, to_currency, company, today,
                )
            except Exception as exc:  # noqa: BLE001 — SOFT-FAIL per ADR-016 D4
                _logger.warning(
                    "multichannel.listing %s: currency conversion %s→%s "
                    "failed (%s) — display_price_in_shop_currency=0.0",
                    rec.id, from_currency.name, to_currency.name, exc,
                )
                rec.display_price_in_shop_currency = 0.0

    etsy_taxonomy_id = fields.Many2one(
        'etsy.taxonomy.node',
        string='Etsy Category',
        ondelete='set null',
        help='Per-listing Etsy taxonomy override. Empty → falls back to '
             'product.template.x_taxonomy_id → etsy.shop.default_taxonomy_id.',
    )

    # P-LIST-SHIPPING (ADR-015 §3 / spec 012 §US5)
    etsy_shipping_profile_id = fields.Many2one(
        'etsy.shipping.profile',
        string='Etsy Shipping Profile',
        ondelete='set null',
        help='Per-listing shipping profile override. Empty → falls back to '
             'etsy.shop.default_shipping_profile_id.',
    )

    # P-LIST-HOW-ITS-MADE (ADR-015 §3 / spec 012 §US1)
    etsy_who_made = fields.Selection(
        selection=[
            ('i_did', 'I did'),
            ('someone_else', 'Someone else'),
            ('collective', 'A member of my shop'),
        ],
        string='Who made it',
        help='Per-listing override. Empty → falls back to product '
             '(x_who_made) → shop default (default_who_made).',
    )
    etsy_when_made = fields.Selection(
        selection=[
            ('made_to_order', 'Made to order'),
            ('2020_2026', '2020 – 2026'),
            ('2010_2019', '2010 – 2019'),
            ('2003_2009', '2003 – 2009'),
            ('before_2004', 'Before 2004'),
            ('2000_2003', '2000 – 2003'),
            ('1990s', '1990s'),
            ('1980s', '1980s'),
            ('1970s', '1970s'),
            ('1960s', '1960s'),
            ('1950s', '1950s'),
            ('1940s', '1940s'),
            ('1930s', '1930s'),
            ('1920s', '1920s'),
            ('1910s', '1910s'),
            ('1900s', '1900s'),
            ('1800s', '1800s'),
            ('1700s', '1700s'),
            ('before_1700', 'Before 1700'),
        ],
        string='When made',
        help='Per-listing override. Empty → falls back to product '
             '(x_when_made) → shop default (default_when_made).',
    )
    etsy_is_supply = fields.Boolean(
        string='Is supply',
        default=False,
        help='True when this item is a supply (raw materials, tools). '
             'Per-listing — no fallback chain; the shop default is used '
             'only when no listing intent row exists.',
    )

    # P-LIST-UX-FIXES R4 — surface cache freshness next to each dropdown
    # so operators know whether to trust the choices. Related read-only
    # mirrors of the picked cache rows' last_synced_at.
    etsy_taxonomy_last_synced_at = fields.Datetime(
        related='etsy_taxonomy_id.last_synced_at',
        string='Taxonomy cache last synced',
        readonly=True,
    )
    etsy_shipping_last_synced_at = fields.Datetime(
        related='etsy_shipping_profile_id.last_synced_at',
        string='Shipping cache last synced',
        readonly=True,
    )

    # P-LIST-ATTRIBUTES (ADR-015 §3 / spec 012 §US6)
    attribute_mapping_ids = fields.One2many(
        'multichannel.listing.attribute.mapping',
        'listing_id',
        string='Attribute mapping overrides',
        help='Per-listing Etsy property_id overrides. Priority chain when '
             'the publisher resolves an Etsy property for a variation axis: '
             '1) listing mapping row, 2) shop default mapping, 3) global '
             'product.attribute.x_etsy_property_id. Leave a row empty to '
             'fall through to the next tier.',
    )

    # ------------------------------------------------------------------
    # P-LIST-PUBLISH-FROM-LISTING — bridge to existing publish wizard.
    # Marketing curates the Listing form (overrides + shop); the only
    # publish button used to live on the product form, forcing a bounce.
    # This action pre-fills the wizard with both product_tmpl_id and
    # shop_id straight off the Listing record. No resolver needed —
    # etsy_shop_id is the typed M2O backfilled by migration 19.0.3.8.0
    # (post-migrate name-lookup from the legacy shop_ref Char).
    #
    # FR-017 defense in depth:
    #   layer-1 view button gate (groups + invisible on etsy_shop_id)
    #   layer-2 wizard method gate (_check_ba_or_raise on publish action)
    # This bridge intentionally has NO gate of its own; opening the
    # wizard is harmless without the second layer.
    # ------------------------------------------------------------------
    def action_open_etsy_publish_wizard(self):
        self.ensure_one()
        if not self.channel_id or self.channel_id.code != 'etsy':
            raise UserError(_(
                "This listing is not bound to the Etsy channel.",
            ))
        if not self.etsy_shop_id:
            raise UserError(_(
                "This listing has no Etsy Shop resolved. Open the "
                "Advanced settings group and set the Etsy Shop manually, "
                "or contact an admin to re-run the shop backfill.",
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Publish to Etsy'),
            'res_model': 'etsy.publish.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_id': self.product_tmpl_id.id,
                'default_shop_id': self.etsy_shop_id.id,
            },
        }
