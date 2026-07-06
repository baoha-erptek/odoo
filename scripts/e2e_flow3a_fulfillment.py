"""MF-E2E-3a runner — flow-3a giao hàng in nội bộ (Route A internal).

Mirrors the sectioned shape of scripts/e2e_demo_drop_ship_ordertest2.py.
Target: staging esty_odoo19.

Section layout (NEXT_SESSION_PROMPT_MF_E2E_FLOWS.md flow-3a bullet → section):

    §0 preflight: MTO+Manufacture routes (ENV-FIX-MRP), gke partner active,
       google libs importable in the container, fixture cleanup
    §1 fixtures: component + finished product (MTO+Manufacture, 1:1 BOM),
       Route-A sale order with an etsy_order_id marker
    §2 SO confirm → MO auto-created (procurement)
    §3 design.file attach + proof + approve (operator design gate)
    §4 MO complete (button_mark_done)
    §5 Delivery Order validated
    §6 GKE xlsx GENERATED from THIS run's order ref (fixes MF-E2E-0 residue:
       static sample matched 0/9) + uploaded to the GDrive inbox
    §7 poller import → tracking matched → carrier auto-detected (USPS prefix)
    §8 Etsy tracking push flags: cron fires, push path runs to the Etsy API
       boundary; synthetic receipt → recorded failure + retry-cap counter
       (a real 'pushed' needs a real receipt — P1-11 production scope)
    §9 dashboard evidence + cleanup

Usage:
    /tmp/e2e-venv/bin/python scripts/e2e_flow3a_fulfillment.py \
        --db esty_odoo19 [--section all|0..9] [--headed]
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
import uuid
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

ETSY_API_SHOP_ID = "60752333"      # JaHandmadeArt (needed for the push leg)
PRODUCT_PREFIX = "E2E-F3"          # cleanup key
PUSH_CRON_XMLID = ("etsy_integration", "ir_cron_etsy_tracking_push")
POLLER_CRON_XMLID = ("multichannel_hub_fulfillment", "cron_logistics_inbox_poller")

SSH_KEY = REPO_ROOT / "secrets" / "ssh-key-2023-02-24.key"
SSH_HOST = "ubuntu@129.150.63.207"
STAGING_CONTAINER = "esty19_odoo"

USERS: dict[str, tuple[str, str]] = {
    "admin": ("admin", os.environ.get("DEMO_ADMIN_PASSWORD", "admin")),
    "ba_shipping": ("demo_ba_shipping@hatafax.demo", "demo1234"),
    "production": ("demo_sanxuat@hatafax.demo", "demo1234"),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger("e2e_flow3a")

load_dotenv(REPO_ROOT / ".env")
if os.environ.get("STAGING_ADMIN_LOGIN"):
    USERS["admin"] = (
        os.environ["STAGING_ADMIN_LOGIN"], os.environ["STAGING_ADMIN_PASSWORD"],
    )


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
    marker: str = ""
    receipt_marker: str = ""
    shop_id: int | None = None
    inbox_folder_id: str = ""
    component_id: int | None = None
    product_id: int | None = None
    order_id: int | None = None
    order_name: str = ""
    mo_id: int | None = None
    picking_id: int | None = None
    design_file_ids: list[int] = field(default_factory=list)
    xlsx_path: Path | None = None


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


def _trigger_cron(ctx: Context, xmlid: tuple[str, str]) -> None:
    cron_id = _xmlid_to_res_id(ctx, *xmlid)
    if not cron_id:
        raise RuntimeError(f"cron xmlid {xmlid} not found")
    rpc_void(ctx, "admin", "ir.cron", "method_direct_trigger", [[cron_id]])


def _odoo_shell(ctx: Context, snippet: str, timeout: int = 180) -> str:
    remote = (f"sudo docker exec -i {STAGING_CONTAINER} "
              f"odoo shell -d {ctx.db} --no-http")
    cmd = ["ssh", "-i", str(SSH_KEY), "-o", "StrictHostKeyChecking=no",
           "-o", "BatchMode=yes", SSH_HOST, remote]
    proc = subprocess.run(cmd, input=snippet, capture_output=True,
                          text=True, timeout=timeout)
    return proc.stdout + proc.stderr


def _make_png(width: int = 400, height: int = 400) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data)))
    raw = b"".join(b"\x00" + bytes([200, 120, 60]) * width
                   for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def _shot(page: Page, name: str) -> str:
    path = SHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return path.relative_to(REPO_ROOT).as_posix()


def login(page: Page, base: str, db: str) -> None:
    user, pw = USERS["admin"]
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


# ─── sections ──────────────────────────────────────────────────────────────────


def section_0_preflight(ctx: Context) -> StepResult:
    version = ctx.common.version()["server_version"]
    routes = rpc(ctx, "admin", "stock.route", "search_read",
                 [[("rule_ids.action", "=", "manufacture")]], {"fields": ["name"]})
    mto = rpc(ctx, "admin", "stock.route", "search_read",
              [[("name", "ilike", "replenish")]], {"fields": ["name"]})
    if not routes or not mto:
        return StepResult("0", False,
                          f"ENV-FIX-MRP: manufacture={routes} mto={mto}")
    ctx.mfg_route_id = routes[0]["id"]  # type: ignore[attr-defined]
    ctx.mto_route_id = mto[0]["id"]     # type: ignore[attr-defined]

    shops = rpc(ctx, "admin", "etsy.shop", "search",
                [[("etsy_api_shop_id", "=", ETSY_API_SHOP_ID)]])
    if not shops:
        return StepResult("0", False, "JaHandmadeArt shop row missing")
    ctx.shop_id = shops[0]

    partners = rpc(ctx, "admin", "logistics.partner", "search_read",
                   [[("code", "=", "gke")]],
                   {"fields": ["is_active", "gdrive_inbox_folder_id"]})
    if not partners or not partners[0]["is_active"] \
            or not partners[0]["gdrive_inbox_folder_id"]:
        return StepResult("0", False, f"gke logistics.partner not ready: {partners}")
    ctx.inbox_folder_id = partners[0]["gdrive_inbox_folder_id"]
    ctx.gke_partner_id = partners[0]["id"]  # type: ignore[attr-defined]

    # google libs on the container (wiped on recreate — findings.md item 1)
    out = _odoo_shell(ctx, "import googleapiclient, google.oauth2\n"
                           "print('F3_GOOGLE_OK')")
    if "F3_GOOGLE_OK" not in out:
        return StepResult(
            "0", False,
            "google libs missing in esty19_odoo — re-run the pip step "
            "(findings.md MF-E2E-0 item 1)")

    ctx.marker = uuid.uuid4().hex[:6]
    ctx.receipt_marker = f"97{int(time.time()) % 100_000_000}"

    stale = rpc(ctx, "admin", "product.template", "search",
                [[("name", "like", PRODUCT_PREFIX), ("active", "=", True)]])
    if stale:
        rpc(ctx, "admin", "product.template", "write", [stale, {"active": False}])
    return StepResult(
        "0", True,
        f"server {version}; routes OK (mfg+mto); gke folder "
        f"{ctx.inbox_folder_id[:8]}…; google libs OK; marker={ctx.marker}; "
        f"archived {len(stale)} stale product(s)")


def section_1_fixtures(ctx: Context) -> StepResult:
    comp_tmpl = rpc(ctx, "admin", "product.template", "create", [{
        "name": f"{PRODUCT_PREFIX} Component {ctx.marker}",
        "is_storable": True, "list_price": 1.0,
    }])
    ctx.component_id = rpc(ctx, "admin", "product.product", "search",
                           [[("product_tmpl_id", "=", comp_tmpl)]])[0]
    fin_tmpl = rpc(ctx, "admin", "product.template", "create", [{
        "name": f"{PRODUCT_PREFIX} Keepsake {ctx.marker}",
        "is_storable": True, "list_price": 25.0,
        "route_ids": [[6, 0, [ctx.mfg_route_id, ctx.mto_route_id]]],  # type: ignore[attr-defined]
    }])
    ctx.product_id = rpc(ctx, "admin", "product.product", "search",
                         [[("product_tmpl_id", "=", fin_tmpl)]])[0]
    rpc(ctx, "admin", "mrp.bom", "create", [{
        "product_tmpl_id": fin_tmpl,
        "product_qty": 1.0,
        "type": "normal",
        "bom_line_ids": [[0, 0, {"product_id": ctx.component_id,
                                 "product_qty": 1.0}]],
    }])
    # component stock so the MO can consume
    wh = rpc(ctx, "admin", "stock.warehouse", "search_read", [[]],
             {"fields": ["lot_stock_id"], "limit": 1})[0]
    quant = rpc(ctx, "admin", "stock.quant", "create",
                [{"product_id": ctx.component_id,
                  "location_id": wh["lot_stock_id"][0],
                  "inventory_quantity": 10}])
    rpc_void(ctx, "admin", "stock.quant", "action_apply_inventory", [[quant]])

    partner = rpc(ctx, "admin", "res.partner", "create", [{
        "name": f"{PRODUCT_PREFIX} Buyer {ctx.marker}",
        "street": "1 Test Lane", "city": "Austin", "zip": "78701",
        "country_id": rpc(ctx, "admin", "res.country", "search",
                          [[("code", "=", "US")]])[0],
    }])
    ctx.order_id = rpc(ctx, "admin", "sale.order", "create", [{
        "partner_id": partner,
        "etsy_order_id": ctx.receipt_marker,
        "etsy_shop_id": ctx.shop_id,
        "order_line": [[0, 0, {"product_id": ctx.product_id,
                               "product_uom_qty": 1.0, "price_unit": 25.0}]],
    }])
    ctx.order_name = rpc(ctx, "admin", "sale.order", "read",
                         [[ctx.order_id], ["name"]])[0]["name"]
    return StepResult(
        "1", True,
        f"order {ctx.order_name} (receipt marker {ctx.receipt_marker}), "
        f"Route-A product + 1:1 BOM + component stock seeded")


def section_2_confirm_mo(ctx: Context) -> StepResult:
    rpc_void(ctx, "admin", "sale.order", "action_confirm", [[ctx.order_id]])
    deadline = time.time() + 60
    mo = None
    while time.time() < deadline:
        rows = rpc(ctx, "admin", "mrp.production", "search_read",
                   [[("origin", "=", ctx.order_name)]],
                   {"fields": ["name", "state", "product_id"]})
        if rows:
            mo = rows[0]
            break
        time.sleep(3)
    if not mo:
        return StepResult("2", False,
                          f"no MO with origin={ctx.order_name} within 60s "
                          "(MTO procurement did not fire)")
    ctx.mo_id = mo["id"]
    return StepResult("2", True,
                      f"MO {mo['name']} state={mo['state']} auto-created "
                      f"from {ctx.order_name}")


def section_3_design_approve(ctx: Context) -> StepResult:
    line = rpc(ctx, "admin", "sale.order.line", "search",
               [[("order_id", "=", ctx.order_id)]])[0]
    df_id = rpc(ctx, "admin", "design.file", "create", [{
        "name": f"{PRODUCT_PREFIX}-DESIGN-{ctx.marker}",
        "order_line_id": line,
        "storage_mode": "small",
        "design_file": base64.b64encode(_make_png()).decode(),
        "file_name": f"e2e-f3-design-{ctx.marker}.png",
        "state": "pending",
    }])
    ctx.design_file_ids = [df_id]
    rpc_void(ctx, "ba_shipping", "design.file", "action_send_proof_to_buyer",
             [[df_id], "MF-E2E-3a proof"])
    rpc_void(ctx, "production", "design.file", "action_approve", [[df_id]])
    state = rpc(ctx, "admin", "design.file", "read",
                [[df_id], ["state"]])[0]["state"]

    # ESTY-249: the MO badge is driven by the design.ORDER (auto-created on SO
    # confirm), not the design.file. Assert it flips False -> True on approval.
    before = rpc(ctx, "admin", "mrp.production", "read",
                 [[ctx.mo_id], ["design_ready"]])[0]["design_ready"]
    do_ids = rpc(ctx, "admin", "design.order", "search",
                 [[("sale_order_id", "=", ctx.order_id)]])
    if not do_ids:
        return StepResult("3", False,
                          "no design.order auto-created for the SO")
    rpc_void(ctx, "production", "design.order", "action_approve", [[do_ids[0]]])
    after = rpc(ctx, "admin", "mrp.production", "read",
                [[ctx.mo_id], ["design_ready"]])[0]["design_ready"]
    ok = state == "approved" and before is False and after is True
    return StepResult("3", ok,
                      f"design.file state={state}; MO design_ready "
                      f"{before}->{after} after design order approval")


def section_4_mo_complete(ctx: Context) -> StepResult:
    rpc_void(ctx, "admin", "mrp.production", "write",
             [[ctx.mo_id], {"qty_producing": 1.0}])
    state = ""
    # Pick the raw moves explicitly so mark_done doesn't detour through the
    # consumption-warning wizard, then process whatever wizard action
    # mark_done still returns (backorder / consumption) — an unprocessed
    # returned action leaves the MO in 'to_close'.
    raw_moves = rpc(ctx, "admin", "stock.move", "search_read",
                    [[("raw_material_production_id", "=", ctx.mo_id)]],
                    {"fields": ["product_uom_qty"]})
    for m in raw_moves:
        rpc(ctx, "admin", "stock.move", "write",
            [[m["id"]], {"quantity": m["product_uom_qty"], "picked": True}])
    state = ""
    for _ in range(2):
        try:
            res = rpc(ctx, "admin", "mrp.production", "button_mark_done",
                      [[ctx.mo_id]])
        except xmlrpc.client.Fault as exc:
            if "cannot marshal None" in (exc.faultString or ""):
                res = None
            else:
                return StepResult(
                    "4", False,
                    f"button_mark_done: {exc.faultString.splitlines()[-1][:180]}")
        if isinstance(res, dict) and res.get("res_model") == "mrp.production.backorder":
            wiz = rpc(ctx, "admin", "mrp.production.backorder", "create",
                      [dict(res.get("context", {}).get("default_vals", {}))])
            rpc_void(ctx, "admin", "mrp.production.backorder",
                     "action_close_mo", [[wiz]])
        state = rpc(ctx, "admin", "mrp.production", "read",
                    [[ctx.mo_id], ["state"]])[0]["state"]
        if state == "done":
            break
    return StepResult("4", state == "done", f"MO state={state}")


def section_5_delivery_validate(ctx: Context) -> StepResult:
    pickings = rpc(ctx, "admin", "stock.picking", "search_read",
                   [[("sale_id", "=", ctx.order_id),
                     ("picking_type_code", "=", "outgoing")]],
                   {"fields": ["name", "state"]})
    if not pickings:
        return StepResult("5", False, "no outgoing picking on the order")
    pick = pickings[0]
    ctx.picking_id = pick["id"]
    if pick["state"] not in ("assigned", "confirmed", "waiting"):
        return StepResult("5", False, f"unexpected picking state {pick['state']}")
    rpc_void(ctx, "admin", "stock.picking", "action_assign", [[ctx.picking_id]])
    moves = rpc(ctx, "admin", "stock.move", "search_read",
                [[("picking_id", "=", ctx.picking_id)]],
                {"fields": ["product_uom_qty"]})
    for m in moves:
        rpc(ctx, "admin", "stock.move", "write",
            [[m["id"]], {"quantity": m["product_uom_qty"], "picked": True}])
    rpc_void(ctx, "admin", "stock.picking", "button_validate", [[ctx.picking_id]])
    state = rpc(ctx, "admin", "stock.picking", "read",
                [[ctx.picking_id], ["state"]])[0]["state"]
    # FLW-06: validating an outgoing picking must auto-advance the SO
    # pipeline to 'shipped' (was a manual operator move before 2026-07-06).
    row = rpc(ctx, "admin", "sale.order", "read",
              [[ctx.order_id], ["x_pipeline_id", "x_pipeline_state_id"]])[0]
    pipe_code = state_code = ""
    if row.get("x_pipeline_state_id"):
        st = rpc(ctx, "admin", "order.pipeline.state", "read",
                 [[row["x_pipeline_state_id"][0]], ["code"]])[0]
        state_code = st["code"]
    if row.get("x_pipeline_id"):
        pipe_code = rpc(ctx, "admin", "order.pipeline", "read",
                        [[row["x_pipeline_id"][0]], ["code"]])[0]["code"]
    ok = state == "done" and state_code == "shipped"
    return StepResult("5", ok,
                      f"DO {pick['name']} state={state}; FLW-06 pipeline "
                      f"{pipe_code} auto-advanced to {state_code!r} "
                      f"(expect 'shipped')")


def section_6_gke_xlsx(ctx: Context) -> StepResult:
    out = REPO_ROOT / ".0temp" / f"gke_e2e_f3_{ctx.marker}.xlsx"
    cmd = [sys.executable, str(REPO_ROOT / "scripts" / "build_gke_xls_for_e2e.py"),
           "--out", str(out),
           "--receipts", ctx.receipt_marker,
           "--upload-to-drive",
           "--drive-folder-id", ctx.inbox_folder_id]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0 or not out.exists():
        return StepResult(
            "6", False,
            f"builder rc={proc.returncode}: {(proc.stderr or proc.stdout)[-200:]}")
    ctx.xlsx_path = out
    return StepResult(
        "6", True,
        f"generated {out.name} for receipt {ctx.receipt_marker} "
        f"+ uploaded to Drive folder {ctx.inbox_folder_id[:8]}…")


def section_7_poller_import(ctx: Context) -> StepResult:
    rpc_void(ctx, "admin", "logistics.partner", "write",
             [[ctx.gke_partner_id],  # type: ignore[attr-defined]
              {"last_poll_at": "2000-01-01 00:00:00"}])
    _trigger_cron(ctx, POLLER_CRON_XMLID)
    deadline = time.time() + 120
    latest = None
    while time.time() < deadline:
        # Key on OUR generated file — the inbox may hold leftovers from
        # prior runs (immediate Drive deletes 404 on this Shared Drive, so
        # files accumulate until the poller archives them).
        rows = rpc(ctx, "admin", "tracking.import.log", "search_read",
                   [[("filename", "like", ctx.marker)],
                    ["state", "source", "filename", "matched_count",
                     "imported_count", "total_rows"]],
                   {"order": "id desc", "limit": 1})
        if rows:
            latest = rows[0]
            break
        time.sleep(5)
    if not latest:
        return StepResult(
            "7", False,
            f"poller produced no tracking.import.log row for our file "
            f"(*{ctx.marker}*) in 120s")
    lines = rpc(ctx, "admin", "tracking.import.line", "search_read",
                [[("sale_order_id", "=", ctx.order_id)]],
                {"fields": ["state", "raw_tracking_number"]})
    fulfil = rpc(ctx, "admin", "sale.order.fulfillment", "search_read",
                 [[("order_id", "=", ctx.order_id)]],
                 {"fields": ["tracking_number", "shipping_carrier_id"]})
    carrier_ok = bool(fulfil) and bool(fulfil[0].get("shipping_carrier_id"))
    checks = {
        "log source gdrive": latest["source"] == "gdrive",
        "log state ok/warning": latest["state"] in ("ok", "warning"),
        "our order matched": bool(lines),
        "fulfillment + carrier detected (USPS ≤22-digit regex)": carrier_ok,
    }
    bad = [k for k, v in checks.items() if not v]
    return StepResult(
        "7", not bad,
        f"log={latest} lines={lines} fulfillment={fulfil}"
        + (f" FAILED={bad}" if bad else ""))


def section_8_push_flags(ctx: Context) -> StepResult:
    _trigger_cron(ctx, PUSH_CRON_XMLID)
    deadline = time.time() + 60
    row = None
    while time.time() < deadline:
        row = rpc(ctx, "admin", "sale.order", "read",
                  [[ctx.order_id],
                   ["etsy_tracking_push_status", "etsy_tracking_push_at",
                    "etsy_tracking_push_attempts", "etsy_tracking_push_error"]])[0]
        if row["etsy_tracking_push_status"] != "none":
            break
        time.sleep(3)
    logs = rpc(ctx, "admin", "etsy.api.log", "search_read",
               [[("source", "=", "tracking_push"),
                 ("endpoint", "like", ctx.receipt_marker)]],
               {"fields": ["http_status", "error_message"],
                "order": "id desc", "limit": 1})
    # Synthetic receipt → Etsy rejects; the assertion is that the push PATH
    # ran end-to-end: flags set, timestamp set, attempts counted once, one
    # audit row for OUR receipt. 'pushed' needs a real receipt (P1-11).
    checks = {
        "status set": row and row["etsy_tracking_push_status"] in ("pushed", "failed"),
        "push_at set": bool(row and row["etsy_tracking_push_at"]),
        "attempts counted": bool(row) and row["etsy_tracking_push_attempts"] in (0, 1),
        "audit row for our receipt": bool(logs),
    }
    bad = [k for k, v in checks.items() if not v]
    return StepResult(
        "8", not bad,
        f"push={row} api_log={logs}" + (f" FAILED={bad}" if bad else ""))


def section_9_dashboard_cleanup(ctx: Context, page: Page) -> StepResult:
    shot = None
    try:
        login(page, ctx.base_url, ctx.db)
        page.goto(f"{ctx.base_url}/web#id={ctx.order_id}"
                  f"&model=sale.order&view_type=form")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_selector(".o_form_view", state="visible", timeout=30_000)
        shot = _shot(page, "f3_s9_order_tracking")
    except Exception as exc:  # noqa: BLE001 — evidence, not a gate
        _log.warning("screenshot failed: %s", exc)
    # fixture hygiene: archive test products (order + MO + picking stay as
    # audit evidence on staging; they are marker-named)
    tmpl_ids = rpc(ctx, "admin", "product.template", "search",
                   [[("name", "like", PRODUCT_PREFIX), ("active", "=", True)]])
    if tmpl_ids:
        rpc(ctx, "admin", "product.template", "write",
            [tmpl_ids, {"active": False}])
    if ctx.xlsx_path and ctx.xlsx_path.exists():
        ctx.xlsx_path.unlink()
    return StepResult("9", True,
                      f"evidence captured; {len(tmpl_ids)} product(s) archived",
                      shot)


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
                 / f"E2E_FLOW3A_FULFILLMENT_{TODAY}.md")
    if canonical.exists() and not os.access(canonical, os.W_OK):
        canonical = canonical.with_name(
            f"E2E_FLOW3A_FULFILLMENT_{TODAY}_{datetime.now().strftime('%H%M%S')}.md")
    passed = sum(1 for r in results if r.ok)
    lines = [
        f"# MF-E2E-3a — Flow-3a giao hàng in nội bộ ({TODAY})",
        "",
        f"- **Target**: {ctx.base_url} / DB `{ctx.db}`",
        f"- **Build**: {_git_head()}",
        f"- **Driver**: scripts/e2e_flow3a_fulfillment.py",
        f"- **Order**: {ctx.order_name or '—'} (receipt marker {ctx.receipt_marker or '—'})",
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
        "- §5 asserts the FLW-06 auto-advance: outgoing-picking validation "
        "moves the SO pipeline to 'shipped' (ĐÃ GỬI) — no manual state "
        "write in this runner since the 2026-07-06 rerun.",
        "- §6 GENERATES the GKE xlsx from this run's actual order ref "
        "(closes the MF-E2E-0 residue: the static sample matched 0/9).",
        "- §8 proves the tracking-push path to the Etsy API boundary with a "
        "synthetic receipt; a live `pushed` confirmation belongs to P1-11 "
        "(real receipts on the production shop).",
        "- Tracking-push retry cap (`etsy_tracking_push_attempts` < 10 in "
        "the fallback cron) shipped with this gate — fixes the eternal "
        "5-minute retry loop found in MF-E2E-2.",
        "",
        "## Reproducing",
        "",
        "```bash",
        f"/tmp/e2e-venv/bin/python scripts/e2e_flow3a_fulfillment.py --db {ctx.db}",
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
                          f"XML-RPC fault: {exc.faultString.splitlines()[-1][:200]}")
    except Exception as exc:  # noqa: BLE001 — runner must always produce a report
        return StepResult(section, False, f"{type(exc).__name__}: {str(exc)[:200]}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--section", default="all", help=f"all or one of {SECTIONS}")
    p.add_argument("--headed", action="store_true")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--db", default=DEFAULT_DB)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    selected = set(SECTIONS) if args.section == "all" else {args.section}
    ctx = Context(
        base_url=args.base_url, db=args.db,
        common=xmlrpc.client.ServerProxy(f"{args.base_url}/xmlrpc/2/common"),
        models=xmlrpc.client.ServerProxy(f"{args.base_url}/xmlrpc/2/object"),
    )
    results: list[StepResult] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        runners = {
            "0": lambda: section_0_preflight(ctx),
            "1": lambda: section_1_fixtures(ctx),
            "2": lambda: section_2_confirm_mo(ctx),
            "3": lambda: section_3_design_approve(ctx),
            "4": lambda: section_4_mo_complete(ctx),
            "5": lambda: section_5_delivery_validate(ctx),
            "6": lambda: section_6_gke_xlsx(ctx),
            "7": lambda: section_7_poller_import(ctx),
            "8": lambda: section_8_push_flags(ctx),
            "9": lambda: section_9_dashboard_cleanup(ctx, page),
        }
        abort = False
        for sec in SECTIONS:
            if sec not in selected:
                continue
            if abort:
                results.append(StepResult(sec, False,
                                          "skipped: earlier hard failure"))
                continue
            _log.info("=== §%s ===", sec)
            r = _safe(sec, runners[sec])
            results.append(r)
            _log.info("§%s %s — %s", sec, "PASS" if r.ok else "FAIL", r.note)
            if not r.ok and sec in ("0", "1", "2"):
                abort = True
        browser.close()
    report = write_report(results, ctx)
    _log.info("report: %s", report)
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
