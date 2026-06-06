"""P-LIST-CATEGORY (ADR-015 §3 / spec 012 §US4) — Etsy taxonomy extension.

mhc cannot depend on etsy_integration (ADR-003 keeps the dependency
graph one-way). Etsy-specific listing fields therefore live here, as
classic ``_inherit`` extensions of ``multichannel.listing``.
"""

from odoo import fields, models


class MultichannelListingEtsy(models.Model):
    _inherit = 'multichannel.listing'

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
