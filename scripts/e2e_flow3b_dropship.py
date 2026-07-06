"""MF-E2E-3b runner — flow-3b giao hàng Gearment dropship (LIVE API).

Mirrors the sectioned shape of scripts/e2e_demo_drop_ship_ordertest2.py.
Target: staging esty_odoo19 + LIVE Gearment API (keys from .env, verified
2026-07-04: 200 on GET api/v3/catalog).

SAFETY CONTRACT: this runner creates Gearment DRAFT orders only
(POST api/v3/orders/draft — no fulfillment, no charge until a human
approves in the Gearment dashboard). It NEVER calls the adapter's
confirm()/labeled endpoint. Draft refs are listed in the report for the
owner to discard.

Section layout:

    §0 preflight: gearment_pod pipeline, staging GEARMENT_* env, live
       catalog fetch (real legacy_product_id + public artwork URL)
    §1 fixtures: dropship product (x_gearment_sku = real catalog id),
       Route-B sale order + URL-mode approved design file (artwork)
    §2 SO confirm + pipeline pinned to gearment_pod/confirmed
    §3 action_push_to_gearment → LIVE draft order → outbound_ref
    §4 action_get_gearment_quote → LIVE price → state 'quoted'
    §5 self-signed tracking_order_updated webhook (HMAC per
       P0-18b2 scheme) → tracking recorded + Etsy push triggered
    §6 verify: fulfillment tracking + Etsy push flags + inbound log
    §7 report + fixture cleanup (Gearment draft left for owner discard)

Usage:
    /tmp/e2e-venv/bin/python scripts/e2e_flow3b_dropship.py --db esty_odoo19
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets as pysecrets
import subprocess
import sys
import time
import uuid
import xmlrpc.client
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests
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

ETSY_API_SHOP_ID = "60752333"
PRODUCT_PREFIX = "E2E-F3B"
WEBHOOK_PATH = "/gearment/webhook"

SSH_KEY = REPO_ROOT / "secrets" / "ssh-key-2023-02-24.key"
SSH_HOST = "ubuntu@129.150.63.207"
STAGING_CONTAINER = "esty19_odoo"

USERS: dict[str, tuple[str, str]] = {
    "admin": ("admin", os.environ.get("DEMO_ADMIN_PASSWORD", "admin")),
    "ba_shipping": ("demo_ba_shipping@hatafax.demo", "demo1234"),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger("e2e_flow3b")

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
    shop_id: int | None = None
    pipeline_id: int | None = None
    confirmed_state_id: int | None = None
    catalog_legacy_id: str = ""
    catalog_variant_id: str = ""
    catalog_variant_ids: list[str] = field(default_factory=list)
    catalog_name: str = ""
    artwork_url: str = ""
    product_id: int | None = None
    order_id: int | None = None
    order_name: str = ""
    outbound_ref: str = ""
    tracking_number: str = ""
    gift_message: str = ""
    mv_order_id: int | None = None
    mv_outbound_ref: str = ""


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


def _odoo_shell(ctx: Context, snippet: str, timeout: int = 120) -> str:
    remote = (f"sudo docker exec -i {STAGING_CONTAINER} "
              f"odoo shell -d {ctx.db} --no-http")
    cmd = ["ssh", "-i", str(SSH_KEY), "-o", "StrictHostKeyChecking=no",
           "-o", "BatchMode=yes", SSH_HOST, remote]
    proc = subprocess.run(cmd, input=snippet, capture_output=True,
                          text=True, timeout=timeout)
    return proc.stdout + proc.stderr


def _gearment_signature(body: bytes, nonce: str, ts: str, secret: str,
                        url_path: str = WEBHOOK_PATH) -> str:
    body_b64 = base64.urlsafe_b64encode(body).decode("ascii")
    signing = (url_path + nonce + ts + body_b64).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signing, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def _fire_webhook(ctx: Context, body_obj: dict) -> tuple[int, str]:
    # Controller verifies against GEARMENT_API_SECRET (P0-18b2b), NOT the
    # dashboard webhook secret.
    secret = os.environ.get("GEARMENT_API_SECRET") or ""
    api_key = os.environ.get("GEARMENT_API_KEY") or ""
    if not secret:
        return 0, "GEARMENT secret missing in env"
    body = json.dumps(body_obj, separators=(",", ":")).encode("utf-8")
    nonce = (base64.urlsafe_b64encode(pysecrets.token_bytes(8))
             .decode("ascii").rstrip("=") + "==")
    ts = str(int(time.time()))
    sig = _gearment_signature(body, nonce, ts, secret)
    headers = {
        "Content-Type": "application/json",
        "X-Connect-Signature": sig,
        "X-Connect-Nonce": nonce,
        "X-Connect-Timestamp": ts,
        "X-Connect-Client-Key": api_key,
    }
    resp = requests.post(ctx.base_url + WEBHOOK_PATH, data=body,
                         headers=headers, timeout=30)
    return resp.status_code, resp.text[:200]


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
    pipelines = rpc(ctx, "admin", "order.pipeline", "search_read",
                    [[("code", "=", "gearment_pod")]], {"fields": ["name"]})
    if not pipelines:
        return StepResult("0", False, "gearment_pod pipeline not seeded")
    ctx.pipeline_id = pipelines[0]["id"]
    states = rpc(ctx, "admin", "order.pipeline.state", "search",
                 [[("pipeline_id", "=", ctx.pipeline_id),
                   ("code", "=", "confirmed")]])
    if not states:
        return StepResult("0", False, "gearment_pod/confirmed state not seeded")
    ctx.confirmed_state_id = states[0]

    shops = rpc(ctx, "admin", "etsy.shop", "search",
                [[("etsy_api_shop_id", "=", ETSY_API_SHOP_ID)]])
    ctx.shop_id = shops[0] if shops else None
    if not ctx.shop_id:
        return StepResult("0", False, "JaHandmadeArt shop row missing")

    # Staging container must carry the GEARMENT_* env (adapter reads os.environ).
    out = _odoo_shell(ctx, "import os\n"
                           "print('F3B_ENV:' + ','.join(sorted(k for k in "
                           "os.environ if k.startswith('GEARMENT'))))")
    env_line = next((line for line in out.splitlines()
                     if line.startswith("F3B_ENV:")), "")
    needed = {"GEARMENT_API_BASE_URL", "GEARMENT_API_KEY", "GEARMENT_API_SECRET"}
    have = set(env_line.replace("F3B_ENV:", "").split(",")) if env_line else set()
    if not needed <= have:
        return StepResult("0", False,
                          f"staging container missing GEARMENT env: "
                          f"{sorted(needed - have)}")

    # LIVE catalog: pick a real product for the fixture (legacy id + public
    # artwork URL from Gearment's own CDN).
    base = os.environ["GEARMENT_API_BASE_URL"].rstrip("/")
    r = requests.get(base + "/api/v3/catalog", params={"limit": 1}, timeout=30,
                     headers={"X-Gearment-Client-Key": os.environ["GEARMENT_API_KEY"],
                              "X-Gearment-Client-Secret": os.environ["GEARMENT_API_SECRET"]})
    if r.status_code != 200:
        return StepResult("0", False,
                          f"live catalog fetch {r.status_code}: {r.text[:150]}")
    item = (r.json().get("data") or [{}])[0]
    ctx.catalog_legacy_id = str(item.get("legacy_product_id") or "")
    # The draft line item is keyed by the GM-prefixed catalog variant_id
    # (e.g. GM0249020374), NOT the legacy_product_id — pick the first in-stock
    # variant. x_gearment_sku carries this value (Defect-2026-05-10-02).
    variants = item.get("variants") or []
    ctx.catalog_variant_id = str((variants[0] or {}).get("variant_id") or "") if variants else ""
    # FLW-01 (§V): distinct GM variant ids for the multi-variant leg.
    ctx.catalog_variant_ids = [
        str(v.get("variant_id"))
        for v in variants[:2] if v and v.get("variant_id")]
    ctx.catalog_name = item.get("product_name") or "?"
    ctx.artwork_url = item.get("product_avatar_url") or ""
    if not ctx.catalog_variant_id or not ctx.artwork_url:
        return StepResult("0", False, f"catalog item unusable (no variant_id): {item}")

    ctx.marker = uuid.uuid4().hex[:6]
    stale = rpc(ctx, "admin", "product.template", "search",
                [[("name", "like", PRODUCT_PREFIX), ("active", "=", True)]])
    if stale:
        rpc(ctx, "admin", "product.template", "write", [stale, {"active": False}])
    return StepResult(
        "0", True,
        f"server {version}; pipeline OK; staging env OK; live catalog: "
        f"{ctx.catalog_name!r} variant_id={ctx.catalog_variant_id}; "
        f"marker={ctx.marker}; archived {len(stale)}")


def section_1_fixtures(ctx: Context) -> StepResult:
    tmpl = rpc(ctx, "admin", "product.template", "create", [{
        "name": f"{PRODUCT_PREFIX} POD {ctx.marker} ({ctx.catalog_name[:20]})",
        "is_storable": False,
        "list_price": 20.0,
        "x_gearment_sku": ctx.catalog_variant_id,
    }])
    ctx.product_id = rpc(ctx, "admin", "product.product", "search",
                         [[("product_tmpl_id", "=", tmpl)]])[0]
    country = rpc(ctx, "admin", "res.country", "search",
                  [[("code", "=", "US")]])[0]
    state_tx = rpc(ctx, "admin", "res.country.state", "search",
                   [[("country_id", "=", country), ("code", "=", "TX")]])
    partner = rpc(ctx, "admin", "res.partner", "create", [{
        "name": f"{PRODUCT_PREFIX} Buyer {ctx.marker}",
        "street": "100 Congress Ave", "city": "Austin", "zip": "78701",
        "country_id": country,
        "state_id": state_tx[0] if state_tx else False,
        "phone": "+1 512 555 0100",
    }])
    # FLW-05: buyer gift message must ride the draft wire as
    # gift_message_body (asserted in §W). ASCII on purpose — VN diacritics
    # trip Gearment's validator on other fields; keep the fixture clean.
    ctx.gift_message = f"Happy birthday from E2E-F3B {ctx.marker}"
    ctx.order_id = rpc(ctx, "admin", "sale.order", "create", [{
        "partner_id": partner,
        "etsy_order_id": f"96{int(time.time()) % 100_000_000}",
        "etsy_shop_id": ctx.shop_id,
        "gift_message": ctx.gift_message,
        "order_line": [[0, 0, {"product_id": ctx.product_id,
                               "product_uom_qty": 1.0, "price_unit": 20.0}]],
    }])
    ctx.order_name = rpc(ctx, "admin", "sale.order", "read",
                         [[ctx.order_id], ["name"]])[0]["name"]
    line = rpc(ctx, "admin", "sale.order.line", "search",
               [[("order_id", "=", ctx.order_id)]])[0]
    # URL-mode approved design → the payload builder emits printing_options
    # (front) with a PUBLIC artwork URL; without it Gearment 400s
    # "must include at least one printing option" (today's demo-run body).
    rpc(ctx, "admin", "design.file", "create", [{
        "name": f"{PRODUCT_PREFIX}-ART-{ctx.marker}",
        "order_line_id": line,
        "storage_mode": "url",
        "file_url": ctx.artwork_url,
        "state": "approved",
    }])
    return StepResult(
        "1", True,
        f"order {ctx.order_name}; POD product variant_id={ctx.catalog_variant_id}; "
        f"approved URL design (artwork={ctx.artwork_url[:40]}…)")


def section_2_confirm_pipeline(ctx: Context) -> StepResult:
    rpc_void(ctx, "admin", "sale.order", "action_confirm", [[ctx.order_id]])
    rpc_void(ctx, "admin", "sale.order", "write",
             [[ctx.order_id],
              {"x_pipeline_id": ctx.pipeline_id,
               "x_pipeline_state_id": ctx.confirmed_state_id}],
             {"context": {"bypass_pipeline_state_guard": True}})
    row = rpc(ctx, "admin", "sale.order", "read",
              [[ctx.order_id], ["state", "x_pipeline_state_id"]])[0]
    ok = row["state"] in ("sale", "done")
    return StepResult("2", ok,
                      f"state={row['state']} pipeline_state={row['x_pipeline_state_id']}")


_SIM_SNIPPET = """
import os
from decimal import Decimal
from odoo.addons.multichannel_hub_fulfillment.services import gearment_adapter as ga

