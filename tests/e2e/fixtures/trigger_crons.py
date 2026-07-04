"""Phase D residual #1 — fire selected ir.cron records on staging.

Some specs (notably Flow-2 TC-003) require at least one fresh
`etsy.api.log` row with `http_status` in [200, 299] in the last 24h. The
cron that produces those rows runs every 5 minutes on staging, but a fresh
CI run may land between cron ticks (or hit a transient 5xx on the prior
tick). Triggering the cron once at globalSetup-time produces a known-fresh
log row before the spec asserts on it.

Best-effort: failures here are surfaced as warnings, not hard errors. If
the cron itself fails (Etsy 4xx/5xx), the spec assertion will surface the
real issue instead — that's the right place for it, not here.

Usage:
    STAGING_ADMIN_PASSWORD=... python3 fixtures/trigger_crons.py
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _xmlrpc_session import connect  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("trigger_crons")

# Loose-match on `name ilike` so owner renames don't break the trigger.
CRON_NAME_FRAGMENTS = (
    "Etsy: API Receipts Sync",
)


def _trigger_one(s, fragment: str) -> bool:
    ids = s.call(
        "ir.cron",
        "search",
        [[("name", "ilike", fragment), ("active", "=", True)]],
        {"limit": 5},
    )
    if not ids:
        log.warning("trigger_crons: no active cron matches %r — skip", fragment)
        return False
    try:
        s.call("ir.cron", "method_direct_trigger", [ids])
    except Exception as exc:
        log.warning("trigger_crons: %r method_direct_trigger raised: %s", fragment, exc)
        return False
    log.info("trigger_crons: fired %r (ids=%s)", fragment, ids)
    return True


def _report_recent_api_log(s) -> None:
    if not s.call("ir.model", "search",
                  [[("model", "=", "etsy.api.log")]], {"limit": 1}):
        return
    since = (datetime.utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    rows = s.call(
        "etsy.api.log",
        "search_read",
        [[("create_date", ">=", since)]],
        {"fields": ["id", "http_status", "error_message"],
         "order": "create_date desc", "limit": 5},
    )
    if not rows:
        log.warning("trigger_crons: etsy.api.log has 0 rows in last 24h after trigger — "
                    "spec TC-003 will fail; check cron code and Etsy token state")
        return
    log.info("trigger_crons: %d recent etsy.api.log rows; last 5: %s",
             len(rows),
             [(r["id"], r.get("http_status"), bool(r.get("error_message"))) for r in rows])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    try:
        s = connect(base_url=args.base_url, db=args.db)
    except SystemExit as e:
        log.error("trigger_crons: connect failed — %s", e)
        return 0  # best-effort

    for fragment in CRON_NAME_FRAGMENTS:
        _trigger_one(s, fragment)
    _report_recent_api_log(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
