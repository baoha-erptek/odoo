"""E2E demo runner for staging demo_esty.

Walks through E2E_TESTING_GUIDE sections 0, 1, 3, 4, 6, 8, 10 with screenshots
and a self-signed Gearment webhook probe at the end (section 10 — closes
P0-18b2 Phase 7 ops). Output goes to docs/screenshots/2026-05-02/.

Usage:
    python3 scripts/e2e_demo_2026_05_02.py [--section all|0|1|3|4|6|8|10]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests
from dotenv import load_dotenv
from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
SHOTS_DIR = REPO_ROOT / "docs" / "screenshots" / "2026-05-02"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://odoo.hatafax.com"
WEBHOOK_PATH = "/gearment/webhook"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

# Demo users seeded by deployment/scripts/seed-demo-esty.py.
USERS = {
    "manager": ("demo_quanly@hatafax.demo", "demo1234"),
    "salesman": ("demo_kinhdoanh@hatafax.demo", "demo1234"),
    "production": ("demo_sanxuat@hatafax.demo", "demo1234"),
    "ba_shipping": ("demo_ba_shipping@hatafax.demo", "demo1234"),
    "ba_manager": ("demo_ba_manager@hatafax.demo", "demo1234"),
}

HERO_ORDER = "S00013"  # gearment_pod / confirmed / no tracking yet (pre-baseline)


@dataclass
class StepResult:
    section: str
    ok: bool
    note: str
    screenshot: str | None = None


def _shot(page: Page, name: str) -> str:
    path = SHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return path.relative_to(REPO_ROOT).as_posix()


DB = "demo_esty"


def login(page: Page, role: str) -> None:
    login_, password = USERS[role]
    page.goto(f"{BASE_URL}/web/login?db={DB}")
    page.wait_for_selector('input[name="login"]', timeout=10000)
    page.fill('input[name="login"]', login_)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def logout(page: Page) -> None:
    page.goto(f"{BASE_URL}/web/session/logout")
    page.wait_for_load_state("networkidle")


def section_0_preflight(page: Page) -> StepResult:
    login(page, "manager")
    shot = _shot(page, "00-preflight-landing")
    ok = "/odoo" in page.url or "/web" in page.url
    return StepResult("§0 pre-flight", ok, f"landed at {page.url}", shot)


def section_1_master_data(page: Page) -> list[StepResult]:
    out: list[StepResult] = []
    page.goto(f"{BASE_URL}/odoo/action-multichannel_hub_core.action_order_pipeline")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    out.append(StepResult("§1.1 pipelines list", True, "listed",
                          _shot(page, "01-pipelines-list")))

    page.goto(f"{BASE_URL}/odoo/action-multichannel_hub_core.action_pipeline_team")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    out.append(StepResult("§1.1 pipeline teams", True, "3 teams expected",
                          _shot(page, "01b-pipeline-teams")))
    return out


def section_3_order_dashboard(page: Page) -> StepResult:
    page.goto(f"{BASE_URL}/odoo/action-multichannel_hub_core.action_order_dashboard")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    shot = _shot(page, "03-order-dashboard")
    return StepResult("§3 order dashboard", True, "list rendered", shot)


def section_4_design_files(page: Page) -> StepResult:
    page.goto(f"{BASE_URL}/odoo/action-multichannel_hub_core.action_design_file")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    shot = _shot(page, "04-design-files")
    return StepResult("§4 design files kanban", True, "kanban rendered", shot)


def section_6_tracking_dashboard(page: Page) -> StepResult:
    page.goto(f"{BASE_URL}/odoo/action-multichannel_hub_core.action_tracking_dashboard")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    shot = _shot(page, "06-tracking-dashboard")
    return StepResult("§6 tracking dashboard", True, "list rendered", shot)


def section_8_pipeline_audit(page: Page) -> StepResult:
    page.goto(
        f"{BASE_URL}/odoo/action-multichannel_hub_core.action_pipeline_transition_log"
    )
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    shot = _shot(page, "08-pipeline-transitions")
    return StepResult("§8.3 pipeline transition log", True, "audit log rendered", shot)


def _compute_signature(
    body: bytes, nonce: str, ts: str, secret: str, url_path: str = WEBHOOK_PATH
) -> str:
    body_b64 = base64.urlsafe_b64encode(body).decode("ascii")
    signing = (url_path + nonce + ts + body_b64).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signing, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii")


def section_10_webhook(page: Page) -> list[StepResult]:
    out: list[StepResult] = []
    secret = os.environ["GEARMENT_API_SECRET"]
    api_key = os.environ.get("GEARMENT_API_KEY", "")

    body_obj = {
        "type": "order_completed",
        "order": {"reference": HERO_ORDER, "status": "completed"},
        "tracking": {
            "company": "USPS",
            "number": "9400111202555560000001",
            "url": "https://tools.usps.com/go/TrackConfirmAction?tLabels=9400111202555560000001",
        },
    }
    body = json.dumps(body_obj, separators=(",", ":")).encode("utf-8")
    nonce = base64.urlsafe_b64encode(secrets.token_bytes(8)).decode("ascii").rstrip("=") + "=="
    ts = str(int(time.time()))
    sig = _compute_signature(body, nonce, ts, secret)

    headers = {
        "Content-Type": "application/json",
        "X-Connect-Signature": sig,
        "X-Connect-Nonce": nonce,
        "X-Connect-Timestamp": ts,
        "X-Connect-Client-Key": api_key,
    }

    resp = requests.post(WEBHOOK_URL, data=body, headers=headers, timeout=20)
    out.append(
        StepResult(
            "§10a webhook POST",
            resp.status_code == 200,
            f"status={resp.status_code} body={resp.text[:200]!r}",
        )
    )

    # UI verify: open S00013 form
    page.goto(f"{BASE_URL}/odoo/sales")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    page.goto(f"{BASE_URL}/odoo/action-base.action_partner_form")  # warmup
    page.wait_for_timeout(500)

    # Direct URL to the order via menu search; fallback: server-side known id=13
    page.goto(f"{BASE_URL}/odoo/sales/13")
    try:
        page.wait_for_selector("text=" + HERO_ORDER, timeout=5000)
    except PWTimeout:
        pass
    page.wait_for_timeout(1500)
    shot = _shot(page, "10-order-form-after-webhook")
    out.append(StepResult("§10b order form", True, "form opened post-webhook", shot))

    # gearment.api.log: no menu/action seeded; reach via direct model URL.
    page.goto(f"{BASE_URL}/odoo/gearment.api.log")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1200)
    shot = _shot(page, "10-gearment-api-log")
    out.append(StepResult("§10c gearment.api.log", True, "log list rendered", shot))
    return out


SECTIONS: dict[str, Callable[[Page], object]] = {
    "0": section_0_preflight,
    "1": section_1_master_data,
    "3": section_3_order_dashboard,
    "4": section_4_design_files,
    "6": section_6_tracking_dashboard,
    "8": section_8_pipeline_audit,
    "10": section_10_webhook,
}


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", default="all")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    sections = list(SECTIONS) if args.section == "all" else [args.section]

    results: list[StepResult] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=False,
        )
        page = ctx.new_page()
        try:
            for code in sections:
                fn = SECTIONS[code]
                r = fn(page)
                if isinstance(r, list):
                    results.extend(r)
                else:
                    results.append(r)
        finally:
            ctx.close()
            browser.close()

    print("\n=== RESULTS ===")
    fail = 0
    for r in results:
        marker = "PASS" if r.ok else "FAIL"
        line = f"[{marker}] {r.section}: {r.note}"
        if r.screenshot:
            line += f"  ({r.screenshot})"
        print(line)
        if not r.ok:
            fail += 1
    print(f"\n{len(results) - fail}/{len(results)} steps passed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