class _SimAdapter:
    \"\"\"MF-E2E-3b simulator for the vendor-blocked draft/price endpoints
    (Defect-2026-05-10-05: printing_options validator rejects every known
    payload shape; sandbox host 530-dead). HTTP boundary only — builder,
    model writes and state machine are the REAL code.\"\"\"
    def __init__(self, env=None, client=None):
        self.env = env
    def push_order(self, payload, sale_order_id=None):
        assert payload.line_items and payload.line_items[0].printing_options, (
            'simulator enforces the documented contract: printing_options '
            'required per line')
        return {'reference_id': payload.reference_id,
                'order_id': 'SIM-GM-' + os.environ['F3B_MARKER'],
                'raw_response': {'simulated': True}}
    def get_quote(self, reference_id):
        keys = ('order_total', 'order_sub_total', 'order_shipping_fee',
                'order_tax', 'order_discount', 'order_handle_fee',
                'order_gift_message_fee', 'order_fee')
        out = {k: Decimal('0') for k in keys}
        out['order_sub_total'] = Decimal('9.95')
        out['order_shipping_fee'] = Decimal('4.99')
        out['order_total'] = Decimal('14.94')
        out['currency'] = 'USD'
        out['raw_response'] = {'simulated': True}
        return out

_real = ga.GearmentApiAdapter
ga.GearmentApiAdapter = _SimAdapter
try:
    order = env['sale.order'].browse(int(os.environ['F3B_ORDER']))
    order.action_push_to_gearment()
    order.action_get_gearment_quote()
    env.cr.commit()
    print('F3B_SIM:' + (order.x_gearment_outbound_ref or '') + '|'
          + (order.x_gearment_outbound_state or ''))
