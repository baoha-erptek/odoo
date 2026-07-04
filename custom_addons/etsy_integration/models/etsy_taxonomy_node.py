"""Etsy seller taxonomy node cache (P-LIST-CATEGORY / ADR-015).

Flat materialization of Etsy's seller-taxonomy tree (root level 0 → leaves).
Synced by the ``etsy_taxonomy_syncer`` service on demand and on a weekly
cron (see ``data/etsy_taxonomy_cron.xml``).

Per ADR-015 §3 + spec 012 P-LIST-CATEGORY: the listing layer holds the
operator-chosen ``multichannel.listing.etsy_taxonomy_id`` override; the
publisher reads it with a shop-default fallback.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class EtsyTaxonomyNode(models.Model):
    _name = 'etsy.taxonomy.node'
    _description = 'Etsy Seller Taxonomy Node (cache)'
    _order = 'full_path, name'
    _rec_name = 'display_name'

    etsy_id = fields.Char(
        string='Etsy ID',
        required=True,
        index=True,
        copy=False,
        help='The Etsy seller-taxonomy node id (int64 stored as string to '
             'avoid XML-RPC int32 overflow).',
    )
    name = fields.Char(
        required=True,
        help='Leaf name (e.g. "Cookware", "Throw Pillows").',
    )
    parent_id = fields.Many2one(
        'etsy.taxonomy.node',
        string='Parent',
        ondelete='set null',
        index=True,
        recursive=True,
    )
    child_ids = fields.One2many(
        'etsy.taxonomy.node',
        'parent_id',
        string='Children',
    )
    level = fields.Integer(
        default=0,
        help='Depth in the seller-taxonomy tree (root = 0).',
    )
    full_path = fields.Char(
        compute='_compute_full_path',
        store=True,
        index=True,
        help='Slash-joined breadcrumb, e.g. "Home & Living / Kitchen / Cookware".',
    )
    active = fields.Boolean(
        default=True,
        help='Soft-disable when Etsy retires a taxonomy node so historical '
             'listings still resolve their label.',
    )
    last_synced_at = fields.Datetime(copy=False)
    display_name = fields.Char(
        compute='_compute_display_name', store=True,
    )

    def init(self):
        """Mirror UNIQUE(etsy_id) at PG per project_sql_constraints_drift."""
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                uniq_etsy_taxonomy_node_etsy_id
            ON etsy_taxonomy_node (etsy_id)
        """)

    @api.depends('name', 'parent_id.full_path')
    def _compute_full_path(self):
        for rec in self:
            if rec.parent_id and rec.parent_id.full_path:
                rec.full_path = '%s / %s' % (rec.parent_id.full_path, rec.name)
            else:
                rec.full_path = rec.name or ''

    @api.depends('full_path', 'etsy_id')
    def _compute_display_name(self):
        for rec in self:
            if rec.full_path and rec.etsy_id:
                rec.display_name = '%s [#%s]' % (rec.full_path, rec.etsy_id)
            else:
                rec.display_name = rec.name or rec.etsy_id or ''
