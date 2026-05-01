#!/usr/bin/env python3
"""Seed the `demo_esty` database for E2E end-user demo.

Run via:
    docker exec -i namco_odoo19 odoo shell -d demo_esty \\
        --http-port=8889 --workers=0 --max-cron-threads=0 \\
        < deployment/scripts/seed-demo-esty.py

The script is idempotent — re-running deletes prior demo entities by
xmlid prefix `demo_esty.*` and reseeds.

What it builds:
- 5 demo users (kinhdoanh / sanxuat / ba_shipping / ba_manager / quanly)
- 9 demo products (3 per pipeline) with x_default_pipeline_id set so
  routing is auto-resolved per Spec 004.
- 30 sale orders (10 per pipeline) using REAL buyer names + addresses
  from `.0temp/Esty main 2 - 15h VN 06 08 2025.xlsx`.
- A few orders pre-positioned in mid-pipeline states to demonstrate
  the Tracking Dashboard + Mark Shipped flow.

Verifies:
- Each order has the right x_pipeline_id resolved.
- Each order has an initial transition log row.
"""
from __future__ import annotations

import logging
import os
import random
from itertools import cycle

import openpyxl

_logger = logging.getLogger('seed_demo_esty')
_logger.setLevel(logging.INFO)

# ``env`` is provided by ``odoo shell``.
env = env  # noqa: F821 — odoo shell injects this.

EXCEL_PATH = '/tmp/etsy_main.xlsx'
DEMO_PASSWORD = 'demo1234'
random.seed(42)


# ---------------------------------------------------------------------------
# 1. Cleanup prior demo entities (idempotency).
# ---------------------------------------------------------------------------
def cleanup():
    """Delete previously-seeded demo orders + products + users + partners."""
    SaleOrder = env['sale.order']
    Order = SaleOrder.search([('client_order_ref', 'like', 'DEMO-%')])
    if Order:
        _logger.info("Cleanup: removing %d demo orders", len(Order))
        Order.with_context(force_delete=True).unlink()

    Product = env['product.product'].search(
        [('default_code', 'like', 'DEMO-%')])
    if Product:
        _logger.info("Cleanup: removing %d demo products", len(Product))
        Product.unlink()

    Partner = env['res.partner'].search([('ref', 'like', 'DEMO-PARTNER-%')])
    if Partner:
        _logger.info("Cleanup: removing %d demo partners", len(Partner))
        Partner.unlink()

    Users = env['res.users'].search([('login', 'like', 'demo_%@hatafax.demo')])
    if Users:
        _logger.info("Cleanup: removing %d demo users", len(Users))
        Users.unlink()


# ---------------------------------------------------------------------------
# 2. Create demo users mapped to the user-guide vai trò.
# ---------------------------------------------------------------------------
def make_users():
    """Return dict role→user record."""
    Users = env['res.users']
    G = env.ref

    # Demo: every role also gets group_sale_manager so they can SEE all
    # 30 demo orders during the user-manual walk-through. Standard Odoo
    # salesman role applies an "Own Documents Only" record rule that
    # would otherwise hide orders created by another user. Production
    # deployment can revisit per-team scoping later.
    sale_mgr = G('sales_team.group_sale_manager')
    role_groups = {
        'kinhdoanh': [G('sales_team.group_sale_salesman'), sale_mgr],
        'sanxuat': [G('multichannel_hub_core.group_production_team'), sale_mgr],
        'ba_shipping': [G('multichannel_hub_fulfillment.group_ba_shipping'), sale_mgr],
        'ba_manager': [G('multichannel_hub_fulfillment.group_ba_manager'), sale_mgr],
        'quanly': [sale_mgr],
    }

    users = {}
    for role, groups in role_groups.items():
        login = f'demo_{role}@hatafax.demo'
        user = Users.create({
            'name': f'Demo {role.title()}',
            'login': login,
            'email': login,
            'password': DEMO_PASSWORD,
            'group_ids': [(6, 0, [g.id for g in groups])],
        })
        users[role] = user
        _logger.info("User %s id=%s pw=%s", login, user.id, DEMO_PASSWORD)
    return users


