"""Etsy seller taxonomy syncer (P-LIST-CATEGORY).

Pulls the full taxonomy tree from
``GET /v3/application/seller-taxonomy/nodes`` and upserts every node into
``etsy.taxonomy.node``. Two-pass:
  1. Flatten the recursive ``children`` payload into a flat list.
  2. Upsert in two phases — first pass creates/updates without parents;
     second pass wires parent_id (parents now resolvable in cache).

Caller (cron or manual button) provides an ``etsy.shop`` so the API
client can pull credentials. The endpoint is shop-agnostic, but the API
client wrapper is shop-bound; the resulting cache is *shared* across
shops (Etsy's taxonomy is a global catalog).
"""

import logging

from odoo import fields as odoo_fields

from .etsy_api_client import EtsyApiClient

_logger = logging.getLogger(__name__)


def _flatten(nodes, parent_id=None, level=0, out=None):
    """Walk the recursive nodes list, emit (etsy_id, name, parent_etsy_id,
    level) tuples. Parent ids are tracked as Etsy ids, not Odoo ids — the
    caller resolves to Odoo records in the upsert pass.
    """
    if out is None:
        out = []
    for n in nodes or []:
        etsy_id = n.get('id')
        if etsy_id is None:
            continue
        out.append((str(etsy_id), n.get('name') or '', parent_id, level))
        children = n.get('children') or []
        if children:
            _flatten(children, parent_id=str(etsy_id), level=level + 1,
                     out=out)
    return out


def sync_taxonomy(env, shop, client=None):
    """Pull + upsert. Returns ``(created, updated)``.

    ``client`` is injectable for tests. Production callers pass None and
    we instantiate ``EtsyApiClient(shop)``.
    """
    if client is None:
        client = EtsyApiClient(shop)
    response = client.get('seller-taxonomy/nodes')
    nodes = (response or {}).get('results') or []
    flat = _flatten(nodes)
    if not flat:
        _logger.warning(
            "Etsy taxonomy sync: empty response from /seller-taxonomy/nodes "
            "for shop %r; nothing to upsert.", shop.name,
        )
        return 0, 0

    Node = env['etsy.taxonomy.node'].sudo()
    now = odoo_fields.Datetime.now()

    # Pass 1: upsert without parent_id (parents may not exist yet).
    by_etsy_id = {}
    created = 0
    updated = 0
    for etsy_id, name, _parent_etsy_id, level in flat:
        existing = Node.search([('etsy_id', '=', etsy_id)], limit=1)
        vals = {
            'name': name,
            'level': level,
            'active': True,
            'last_synced_at': now,
        }
        if existing:
            existing.write(vals)
            by_etsy_id[etsy_id] = existing
            updated += 1
        else:
            new = Node.create(dict(vals, etsy_id=etsy_id))
            by_etsy_id[etsy_id] = new
            created += 1

    # Pass 2: wire parents. Skip when parent is missing from the cache
    # (shouldn't happen with a well-formed Etsy response).
    for etsy_id, _name, parent_etsy_id, _level in flat:
        if not parent_etsy_id:
            continue
        node = by_etsy_id.get(etsy_id)
        parent = by_etsy_id.get(parent_etsy_id)
        if not (node and parent):
            continue
        if node.parent_id != parent:
            node.parent_id = parent

    _logger.info(
        "Etsy taxonomy sync (shop %r): %s created, %s updated, %s total nodes.",
        shop.name, created, updated, len(flat),
    )
    return created, updated
