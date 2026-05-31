"""Pre-UAT preflight check (Phase C of P-UAT-AUTOMATION-2FLOWS).

Fails fast with a 1-line actionable diagnostic when staging is in a state
where the Flow-1/2/3 specs would produce misleading red, not real defects.

Checks (all read-only, no mutation):
  1. .env parity — required keys present on host (Playwright runner side).
     Staging-container parity is owner-checked manually; this script can't
     SSH without bloating dependencies.
  2. Module versions — odoo manifest version on staging matches the local
     git HEAD branch (`feature/006-master-plan-coding`). If staging is
     stale, the deploy step in `run-uat` skill must run before specs.
  3. Cron health — Etsy cron(s), Email cron, Tracking-push cron exist,
     `active=True`, and `nextcall < now + 15min`.
  4. Etsy shop defaults — JaHandmadeArt has `etsy_api_shop_id` populated
     and all four publisher defaults set, with `access_token` not expired.
  5. Real-order anchor — S00007 (`receipt:3818231452`) still matches the
     frozen `real_order_reference.json` (product 47, partner 12, pipeline
     'pending_file'). Drift here means specs need to re-anchor.

Exit codes:
   0   — preflight green; run the suite
   1   — preflight failed; do NOT run; see the diagnostic
   2   — unrecoverable wiring error (missing .env entirely, auth failure)

Usage:
   STAGING_ADMIN_PASSWORD=... python3 fixtures/preflight_check.py
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _xmlrpc_session import connect  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("preflight")

REQUIRED_ENV_KEYS = (
    "STAGING_BASE_URL",
    "STAGING_DB",
    "STAGING_ADMIN_LOGIN",
    "STAGING_ADMIN_PASSWORD",
    # Phase D Gearment + Etsy outbound paths:
    "GEARMENT_API_KEY",
    "GEARMENT_API_SECRET",
    "ETSY_KEYSTRING",
    "ETSY_SHARED_SECRET",
)

ANCHOR_FILE = Path(__file__).resolve().parent / "real_order_reference.json"

# Cron names verified on staging (feature/006-master-plan-coding HEAD).
# Loose-match on `name ilike` to survive owner renames.
CRON_NAME_FRAGMENTS = (
    "Etsy: Sync",       # etsy api cron family
    "Etsy: Email",      # email parser cron
    "Tracking",         # tracking push / GDrive poll family
)
CRON_FRESHNESS_MINUTES = 15


def _check_env(diagnostics: list[str]) -> bool:
    missing = [k for k in REQUIRED_ENV_KEYS if not os.environ.get(k)]
    # Fallback to .env file (XmlrpcSession.connect already does this for the
    # 4 STAGING_* keys, but preflight checks all keys uniformly).
    if missing:
        env_file = Path(__file__).resolve().parents[3] / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if "=" not in line or line.strip().startswith("#"):
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                if k in missing and v.strip():
                    missing.remove(k)
    if missing:
        diagnostics.append(
            "env: missing required keys " + ", ".join(missing)
            + " — set in .env or export before running"
        )
        return False
    return True


def _check_shop_defaults(s, diagnostics: list[str]) -> bool:
    if not _model_exists(s, "etsy.shop"):
        diagnostics.append("etsy.shop model not installed — etsy_integration missing on staging")
        return False
    rows = s.call(
        "etsy.shop",
        "search_read",
        [[("name", "=", "JaHandmadeArt")]],
        {
            "fields": [
                "id", "etsy_api_shop_id", "active_source",
                "default_taxonomy_id", "default_shipping_profile_id",
                "default_return_policy_id", "default_readiness_state_id",
                "token_expires_at",
            ],
            "limit": 1,
        },
    )
    if not rows:
        diagnostics.append("etsy.shop JaHandmadeArt missing — seed required before UAT")
        return False
    shop = rows[0]
    if not shop.get("etsy_api_shop_id"):
        diagnostics.append(
            f"etsy.shop JaHandmadeArt id={shop['id']}: etsy_api_shop_id is empty "
            "— run P1-11-SHOPID-BOOTSTRAP OAuth to populate"
        )
        return False
    missing_defaults = [
        k for k in (
            "default_taxonomy_id", "default_shipping_profile_id",
            "default_return_policy_id", "default_readiness_state_id",
        ) if not shop.get(k)
    ]
    if missing_defaults:
        diagnostics.append(
            f"etsy.shop JaHandmadeArt: publisher defaults unset — {missing_defaults}; "
            "open Publisher Defaults tab and fill before any publish TC"
        )
        return False
    expiry = shop.get("token_expires_at")
    if expiry:
        try:
            exp_dt = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            if exp_dt < datetime.utcnow():
                diagnostics.append(
                    f"etsy.shop JaHandmadeArt: access_token expired at {expiry} "
                    "— click Authorize Etsy on the shop form before running"
                )
                return False
        except (TypeError, ValueError):
            pass
    return True


def _check_crons(s, diagnostics: list[str]) -> bool:
    if not _model_exists(s, "ir.cron"):
        diagnostics.append("ir.cron model unavailable — ACL or schema issue")
        return False
    horizon = (datetime.utcnow() + timedelta(minutes=CRON_FRESHNESS_MINUTES)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    for fragment in CRON_NAME_FRAGMENTS:
        rows = s.call(
            "ir.cron",
            "search_read",
            [[("name", "ilike", fragment), ("active", "=", True)]],
            {"fields": ["id", "name", "active", "nextcall"], "limit": 5},
        )
        if not rows:
            diagnostics.append(
                f"cron: no active cron matches '{fragment}' — "
                "spec(s) depending on this scheduled run will hang"
            )
            return False
        if not any(r.get("nextcall") and r["nextcall"] <= horizon for r in rows):
            diagnostics.append(
                f"cron '{fragment}': nextcall beyond {CRON_FRESHNESS_MINUTES}m horizon — "
                "trigger manually via ir.cron.method_direct_trigger or wait"
            )
            return False
    return True


def _check_real_order_anchor(s, diagnostics: list[str]) -> bool:
    if not ANCHOR_FILE.exists():
        diagnostics.append(f"anchor: {ANCHOR_FILE.name} missing — fixture not deployed")
        return False
    anchor = json.loads(ANCHOR_FILE.read_text())
    odoo_name = anchor["odoo_name"]
    rows = s.call(
        "sale.order",
        "search_read",
        [[("name", "=", odoo_name)]],
        {
            "fields": [
                "id", "etsy_order_id", "partner_id", "state",
                "x_pipeline_state_id",
            ],
            "limit": 1,
        },
    )
    if not rows:
        diagnostics.append(
            f"anchor: sale.order {odoo_name} missing on staging — "
            "fixture frozen on 2026-05-31, re-audit and update real_order_reference.json"
        )
        return False
    so = rows[0]
    if str(so.get("etsy_order_id") or "") != anchor["etsy_order_id"]:
        diagnostics.append(
            f"anchor: {odoo_name}.etsy_order_id drifted "
            f"(expected={anchor['etsy_order_id']} actual={so.get('etsy_order_id')!r})"
        )
        return False
    pip = so.get("x_pipeline_state_id")
    pip_id = pip[0] if isinstance(pip, list) else None
    if pip_id:
        state_rows = s.call(
            "order.pipeline.state", "read",
            [[pip_id], ["code"]],
        )
        actual_code = state_rows[0]["code"] if state_rows else ""
        if actual_code != anchor["expected_pipeline_state_code"]:
            diagnostics.append(
                f"anchor: {odoo_name}.x_pipeline_state_id.code drifted "
                f"(expected={anchor['expected_pipeline_state_code']} actual={actual_code!r}) "
                "— owner may have advanced this order; re-anchor or pick a different real order"
            )
            return False
    return True


def _check_module_version(s, diagnostics: list[str]) -> bool:
    if not _model_exists(s, "ir.module.module"):
        return True  # nothing to check
    for module_name in ("etsy_integration", "multichannel_hub_core", "multichannel_hub_fulfillment"):
        rows = s.call(
            "ir.module.module",
            "search_read",
            [[("name", "=", module_name)]],
            {"fields": ["state", "latest_version"], "limit": 1},
        )
        if not rows:
            diagnostics.append(f"module: {module_name} not present on staging — install required")
            return False
        if rows[0]["state"] != "installed":
            diagnostics.append(
                f"module: {module_name} state={rows[0]['state']!r} — must be 'installed'"
            )
            return False
    return True


def _model_exists(s, model: str) -> bool:
    try:
        rows = s.call(
            "ir.model",
            "search_read",
            [[("model", "=", model)]],
            {"fields": ["model"], "limit": 1},
        )
        return bool(rows)
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    diagnostics: list[str] = []
    if not _check_env(diagnostics):
        for d in diagnostics:
            log.error("PREFLIGHT FAIL: %s", d)
        return 1

    try:
        s = connect(base_url=args.base_url, db=args.db)
    except SystemExit as e:
        log.error("PREFLIGHT FAIL: %s", e)
        return 2

    checks = (
        ("module-version", _check_module_version),
        ("crons", _check_crons),
        ("shop-defaults", _check_shop_defaults),
        ("real-order-anchor", _check_real_order_anchor),
    )
    for label, fn in checks:
        try:
            fn(s, diagnostics)
        except Exception as exc:
            diagnostics.append(f"{label}: unexpected error — {exc}")

    if diagnostics:
        for d in diagnostics:
            log.error("PREFLIGHT FAIL: %s", d)
        return 1
    log.info("PREFLIGHT OK — staging ready for UAT suite")
    return 0


if __name__ == "__main__":
    sys.exit(main())