# ---------------------------------------------------------------------------
# 3. Demo products — 3 per pipeline, x_default_pipeline_id pre-routed.
# ---------------------------------------------------------------------------
def make_products():
    """Return dict pipeline_code→list[product.product]."""
    Product = env['product.product']
    pipelines = {
        'vn_internal_production': env.ref(
            'multichannel_hub_core.order_pipeline_vn_internal_production'),
        'gearment_pod': env.ref(
            'multichannel_hub_core.order_pipeline_gearment_pod'),
        'multi_technique_hybrid': env.ref(
            'multichannel_hub_core.order_pipeline_multi_technique_hybrid'),
    }
    cat_default = env.ref('product.product_category_goods')

    plan = {
        'vn_internal_production': [
            ('Áo Thun In Nội Địa A', 'DEMO-VN-TSHIRT-A', 18.50),
            ('Cốc Sứ In Nội Địa B', 'DEMO-VN-MUG-B', 12.00),
            ('Poster A2 In Nội Địa C', 'DEMO-VN-POSTER-C', 9.50),
        ],
        'gearment_pod': [
            ('Gearment T-Shirt POD A', 'DEMO-GM-TSHIRT-A', 19.99),
            ('Gearment Hoodie POD B', 'DEMO-GM-HOODIE-B', 34.99),
            ('Gearment Sweatshirt POD C', 'DEMO-GM-SWEAT-C', 28.50),
        ],
        'multi_technique_hybrid': [
            ('Hybrid Embroidered Hat A', 'DEMO-HY-HAT-A', 22.00),
            ('Hybrid Print + Embroidery Tote B', 'DEMO-HY-TOTE-B', 26.50),
            ('Hybrid Custom Order Multi-Tech C', 'DEMO-HY-MULTI-C', 45.00),
        ],
    }

    out = {}
    for code, items in plan.items():
        pipeline = pipelines[code]
        prods = []
        for name, sku, price in items:
            prod = Product.create({
                'name': name,
                'default_code': sku,
                'list_price': price,
                'categ_id': cat_default.id,
                'is_storable': True,
            })
            prod.product_tmpl_id.x_default_pipeline_id = pipeline.id
            prods.append(prod)
        out[code] = prods
        _logger.info("Pipeline %s → %d products", code, len(prods))
    return out


# ---------------------------------------------------------------------------
# 4. Read real Etsy orders from the source workbook.
# ---------------------------------------------------------------------------
def load_orders(n: int = 30):
    """Return list of dicts with buyer + address fields (real data)."""
    if not os.path.exists(EXCEL_PATH):
        raise FileNotFoundError(
            f"Expected {EXCEL_PATH} — run "
            f"`docker cp '.0temp/Esty main 2 - 15h VN 06 08 2025.xlsx' "
            f"namco_odoo19:{EXCEL_PATH}` first.")
    wb = openpyxl.load_workbook(
        EXCEL_PATH, read_only=True, data_only=True, keep_links=False)
    ws = wb[wb.sheetnames[0]]
    rows_iter = ws.iter_rows(values_only=True)
    headers = [h.strip() if isinstance(h, str) else h for h in next(rows_iter)]
    idx = {h: i for i, h in enumerate(headers)}

    def cell(row, key):
        i = idx.get(key)
        if i is None or i >= len(row):
            return None
        v = row[i]
        if v is None:
            return None
        return str(v).strip() or None

    sample = []
    for row in rows_iter:
        if (cell(row, 'SHIPPING_NAME')
                and cell(row, 'SHIPPING_ADDRESS1')
                and cell(row, 'ORDER_ID')):
            sample.append({
                'buyer': cell(row, 'SHIPPING_NAME'),
                'addr1': cell(row, 'SHIPPING_ADDRESS1'),
                'addr2': cell(row, 'SHIPPING_ADDRESS2') or '',
                'city': cell(row, 'SHIPPING_CITY') or '',
                'state': cell(row, 'SHIPPING_STATE') or '',
                'zip': cell(row, 'SHIPPING_ZIPCODE') or '',
                'country': cell(row, 'SHIPPING_COUNTRY') or 'US',
                'email': cell(row, 'SHIPPING_EMAIL'),
                'order_ref': cell(row, 'ORDER_ID'),
                'shop': cell(row, 'SHOP') or 'demo',
                'qty': int(float(cell(row, 'QUANTITY') or '1')),
                'note': (cell(row, 'NOTE_FROM_BUYER') or '')[:240],
                'gift': (cell(row, 'GIFT_MESSAGE') or '')[:240],
                'personalisation': (cell(row, 'PERSONALISATION') or '')[:240],
                'product_name': cell(row, 'PRODUCT_NAME') or '',
            })
        if len(sample) >= 200:  # take a window so random() has variety
            break
    wb.close()
    chosen = random.sample(sample, min(n, len(sample)))
    _logger.info("Loaded %d real Etsy rows for demo seed", len(chosen))
    return chosen


# ---------------------------------------------------------------------------
# 5. Country code → res.country mapping (best-effort).
# ---------------------------------------------------------------------------
_COUNTRY_CACHE = {}


