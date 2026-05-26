"""Clean up UAT artifacts on staging after a Playwright suite.

Archives:
  - product.template records with default_code LIKE 'UAT-%'
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
BA_USER_LOGIN = "uat_ba_user@hatafax.demo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    s = connect(base_url=args.base_url, db=args.db)

    # 1. Archive UAT products
    pids = s.call(
        "product.template",
        "search",
        [[("default_code", "=like", f"{UAT_SKU_PREFIX}%")]],
        {"context": {"active_test": False}},
    )
    if pids:
        log.info("Archiving %d UAT product templates: %s", len(pids), pids)
        s.call("product.template", "write", [pids, {"active": False}])
    else:
        log.info("No UAT product templates found to archive")

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
