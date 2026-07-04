"""MF-E2E-1 runner — flow-1 tạo sản phẩm → publish (Etsy draft → active).

Mirrors the sectioned shape of scripts/e2e_demo_drop_ship_ordertest2.py.
Target: staging esty_odoo19 + live Etsy shop JaHandmadeArt (60752333).

Section layout (NEXT_SESSION_PROMPT_MF_E2E_FLOWS.md flow-1 bullet → section):

    §0 preflight + cleanup of prior E2E-F1 products/listings
    §1 SKU auto-derive chain via onchange RPC (MUG → MUG-CR → MUG-CR-F11)
    §2 product create: categ Mug + Material/Fluid oz variants + image
    §3 publish wizard draft-only (create_draft + images + inventory)
    §4 verify draft via Etsy GET readback (odoo shell over SSH)
    §5 action_run_publish → listing active on Etsy
    §6 verify active via Etsy GET readback
    §7 inventory-only re-push (idempotent) + inventory readback
    §8 listing-drift report clean for the test SKUs (after variant sync)
    §9 Etsy hygiene: deactivate listing (PATCH state=inactive) + archive
       test product. True DELETE needs the `listings_d` OAuth scope which
       the current grant lacks — see report note.

Playwright is used only for evidence screenshots (product form, publish
state); the interactive UI walk lives in
tests/e2e/tests/uat_huong_dan_tao_san_pham.spec.ts (TC-001..TC-015).

Usage:
    /tmp/e2e-venv/bin/python scripts/e2e_flow1_publish.py \
        --db esty_odoo19 [--section all|0..9] [--headed] [--keep-listing]
"""

from __future__ import annotations

import argparse
import base64
import logging
import os
import struct
import subprocess
import sys
import time
import xmlrpc.client
import zlib
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
TODAY = date.today().isoformat()
_SHOTS_BASE = REPO_ROOT / "docs" / "screenshots" / TODAY
if _SHOTS_BASE.exists() and not os.access(_SHOTS_BASE, os.W_OK):
    SHOTS_DIR = _SHOTS_BASE.with_name(
        f"{TODAY}_{datetime.now().strftime('%H%M%S')}")
else:
    SHOTS_DIR = _SHOTS_BASE
SHOTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_BASE_URL = "https://odoo.hatafax.com"
DEFAULT_DB = "esty_odoo19"

ETSY_API_SHOP_ID = "60752333"          # JaHandmadeArt
PRODUCT_PREFIX = "E2E-F1 Mug"          # cleanup key — never rename mid-series
# list_price is in COMPANY currency (USD on staging); the publisher converts
# to the shop listing currency (VND @ ~25400). 19.99 USD → ~507k VND, inside
# Etsy's [min, ₫1,257,533,727] window. 350000 here 400s with price_too_high.
LISTING_PRICE = float(os.environ.get("E2E_LISTING_PRICE", 19.99))

# SSH → odoo shell channel (same recipe as tests/e2e/fixtures/verify_etsy_listing.py)
SSH_KEY = REPO_ROOT / "secrets" / "ssh-key-2023-02-24.key"
SSH_HOST = "ubuntu@129.150.63.207"
STAGING_CONTAINER = "esty19_odoo"

LISTING_SYNC_CRONS = (
    ("etsy_integration", "cron_etsy_listing_sync"),
    ("etsy_integration", "cron_etsy_listing_variant_sync"),
)

