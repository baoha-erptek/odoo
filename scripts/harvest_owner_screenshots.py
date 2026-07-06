"""Harvest real staging screenshots for the owner-facing guides.

Captures the docs/owner/img/ shot list for HUONG_DAN_DON_HANG / GIAO_HANG /
HAU_MAI (previously image-less) plus the ESTY-250 Original Design tab refresh
for HUONG_DAN_TAO_SAN_PHAM. Targets persistent staging records (real synced
orders, E2E leftovers kept for evidence) — nothing is created or modified.

Usage:
    /tmp/e2e-venv/bin/python scripts/harvest_owner_screenshots.py \
        [--db esty_odoo19] [--base-url https://odoo.hatafax.com] [--headed]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import xmlrpc.client
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "owner" / "img"

DEFAULT_BASE_URL = "https://odoo.hatafax.com"
DEFAULT_DB = "esty_odoo19"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger("harvest")

load_dotenv(REPO_ROOT / ".env")
ADMIN = (
    os.environ.get("STAGING_ADMIN_LOGIN", "admin"),
    os.environ.get("STAGING_ADMIN_PASSWORD",
                   os.environ.get("DEMO_ADMIN_PASSWORD", "admin")),
)

# (filename, kind, target, extra, marker)
#   kind="form"   target=(model, res_id)         extra=optional notebook tab label
#   kind="action" target=(module, action_xmlid)  extra=optional view_type
#   marker: optional page text that must be visible BEFORE capture — the
#   shot-specific correctness anchor (2026-07-06 correct-view pass).
SHOTS: list[tuple[str, str, tuple, str | None, str | None]] = [
    # HUONG_DAN_DON_HANG_ETSY_VN (flow-2)
    ("don-hang-etsy-shop-form", "form", ("etsy.shop", 10), None, None),
    ("don-hang-order-list", "action", ("etsy_integration", "action_etsy_orders"), None, None),
    ("don-hang-order-form", "form", ("sale.order", 3355), None, None),
    ("don-hang-email-log-list", "action", ("etsy_integration", "action_etsy_email_log"), None, None),
    ("don-hang-sync-health", "action", ("etsy_integration", "action_etsy_sync_health"), None, None),
    # HUONG_DAN_GIAO_HANG_VN (flow-3a/3b)
    ("giao-hang-operations-dashboard", "action",
     ("multichannel_hub_core", "action_operations_dashboard"), None, None),
    ("giao-hang-order-pipeline", "action",
     ("multichannel_hub_core", "action_order_pipeline"), None, None),
    ("giao-hang-order-form-tracking", "form", ("sale.order", 3355), None, None),
    ("giao-hang-mo-form", "form", ("mrp.production", 20), None, None),
    ("giao-hang-design-file-form", "form", ("design.file", 111), None, None),
    ("giao-hang-tracking-import-log", "action",
     ("multichannel_hub_fulfillment", "action_tracking_import_log"), None, None),
    ("giao-hang-fulfillment-detail", "action",
     ("multichannel_hub_fulfillment", "action_sale_order_fulfillment_detail"), None, None),
    # HUONG_DAN_HAU_MAI_VN (flow-4)
    ("hau-mai-ticket-list", "action",
     ("etsy_integration", "action_etsy_order_ticket"), None, None),
    ("hau-mai-ticket-form", "form", ("etsy.order.ticket", 4), None, None),
    ("hau-mai-address-change-list", "action",
     ("etsy_integration", "action_etsy_address_change_request"), None, None),
    ("hau-mai-address-change-form", "form",
     ("etsy.address.change.request", 22), None, None),
    # HUONG_DAN_TAO_SAN_PHAM_VN refresh (ESTY-250)
    ("product-tab-original-design", "form", ("product.template", 614),
     "Thiết kế gốc", None),  # "Original Design" tab (admin UI is vi_VN)
    # mockup-v3 refresh (theme + vi_VN UI) — re-capture the flow-1 anchors
    ("product-form-header", "form", ("product.template", 614), None, None),
    ("listing-form-overview", "form", ("multichannel.listing", 62), None, None),
    ("tao-san-pham-channel-status-kanban", "action",
     ("multichannel_hub_core", "action_product_channel_status"), None, None),
    ("tao-san-pham-sku-drift", "action",
     ("multichannel_hub_core", "action_product_sku_drift"), None, None),
    # flow-3b PO-driven Gearment quote (ESTY-246) + picking status (ESTY-248)
    ("giao-hang-gearment-po-form", "form", ("purchase.order", 16), None, "Gearment"),
    ("giao-hang-picking-gearment-status", "form", ("stock.picking", 102), None, None),
    # FLW-01..07 rerun (2026-07-06) — new behavior anchors
    # held order surfaces production_blocked/block_reason on the FULFILLMENT
    # form (delegated fields; sale.order form has no hold banner)
    ("flw-don-hang-held-order", "form", ("sale.order.fulfillment", 3412), None,
     "Unresolved Etsy line"),
    ("flw-giao-hang-pipeline-shipped", "form", ("sale.order", 3391), None,
     "Đã Gửi"),
    # per-variant GM mapping: the Purchase-tab list hides product_code, so
    # shoot the supplierinfo record itself (variant + Vendor Product Code)
    ("flw-tao-san-pham-variant-supplierinfo", "form",
     ("product.supplierinfo", 69), None, "GM0249020374"),
    ("flw-giao-hang-gift-message-log", "form", ("gearment.api.log", 61), None,
     "gift_message_body"),
]


def login(page: Page, base: str, db: str) -> None:
    page.context.clear_cookies()
    page.goto(f"{base}/web/login?db={db}")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector('input[name="login"]', state="visible", timeout=15_000)
    page.fill('input[name="login"]', ADMIN[0])
    page.fill('input[name="password"]', ADMIN[1])
    page.click('button[type="submit"]')
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector(".o_action_manager", state="visible", timeout=30_000)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--headed", action="store_true")
    p.add_argument("--only", help="capture just this shot name")
    args = p.parse_args()

    common = xmlrpc.client.ServerProxy(f"{args.base_url}/xmlrpc/2/common")
    uid = common.authenticate(args.db, ADMIN[0], ADMIN[1], {})
    if not uid:
        _log.error("XML-RPC auth failed")
        return 1
    models = xmlrpc.client.ServerProxy(f"{args.base_url}/xmlrpc/2/object")

    def action_id(module: str, xmlid: str) -> int:
        return models.execute_kw(
            args.db, uid, ADMIN[1], "ir.model.data", "check_object_reference",
            [module, xmlid])[1]

    def display_name(model: str, res_id: int) -> str:
        rows = models.execute_kw(
            args.db, uid, ADMIN[1], model, "read",
            [[res_id], ["display_name"]],
            {"context": {"lang": "vi_VN", "active_test": False}})
        return rows[0]["display_name"] if rows else ""

    def action_name(module: str, xmlid: str, aid: int) -> str:
        rows = models.execute_kw(
            args.db, uid, ADMIN[1], "ir.actions.act_window", "read",
            [[aid], ["name"]], {"context": {"lang": "vi_VN"}})
        return rows[0]["name"] if rows else ""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    captured, failed = [], []
    manifest: dict[str, dict] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        login(page, args.base_url, args.db)

        for name, kind, target, extra, marker in SHOTS:
            if args.only and name != args.only:
                continue
            try:
                entry: dict = {"kind": kind, "marker": marker}
                # ── correct-view verification pass (2026-07-06): deep-link
                # nav → concrete view selector → breadcrumb + URL identity
                # assert → shot-specific marker. Capture happens only after
                # every check passes; any miss records a FAIL, not a PNG.
                if kind == "form":
                    model, res_id = target
                    expected = display_name(model, res_id)
                    page.goto(f"{args.base_url}/web#id={res_id}"
                              f"&model={model}&view_type=form")
                    page.wait_for_selector(".o_form_view", state="visible",
                                           timeout=30_000)
                    # NB: Odoo 19 rewrites /web#id=..&model=.. to
                    # /odoo/action-N/<id>, so the URL cannot assert the model;
                    # record identity is proven by the breadcrumb below.
                    crumb = page.locator(
                        ".o_breadcrumb, .breadcrumb").first.inner_text(
                        timeout=10_000).strip()
                    # breadcrumb ends with the record's display name (allow
                    # truncation of long names to the first 25 chars)
                    if expected and expected[:25] not in crumb:
                        raise AssertionError(
                            f"breadcrumb {crumb!r} != record {expected!r}")
                    entry.update(model=model, res_id=res_id,
                                 record=expected, breadcrumb=crumb)
                    if extra:  # lazy notebook tab
                        tab = page.locator(
                            f'.o_form_view a.nav-link:has-text("{extra}")')
                        if not tab.count():
                            raise AssertionError(f"notebook tab {extra!r} absent")
                        tab.first.click()
                        page.wait_for_timeout(800)
                else:
                    module, xmlid = target
                    aid = action_id(module, xmlid)
                    expected = action_name(module, xmlid, aid)
                    url = f"{args.base_url}/web#action={aid}"
                    if extra:
                        url += f"&view_type={extra}"
                    page.goto(url)
                    page.wait_for_selector(
                        ".o_list_view, .o_kanban_view, .o_form_view",
                        state="visible", timeout=30_000)
                    crumb = page.locator(
                        ".o_breadcrumb, .breadcrumb").first.inner_text(
                        timeout=10_000).strip()
                    if expected and expected[:25] not in crumb:
                        raise AssertionError(
                            f"breadcrumb {crumb!r} != action {expected!r}")
                    entry.update(action=f"{module}.{xmlid}", action_id=aid,
                                 record=expected, breadcrumb=crumb)
                if marker:
                    # marker may render as a text node OR as an input/
                    # textarea VALUE (Odoo editable widgets) — check both.
                    page.wait_for_function(
                        """(needle) => document.body.innerText.includes(needle)
                           || [...document.querySelectorAll('input,textarea')]
                              .some(el => (el.value || '').includes(needle))""",
                        arg=marker, timeout=10_000)
                page.wait_for_timeout(1200)  # let counters/images settle
                path = OUT_DIR / f"{name}.png"
                page.screenshot(path=str(path), full_page=False)
                entry["captured_at"] = datetime.utcnow().isoformat() + "Z"
                entry["url"] = page.url
                manifest[name] = entry
                captured.append(name)
                _log.info("OK  %s", name)
            except Exception as exc:  # noqa: BLE001 — keep harvesting
                failed.append((name, str(exc).splitlines()[0][:120]))
                _log.warning("FAIL %s: %s", name, exc)

        browser.close()

    if manifest:
        mf = OUT_DIR / "manifest.json"
        existing = {}
        if mf.exists():
            try:
                existing = json.loads(mf.read_text(encoding="utf-8"))
            except ValueError:
                existing = {}
        existing.update(manifest)
        mf.write_text(json.dumps(existing, ensure_ascii=False, indent=2,
                                 sort_keys=True) + "\n", encoding="utf-8")
        _log.info("manifest: %s (%d entries)", mf, len(existing))

    _log.info("captured=%d failed=%d", len(captured), len(failed))
    for name, err in failed:
        _log.info("  FAILED %s — %s", name, err)
    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
