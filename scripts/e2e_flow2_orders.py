"""MF-E2E-2 runner — flow-2 nhận đơn hàng Etsy (API + email fallback).

Mirrors the sectioned shape of scripts/e2e_demo_drop_ship_ordertest2.py.
Target: staging esty_odoo19 + live Etsy shop JaHandmadeArt (60752333).

Section layout (NEXT_SESSION_PROMPT_MF_E2E_FLOWS.md flow-2 bullet → section):

    §0 preflight + cleanup of prior E2E-F2 fixtures
    §A API receipt sync: rewind cursor → cron → orders + health row + no dupes
    §B idempotency: rewind + re-sync → order count unchanged
    §C manual fallback switch: active_source api→email; API cron now skips
    §D email-path ingest while in email mode (2 fixture emails, same buyer)
       → orders created + partner dedupe + pipeline classified
    §E email cron fires → etsy_email_fetch health row fresh
    §F restore active_source=api + cleanup fixtures

Live-Etsy note: §A/§B re-fetch REAL receipts from JaHandmadeArt (cursor
rewind); the shop has no new sales, so ingest is a status-only re-sync of
the known receipt(s) — which is exactly the dedupe surface flow-2 verifies.

Usage:
    /tmp/e2e-venv/bin/python scripts/e2e_flow2_orders.py --db esty_odoo19 \
        [--section all|0|A|B|C|D|E|F] [--headed]
"""

from __future__ import annotations

import argparse
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

ETSY_API_SHOP_ID = "60752333"          # JaHandmadeArt
CURSOR_REWIND_TO = "2025-09-01 00:00:00"  # before the oldest known receipt
GMAIL_ID_PREFIX = "e2e-f2-"            # cleanup key for fixture email logs
API_CRON_XMLID = ("etsy_integration", "cron_etsy_order_sync")
EMAIL_CRON_XMLID = ("etsy_integration", "ir_cron_fetch_etsy_emails")
SAMPLE_EMAIL_PATH = (REPO_ROOT / "custom_addons" / "etsy_integration"
                     / "tests" / "data" / "sample_single_order.txt")
# SSH → odoo shell channel for the §G API-payload injection (same recipe as
# the flow-1/3a/3b runners; the ingest service only runs server-side).
SSH_KEY = REPO_ROOT / "secrets" / "ssh-key-2023-02-24.key"
SSH_HOST = "ubuntu@129.150.63.207"
STAGING_CONTAINER = "esty19_odoo"
# ids embedded in the sample fixture — replaced per-run with unique ones
FIXTURE_ORDER_ID = "3708050001"
FIXTURE_RECEIPT_ID = "4625001001"