USERS: dict[str, tuple[str, str]] = {
    "admin": ("admin", os.environ.get("DEMO_ADMIN_PASSWORD", "admin")),
    "ba_manager": ("demo_ba_manager@hatafax.demo", "demo1234"),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger("e2e_flow1_publish")

load_dotenv(REPO_ROOT / ".env")
# Staging admin creds override the demo default when present.
if os.environ.get("STAGING_ADMIN_LOGIN"):
    USERS["admin"] = (
        os.environ["STAGING_ADMIN_LOGIN"], os.environ["STAGING_ADMIN_PASSWORD"],
    )


# ─── result + context ──────────────────────────────────────────────────────────


@dataclass
class StepResult:
    section: str
    ok: bool
    note: str
    screenshot: str | None = None


@dataclass
class Context:
    base_url: str
    db: str
    common: xmlrpc.client.ServerProxy
    models: xmlrpc.client.ServerProxy
    uids: dict[str, int] = field(default_factory=dict)
    keep_listing: bool = False
    # populated as sections run
    shop_id: int | None = None
    tmpl_id: int | None = None
    tmpl_name: str = ""
    variant_ids: list[int] = field(default_factory=list)
    variant_skus: list[str] = field(default_factory=list)
    listing_id: str = ""


# ─── XML-RPC helpers (drop-ship runner idiom) ─────────────────────────────────


def _authenticate(ctx: Context, role: str) -> int:
    if role in ctx.uids:
        return ctx.uids[role]
    user, pw = USERS[role]
    uid = ctx.common.authenticate(ctx.db, user, pw, {})
    if not uid:
        raise RuntimeError(f"XML-RPC authenticate failed for {role} ({user})")
    ctx.uids[role] = uid
    return uid


def rpc(ctx: Context, role: str, model: str, method: str,
        args: list, kwargs: dict | None = None) -> Any:
    uid = _authenticate(ctx, role)
    _, pw = USERS[role]
    return ctx.models.execute_kw(
        ctx.db, uid, pw, model, method, args, kwargs or {})


def rpc_void(ctx: Context, role: str, model: str, method: str,
             args: list, kwargs: dict | None = None) -> None:
    try:
        rpc(ctx, role, model, method, args, kwargs)
    except xmlrpc.client.Fault as exc:
        if "cannot marshal None" in (exc.faultString or ""):
            return
        raise


def _xmlid_to_res_id(ctx: Context, module: str, name: str) -> int | None:
    rows = rpc(ctx, "admin", "ir.model.data", "search_read",
               [[("module", "=", module), ("name", "=", name)], ["res_id"]])
    return rows[0]["res_id"] if rows else None


# ─── SSH → odoo shell channel ──────────────────────────────────────────────────


def _odoo_shell(ctx: Context, snippet: str, env: dict[str, str] | None = None,
                timeout: int = 300) -> str:
    """Pipe a python snippet to `odoo shell` inside the staging container.

    The Etsy OAuth tokens only exist server-side (Fernet-encrypted on
    etsy.shop), so all live-API readbacks run in this channel — same
    recipe as tests/e2e/fixtures/verify_etsy_listing.py.
    """
    env_flags = " ".join(
        f"-e {k}='{v}'" for k, v in (env or {}).items())
    remote = (
        f"sudo docker exec {env_flags} -i {STAGING_CONTAINER} "
        f"odoo shell -d {ctx.db} --no-http"
    )
    cmd = ["ssh", "-i", str(SSH_KEY), "-o", "StrictHostKeyChecking=no",
           "-o", "BatchMode=yes", SSH_HOST, remote]
    proc = subprocess.run(
        cmd, input=snippet, capture_output=True, text=True, timeout=timeout)
    if proc.returncode not in (0,):
        _log.warning("odoo shell rc=%s stderr tail: %s",
                     proc.returncode, proc.stderr[-400:])
    return proc.stdout + proc.stderr


_GET_LISTING_SNIPPET = """
import json, os
from odoo.addons.etsy_integration.services.etsy_api_client import EtsyApiClient
shop = env['etsy.shop'].search([('etsy_api_shop_id', '=', os.environ['F1_SHOP'])], limit=1)
client = EtsyApiClient(shop)
try:
    listing = client.get('listings/%s' % os.environ['F1_LISTING'],
                         {'includes': 'Images,Inventory'})
    imgs = listing.get('images') or []
    inv = (listing.get('inventory') or {}).get('products') or []
    print('F1_JSON:' + json.dumps({
        'state': listing.get('state'),
        'title': (listing.get('title') or '')[:60],
        'quantity': listing.get('quantity'),
        'taxonomy_id': listing.get('taxonomy_id'),
        'n_images': len(imgs),
        'n_products': len(inv),
        'skus': sorted({p.get('sku') for p in inv if p.get('sku')}),
    }))
except Exception as exc:
    print('F1_ERROR:%s: %s' % (type(exc).__name__, str(exc)[:300]))
"""

_DEACTIVATE_SNIPPET = """
import os
from odoo.addons.etsy_integration.services.etsy_api_client import (
    EtsyApiClient, ETSY_API_BASE_URL)
shop = env['etsy.shop'].search([('etsy_api_shop_id', '=', os.environ['F1_SHOP'])], limit=1)
client = EtsyApiClient(shop)
lid = os.environ['F1_LISTING']
# PATCH via the raw session: state=inactive only needs listings_w. A true
# DELETE needs the listings_d scope, which the current OAuth grant lacks.
sess = client._session()
url = '%s/shops/%s/listings/%s' % (
    ETSY_API_BASE_URL, os.environ['F1_SHOP'], lid)
r = sess.patch(url, data={'state': 'inactive'})
print('F1_PATCH_STATUS:%s' % r.status_code)
if r.status_code >= 400:
    print('F1_PATCH_BODY:%s' % (r.text or '')[:300])
g = sess.get('%s/listings/%s' % (ETSY_API_BASE_URL, lid))
print('F1_STATE_AFTER:%s' % ((g.json() or {}).get('state') if g.ok else g.status_code))
"""

_DRIFT_SNIPPET = """
import json, os
from odoo.addons.etsy_integration.services.etsy_listing_drift_reporter import (
    EtsyListingDriftReporter)
shop = env['etsy.shop'].search([('etsy_api_shop_id', '=', os.environ['F1_SHOP'])], limit=1)
rep = EtsyListingDriftReporter(env)
skus = set(os.environ['F1_SKUS'].split(','))
rows = (rep.get_unlinked_variants(shop) + rep.get_qty_drifts(shop)
        + rep.get_orphan_products(shop))
mine = [r for r in rows if r.get('sku') in skus]
print('F1_DRIFT:' + json.dumps({'total_rows': len(rows), 'test_sku_rows': mine}))
"""


def _parse_marker(output: str, marker: str) -> str | None:
    for line in output.splitlines():
        if marker in line:
            return line.split(marker, 1)[1].strip()
    return None


# ─── tiny stdlib PNG (no Pillow in the venv) ──────────────────────────────────


def _make_png(width: int = 1200, height: int = 1200) -> bytes:
    """Solid-banded RGB PNG via zlib/struct — enough for Etsy's format check."""
    bands = [(196, 116, 62), (240, 234, 224), (62, 116, 196)]

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data)))

    raw = b""
    for y in range(height):
        r, g, b = bands[(y * len(bands)) // height]
        raw += b"\x00" + bytes([r, g, b]) * width
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


# ─── Playwright evidence helpers ──────────────────────────────────────────────


def _shot(page: Page, name: str) -> str:
    path = SHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return path.relative_to(REPO_ROOT).as_posix()


def _settle(page: Page, selector: str = ".o_form_view") -> None:
    # Selector wait, never networkidle (staging runs workers=0).
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector(selector, state="visible", timeout=30_000)


def login(page: Page, role: str, base: str, db: str) -> None:
    user, pw = USERS[role]
    try:
        page.context.clear_cookies()
    except Exception:
        pass
    page.goto(f"{base}/web/login?db={db}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector('input[name="login"]', state="visible", timeout=15_000)
    page.fill('input[name="login"]', user)
    page.fill('input[name="password"]', pw)
    page.click('button[type="submit"]')
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector(".o_action_manager", state="visible", timeout=30_000)


def _form_screenshot(ctx: Context, page: Page, name: str) -> str | None:
    try:
        login(page, "admin", ctx.base_url, ctx.db)
        page.goto(f"{ctx.base_url}/web#id={ctx.tmpl_id}"
                  f"&model=product.template&view_type=form")
        _settle(page)
        return _shot(page, name)
    except Exception as exc:  # noqa: BLE001 — screenshots are evidence, not gates
        _log.warning("screenshot %s failed: %s", name, exc)
        return None


# ─── sections ──────────────────────────────────────────────────────────────────


def section_0_preflight(ctx: Context) -> StepResult:
    version = ctx.common.version()["server_version"]
    _authenticate(ctx, "admin")
    _authenticate(ctx, "ba_manager")

    shops = rpc(ctx, "admin", "etsy.shop", "search_read",
                [[("etsy_api_shop_id", "=", ETSY_API_SHOP_ID)]],
                {"fields": ["name", "default_taxonomy_id",
                            "default_shipping_profile_id",
                            "default_return_policy_id",
                            "default_readiness_state_id"]})
    if not shops:
        return StepResult("0", False, "JaHandmadeArt shop row not found")
    shop = shops[0]
    missing = [f for f in ("default_taxonomy_id", "default_shipping_profile_id",
                           "default_return_policy_id",
                           "default_readiness_state_id") if not shop.get(f)]
    if missing:
        return StepResult("0", False, f"shop defaults missing: {missing}")
    ctx.shop_id = shop["id"]

    # cleanup: archive leftovers from prior runs (unlink blocked once rows
    # like channel.status reference them; archive is enough isolation).
    stale = rpc(ctx, "admin", "product.template", "search",
                [[("name", "like", PRODUCT_PREFIX)]],
                {"context": {"active_test": False}})
    fresh_stale = rpc(ctx, "admin", "product.template", "search",
                      [[("name", "like", PRODUCT_PREFIX), ("active", "=", True)]])
    if fresh_stale:
        rpc(ctx, "admin", "product.template", "write",
            [fresh_stale, {"active": False}])
    # Local mirror hygiene: prior runs' listings were deactivated on Etsy
    # (§9), but their etsy.listing.product rows stay is_active until a full
    # re-sync — which §8's drift reporter would flag as stale qty_drift.
    stale_variants = rpc(ctx, "admin", "etsy.listing.product", "search",
                         [[("listing_id.title", "like", PRODUCT_PREFIX),
                           ("is_active", "=", True)]])
    if stale_variants:
        rpc(ctx, "admin", "etsy.listing.product", "write",
            [stale_variants, {"is_active": False}])
    return StepResult(
        "0", True,
        f"server {version}; shop id={ctx.shop_id} defaults OK; "
        f"archived {len(fresh_stale)} stale test product(s) "
        f"({len(stale)} total historical)")


def section_1_sku_chain(ctx: Context) -> StepResult:
    """Drive the public onchange RPC through the derive chain.

    Same code path as the web client (`_onchange_auto_fill_default_code`),
    so this verifies MUG → MUG-CR → MUG-CR-F11 without a browser.
    """
    def _attr_id(name: str) -> int:
        return rpc(ctx, "admin", "product.attribute", "search",
                   [[("name", "=", name)]])[0]

    def _val_id(attr_id: int, name: str) -> int:
        return rpc(ctx, "admin", "product.attribute.value", "search",
                   [[("attribute_id", "=", attr_id), ("name", "=", name)]])[0]

    categ = rpc(ctx, "admin", "product.category", "search",
                [[("name", "=", "Mug")]])[0]
    mat = _attr_id("Material")
    mat_cr = _val_id(mat, "Ceramic + Chrome")
    foz = _attr_id("Fluid oz")
    foz_11 = _val_id(foz, "11 oz")
    ctx.sku_inputs = {  # type: ignore[attr-defined]
        "categ": categ, "mat": mat, "mat_cr": mat_cr,
        "foz": foz, "foz_11": foz_11,
    }

    spec = {"name": {}, "categ_id": {}, "default_code": {},
            "x_sku_auto_value": {}, "x_sku_v2_status": {},
            "attribute_line_ids": {
                "fields": {"attribute_id": {}, "value_ids": {}}}}
    base_vals = {"name": f"{PRODUCT_PREFIX} chain-check",
                 "default_code": False, "x_sku_auto_value": False,
                 "x_sku_v2_status": "non_canonical"}

    chain = []
    steps = [
        ("categ only", []),
        ("+ Material", [[0, 0, {"attribute_id": mat, "value_ids": [[6, 0, [mat_cr]]]}]]),
        ("+ Fluid oz", [
            [0, 0, {"attribute_id": mat, "value_ids": [[6, 0, [mat_cr]]]}],
            [0, 0, {"attribute_id": foz, "value_ids": [[6, 0, [foz_11]]]}],
        ]),
    ]
    prev_code = False
    for label, lines in steps:
        vals = dict(base_vals, categ_id=categ, attribute_line_ids=lines)
        if prev_code:
            # feed the previous auto value back in, as the browser would
            vals["default_code"] = prev_code
            vals["x_sku_auto_value"] = prev_code
        res = rpc(ctx, "admin", "product.template", "onchange",
                  [[], vals, ["categ_id", "attribute_line_ids"], spec])
        code = (res.get("value") or {}).get("default_code", prev_code)
        chain.append(f"{label}→{code}")
        prev_code = code

    ok = prev_code == "MUG-CR-F11"
    return StepResult("1", ok, "; ".join(chain))


def section_2_product_create(ctx: Context, page: Page) -> StepResult:
    si = ctx.sku_inputs  # type: ignore[attr-defined]
    foz_15 = rpc(ctx, "admin", "product.attribute.value", "search",
                 [[("attribute_id", "=", si["foz"]), ("name", "=", "15 oz")]])[0]
    ctx.tmpl_name = f"{PRODUCT_PREFIX} {datetime.now().strftime('%m%d-%H%M%S')}"
    ctx.tmpl_id = rpc(ctx, "admin", "product.template", "create", [{
        "name": ctx.tmpl_name,
        "categ_id": si["categ"],
        "is_storable": True,  # storable → quants allowed (§2 stock seed)
        "default_code": "MUG-CR-F11",
        "list_price": LISTING_PRICE,
        "image_1920": base64.b64encode(_make_png()).decode(),
        "attribute_line_ids": [
            [0, 0, {"attribute_id": si["mat"],
                    "value_ids": [[6, 0, [si["mat_cr"]]]]}],
            [0, 0, {"attribute_id": si["foz"],
                    "value_ids": [[6, 0, [si["foz_11"], foz_15]]]}],
        ],
    }])
    variants = rpc(ctx, "admin", "product.product", "search_read",
                   [[("product_tmpl_id", "=", ctx.tmpl_id)]],
                   {"fields": ["product_template_attribute_value_ids"]})
    if len(variants) != 2:
        return StepResult("2", False, f"expected 2 variants, got {len(variants)}")
    # Deterministic per-variant SKUs (the SKU-builder path BA uses in prod).
    sku_by_size = {"11 oz": "MUG-CR-F11", "15 oz": "MUG-CR-F15"}
    ctx.variant_ids, ctx.variant_skus = [], []
    for v in variants:
        names = rpc(ctx, "admin", "product.template.attribute.value", "read",
                    [v["product_template_attribute_value_ids"], ["name"]])
        size = next((n["name"] for n in names if n["name"] in sku_by_size), None)
        if not size:
            return StepResult("2", False, f"variant {v['id']} has no size value")
        rpc(ctx, "admin", "product.product", "write",
            [[v["id"]], {"default_code": sku_by_size[size]}])
        ctx.variant_ids.append(v["id"])
        ctx.variant_skus.append(sku_by_size[size])
    # Real on-hand stock (5/variant): the publisher floors offering qty to 1
    # for zero-stock products, which §8's drift reporter would (correctly)
    # flag as qty_drift vs Odoo's 0.
    wh = rpc(ctx, "admin", "stock.warehouse", "search_read", [[]],
             {"fields": ["lot_stock_id"], "limit": 1})[0]
    for vid in ctx.variant_ids:
        quant = rpc(ctx, "admin", "stock.quant", "create",
                    [{"product_id": vid,
                      "location_id": wh["lot_stock_id"][0],
                      "inventory_quantity": 5}])
        rpc_void(ctx, "admin", "stock.quant", "action_apply_inventory", [[quant]])
    shot = _form_screenshot(ctx, page, "f1_s2_product_form")
    return StepResult(
        "2", True,
        f"tmpl {ctx.tmpl_id} '{ctx.tmpl_name}' 2 variants "
        f"{sorted(ctx.variant_skus)} price={LISTING_PRICE:g}", shot)


def section_3_publish_draft(ctx: Context) -> StepResult:
    wiz = rpc(ctx, "ba_manager", "etsy.publish.wizard", "create",
              [{"product_tmpl_id": ctx.tmpl_id, "shop_id": ctx.shop_id}])
    res = rpc(ctx, "ba_manager", "etsy.publish.wizard",
              "action_run_publish_draft_only", [[wiz]])
    listing_id = res.get("listing_id") if isinstance(res, dict) else None
    if not listing_id:
        return StepResult("3", False, f"wizard returned no listing_id: {res!r}")
    ctx.listing_id = str(listing_id)
    status = rpc(ctx, "admin", "product.channel.status", "search_read",
                 [[("product_tmpl_id", "=", ctx.tmpl_id)]],
                 {"fields": ["state", "external_ref"]})
    st = status[0] if status else {}
    ok = st.get("external_ref") == ctx.listing_id
    return StepResult(
        "3", ok,
        f"listing_id={ctx.listing_id} channel.status state={st.get('state')} "
        f"external_ref={st.get('external_ref')}")


def _readback(ctx: Context) -> dict | None:
    out = _odoo_shell(ctx, _GET_LISTING_SNIPPET,
                      {"F1_SHOP": ETSY_API_SHOP_ID, "F1_LISTING": ctx.listing_id})
    payload = _parse_marker(out, "F1_JSON:")
    if payload is None:
        err = _parse_marker(out, "F1_ERROR:")
        _log.warning("readback failed: %s", err or out[-400:])
        return None
    import json
    return json.loads(payload)


def section_4_verify_draft(ctx: Context) -> StepResult:
    data = _readback(ctx)
    if data is None:
        return StepResult("4", False, "Etsy GET readback failed (see log)")
    checks = {
        "state=draft": data["state"] == "draft",
        "images>=1": data["n_images"] >= 1,
        "products>=2": data["n_products"] >= 2,
        "skus match": set(ctx.variant_skus) <= set(data["skus"]),
        "taxonomy>0": (data["taxonomy_id"] or 0) > 0,
    }
    bad = [k for k, v in checks.items() if not v]
    return StepResult("4", not bad,
                      f"{data}" if not bad else f"failed={bad} data={data}")


def section_5_publish_active(ctx: Context, page: Page) -> StepResult:
    wiz = rpc(ctx, "ba_manager", "etsy.publish.wizard", "create",
              [{"product_tmpl_id": ctx.tmpl_id, "shop_id": ctx.shop_id}])
    rpc_void(ctx, "ba_manager", "etsy.publish.wizard", "action_run_publish", [[wiz]])
    status = rpc(ctx, "admin", "product.channel.status", "search_read",
                 [[("product_tmpl_id", "=", ctx.tmpl_id)]],
                 {"fields": ["state", "external_ref"]})
    st = status[0] if status else {}
    shot = _form_screenshot(ctx, page, "f1_s5_published_form")
    ok = st.get("state") == "published" and st.get("external_ref") == ctx.listing_id
    return StepResult("5", ok,
                      f"channel.status state={st.get('state')} "
                      f"external_ref={st.get('external_ref')}", shot)


def section_6_verify_active(ctx: Context) -> StepResult:
    data = _readback(ctx)
    if data is None:
        return StepResult("6", False, "Etsy GET readback failed (see log)")
    ok = data["state"] == "active"
    return StepResult("6", ok, f"{data}")


def section_7_inventory_repush(ctx: Context) -> StepResult:
    wiz = rpc(ctx, "ba_manager", "etsy.publish.wizard", "create",
              [{"product_tmpl_id": ctx.tmpl_id, "shop_id": ctx.shop_id}])
    rpc_void(ctx, "ba_manager", "etsy.publish.wizard",
             "action_run_inventory_only", [[wiz]])
    data = _readback(ctx)
    if data is None:
        return StepResult("7", False, "Etsy GET readback failed after re-push")
    ok = (data["state"] == "active" and data["n_products"] >= 2
          and set(ctx.variant_skus) <= set(data["skus"]))
    return StepResult("7", ok, f"idempotent re-push OK: {data}" if ok else f"{data}")


def section_8_drift_report(ctx: Context) -> StepResult:
    # Pull Etsy → local mirror first so the reporter sees today's listing.
    for module, name in LISTING_SYNC_CRONS:
        cron_id = _xmlid_to_res_id(ctx, module, name)
        if not cron_id:
            return StepResult("8", False, f"cron xmlid {module}.{name} not found")
        rpc_void(ctx, "admin", "ir.cron", "method_direct_trigger", [[cron_id]])
        time.sleep(2)
    out = _odoo_shell(ctx, _DRIFT_SNIPPET,
                      {"F1_SHOP": ETSY_API_SHOP_ID,
                       "F1_SKUS": ",".join(ctx.variant_skus)})
    payload = _parse_marker(out, "F1_DRIFT:")
    if payload is None:
        return StepResult("8", False, f"drift snippet failed: {out[-300:]}")
    import json
    drift = json.loads(payload)
    mine = drift["test_sku_rows"]
    return StepResult(
        "8", not mine,
        f"drift rows total={drift['total_rows']}; test-SKU rows={mine or 'none'}")


def section_9_hygiene(ctx: Context) -> StepResult:
    if ctx.keep_listing:
        return StepResult("9", True,
                          f"--keep-listing: listing {ctx.listing_id} left active")
    out = _odoo_shell(ctx, _DEACTIVATE_SNIPPET,
                      {"F1_SHOP": ETSY_API_SHOP_ID, "F1_LISTING": ctx.listing_id})
    patch_status = _parse_marker(out, "F1_PATCH_STATUS:")
    state_after = _parse_marker(out, "F1_STATE_AFTER:")
    # archive the test product (unlink blocked by channel.status FK rows)
    rpc(ctx, "admin", "product.template", "write",
        [[ctx.tmpl_id], {"active": False}])
    # Etsy reports an owner-deactivated listing as 'edit' (Shop-Manager
    # editing state) on GET; both mean "no longer buyer-visible".
    ok = patch_status == "200" and state_after in ("inactive", "edit")
    note = (f"listing {ctx.listing_id} PATCH={patch_status} "
            f"state_after={state_after}; product archived. "
            f"True DELETE needs listings_d scope (not granted — owner item).")
    if not ok:
        note += f" body={_parse_marker(out, 'F1_PATCH_BODY:')}"
    return StepResult("9", ok, note)


# ─── report writer ─────────────────────────────────────────────────────────────


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True,
        ).strip()
    except Exception:
        return "unknown"


def write_report(results: list[StepResult], ctx: Context) -> Path:
    canonical = (REPO_ROOT / "docs" / "engineering" / "uats"
                 / f"E2E_FLOW1_PUBLISH_{TODAY}.md")
    if canonical.exists() and not os.access(canonical, os.W_OK):
        canonical = canonical.with_name(
            f"E2E_FLOW1_PUBLISH_{TODAY}_{datetime.now().strftime('%H%M%S')}.md")
    passed = sum(1 for r in results if r.ok)
    lines = [
        f"# MF-E2E-1 — Flow-1 tạo sản phẩm → publish ({TODAY})",
        "",
        f"- **Target**: {ctx.base_url} / DB `{ctx.db}`",
        f"- **Build**: {_git_head()}",
        f"- **Driver**: scripts/e2e_flow1_publish.py",
        f"- **Etsy shop**: JaHandmadeArt ({ETSY_API_SHOP_ID})",
        f"- **Listing**: {ctx.listing_id or '—'}",
        f"- **Result**: {passed}/{len(results)} sections PASS",
        "",
        "| § | Result | Note | Screenshot |",
        "|---|---|---|---|",
    ]
    for r in results:
        note = r.note.replace("|", "\\|")
        lines.append(f"| {r.section} | {'PASS' if r.ok else 'FAIL'} "
                     f"| {note} | {r.screenshot or '—'} |")
    lines += [
        "",
        "## Notes",
        "",
        "- §9 deactivates (PATCH state=inactive) instead of deleting: Etsy "
        "`deleteListing` requires the `listings_d` OAuth scope, which the "
        "current grant (transactions_r/w, listings_r/w, shops_r/w, email_r) "
        "does not include. Owner decision: add `listings_d` to "
        "DEFAULT_SCOPES + re-authorize, or keep manual Shop-Manager deletes.",
        "- `publisher.publish()` PATCH path fixed to the shop-scoped "
        "updateListing route in etsy_integration 19.0.3.16.0 (pre-fix it "
        "targeted bare listings/{id}, which 404s — never exercised live "
        "before this gate).",
        "",
        "## Reproducing",
        "",
        "```bash",
        f"/tmp/e2e-venv/bin/python scripts/e2e_flow1_publish.py --db {ctx.db}",
        "```",
    ]
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return canonical


# ─── main ──────────────────────────────────────────────────────────────────────


SECTIONS = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9")


def _safe(section: str, fn, *args, **kwargs) -> StepResult:
    try:
        return fn(*args, **kwargs)
    except xmlrpc.client.Fault as exc:
        return StepResult(section, False,
                          f"XML-RPC fault: {exc.faultString.splitlines()[0][:200]}")
    except Exception as exc:  # noqa: BLE001 — runner must always produce a report
        return StepResult(section, False, f"{type(exc).__name__}: {str(exc)[:200]}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--section", default="all", help=f"all or one of {SECTIONS}")
    p.add_argument("--headed", action="store_true")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--keep-listing", action="store_true",
                   help="skip §9 deactivation (leave the listing live)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    selected = set(SECTIONS) if args.section == "all" else {args.section}
    ctx = Context(
        base_url=args.base_url, db=args.db,
        common=xmlrpc.client.ServerProxy(f"{args.base_url}/xmlrpc/2/common"),
        models=xmlrpc.client.ServerProxy(f"{args.base_url}/xmlrpc/2/object"),
        keep_listing=args.keep_listing,
    )
    results: list[StepResult] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        runners = {
            "0": lambda: section_0_preflight(ctx),
            "1": lambda: section_1_sku_chain(ctx),
            "2": lambda: section_2_product_create(ctx, page),
            "3": lambda: section_3_publish_draft(ctx),
            "4": lambda: section_4_verify_draft(ctx),
            "5": lambda: section_5_publish_active(ctx, page),
            "6": lambda: section_6_verify_active(ctx),
            "7": lambda: section_7_inventory_repush(ctx),
            "8": lambda: section_8_drift_report(ctx),
            "9": lambda: section_9_hygiene(ctx),
        }
        abort = False
        for sec in SECTIONS:
            if sec not in selected:
                continue
            if abort:
                results.append(StepResult(sec, False, "skipped: earlier section failed hard"))
                continue
            _log.info("=== §%s ===", sec)
            r = _safe(sec, runners[sec])
            results.append(r)
            _log.info("§%s %s — %s", sec, "PASS" if r.ok else "FAIL", r.note)
            # §0-§3 failures make everything downstream meaningless.
            if not r.ok and sec in ("0", "1", "2", "3"):
                abort = True
        browser.close()
    report = write_report(results, ctx)
    _log.info("report: %s", report)
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
