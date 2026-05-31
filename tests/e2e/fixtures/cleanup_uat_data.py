"""Clean up UAT artifacts on staging after a Playwright suite.

Archives:
  - product.template records with default_code LIKE 'UAT-%' (legacy wizard TC-001..007)
  - product.template records with name LIKE 'UAT-SKU-BUILDER%' (builder wizard TC-008..011 —
    these have deterministic SKUs like 'MUG-CR-F11' that we don't want to filter on)
  - res.users with login = uat_ba_user@hatafax.demo

Does NOT delete:
  - Etsy draft listings (owner clears manually per P-PUB-E2E protocol)
  - product.channel.status rows (cascade with product archive is safer than unlink)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _xmlrpc_session import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cleanup_uat")

UAT_SKU_PREFIX = "UAT-"
UAT_BUILDER_NAME_PREFIX = "UAT-SKU-BUILDER"
UAT_FORM_NAME_PREFIX = "UAT-TAOSP"  # v1.2 standard-form suite product names
UAT_ORDER_REF_PREFIX = "UAT-2026-05-31"  # Flow-2/3 seed_uat_orders() naming
UAT_EMAIL_DEDUP_GMAIL_ID = "uat-2026-05-31-dedupe-fixture-msg-id"
BA_USER_LOGIN = "uat_ba_user@hatafax.demo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    s = connect(base_url=args.base_url, db=args.db)

    # 1. Archive UAT products — OR domain across the known UAT markers.
    #    NOTE: the legacy SKU-drift fixture (UAT-MUG-001) matches UAT_SKU_PREFIX
    #    and is intentionally archived here too (seed re-creates it on next run).
    pids = s.call(
        "product.template",
        "search",
        [[
            "|", "|",
            ("default_code", "=like", f"{UAT_SKU_PREFIX}%"),
            ("name", "=like", f"{UAT_BUILDER_NAME_PREFIX}%"),
            ("name", "=like", f"{UAT_FORM_NAME_PREFIX}%"),
        ]],
        {"context": {"active_test": False}},
    )
    if pids:
        log.info("Archiving %d UAT product templates: %s", len(pids), pids)
        s.call("product.template", "write", [pids, {"active": False}])
    else:
        log.info("No UAT product templates found to archive")

    # 1b. Cancel UAT-2026-05-31-* sale.order rows still in draft. Confirmed orders
    #     are left for owner review (per plan file Phase 1 partition).
    oids = s.call(
        "sale.order",
        "search",
        [[
            ("client_order_ref", "=like", f"{UAT_ORDER_REF_PREFIX}%"),
            ("state", "in", ["draft", "sent"]),
        ]],
        {"context": {"active_test": False}},
    )
    if oids:
        log.info("Cancelling %d UAT-2026-05-31-* draft sale.order rows: %s", len(oids), oids)
        try:
            s.call("sale.order", "action_cancel", [oids])
        except Exception as e:
            log.warning("action_cancel failed (continuing): %s", e)

    # 1c. Unlink the dedupe email-log fixture (safe — it's parse_status=skipped,
    #     no downstream side effect). Wrapped in try/except: model may be absent.
    try:
        eids = s.call(
            "etsy.email.log",
            "search",
            [[("gmail_message_id", "=", UAT_EMAIL_DEDUP_GMAIL_ID)]],
            {"context": {"active_test": False}},
        )
        if eids:
            log.info("Unlinking %d email-log dedupe fixture rows: %s", len(eids), eids)
            s.call("etsy.email.log", "unlink", [eids])
    except Exception as e:
        log.info("email-log cleanup skipped (model absent or insufficient ACL): %s", e)

    # 2. Archive BA User
    uids = s.call(
        "res.users",
        "search",
        [[("login", "=", BA_USER_LOGIN)]],
        {"context": {"active_test": False}},
    )
    if uids:
        log.info("Archiving BA User uid=%s", uids[0])
        s.call("res.users", "write", [uids, {"active": False}])

    log.info("UAT cleanup complete")


if __name__ == "__main__":
    main()
