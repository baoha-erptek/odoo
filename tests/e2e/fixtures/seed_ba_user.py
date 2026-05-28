"""Seed (or reuse) a low-privilege BA User on staging for UAT TC-006/TC-007.

Behaviour:
  - Idempotent: if uat_ba_user@hatafax.demo exists, rotate password instead of creating.
  - Assigns ONLY multichannel_hub_core.group_ba_user (+ base.group_user implied).
  - Prints final line `BA_USER_PASSWORD=<value>` for Playwright globalSetup to consume.

Usage:
  STAGING_ADMIN_PASSWORD=... python3 seed_ba_user.py [--base-url URL] [--db DB]
"""
from __future__ import annotations

import argparse
import logging
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _xmlrpc_session import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_ba_user")

LOGIN = "uat_ba_user@hatafax.demo"
NAME = "UAT BA User (auto-seeded)"
GROUP_XMLID = "multichannel_hub_core.group_ba_user"


def gen_password(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    s = connect(base_url=args.base_url, db=args.db)

    # 1. Resolve group_ba_user xmlid → res.groups id (via ir.model.data public search)
    module, name = GROUP_XMLID.split(".", 1)
    rows = s.call(
        "ir.model.data",
        "search_read",
        [[("module", "=", module), ("name", "=", name)]],
        {"fields": ["res_id", "model"], "limit": 1},
    )
    if not rows:
        log.error("Group %s not found on staging (ir.model.data lookup empty)", GROUP_XMLID)
        raise SystemExit(2)
    if rows[0]["model"] != "res.groups":
        log.error("xmlid %s resolves to model %s, expected res.groups", GROUP_XMLID, rows[0]["model"])
        raise SystemExit(2)
    group_id = rows[0]["res_id"]
    log.info("group_ba_user resolved to id=%s", group_id)

    # 2. Look up existing user (active OR archived) — search by login, all variants
    existing = s.call(
        "res.users",
        "search",
        [[("login", "=", LOGIN)]],
        {"context": {"active_test": False}},
    )

    pwd = gen_password()
    if existing:
        uid = existing[0]
        log.info("Reusing existing res.users id=%s — rotating password + ensuring active + group", uid)
        s.call(
            "res.users",
            "write",
            [[uid], {
                "password": pwd,
                "active": True,
                "group_ids": [(4, group_id)],
            }],
        )
    else:
        log.info("Creating new BA User login=%s", LOGIN)
        try:
            uid = s.call(
                "res.users",
                "create",
                [{
                    "login": LOGIN,
                    "name": NAME,
                    "password": pwd,
                    "group_ids": [(6, 0, [group_id])],
                }],
            )
        except Exception as e:
            log.error("create failed (possibly UNIQUE-login race): %s — retrying via search", e)
            existing = s.call(
                "res.users",
                "search",
                [[("login", "=", LOGIN)]],
                {"context": {"active_test": False}},
            )
            if not existing:
                raise SystemExit(3)
            uid = existing[0]
            s.call(
                "res.users",
                "write",
                [[uid], {"password": pwd, "active": True, "group_ids": [(4, group_id)]}],
            )

    # 3. Final-line contract for globalSetup.ts to parse
    log.info("BA User ready: uid=%s login=%s", uid, LOGIN)
    print(f"BA_USER_PASSWORD={pwd}")


if __name__ == "__main__":
    main()