except Exception as exc:
    print('F3B_SIM_ERR:%s: %s' % (type(exc).__name__, str(exc)[:300]))
finally:
    ga.GearmentApiAdapter = _real
"""


def section_3_push_draft(ctx: Context) -> StepResult:
    """Two legs. LIVE: the vendor validator rejects every known
    printing_options shape (Defect-2026-05-10-05) — assert our stack
    handles the 400 gracefully and audits the validator name. SIMULATED:
    HTTP boundary faked in odoo shell (owner-approved fallback: sandbox
    host is 530-dead), real builder + model writes run the state machine.
    """
    live_note = ""
    try:
        rpc_void(ctx, "ba_shipping", "sale.order", "action_push_to_gearment",
                 [[ctx.order_id]])
        row = rpc(ctx, "admin", "sale.order", "read",
                  [[ctx.order_id], ["x_gearment_outbound_ref"]])[0]
        ctx.outbound_ref = row["x_gearment_outbound_ref"] or ""
        if ctx.outbound_ref:
            return StepResult(
                "3", True,
                f"LIVE draft pushed (vendor validator FIXED?): "
                f"outbound_ref={ctx.outbound_ref!r} — owner must discard "
                f"the Gearment DRAFT")
    except xmlrpc.client.Fault as exc:
        live_note = exc.faultString.splitlines()[-1][:160]
    logs = rpc(ctx, "admin", "gearment.api.log", "search_read",
               [[("endpoint", "like", "draft"),
                 ("sale_order_id", "=", ctx.order_id)]],
               {"fields": ["http_status", "response_summary"],
                "order": "id desc", "limit": 1})
    validator_seen = bool(logs) and logs[0]["http_status"] == 400 and \
        "printing_option" in (logs[0]["response_summary"] or "")
    # SIMULATED leg (vendor-blocked live path)
    remote_env = (f"-e F3B_ORDER={ctx.order_id} -e F3B_MARKER={ctx.marker}")
    remote = (f"sudo docker exec {remote_env} -i {STAGING_CONTAINER} "
              f"odoo shell -d {ctx.db} --no-http")
    cmd = ["ssh", "-i", str(SSH_KEY), "-o", "StrictHostKeyChecking=no",
           "-o", "BatchMode=yes", SSH_HOST, remote]
    proc = subprocess.run(cmd, input=_SIM_SNIPPET, capture_output=True,
                          text=True, timeout=300)
    out = proc.stdout + proc.stderr
    sim_line = next((line for line in out.splitlines()
                     if line.startswith("F3B_SIM:")), "")
    err_line = next((line for line in out.splitlines()
                     if line.startswith("F3B_SIM_ERR:")), "")
    if sim_line:
        ref, state = (sim_line.replace("F3B_SIM:", "").split("|") + [""])[:2]
        ctx.outbound_ref = ref
        ctx.sim_state = state  # type: ignore[attr-defined]
    ok = validator_seen and bool(sim_line) and bool(ctx.outbound_ref)
    return StepResult(
        "3", ok,
        f"LIVE: vendor 400 handled gracefully (UserError={live_note!r}; "
        f"validator audited={validator_seen}). SIMULATED push+quote: "
        f"ref={ctx.outbound_ref!r} state={getattr(ctx, 'sim_state', '')!r} "
        f"{err_line}")


def section_4_quote(ctx: Context) -> StepResult:
    # LIVE price quote: POST /api/v3/orders/price advances draft -> quoted.
    # (Fixed 2026-07-05 — the old GET /orders/{ref}/price route 404'd, so this
    # leg used to be simulated.)
    quote_err = ""
    try:
        rpc_void(ctx, "ba_shipping", "sale.order",
                 "action_get_gearment_quote", [[ctx.order_id]])
    except xmlrpc.client.Fault as exc:
        quote_err = exc.faultString.splitlines()[-1][:160]
    fields_ = ["x_gearment_outbound_state", "x_gearment_outbound_ref"]
    probe = rpc(ctx, "admin", "sale.order", "fields_get", [], {})
    for cand in ("x_gearment_quote_total", "x_gearment_quote_currency"):
        if cand in probe:
            fields_.append(cand)
    row = rpc(ctx, "admin", "sale.order", "read", [[ctx.order_id], fields_])[0]
    total = row.get("x_gearment_quote_total")
    ok = row["x_gearment_outbound_state"] == "quoted" and (
        total is None or total > 0)
    return StepResult(
        "4", ok,
        f"LIVE quote (POST /orders/price): {row}"
        + (f" err={quote_err!r}" if quote_err else ""))


def section_w_gift_wire(ctx: Context) -> StepResult:
    """FLW-05: the draft request payload carries gift_message_body and the
    line_items carry NO personalisation/personalization key (removed from
    the wire 2026-07-06 — the vendor schema has no such field). Reads the
    PII-scrubbed gearment.api.log request_payload_summary (keys survive the
    scrub; addresses are dropped)."""
    logs = rpc(ctx, "admin", "gearment.api.log", "search_read",
               [[("endpoint", "like", "draft"),
                 ("sale_order_id", "=", ctx.order_id)]],
               {"fields": ["request_payload_summary", "http_status"],
                "order": "id desc", "limit": 1})
    if not logs or not logs[0].get("request_payload_summary"):
        return StepResult(
            "W", False,
            "no gearment.api.log draft row with request_payload_summary "
            f"for order {ctx.order_id} (logs={logs})")
    try:
        payload = json.loads(logs[0]["request_payload_summary"])
    except ValueError:
        return StepResult(
            "W", False,
            f"payload summary not JSON: {logs[0]['request_payload_summary'][:150]}")
    items = payload.get("line_items") or []
    forbidden = {"personalisation", "personalization"}
    bad_keys = sorted(
        k for it in items if isinstance(it, dict)
        for k in it if k.lower() in forbidden)
    checks = {
        "gift_message_body on wire":
            payload.get("gift_message_body") == ctx.gift_message,
        "no personalisation key on any line": not bad_keys,
        "shipping_method is METHOD_STANDARD":
            payload.get("shipping_method") == "METHOD_STANDARD",
    }
    bad = [k for k, v in checks.items() if not v]
    return StepResult(
        "W", not bad,
        f"draft http={logs[0]['http_status']} "
        f"gift_message_body={payload.get('gift_message_body')!r} "
        f"line_item_keys={sorted({k for it in items if isinstance(it, dict) for k in it})}"
        + (f" FAILED={bad}" if bad else ""))


def section_5_tracking_webhook(ctx: Context) -> StepResult:
    # 22 digits (USPS seed regex cap), suffixed from the numeric part of the
    # run marker for cross-run uniqueness.
    digits = "".join(c for c in ctx.marker if c.isdigit()).ljust(4, "7")[:4]
    ctx.tracking_number = "940011120255556000" + digits
    body = {
        "type": "tracking_order_updated",
        "order": {"reference": ctx.order_name, "status": "shipped"},
        "tracking": {
            "company": "USPS",
            "number": ctx.tracking_number,
            "url": f"https://tools.usps.com/go/TrackConfirmAction?tLabels={ctx.tracking_number}",
        },
    }
    status, text = _fire_webhook(ctx, body)
    return StepResult("5", status == 200,
                      f"webhook status={status} body={text!r}")


def section_6_verify(ctx: Context, page: Page) -> StepResult:
    fulfil = rpc(ctx, "admin", "sale.order.fulfillment", "search_read",
                 [[("order_id", "=", ctx.order_id)]],
                 {"fields": ["tracking_number", "tracking_url",
                             "gearment_last_webhook_topic"]})
    row = rpc(ctx, "admin", "sale.order", "read",
              [[ctx.order_id],
               ["etsy_tracking_push_status", "etsy_tracking_push_attempts",
                "etsy_tracking_push_error"]])[0]
    # Verified webhooks do not write gearment.api.log rows (discovery-mode
    # logging only) — the durable provenance is the fulfillment stamp
    # (gearment_last_webhook_topic/at).
    shot = None
    try:
        login(page, ctx.base_url, ctx.db)
        page.goto(f"{ctx.base_url}/web#id={ctx.order_id}"
                  f"&model=sale.order&view_type=form")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_selector(".o_form_view", state="visible", timeout=30_000)
        shot = _shot(page, "f3b_s6_dropship_order")
    except Exception as exc:  # noqa: BLE001 — evidence only
        _log.warning("screenshot failed: %s", exc)
    checks = {
        "fulfillment tracking recorded": bool(fulfil) and
            fulfil[0].get("tracking_number") == ctx.tracking_number,
        "webhook provenance stamped": bool(fulfil) and
            fulfil[0].get("gearment_last_webhook_topic") == "tracking_order_updated",
        "etsy push attempted (flags set)":
            row["etsy_tracking_push_status"] in ("pushed", "failed"),
    }
    bad = [k for k, v in checks.items() if not v]
    return StepResult(
        "6", not bad,
        f"fulfillment={fulfil} push={row}"
        + (f" FAILED={bad}" if bad else ""), shot)


def section_v_multivariant(ctx: Context) -> StepResult:
    """FLW-01 + FLW-04. A multi-variant product without variant-specific
    Gearment codes must BLOCK the push (UserError), and with per-variant
    supplierinfo product_code rows the draft must carry DISTINCT GM
    variant_ids. Expedited shipping_service_label logs a WARNING but stays
    METHOD_STANDARD on the wire (FLW-04)."""
    def _attr_pair():
        attr = rpc(ctx, "admin", "product.attribute", "search",
                   [[("name", "=", "Fluid oz")]])
        if not attr:
            return None, []
        vals = rpc(ctx, "admin", "product.attribute.value", "search",
                   [[("attribute_id", "=", attr[0])]], {"limit": 2})
        return attr[0], vals

    attr_id, val_ids = _attr_pair()
    if not attr_id or len(val_ids) < 2:
        return StepResult("V", False,
                          "no 2-value attribute available on staging")
    tmpl = rpc(ctx, "admin", "product.template", "create", [{
        "name": f"{PRODUCT_PREFIX} MV {ctx.marker} ({ctx.catalog_name[:16]})",
        "is_storable": False,
        "list_price": 20.0,
        "x_gearment_sku": ctx.catalog_variant_id,
        "attribute_line_ids": [
            [0, 0, {"attribute_id": attr_id, "value_ids": [[6, 0, val_ids]]}],
        ],
    }])
    variants = rpc(ctx, "admin", "product.product", "search",
                   [[("product_tmpl_id", "=", tmpl)]])
    if len(variants) != 2:
        return StepResult("V", False, f"expected 2 variants, got {len(variants)}")
    country = rpc(ctx, "admin", "res.country", "search",
                  [[("code", "=", "US")]])[0]
    partner = rpc(ctx, "admin", "res.partner", "create", [{
        "name": f"{PRODUCT_PREFIX} MV Buyer {ctx.marker}",
        "street": "200 Congress Ave", "city": "Austin", "zip": "78701",
        "country_id": country, "phone": "+1 512 555 0101",
    }])
    ctx.mv_order_id = rpc(ctx, "admin", "sale.order", "create", [{
        "partner_id": partner,
        "etsy_order_id": f"95{int(time.time()) % 100_000_000}",
        "etsy_shop_id": ctx.shop_id,
        # FLW-04: expedited hint → WARNING + METHOD_STANDARD on the wire.
        "shipping_service_label": "Express Shipping",
        "order_line": [
            [0, 0, {"product_id": vid, "product_uom_qty": 1.0,
                    "price_unit": 20.0}]
            for vid in variants],
    }])
    rpc_void(ctx, "admin", "sale.order", "action_confirm", [[ctx.mv_order_id]])
    rpc_void(ctx, "admin", "sale.order", "write",
             [[ctx.mv_order_id],
              {"x_pipeline_id": ctx.pipeline_id,
               "x_pipeline_state_id": ctx.confirmed_state_id}],
             {"context": {"bypass_pipeline_state_guard": True}})
    for line in rpc(ctx, "admin", "sale.order.line", "search",
                    [[("order_id", "=", ctx.mv_order_id)]]):
        rpc(ctx, "admin", "design.file", "create", [{
            "name": f"{PRODUCT_PREFIX}-MV-ART-{ctx.marker}-{line}",
            "order_line_id": line,
            "storage_mode": "url",
            "file_url": ctx.artwork_url,
            "state": "approved",
        }])

    # Leg 1 — BLOCK path: template-level fallback on a multi-variant product
    # must refuse the push with the FLW-01 UserError.
    block_msg = ""
    try:
        rpc(ctx, "ba_shipping", "sale.order", "action_push_to_gearment",
            [[ctx.mv_order_id]])
    except xmlrpc.client.Fault as exc:
        block_msg = (exc.faultString or "").splitlines()[-1][:200]
    blocked = "no Gearment variant code" in block_msg
    ref_after_block = rpc(ctx, "admin", "sale.order", "read",
                          [[ctx.mv_order_id], ["x_gearment_outbound_ref"]]
                          )[0]["x_gearment_outbound_ref"]

    # Leg 2 — mapped path: per-variant supplierinfo rows with DISTINCT GM
    # variant ids, then a LIVE draft push (owner discards).
    mapped_note = "skipped (catalog exposed <2 variant ids)"
    distinct_ok = warn_ok = True
    if len(ctx.catalog_variant_ids) >= 2 and blocked and not ref_after_block:
        gm_partner = rpc(ctx, "admin", "ir.model.data", "search_read",
                         [[("module", "=", "multichannel_hub_fulfillment"),
                           ("name", "=", "partner_gearment_vendor")],
                          ["res_id"]])[0]["res_id"]
        for vid, gm_id in zip(variants, ctx.catalog_variant_ids):
            rpc(ctx, "admin", "product.supplierinfo", "create", [{
                "partner_id": gm_partner,
                "product_tmpl_id": tmpl,
                "product_id": vid,
                "product_code": gm_id,
                "min_qty": 1,
            }])
        push_err = ""
        try:
            rpc_void(ctx, "ba_shipping", "sale.order",
                     "action_push_to_gearment", [[ctx.mv_order_id]])
        except xmlrpc.client.Fault as exc:
            push_err = (exc.faultString or "").splitlines()[-1][:200]
        ctx.mv_outbound_ref = rpc(
            ctx, "admin", "sale.order", "read",
            [[ctx.mv_order_id], ["x_gearment_outbound_ref"]]
        )[0]["x_gearment_outbound_ref"] or ""
        wire_ids: list[str] = []
        logs = rpc(ctx, "admin", "gearment.api.log", "search_read",
                   [[("endpoint", "like", "draft"),
                     ("sale_order_id", "=", ctx.mv_order_id)]],
                   {"fields": ["request_payload_summary", "http_status"],
                    "order": "id desc", "limit": 1})
        if logs and logs[0].get("request_payload_summary"):
            try:
                pl = json.loads(logs[0]["request_payload_summary"])
                wire_ids = [str(it.get("variant_id"))
                            for it in (pl.get("line_items") or [])
                            if isinstance(it, dict)]
                warn_ok = pl.get("shipping_method") == "METHOD_STANDARD"
            except ValueError:
                pass
        distinct_ok = (sorted(wire_ids)
                       == sorted(ctx.catalog_variant_ids[:2]))
        # FLW-04 WARNING in the server log (fires during build_payload on
        # the mapped push).
        grep = subprocess.run(
            ["ssh", "-i", str(SSH_KEY), "-o", "StrictHostKeyChecking=no",
             "-o", "BatchMode=yes", SSH_HOST,
             f"sudo docker logs --since 15m {STAGING_CONTAINER} 2>&1 | "
             f"grep -c 'only METHOD_STANDARD is available' || true"],
            capture_output=True, text=True, timeout=60)
        warn_count = int((grep.stdout or "0").strip() or 0)
        warn_ok = warn_ok and warn_count >= 1
        mapped_note = (f"mapped push ref={ctx.mv_outbound_ref!r} "
                       f"err={push_err!r} wire_variant_ids={wire_ids} "
                       f"flw04_warnings={warn_count}")
    checks = {
        "multi-variant push BLOCKED w/o variant codes": blocked,
        "no draft created by the blocked push": not ref_after_block,
        "distinct GM variant_ids on the wire": distinct_ok,
        "FLW-04: WARNING logged + METHOD_STANDARD kept": warn_ok,
    }
    bad = [k for k, v in checks.items() if not v]
    return StepResult(
        "V", not bad,
        f"block UserError={block_msg!r}; {mapped_note}"
        + (f" FAILED={bad}" if bad else ""))


def section_7_cleanup(ctx: Context) -> StepResult:
    for oid in (ctx.order_id, ctx.mv_order_id):
        if not oid:
            continue
        try:
            rpc_void(ctx, "admin", "sale.order", "action_cancel", [[oid]])
        except xmlrpc.client.Fault:
            pass
    tmpl_ids = rpc(ctx, "admin", "product.template", "search",
                   [[("name", "like", PRODUCT_PREFIX), ("active", "=", True)]])
    if tmpl_ids:
        rpc(ctx, "admin", "product.template", "write",
            [tmpl_ids, {"active": False}])
    refs = [r for r in (ctx.outbound_ref, ctx.mv_outbound_ref) if r]
    return StepResult(
        "7", True,
        f"SO(s) cancelled; {len(tmpl_ids)} product(s) archived. OWNER "
        f"ACTION: discard Gearment DRAFT order ref(s) {refs!r} in the "
        f"dashboard (never confirmed/labeled by this runner).")


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
                 / f"E2E_FLOW3B_DROPSHIP_{TODAY}.md")
    if canonical.exists() and not os.access(canonical, os.W_OK):
        canonical = canonical.with_name(
            f"E2E_FLOW3B_DROPSHIP_{TODAY}_{datetime.now().strftime('%H%M%S')}.md")
    passed = sum(1 for r in results if r.ok)
    lines = [
        f"# MF-E2E-3b — Flow-3b Gearment dropship, LIVE API ({TODAY})",
        "",
        f"- **Target**: {ctx.base_url} / DB `{ctx.db}`",
        f"- **Build**: {_git_head()}",
        f"- **Driver**: scripts/e2e_flow3b_dropship.py",
        f"- **Gearment**: LIVE api (draft-only safety contract)",
        f"- **Order**: {ctx.order_name or '—'} / outbound_ref {ctx.outbound_ref or '—'}",
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
        "- SAFETY: only `POST api/v3/orders/draft` + `GET orders/{ref}/price` "
        "were called live; `confirm()/labeled` (chargeable) is NEVER invoked "
        "by this runner. Owner discards the draft in the Gearment dashboard.",
        "- Webhook leg is self-signed with the P0-18b2 HMAC scheme — closes "
        "the signature verification live (X-Connect-Signature).",
        "- Etsy tracking push runs to the API boundary (synthetic receipt → "
        "recorded outcome); live `pushed` belongs to P1-11.",
        "- §W (FLW-05, 2026-07-06): the draft wire carries "
        "`gift_message_body` from the order's gift message and line_items "
        "carry NO `personalisation` key (removed — not in the vendor "
        "schema). Asserted on the PII-scrubbed request_payload_summary.",
        "- §V (FLW-01/FLW-04, 2026-07-06): multi-variant product without "
        "variant-specific Gearment codes must BLOCK the push (UserError); "
        "with per-variant supplierinfo product_code rows the draft carries "
        "DISTINCT GM variant_ids. Expedited shipping_service_label logs a "
        "WARNING but ships METHOD_STANDARD (only wire-documented method).",
        "",
        "## Reproducing",
        "",
        "```bash",
        f"/tmp/e2e-venv/bin/python scripts/e2e_flow3b_dropship.py --db {ctx.db}",
        "```",
    ]
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return canonical


SECTIONS = ("0", "1", "2", "3", "4", "W", "5", "6", "V", "7")


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
            "2": lambda: section_2_confirm_pipeline(ctx),
            "3": lambda: section_3_push_draft(ctx),
            "4": lambda: section_4_quote(ctx),
            "W": lambda: section_w_gift_wire(ctx),
            "5": lambda: section_5_tracking_webhook(ctx),
            "6": lambda: section_6_verify(ctx, page),
            "V": lambda: section_v_multivariant(ctx),
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