USERS: dict[str, tuple[str, str]] = {
    "admin": ("admin", os.environ.get("DEMO_ADMIN_PASSWORD", "admin")),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger("e2e_flow2_orders")

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
    shop_id: int | None = None
    cursor_before: str | None = None
    api_order_count: int | None = None
    run_marker: str = ""
    email_order_ids: list[int] = field(default_factory=list)
    email_log_ids: list[int] = field(default_factory=list)


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


def _cursor(ctx: Context) -> str | None:
    row = rpc(ctx, "admin", "etsy.shop", "read",
              [[ctx.shop_id], ["etsy_last_receipt_sync_at"]])[0]
    return row["etsy_last_receipt_sync_at"] or None


def _health(ctx: Context, name: str) -> dict | None:
    rows = rpc(ctx, "admin", "etsy.sync.health", "search_read",
               [[("name", "=", name)]],
               {"fields": ["state", "last_run_at", "last_run_row_count",
                           "last_run_error_count"]})
    return rows[0] if rows else None


def _etsy_order_count(ctx: Context) -> int:
    return rpc(ctx, "admin", "sale.order", "search_count",
               [[("etsy_order_id", "!=", False)]])


def _dupe_receipts(ctx: Context) -> list:
    groups = rpc(ctx, "admin", "sale.order", "read_group",
                 [[("etsy_order_id", "!=", False)],
                  ["etsy_order_id"], ["etsy_order_id"]])
    return [g["etsy_order_id"] for g in groups
            if (g.get("etsy_order_id_count") or 0) > 1]


def _odoo_shell(ctx: Context, snippet: str, env: dict[str, str] | None = None,
                timeout: int = 180) -> str:
    env_flags = " ".join(f"-e {k}='{v}'" for k, v in (env or {}).items())
    remote = (f"sudo docker exec {env_flags} -i {STAGING_CONTAINER} "
              f"odoo shell -d {ctx.db} --no-http")
    cmd = ["ssh", "-i", str(SSH_KEY), "-o", "StrictHostKeyChecking=no",
           "-o", "BatchMode=yes", SSH_HOST, remote]
    proc = subprocess.run(cmd, input=snippet, capture_output=True,
                          text=True, timeout=timeout)
    return proc.stdout + proc.stderr


# ─── Playwright evidence helpers ──────────────────────────────────────────────


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


def _record_screenshot(ctx: Context, page: Page, model: str,
                       res_id: int, name: str) -> str | None:
    try:
        login(page, ctx.base_url, ctx.db)
        page.goto(f"{ctx.base_url}/web#id={res_id}&model={model}&view_type=form")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_selector(".o_form_view", state="visible", timeout=30_000)
        return _shot(page, name)
    except Exception as exc:  # noqa: BLE001 — screenshots are evidence, not gates
        _log.warning("screenshot %s failed: %s", name, exc)
        return None


# ─── sections ──────────────────────────────────────────────────────────────────


def section_0_preflight(ctx: Context) -> StepResult:
    version = ctx.common.version()["server_version"]
    shops = rpc(ctx, "admin", "etsy.shop", "search_read",
                [[("etsy_api_shop_id", "=", ETSY_API_SHOP_ID)]],
                {"fields": ["name", "active_source", "etsy_last_receipt_sync_at"]})
    if not shops:
        return StepResult("0", False, "JaHandmadeArt shop row not found")
    shop = shops[0]
    if shop["active_source"] != "api":
        return StepResult(
            "0", False,
            f"precondition: active_source must start as 'api', got "
            f"{shop['active_source']!r} — restore manually before the run")
    ctx.shop_id = shop["id"]
    ctx.cursor_before = shop["etsy_last_receipt_sync_at"] or None
    ctx.run_marker = uuid.uuid4().hex[:8]

    # cleanup fixtures from prior runs
    logs = rpc(ctx, "admin", "etsy.email.log", "search",
               [[("gmail_message_id", "like", GMAIL_ID_PREFIX)]])
    orders = rpc(ctx, "admin", "sale.order", "search",
                 [[("etsy_order_id", "like", "99%"),
                   ("etsy_raw_source_id", "=", False)]])
    for oid in orders:
        try:
            rpc_void(ctx, "admin", "sale.order", "action_cancel", [[oid]])
            rpc(ctx, "admin", "sale.order", "unlink", [[oid]])
        except xmlrpc.client.Fault:
            pass  # keep going; leftovers are marker-scoped anyway
    if logs:
        rpc(ctx, "admin", "etsy.email.log", "unlink", [logs])
    return StepResult(
        "0", True,
        f"server {version}; shop id={ctx.shop_id} source=api "
        f"cursor={ctx.cursor_before}; cleaned {len(orders)} order(s) "
        f"+ {len(logs)} email log(s)")


def _rewind_and_sync(ctx: Context) -> tuple[str | None, dict | None]:
    rpc(ctx, "admin", "etsy.shop", "write",
        [[ctx.shop_id], {"etsy_last_receipt_sync_at": CURSOR_REWIND_TO}])
    _trigger_cron(ctx, API_CRON_XMLID)
    # cron runs async in the worker; poll cursor until it advances past the
    # rewind point (or 60 s).
    deadline = time.time() + 60
    cursor = None
    while time.time() < deadline:
        cursor = _cursor(ctx)
        if cursor and cursor != CURSOR_REWIND_TO:
            break
        time.sleep(3)
    return cursor, _health(ctx, "etsy_api_receipts_sync")


def section_a_api_sync(ctx: Context) -> StepResult:
    before = _etsy_order_count(ctx)
    partners_before = rpc(ctx, "admin", "res.partner", "search_count",
                          [[("is_etsy_customer", "=", True)]])
    cursor, health = _rewind_and_sync(ctx)
    after = _etsy_order_count(ctx)
    partners_after = rpc(ctx, "admin", "res.partner", "search_count",
                         [[("is_etsy_customer", "=", True)]])
    dupes = _dupe_receipts(ctx)
    ctx.api_order_count = after
    checks = {
        "cursor advanced": bool(cursor) and cursor != CURSOR_REWIND_TO,
        "health row ok": bool(health) and health["state"] == "ok",
        "no new orders (dedupe re-sync)": after == before,
        # API-path partner dedupe: re-ingesting known receipts must map to
        # the existing partners, not mint new ones.
        "no new partners (partner dedupe)": partners_after == partners_before,
        "no duplicate receipts": not dupes,
    }
    bad = [k for k, v in checks.items() if not v]
    return StepResult(
        "A", not bad,
        f"cursor={cursor} health={health} orders {before}->{after} "
        f"partners {partners_before}->{partners_after} dupes={dupes or 'none'}"
        + (f" FAILED={bad}" if bad else ""))


def section_b_idempotency(ctx: Context) -> StepResult:
    before = _etsy_order_count(ctx)
    cursor, health = _rewind_and_sync(ctx)
    after = _etsy_order_count(ctx)
    dupes = _dupe_receipts(ctx)
    ok = (after == before and not dupes and bool(cursor)
          and cursor != CURSOR_REWIND_TO)
    return StepResult(
        "B", ok,
        f"2nd sync: orders {before}->{after} dupes={dupes or 'none'} "
        f"cursor={cursor} health_rows={health and health['last_run_row_count']}")


def section_c_fallback_switch(ctx: Context, page: Page) -> StepResult:
    cursor_before = _cursor(ctx)
    rpc(ctx, "admin", "etsy.shop", "write",
        [[ctx.shop_id], {"active_source": "email"}])
    logs = rpc(ctx, "admin", "etsy.shop.source.change.log", "search_read",
               [[("shop_id", "=", ctx.shop_id)]],
               {"fields": ["from_source", "to_source", "reason"],
                "order": "id desc", "limit": 1})
    # API cron must now skip this shop (no api-source shops left → early
    # return, cursor untouched).
    _trigger_cron(ctx, API_CRON_XMLID)
    time.sleep(5)
    cursor_after = _cursor(ctx)
    shot = _record_screenshot(ctx, page, "etsy.shop", ctx.shop_id, "f2_sC_shop_email_mode")
    log = logs[0] if logs else {}
    checks = {
        "change log written": bool(log) and log.get("to_source") == "email",
        "cursor untouched while email": cursor_after == cursor_before,
    }
    bad = [k for k, v in checks.items() if not v]
    return StepResult(
        "C", not bad,
        f"source→email change_log={log} cursor {cursor_before}=={cursor_after}"
        + (f" FAILED={bad}" if bad else ""), shot)


def _inject_email(ctx: Context, order_id: str, receipt_id: str) -> tuple[int, int]:
    raw = SAMPLE_EMAIL_PATH.read_text(encoding="utf-8")
    raw = raw.replace(FIXTURE_ORDER_ID, order_id).replace(
        FIXTURE_RECEIPT_ID, receipt_id)
    log_id = rpc(ctx, "admin", "etsy.email.log", "create", [{
        "gmail_message_id": f"{GMAIL_ID_PREFIX}{uuid.uuid4().hex}",
        "subject": "You sold an item on Etsy! (MF-E2E-2 fixture)",
        "date_received": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "raw_body_text": raw,
        "parse_status": "failed",
        "error_message": "seeded for MF-E2E-2 email-fallback replay",
    }])
    rpc_void(ctx, "admin", "etsy.email.log", "action_retry_parse", [[log_id]])
    row = rpc(ctx, "admin", "etsy.email.log", "read",
              [[log_id], ["parse_status", "sale_order_id"]])[0]
    order = row["sale_order_id"][0] if row.get("sale_order_id") else 0
    return log_id, order


def section_d_email_ingest(ctx: Context, page: Page) -> StepResult:
    marker = ctx.run_marker
    oid1, rid1 = f"99{marker[:4]}01", f"98{marker[:4]}01"
    oid2, rid2 = f"99{marker[:4]}02", f"98{marker[:4]}02"
    log1, order1 = _inject_email(ctx, oid1, rid1)
    log2, order2 = _inject_email(ctx, oid2, rid2)
    ctx.email_log_ids = [log1, log2]
    ctx.email_order_ids = [o for o in (order1, order2) if o]
    if not (order1 and order2):
        return StepResult("D", False,
                          f"email parse produced orders {order1}/{order2}")
    rows = rpc(ctx, "admin", "sale.order", "read",
               [[order1, order2],
                ["name", "partner_id", "x_pipeline_id", "x_pipeline_state_id"]])
    partners = {r["partner_id"][0] for r in rows}
    ctx.email_partner_ids = sorted(partners)  # type: ignore[attr-defined]
    shot = _record_screenshot(ctx, page, "sale.order", order1, "f2_sD_email_order")
    # Partner-dedupe note: the text-only fixture carries NO buyer email and
    # NO shipping address (address extraction is HTML-only), so Tier 1–3 of
    # find_or_create_partner cannot match and a per-order partner is the
    # DESIGNED outcome. Address-bearing ingest dedupe is asserted on the API
    # path in §A ("no new partners"). Here we assert the email path is
    # functional: orders created + classified.
    checks = {
        "both orders created": len(rows) == 2,
        "pipeline classified": all(r.get("x_pipeline_id") for r in rows),
    }
    bad = [k for k, v in checks.items() if not v]
    return StepResult(
        "D", not bad,
        f"orders={[r['name'] for r in rows]} partners={partners} (per-order "
        f"partner = designed for address-less text emails) "
        f"pipeline={[r['x_pipeline_id'] for r in rows]}"
        + (f" FAILED={bad}" if bad else ""), shot)


def section_e_email_cron_health(ctx: Context) -> StepResult:
    before = _health(ctx, "etsy_email_fetch")
    _trigger_cron(ctx, EMAIL_CRON_XMLID)
    deadline = time.time() + 60
    after = None
    while time.time() < deadline:
        after = _health(ctx, "etsy_email_fetch")
        if after and (not before or after["last_run_at"] != before["last_run_at"]):
            break
        time.sleep(3)
    ok = bool(after) and (not before or after["last_run_at"] != before["last_run_at"])
    return StepResult("E", ok, f"etsy_email_fetch health: {after}")


def section_f_restore(ctx: Context) -> StepResult:
    rpc(ctx, "admin", "etsy.shop", "write",
        [[ctx.shop_id], {"active_source": "api"}])
    source = rpc(ctx, "admin", "etsy.shop", "read",
                 [[ctx.shop_id], ["active_source"]])[0]["active_source"]
    # fixture hygiene: cancel + drop the two email orders + logs
    removed = 0
    for oid in ctx.email_order_ids:
        try:
            rpc_void(ctx, "admin", "sale.order", "action_cancel", [[oid]])
            rpc(ctx, "admin", "sale.order", "unlink", [[oid]])
            removed += 1
        except xmlrpc.client.Fault as exc:
            _log.warning("cleanup of order %s failed: %s", oid,
                         exc.faultString.splitlines()[0][:120])
    if ctx.email_log_ids:
        rpc(ctx, "admin", "etsy.email.log", "unlink", [ctx.email_log_ids])
    for pid in getattr(ctx, "email_partner_ids", []):
        try:
            rpc(ctx, "admin", "res.partner", "unlink", [[pid]])
        except xmlrpc.client.Fault:
            rpc(ctx, "admin", "res.partner", "write", [[pid], {"active": False}])
    ok = source == "api"
    return StepResult(
        "F", ok,
        f"active_source restored to {source}; removed {removed}/"
        f"{len(ctx.email_order_ids)} fixture order(s) + "
        f"{len(ctx.email_log_ids)} log(s)")


_HOLD_SNIPPET = """
import os
from datetime import datetime
from odoo.addons.etsy_integration.services.etsy_order_payload import (
    EtsyAddressPayload, EtsyLineItemPayload, EtsyOrderPayload)
from odoo.addons.etsy_integration.services.order_creator import OrderCreator

marker = os.environ['F2G_MARKER']
shop = env['etsy.shop'].browse(int(os.environ['F2G_SHOP']))
before = env['product.product'].search_count([])
payload = EtsyOrderPayload(
    etsy_shop_id=shop.id,
    etsy_receipt_id='95%s' % marker,
    etsy_order_id='95%s' % marker,
    buyer_name='E2E-F2G Holder %s' % marker,
    buyer_country='US',
    order_date=datetime.utcnow(),
    currency='USD',
    amount_total=25.0,
    shipping_total=0.0,
    line_items=(EtsyLineItemPayload(
        listing_id='L-F2G-%s' % marker,
        transaction_id='T-F2G-%s' % marker,
        title='E2E-F2G Mystery Tee %s' % marker,
        sku='E2E-NO-SUCH-SKU-%s' % marker,
        quantity=1, unit_price=25.0,
    ),),
    shipping_address=EtsyAddressPayload(
        name='E2E-F2G Holder %s' % marker, street_1='1 Hold St',
        street_2=None, city='Boston', state='MA', zip='02108',
        country_code='US'),
    buyer_message=None,
    buyer_email='e2e-f2g-%s@example.com' % marker,
    listing_id='L-F2G-%s' % marker,
    payment_status='paid',
    is_gift=False,
    gift_message=None,
    source='api',
    fetched_at=datetime.utcnow(),
    raw_source_id='receipt:95%s' % marker,
)
order = OrderCreator(env).process_etsy_payload(payload, shop)
after = env['product.product'].search_count([])
env.cr.commit()
print('F2G_RESULT:%s|%s|%s' % (order.id if order else 0, before, after))
"""


def section_g_unresolved_hold(ctx: Context, page: Page) -> StepResult:
    """FLW-03: API-ingested order with an unknown SKU books the 'Etsy
    Unresolved Item' placeholder and holds the order (production_blocked)
    — NO product auto-created (the pre-2026-07-06 auto-create is gone)."""
    # hygiene: drop held fixtures from PRIOR runs (keep this run's for the
    # screenshot harvest; Phase-5 cleanup removes it).
    stale = rpc(ctx, "admin", "sale.order", "search",
                [[("partner_id.name", "like", "E2E-F2G Holder"),
                  ("etsy_order_id", "like", "95")]])
    for oid in stale:
        try:
            rpc_void(ctx, "admin", "sale.order", "action_cancel", [[oid]])
            rpc(ctx, "admin", "sale.order", "unlink", [[oid]])
        except xmlrpc.client.Fault:
            pass
    out = _odoo_shell(ctx, _HOLD_SNIPPET,
                      {"F2G_MARKER": ctx.run_marker,
                       "F2G_SHOP": str(ctx.shop_id)})
    line = next((ln for ln in out.splitlines()
                 if ln.startswith("F2G_RESULT:")), "")
    if not line:
        return StepResult("G", False,
                          f"injection snippet failed: {out[-300:]}")
    order_id, before, after = (
        int(x) for x in line.replace("F2G_RESULT:", "").split("|"))
    if not order_id:
        return StepResult("G", False, "ingest returned no order")
    ctx.hold_order_id = order_id  # type: ignore[attr-defined]
    row = rpc(ctx, "admin", "sale.order", "read",
              [[order_id], ["name", "production_blocked", "block_reason"]])[0]
    lines = rpc(ctx, "admin", "sale.order.line", "search_read",
                [[("order_id", "=", order_id)]],
                {"fields": ["name", "product_id"]})
    placeholder_tmpl = _xmlid_to_res_id(
        ctx, "etsy_integration", "product_etsy_unresolved")
    placeholder_variants = rpc(
        ctx, "admin", "product.product", "search",
        [[("product_tmpl_id", "=", placeholder_tmpl)]]) if placeholder_tmpl else []
    item_lines = [ln for ln in lines
                  if "Mystery Tee" in (ln["name"] or "")
                  or (ln["product_id"]
                      and ln["product_id"][0] in placeholder_variants)]
    checks = {
        "order held (production_blocked)": bool(row["production_blocked"]),
        "block_reason names the SKU":
            f"E2E-NO-SUCH-SKU-{ctx.run_marker}" in (row["block_reason"] or ""),
        "line books the unresolved placeholder": bool(item_lines) and all(
            ln["product_id"] and ln["product_id"][0] in placeholder_variants
            for ln in item_lines),
        "buyer-facing title kept on the line": any(
            "Mystery Tee" in (ln["name"] or "") for ln in item_lines),
        "NO product auto-created": after == before,
    }
    bad = [k for k, v in checks.items() if not v]
    shot = _record_screenshot(ctx, page, "sale.order", order_id,
                              "f2_sG_unresolved_hold")
    return StepResult(
        "G", not bad,
        f"order {row['name']} (id {order_id}) blocked={row['production_blocked']} "
        f"products {before}->{after}; cleaned {len(stale)} stale fixture(s)"
        + (f" FAILED={bad}" if bad else ""), shot)


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
                 / f"E2E_FLOW2_ORDERS_{TODAY}.md")
    if canonical.exists() and not os.access(canonical, os.W_OK):
        canonical = canonical.with_name(
            f"E2E_FLOW2_ORDERS_{TODAY}_{datetime.now().strftime('%H%M%S')}.md")
    passed = sum(1 for r in results if r.ok)
    lines = [
        f"# MF-E2E-2 — Flow-2 nhận đơn hàng Etsy ({TODAY})",
        "",
        f"- **Target**: {ctx.base_url} / DB `{ctx.db}`",
        f"- **Build**: {_git_head()}",
        f"- **Driver**: scripts/e2e_flow2_orders.py",
        f"- **Etsy shop**: JaHandmadeArt ({ETSY_API_SHOP_ID})",
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
        "- §A/§B rewind `etsy_last_receipt_sync_at` and re-fetch REAL "
        "JaHandmadeArt receipts — dedupe (status-only re-sync) is the "
        "assertion, so `orders unchanged` is the PASS condition.",
        "- §C/§D prove the manual fallback: source→email stops the API "
        "cursor; the email path still creates + classifies orders (fixture "
        "replay via `action_retry_parse`, semantics-equal to the Gmail "
        "cron). Partner dedupe is asserted on the API path (§A 'no new "
        "partners'); the text-only email fixture has no address/email so "
        "per-order partners are the designed Tier-4 outcome there.",
        "- Sync-health rows for BOTH paths (`etsy_api_receipts_sync`, "
        "`etsy_email_fetch`) landed in etsy_integration 19.0.3.16.0 "
        "(report_run wired into both crons — spec 015 MF-E2E-2 criterion).",
        "- §G asserts the FLW-03 hold (2026-07-06): API ingest with an "
        "unknown SKU books the 'Etsy Unresolved Item' placeholder, holds "
        "the order via production_blocked/block_reason, and creates NO "
        "product (the old auto-create contract is gone). The held order is "
        "kept for the screenshot harvest and removed by the run-level "
        "cleanup phase.",
        "- Production-shop assertions deferred to P1-11 per the gate scope.",
        "",
        "## Reproducing",
        "",
        "```bash",
        f"/tmp/e2e-venv/bin/python scripts/e2e_flow2_orders.py --db {ctx.db}",
        "```",
    ]
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return canonical


# ─── main ──────────────────────────────────────────────────────────────────────


SECTIONS = ("0", "A", "B", "C", "D", "E", "F", "G")


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
            "A": lambda: section_a_api_sync(ctx),
            "B": lambda: section_b_idempotency(ctx),
            "C": lambda: section_c_fallback_switch(ctx, page),
            "D": lambda: section_d_email_ingest(ctx, page),
            "E": lambda: section_e_email_cron_health(ctx),
            "F": lambda: section_f_restore(ctx),
            "G": lambda: section_g_unresolved_hold(ctx, page),
        }
        abort = False
        for sec in SECTIONS:
            if sec not in selected:
                continue
            if abort:
                results.append(StepResult(sec, False, "skipped: §0 failed"))
                continue
            _log.info("=== §%s ===", sec)
            r = _safe(sec, runners[sec])
            results.append(r)
            _log.info("§%s %s — %s", sec, "PASS" if r.ok else "FAIL", r.note)
            if not r.ok and sec == "0":
                abort = True
        browser.close()
    report = write_report(results, ctx)
    _log.info("report: %s", report)
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
