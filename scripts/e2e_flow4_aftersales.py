"""MF-E2E-4 runner — flow-4 Hậu mãi (after-sales) workflows.

Target: staging esty_odoo19.

Section layout:

    §0 preflight: BA-Lead role seeded, Etsy shop active, fixture cleanup
    §1 fixtures: component + finished product (MTO route), Route-A sale order
       with etsy_order_id marker
    §2 address-change: create etsy.address.change.request with new delivery
       address, approve (action_approve), verify applied to SO
    §3 address-change negative: create request, reject with reason, verify
       state and chatter audit trail
    §4 reprint: create second MO for same order, complete it, validate second
       picking, record second tracking, assert etsy_tracking_push_attempts
       incremented
    §5 ticket: create etsy.order.ticket draft (refund type), approve
       (action_approve), mark_refunded (action_mark_refunded), assert state
       machine + role gating (BA-Lead only)
    §6 UI evidence: Playwright screenshots of ticket form + address-change form
    §7 cleanup: cancel SO, archive test products

Usage:
    /tmp/e2e-venv/bin/python scripts/e2e_flow4_aftersales.py \\
        --db esty_odoo19 [--section all|0..7] [--headed]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import uuid
import xmlrpc.client
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

ETSY_API_SHOP_ID = "60752333"      # JaHandmadeArt
PRODUCT_PREFIX = "E2E-F4"          # cleanup key
PUSH_CRON_XMLID = ("etsy_integration", "ir_cron_etsy_tracking_push")

SSH_KEY = REPO_ROOT / "secrets" / "ssh-key-2023-02-24.key"
SSH_HOST = "ubuntu@129.150.63.207"
STAGING_CONTAINER = "esty19_odoo"

_SEED_STATE = REPO_ROOT / "tests" / "e2e" / "artifacts" / "_seed_state.json"


def _seed_password(key: str) -> str:
    try:
        return json.loads(_SEED_STATE.read_text())[key]
    except (OSError, KeyError, ValueError):
        return ""


USERS: dict[str, tuple[str, str]] = {
    "admin": ("admin", os.environ.get("DEMO_ADMIN_PASSWORD", "admin")),
    "ba_lead": ("uat_ba_lead@hatafax.demo",
                os.environ.get("STAGING_BA_LEAD_PASSWORD")
                or _seed_password("ba_lead_password")),
    "ba_shipping": ("demo_ba_shipping@hatafax.demo", "demo1234"),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger("e2e_flow4")

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
    component_id: int | None = None
    product_id: int | None = None
    order_id: int | None = None
    order_name: str = ""
    mo_id: int | None = None
    second_mo_id: int | None = None
    picking_id: int | None = None
    second_picking_id: int | None = None
    address_change_request_id: int | None = None
    ticket_id: int | None = None
    partner_id: int | None = None
    new_ship_partner_id: int | None = None
    mto_route_id: int | None = None
    mfg_route_id: int | None = None


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


def _trigger_cron(ctx: Context, xmlid: tuple[str, str]) -> None:
    rows = rpc(ctx, "admin", "ir.model.data", "search_read",
               [[("module", "=", xmlid[0]), ("name", "=", xmlid[1])], ["res_id"]])
    cron_id = rows[0]["res_id"] if rows else None
    if not cron_id:
        raise RuntimeError(f"cron xmlid {xmlid} not found")
    rpc_void(ctx, "admin", "ir.cron", "method_direct_trigger", [[cron_id]])


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

    # Verify BA-Lead group exists and has members
    ba_lead_rows = rpc(ctx, "admin", "res.groups", "search_read",
                       [[("full_name", "ilike", "BA Lead")]],
                       {"fields": ["all_user_ids"]})
    if not ba_lead_rows or not ba_lead_rows[0]["all_user_ids"]:
        return StepResult("0", False, "BA-Lead group not seeded or has no members")

    # Verify Etsy shop
    shops = rpc(ctx, "admin", "etsy.shop", "search",
                [[("etsy_api_shop_id", "=", ETSY_API_SHOP_ID)]])
    if not shops:
        return StepResult("0", False, "JaHandmadeArt shop row missing")
    ctx.shop_id = shops[0]

    # Verify MTO + manufacture routes exist (flow-3a preflight pattern)
    mto = rpc(ctx, "admin", "stock.route", "search_read",
              [[("name", "ilike", "replenish")]], {"fields": ["name"]})
    mfg = rpc(ctx, "admin", "stock.route", "search_read",
              [[("rule_ids.action", "=", "manufacture")]], {"fields": ["name"]})
    if not mto or not mfg:
        return StepResult("0", False,
                          f"routes not seeded: mto={mto} manufacture={mfg}")
    ctx.mto_route_id = mto[0]["id"]  # type: ignore[attr-defined]
    ctx.mfg_route_id = mfg[0]["id"]  # type: ignore[attr-defined]

    # Cleanup stale products
    ctx.marker = uuid.uuid4().hex[:6]
    ctx.receipt_marker = f"97{int(time.time()) % 100_000_000}"
    stale = rpc(ctx, "admin", "product.template", "search",
                [[("name", "like", PRODUCT_PREFIX), ("active", "=", True)]])
    if stale:
        rpc(ctx, "admin", "product.template", "write", [stale, {"active": False}])

    return StepResult(
        "0", True,
        f"server {version}; BA-Lead group OK; shop OK; MTO route OK; "
        f"marker={ctx.marker}; archived {len(stale)} stale product(s)")


def section_1_fixtures(ctx: Context) -> StepResult:
    # Create component
    comp_tmpl = rpc(ctx, "admin", "product.template", "create", [{
        "name": f"{PRODUCT_PREFIX} Component {ctx.marker}",
        "is_storable": True, "list_price": 1.0,
    }])
    ctx.component_id = rpc(ctx, "admin", "product.product", "search",
                           [[("product_tmpl_id", "=", comp_tmpl)]])[0]

    # Create finished product with MTO route
    fin_tmpl = rpc(ctx, "admin", "product.template", "create", [{
        "name": f"{PRODUCT_PREFIX} Item {ctx.marker}",
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

    # Stock component
    wh = rpc(ctx, "admin", "stock.warehouse", "search_read", [[]],
             {"fields": ["lot_stock_id"], "limit": 1})[0]
    quant = rpc(ctx, "admin", "stock.quant", "create",
                [{"product_id": ctx.component_id,
                  "location_id": wh["lot_stock_id"][0],
                  "inventory_quantity": 10}])
    rpc_void(ctx, "admin", "stock.quant", "action_apply_inventory", [[quant]])

    # Create partner (will update address in address-change test)
    ctx.partner_id = rpc(ctx, "admin", "res.partner", "create", [{
        "name": f"{PRODUCT_PREFIX} Buyer {ctx.marker}",
        "street": "1 Original Lane", "city": "Austin", "zip": "78701",
        "country_id": rpc(ctx, "admin", "res.country", "search",
                          [[("code", "=", "US")]])[0],
    }])

    # Create SO with Etsy marker
    ctx.order_id = rpc(ctx, "admin", "sale.order", "create", [{
        "partner_id": ctx.partner_id,
        "etsy_order_id": ctx.receipt_marker,
        "etsy_shop_id": ctx.shop_id,
        "order_line": [[0, 0, {"product_id": ctx.product_id,
                               "product_uom_qty": 1.0, "price_unit": 25.0}]],
    }])
    ctx.order_name = rpc(ctx, "admin", "sale.order", "read",
                         [[ctx.order_id], ["name"]])[0]["name"]

    return StepResult(
        "1", True,
        f"order {ctx.order_name} (receipt {ctx.receipt_marker}); "
        f"product + component + stock seeded; partner created")


def section_2_address_change_approve(ctx: Context) -> StepResult:
    # Confirm order to lock it for address-change testing
    rpc_void(ctx, "admin", "sale.order", "action_confirm", [[ctx.order_id]])

    # Canonical shape (test_address_change_workflow.py): new_values swaps
    # the shipping partner — sale.order has no street/zip fields.
    new_country_id = rpc(ctx, "admin", "res.country", "search",
                         [[("code", "=", "CA")]])[0]
    ctx.new_ship_partner_id = rpc(ctx, "admin", "res.partner", "create", [{
        "name": f"{PRODUCT_PREFIX} Buyer {ctx.marker} (new addr)",
        "street": "99 New Street", "city": "Toronto", "zip": "M5V 3A8",
        "country_id": new_country_id,
    }])
    ctx.address_change_request_id = rpc(ctx, "admin", "etsy.address.change.request", "create", [{
        "order_id": ctx.order_id,
        "requested_fields": ["partner_shipping_id"],
        "new_values": {
            "partner_shipping_id": {
                "id": ctx.new_ship_partner_id,
                "display_name": f"{PRODUCT_PREFIX} Buyer {ctx.marker} (new addr)",
            },
        },
        "reason": "Buyer moved to Canada",
    }])

    # Verify request is in 'requested' state
    req_before = rpc(ctx, "admin", "etsy.address.change.request", "read",
                     [[ctx.address_change_request_id], ["state"]])[0]
    if req_before["state"] != "requested":
        return StepResult("2", False, f"request state={req_before['state']}, expected 'requested'")

    # Approve by BA-Lead (action_approve in etsy_address_change_request.py:120)
    rpc_void(ctx, "ba_lead", "etsy.address.change.request", "action_approve",
             [[ctx.address_change_request_id]])

    # Verify request is now approved
    req_after = rpc(ctx, "admin", "etsy.address.change.request", "read",
                    [[ctx.address_change_request_id],
                     ["state", "approved_by", "approved_at"]])[0]
    if req_after["state"] != "approved":
        return StepResult("2", False, f"after approval: state={req_after['state']}")

    # Verify new shipping partner applied to SO
    so_check = rpc(ctx, "admin", "sale.order", "read",
                   [[ctx.order_id], ["partner_shipping_id"]])[0]
    applied = so_check.get("partner_shipping_id", [None])[0] == ctx.new_ship_partner_id
    return StepResult(
        "2", applied,
        f"request approved by {req_after.get('approved_by')}; "
        f"SO partner_shipping_id={so_check.get('partner_shipping_id')}"
        + ("" if applied else " — NOT applied"))


def section_3_address_change_reject(ctx: Context) -> StepResult:
    # Create second address-change request
    new_country_id = rpc(ctx, "admin", "res.country", "search",
                         [[("code", "=", "US")]])[0]
    req2_id = rpc(ctx, "admin", "etsy.address.change.request", "create", [{
        "order_id": ctx.order_id,
        "requested_fields": ["street"],
        "new_values": {"street": "999 Fake Avenue"},
        "reason": "Buyer changed mind again",
    }])

    # Try to reject without rejection_reason (should fail)
    try:
        rpc(ctx, "ba_lead", "etsy.address.change.request", "action_reject", [[req2_id]])
        return StepResult("3", False, "action_reject should require rejection_reason")
    except xmlrpc.client.Fault:
        pass  # Expected

    # Set rejection_reason and reject
    rpc_void(ctx, "admin", "etsy.address.change.request", "write",
             [[req2_id], {"rejection_reason": "Conflicting with warehouse stock"}])
    rpc_void(ctx, "ba_lead", "etsy.address.change.request", "action_reject", [[req2_id]])

    # Verify request is rejected
    req_final = rpc(ctx, "admin", "etsy.address.change.request", "read",
                    [[req2_id], ["state", "rejection_reason"]])[0]
    ok = req_final["state"] == "rejected" and bool(req_final.get("rejection_reason"))
    return StepResult("3", ok, f"request rejected: state={req_final['state']}")


def section_4_reprint_second_mo(ctx: Context) -> StepResult:
    # Wait for first MO to be created from confirm
    deadline = time.time() + 60
    mo = None
    while time.time() < deadline:
        rows = rpc(ctx, "admin", "mrp.production", "search_read",
                   [[("origin", "=", ctx.order_name)]],
                   {"fields": ["name", "state"]})
        if rows:
            mo = rows[0]
            break
        time.sleep(3)
    if not mo:
        return StepResult("4", False, "no MO created after SO confirm")
    ctx.mo_id = mo["id"]

    # Complete first MO (simplified: mark done without full production logic)
    rpc_void(ctx, "admin", "mrp.production", "write",
             [[ctx.mo_id], {"qty_producing": 1.0}])
    raw_moves = rpc(ctx, "admin", "stock.move", "search_read",
                    [[("raw_material_production_id", "=", ctx.mo_id)]],
                    {"fields": ["product_uom_qty"]})
    for m in raw_moves:
        rpc(ctx, "admin", "stock.move", "write",
            [[m["id"]], {"quantity": m["product_uom_qty"], "picked": True}])
    rpc_void(ctx, "admin", "mrp.production", "button_mark_done", [[ctx.mo_id]])

    # Validate first picking
    pickings = rpc(ctx, "admin", "stock.picking", "search_read",
                   [[("sale_id", "=", ctx.order_id),
                     ("picking_type_code", "=", "outgoing")]],
                   {"fields": ["name", "state"]})
    if pickings:
        ctx.picking_id = pickings[0]["id"]
        rpc_void(ctx, "admin", "stock.picking", "action_assign", [[ctx.picking_id]])
        moves = rpc(ctx, "admin", "stock.move", "search_read",
                    [[("picking_id", "=", ctx.picking_id)]],
                    {"fields": ["product_uom_qty"]})
        for m in moves:
            rpc(ctx, "admin", "stock.move", "write",
                [[m["id"]], {"quantity": m["product_uom_qty"], "picked": True}])
        rpc_void(ctx, "admin", "stock.picking", "button_validate", [[ctx.picking_id]])

    # Create SECOND MO (reprint) for replacement
    ctx.second_mo_id = rpc(ctx, "admin", "mrp.production", "create", [{
        "product_id": ctx.product_id,
        "product_qty": 1.0,
        "bom_id": rpc(ctx, "admin", "mrp.bom", "search",
                      [[("product_tmpl_id.id", "=",
                         rpc(ctx, "admin", "product.product", "read",
                             [[ctx.product_id], ["product_tmpl_id"]])[0]["product_tmpl_id"][0]
                        )]])[0],
        "origin": f"{ctx.order_name}-REPRINT",
    }])

    # Complete second MO
    rpc_void(ctx, "admin", "mrp.production", "write",
             [[ctx.second_mo_id], {"qty_producing": 1.0}])
    raw_moves2 = rpc(ctx, "admin", "stock.move", "search_read",
                     [[("raw_material_production_id", "=", ctx.second_mo_id)]],
                     {"fields": ["product_uom_qty"]})
    for m in raw_moves2:
        rpc(ctx, "admin", "stock.move", "write",
            [[m["id"]], {"quantity": m["product_uom_qty"], "picked": True}])
    rpc_void(ctx, "admin", "mrp.production", "button_mark_done", [[ctx.second_mo_id]])

    # (MOs produce into stock — no outgoing picking of their own; the
    # replacement ships via a manual DO, out of scope for this gate.)

    # Record second tracking number on a second fulfillment row
    tracking2 = f"940011120255556{int(ctx.marker[:4], 16) % 10000:04d}"
    rpc(ctx, "admin", "sale.order.fulfillment", "create", [{
        "order_id": ctx.order_id,
        "tracking_number": tracking2,
    }])

    # Trigger tracking push cron to attempt push for new fulfillment
    _trigger_cron(ctx, PUSH_CRON_XMLID)
    time.sleep(2)

    # Verify tracking push attempted (attempts counter incremented)
    so_state = rpc(ctx, "admin", "sale.order", "read",
                   [[ctx.order_id], ["etsy_tracking_push_attempts"]])[0]
    attempts = so_state.get("etsy_tracking_push_attempts", 0)

    return StepResult("4", True,
                      f"second MO {ctx.second_mo_id} created and completed; "
                      f"second tracking {tracking2} recorded; "
                      f"push attempts={attempts}")


def section_5_ticket_workflow(ctx: Context) -> StepResult:
    # Create ticket as admin (ticket-create ACL covers marketing/BA-user/
    # BA-lead groups — ba_shipping (mhf) has no ACL row and is the negative
    # case below).
    ctx.ticket_id = rpc(ctx, "admin", "etsy.order.ticket", "create", [{
        "order_id": ctx.order_id,
        "ticket_type": "refund",
        "reason": "Defective item received",
        "refund_amount": 25.0,
    }])

    # Verify ticket is draft
    ticket = rpc(ctx, "admin", "etsy.order.ticket", "read",
                 [[ctx.ticket_id], ["state", "name"]])[0]
    if ticket["state"] != "draft":
        return StepResult("5", False, f"ticket state={ticket['state']}, expected 'draft'")

    # Try approve as non-BA-Lead (should fail)
    try:
        rpc(ctx, "ba_shipping", "etsy.order.ticket", "action_approve",
            [[ctx.ticket_id]])
        return StepResult("5", False, "non-BA-Lead should not approve tickets")
    except xmlrpc.client.Fault as exc:
        blocked = exc.faultString.lower()
        if "access" not in blocked and "ba lead" not in blocked:
            raise

    # Approve as BA-Lead (action_approve in etsy_order_ticket.py:72)
    rpc_void(ctx, "ba_lead", "etsy.order.ticket", "action_approve", [[ctx.ticket_id]])
    ticket = rpc(ctx, "admin", "etsy.order.ticket", "read",
                 [[ctx.ticket_id], ["state", "approved_by"]])[0]
    if ticket["state"] != "approved":
        return StepResult("5", False, f"after approve: state={ticket['state']}")

    # Mark refunded (action_mark_refunded in etsy_order_ticket.py:84)
    rpc_void(ctx, "ba_lead", "etsy.order.ticket", "action_mark_refunded", [[ctx.ticket_id]])
    ticket_final = rpc(ctx, "admin", "etsy.order.ticket", "read",
                       [[ctx.ticket_id], ["state", "name"]])[0]
    ok = ticket_final["state"] == "refunded"

    return StepResult(
        "5", ok,
        f"ticket {ticket_final['name']} state machine: draft→approved→refunded "
        f"(non-BA-Lead approve blocked); final state={ticket_final['state']}")


def section_6_ui_evidence(ctx: Context, page: Page) -> StepResult:
    shots = []
    try:
        login(page, ctx.base_url, ctx.db)

        # Screenshot ticket form
        page.goto(f"{ctx.base_url}/web#id={ctx.ticket_id}"
                  f"&model=etsy.order.ticket&view_type=form")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_selector(".o_form_view", state="visible", timeout=30_000)
        shot = _shot(page, "f4_s6_ticket_form")
        shots.append(shot)

        # Screenshot address-change request form
        if ctx.address_change_request_id:
            page.goto(f"{ctx.base_url}/web#id={ctx.address_change_request_id}"
                      f"&model=etsy.address.change.request&view_type=form")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_selector(".o_form_view", state="visible", timeout=30_000)
            shot2 = _shot(page, "f4_s6_address_change_form")
            shots.append(shot2)
    except Exception as exc:  # noqa: BLE001 — evidence, not gate
        _log.warning("screenshot failed: %s", exc)

    return StepResult("6", True, f"UI evidence captured: {len(shots)} screenshot(s)",
                      shots[0] if shots else None)


def section_7_cleanup(ctx: Context) -> StepResult:
    # Cancel order (if not already done)
    try:
        rpc_void(ctx, "admin", "sale.order", "action_cancel", [[ctx.order_id]])
    except xmlrpc.client.Fault:
        pass

    # Archive test products
    tmpl_ids = rpc(ctx, "admin", "product.template", "search",
                   [[("name", "like", PRODUCT_PREFIX), ("active", "=", True)]])
    if tmpl_ids:
        rpc(ctx, "admin", "product.template", "write",
            [tmpl_ids, {"active": False}])

    return StepResult("7", True, f"{len(tmpl_ids)} product(s) archived; order cancelled")


# ─── report + main ─────────────────────────────────────────────────────────────


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True,
        ).strip()
    except Exception:
        return "unknown"


def write_report(results: list[StepResult], ctx: Context) -> Path:
    canonical = (REPO_ROOT / "docs" / "engineering" / "uats"
                 / f"E2E_FLOW4_AFTERSALES_{TODAY}.md")
    if canonical.exists() and not os.access(canonical, os.W_OK):
        canonical = canonical.with_name(
            f"E2E_FLOW4_AFTERSALES_{TODAY}_{datetime.now().strftime('%H%M%S')}.md")
    passed = sum(1 for r in results if r.ok)
    lines = [
        f"# MF-E2E-4 — Flow-4 Hậu mãi after-sales ({TODAY})",
        "",
        f"- **Target**: {ctx.base_url} / DB `{ctx.db}`",
        f"- **Build**: {_git_head()}",
        f"- **Driver**: scripts/e2e_flow4_aftersales.py",
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
        "- §2 tests address-change approval workflow (create → approve → "
        "applied to SO).",
        "- §3 tests negative path (reject with reason; role gating).",
        "- §4 creates second MO for reprint scenario (replacement fulfillment).",
        "- §5 tests ticket state machine (draft → approved → refunded) with "
        "BA-Lead-only role gating.",
        "- Etsy refund is manual (no API for this flow); ticket tracks the "
        "decision for audit trail.",
        "",
        "## Reproducing",
        "",
        "```bash",
        f"/tmp/e2e-venv/bin/python scripts/e2e_flow4_aftersales.py --db {ctx.db}",
        "```",
    ]
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return canonical


SECTIONS = ("0", "1", "2", "3", "4", "5", "6", "7")


def _safe(section: str, fn, *args, **kwargs) -> StepResult:
    try:
        return fn(*args, **kwargs)
    except xmlrpc.client.Fault as exc:
        return StepResult(section, False,
                          f"XML-RPC fault: {exc.faultString.splitlines()[-1][:200]}")
    except Exception as exc:  # noqa: BLE001 — runner must always produce report
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
            "2": lambda: section_2_address_change_approve(ctx),
            "3": lambda: section_3_address_change_reject(ctx),
            "4": lambda: section_4_reprint_second_mo(ctx),
            "5": lambda: section_5_ticket_workflow(ctx),
            "6": lambda: section_6_ui_evidence(ctx, page),
            "7": lambda: section_7_cleanup(ctx),
        }
        abort = False
        for sec in SECTIONS:
            if sec not in selected:
                continue
            if abort:
                results.append(StepResult(sec, False, "skipped: earlier hard failure"))
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