def country_id(env, code_or_name: str):
    if not code_or_name:
        return False
    key = code_or_name.upper()
    if key in _COUNTRY_CACHE:
        return _COUNTRY_CACHE[key]
    Country = env['res.country']
    found = Country.search([('code', '=', key)], limit=1)
    if not found:
        found = Country.search([('name', 'ilike', code_or_name)], limit=1)
    cid = found.id if found else False
    _COUNTRY_CACHE[key] = cid
    return cid


# ---------------------------------------------------------------------------
# 6. Build sale orders + partners.
# ---------------------------------------------------------------------------
def make_orders(products_by_pipeline, source_rows, kinhdoanh_user):
    SaleOrder = env['sale.order']
    Partner = env['res.partner']

    pipeline_codes = list(products_by_pipeline.keys())
    # Ensure 10 orders per pipeline.
    chunks = {code: [] for code in pipeline_codes}
    for i, raw in enumerate(source_rows):
        chunks[pipeline_codes[i % len(pipeline_codes)]].append(raw)

    orders = []
    for pipeline_code, rows in chunks.items():
        product_cycle = cycle(products_by_pipeline[pipeline_code])
        for j, row in enumerate(rows):
            partner = Partner.create({
                'name': row['buyer'],
                'street': row['addr1'],
                'street2': row['addr2'],
                'city': row['city'],
                'state_id': False,
                'zip': row['zip'],
                'country_id': country_id(env, row['country']),
                'email': row['email'] or False,
                'ref': f'DEMO-PARTNER-{pipeline_code}-{j:02d}',
            })
            product = next(product_cycle)
            so = SaleOrder.create({
                'partner_id': partner.id,
                'user_id': kinhdoanh_user.id,
                'sales_channel': 'etsy',
                'channel_order_ref': row['order_ref'],
                'client_order_ref': f'DEMO-{pipeline_code}-{j:02d}',
                'order_line': [(0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': row['qty'],
                    'name': (product.name + (
                        f"\nNote: {row['note']}" if row['note'] else '')
                        + (f"\nGift: {row['gift']}" if row['gift'] else '')
                        + (f"\nPersonalisation: {row['personalisation']}"
                           if row['personalisation'] else '')),
                })],
            })
            orders.append((pipeline_code, so))
    return orders


# ---------------------------------------------------------------------------
# 7. Pre-position a few orders mid-pipeline for demo richness.
# ---------------------------------------------------------------------------
def position_states(orders):
    """Move some VN-internal orders to 'in_production' / 'packed' so the
    Process Dashboard and Tracking Dashboard show non-trivial data on
    first open."""
    targets = {
        'vn_internal_production': [
            ('multichannel_hub_core.state_vn_in_production', 3),
            ('multichannel_hub_core.state_vn_packed', 2),
        ],
        'gearment_pod': [
            ('multichannel_hub_core.state_gearment_quoted', 2),
            ('multichannel_hub_core.state_gearment_confirmed', 2),
        ],
        'multi_technique_hybrid': [
            ('multichannel_hub_core.state_hybrid_production', 2),
        ],
    }
    by_code = {}
    for code, so in orders:
        by_code.setdefault(code, []).append(so)

    for code, plan_list in targets.items():
        bucket = by_code.get(code, [])
        offset = 0
        for state_xmlid, n in plan_list:
            new_state = env.ref(state_xmlid)
            for so in bucket[offset:offset + n]:
                so._write_pipeline_state(
                    new_state,
                    note=f'Demo seed positioned to {new_state.code}',
                    change_type='migration',
                )
            offset += n


# ---------------------------------------------------------------------------
# 8. Verify: each order has expected pipeline + initial transition log.
# ---------------------------------------------------------------------------
def verify(orders):
    Log = env['order.pipeline.transition.log']
    bad = []
    for code, so in orders:
        expected = env.ref(f'multichannel_hub_core.order_pipeline_{code}')
        if so.x_pipeline_id != expected:
            bad.append(f"{so.name} expected {code} got {so.x_pipeline_id.code}")
        if not Log.search_count([('sale_order_id', '=', so.id),
                                 ('change_type', '=', 'initial')]):
            bad.append(f"{so.name} missing initial transition log")
    if bad:
        for line in bad:
            _logger.error(line)
        raise AssertionError("Demo seed verification failed; see log")
    _logger.info("Verify: %d orders all on expected pipelines + audit-logged",
                 len(orders))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
print("=" * 72)
print("Seeding demo_esty …")
print("=" * 72)
cleanup()
users = make_users()
products = make_products()
rows = load_orders(n=30)
orders = make_orders(products, rows, users['kinhdoanh'])
position_states(orders)
verify(orders)
env.cr.commit()
print("=" * 72)
print(f"Done. Demo users password: {DEMO_PASSWORD}")
print(f"Logins: " + ", ".join(u.login for u in users.values()))
print(f"Orders created: {len(orders)} (10 per pipeline)")
print("=" * 72)
