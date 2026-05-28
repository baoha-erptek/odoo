"""Live Etsy listing readback + field assertions (UAT Round 2, Slice C).

Runs INSIDE the staging container via `odoo shell` (the Etsy client needs the
shop OAuth token, which only exists server-side). It is piped to odoo shell on
stdin, so the `env` global provided by odoo shell is in scope; parameters arrive
through environment variables passed with `docker exec -e`:

    VERIFY_NAMES          pipe-separated product.template names to check
    VERIFY_SHOP           etsy.shop name (default 'JaHandmadeArt')
    VERIFY_MIN_IMAGES     minimum photo count on the Etsy listing (default 1)
    VERIFY_MIN_VARIATIONS minimum inventory products / variations (default 1)
    VERIFY_EXPECT_HEIGHT  '1' to require item_height present on the listing

For each name it resolves the Etsy listing_id from product.channel.status,
GETs the listing (+Inventory,Images), the images, the inventory, and the
shipping profile (for origin country), then prints a per-field PASS/FAIL table.
It prints a final 'VERIFY_RESULT: PASS' or 'VERIFY_RESULT: FAIL n=<count>' line
the orchestrator greps for.

Usage (from the repo host):
    cat tests/e2e/fixtures/verify_etsy_listing.py | ssh <staging> \
      "sudo docker exec -e VERIFY_NAMES='Apron X|Doormat Y' -e VERIFY_MIN_IMAGES=2 \
       -i esty19_odoo odoo shell -d esty_odoo19 --no-http"
"""
import os

from odoo.addons.etsy_integration.services.etsy_api_client import EtsyApiClient

_NAMES = [n for n in (os.environ.get('VERIFY_NAMES') or '').split('|') if n.strip()]
_SHOP = os.environ.get('VERIFY_SHOP') or 'JaHandmadeArt'
_MIN_IMAGES = int(os.environ.get('VERIFY_MIN_IMAGES') or 1)
_MIN_VARIATIONS = int(os.environ.get('VERIFY_MIN_VARIATIONS') or 1)
_EXPECT_HEIGHT = (os.environ.get('VERIFY_EXPECT_HEIGHT') or '') == '1'

_failures = 0


def _check(label, ok, detail=''):
    global _failures
    if not ok:
        _failures += 1
    print("  [%s] %-26s %s" % ('PASS' if ok else 'FAIL', label, detail))


def _info(label, detail):
    print("  [INFO] %-26s %s" % (label, detail))


def _verify_one(env, shop, client, name):
    print("=== %s ===" % name)
    Status = env['product.channel.status'].sudo()
    tmpl = env['product.template'].with_context(active_test=False).search(
        [('name', '=', name)], limit=1)
    if not tmpl:
        _check('product exists', False, 'no product.template named %r' % name)
        return
    st = Status.search([('product_tmpl_id', '=', tmpl.id)], limit=1)
    if not st or not st.external_ref:
        _check('listing_id resolved', False, 'no channel.status.external_ref')
        return
    lid = st.external_ref
    _info('listing_id', lid)

    listing = client.get('listings/%s' % lid, {'includes': 'Images,Inventory'})
    _check('state == draft', listing.get('state') == 'draft', listing.get('state'))
    _check('title present', bool(listing.get('title')), (listing.get('title') or '')[:48])
    _check('description present', bool(listing.get('description')))
    price = listing.get('price') or {}
    _check('price > 0', float(price.get('amount') or 0) > 0,
           '%s %s' % (price.get('amount'), price.get('currency_code')))
    _check('quantity >= 1', int(listing.get('quantity') or 0) >= 1, listing.get('quantity'))
    _check('who_made set', bool(listing.get('who_made')), listing.get('who_made'))
    _check('when_made set', bool(listing.get('when_made')), listing.get('when_made'))
    _check('taxonomy_id > 0', int(listing.get('taxonomy_id') or 0) > 0, listing.get('taxonomy_id'))
    _check('return_policy_id set', bool(listing.get('return_policy_id')), listing.get('return_policy_id'))
    _info('materials', listing.get('materials'))
    _info('tags', listing.get('tags'))
    for dim in ('item_weight', 'item_length', 'item_width', 'item_height'):
        if listing.get(dim) is not None:
            _info(dim, listing.get(dim))
    if _EXPECT_HEIGHT:
        _check('item_height present', listing.get('item_height') is not None, listing.get('item_height'))

    # Shipping profile + origin country
    spid = listing.get('shipping_profile_id')
    _check('shipping_profile_id set', bool(spid), spid)
    if spid:
        try:
            sp = client.get('shops/%s/shipping-profiles/%s' % (shop.sudo().etsy_api_shop_id, spid))
            _info('shipping origin_country_iso', sp.get('origin_country_iso'))
        except Exception as exc:  # noqa: BLE001
            _info('shipping origin lookup', 'err: %s' % exc)

    # Images
    imgs = client.get('listings/%s/images' % lid)
    cnt = imgs.get('count', len(imgs.get('results') or []))
    _check('images >= %d' % _MIN_IMAGES, cnt >= _MIN_IMAGES, 'count=%s' % cnt)

    # Inventory / variations
    inv = client.get('listings/%s/inventory' % lid)
    prods = inv.get('products') or []
    _check('variations >= %d' % _MIN_VARIATIONS, len(prods) >= _MIN_VARIATIONS, 'products=%d' % len(prods))
    for p in prods[:6]:
        pv = [(v.get('property_name'), v.get('values')) for v in (p.get('property_values') or [])]
        _info('  variation', 'sku=%s props=%s' % (p.get('sku'), pv))


shop = env['etsy.shop'].search([('name', '=', _SHOP)], limit=1)
client = EtsyApiClient(shop)
for _n in _NAMES:
    _verify_one(env, shop, client, _n.strip())
print('VERIFY_RESULT: %s' % ('PASS' if _failures == 0 else ('FAIL n=%d' % _failures)))
