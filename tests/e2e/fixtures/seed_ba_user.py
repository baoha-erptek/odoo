"""Seed (or reuse) low-privilege UAT users on staging.

Roles seeded (idempotent — rotates password on re-run):
  - uat_ba_user@hatafax.demo            BA User    (multichannel_hub_core.group_ba_user)
  - uat_ba_lead@hatafax.demo            BA Lead    (multichannel_hub_core.group_ba_lead)
  - uat_ba_shipping@hatafax.demo        BA Ship    (multichannel_hub_fulfillment.group_ba_shipping)
  - uat_ba_shipping_mgr@hatafax.demo    BA Ship Mgr(multichannel_hub_fulfillment.group_ba_manager)

Each role's final password is emitted as `<role>_PASSWORD=<value>` for the
Playwright globalSetup to parse. The original `BA_USER_PASSWORD=` line is
preserved verbatim so existing Flow-1 specs keep working.

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

# (env_var_key, login, display_name, [group_xmlids]). Order is significant:
# the first entry is the legacy "BA User" line consumed by Flow-1 globalSetup;
# other entries are emitted as `<env>_PASSWORD=<value>` for Flow-2/3.
# BA User/Lead ALSO carry Sales "All Documents": production BA people are
# salespeople too — the bare role group has no sale.order ACL, and the
# etsy shop-scope record rule presumes a sales read grant exists
# (TC-006 AccessError, 2026-07-04).
ROLES: list[tuple[str, str, str, list[str]]] = [
    ("BA_USER", "uat_ba_user@hatafax.demo", "UAT BA User (auto-seeded)",
     ["multichannel_hub_core.group_ba_user",
      "sales_team.group_sale_salesman_all_leads"]),
    ("BA_LEAD", "uat_ba_lead@hatafax.demo", "UAT BA Lead (auto-seeded)",
     ["multichannel_hub_core.group_ba_lead",
      "sales_team.group_sale_salesman_all_leads"]),
    ("BA_SHIPPING", "uat_ba_shipping@hatafax.demo", "UAT BA Shipping (auto-seeded)",
     ["multichannel_hub_fulfillment.group_ba_shipping",
      "sales_team.group_sale_salesman_all_leads"]),
    ("BA_SHIPPING_MGR", "uat_ba_shipping_mgr@hatafax.demo", "UAT BA Shipping Mgr (auto-seeded)",
     ["multichannel_hub_fulfillment.group_ba_manager",
      "sales_team.group_sale_salesman_all_leads"]),
]


def gen_password(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _resolve_group_id(s, xmlid: str) -> int | None:
    """Return the res.groups id for an xmlid, or None if the module is absent."""
    module, name = xmlid.split(".", 1)
    rows = s.call(
        "ir.model.data",
        "search_read",
        [[("module", "=", module), ("name", "=", name)]],
        {"fields": ["res_id", "model"], "limit": 1},
    )
    if not rows or rows[0]["model"] != "res.groups":
        return None
    return rows[0]["res_id"]


def _upsert_user(s, login: str, name: str, group_ids: list[int]) -> tuple[int, str]:
    """Create or reuse the named user. Returns (uid, password)."""
    existing = s.call(
        "res.users",
        "search",
        [[("login", "=", login)]],
        {"context": {"active_test": False}},
    )
    pwd = gen_password()
    if existing:
        uid = existing[0]
        s.call(
            "res.users",
            "write",
            [[uid], {
                "password": pwd,
                "active": True,
                "group_ids": [(4, gid) for gid in group_ids],
            }],
        )
        log.info("reused user uid=%s login=%s groups=%s", uid, login, group_ids)
        return uid, pwd
    try:
        uid = s.call(
            "res.users",
            "create",
            [{
                "login": login,
                "name": name,
                "password": pwd,
                "group_ids": [(6, 0, group_ids)],
            }],
        )
    except Exception as e:
        log.error("create failed for %s — retrying via search: %s", login, e)
        existing = s.call(
            "res.users",
            "search",
            [[("login", "=", login)]],
            {"context": {"active_test": False}},
        )
        if not existing:
            raise SystemExit(3)
        uid = existing[0]
        s.call(
            "res.users",
            "write",
            [[uid], {"password": pwd, "active": True, "group_ids": [(4, gid) for gid in group_ids]}],
        )
    log.info("created user uid=%s login=%s groups=%s", uid, login, group_ids)
    return uid, pwd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    s = connect(base_url=args.base_url, db=args.db)

    for env_key, login, name, xmlids in ROLES:
        group_ids = []
        for xmlid in xmlids:
            group_id = _resolve_group_id(s, xmlid)
            if group_id is None:
                log.warning("group %s not found — skipping for %s "
                            "(module not installed?)", xmlid, login)
                continue
            group_ids.append(group_id)
        if not group_ids:
            log.warning("no resolvable groups for %s — skipping", login)
            continue
        uid, pwd = _upsert_user(s, login, name, group_ids)
        print(f"{env_key}_PASSWORD={pwd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
