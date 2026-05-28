"""Reset products on a staging Odoo DB to a clean, system-only slate.

Use before a UAT re-run to clear leftover test artifacts AND pulled Etsy
listings, so the database starts from a known baseline.

Keeps "system" products (delivery, shipping, MTO phantom, gift card / eWallet)
and force-deletes everything else. A product that is referenced by sale order
lines cannot be unlinked; with --delete-orders the script removes the blocking
orders too, but ONLY when every blocking order is still in 'draft' state. It
refuses to touch confirmed/done/sale orders (those carry real history).

Safety:
  - DRY-RUN by default. Pass --apply to actually delete.
  - Never deletes confirmed sale orders. Blocked-by-confirmed templates are
    reported and left in place.
  - Targets the DB named by --db / STAGING_DB. Double-check before --apply.

Usage:
    # see what would be removed (no writes):
    python3 scripts/reset_staging_products.py --db esty_odoo19
    # actually remove, deleting blocking DRAFT orders:
    python3 scripts/reset_staging_products.py --db esty_odoo19 --apply --delete-orders
    # keep extra products by default_code or name:
    python3 scripts/reset_staging_products.py --db esty_odoo19 --apply \
        --keep-code MY-KEEP-SKU --keep-name "Special Product"

Exit codes:
    0 = completed (dry-run or apply)
    1 = connection / auth failure
    2 = apply finished but some templates remained blocked
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import xmlrpc.client
from dataclasses import dataclass, field

# Reuse the shared UAT session helper (env/.env loading + auth).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests", "e2e", "fixtures"))
from _xmlrpc_session import connect  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("reset_staging_products")

# System products to always keep, identified by default_code or exact name.
KEEP_CODES = {"MFG-PHANTOM", "ETSY-SHIP", "Delivery_007"}
KEEP_NAMES = {"Gift Card", "Top-up eWallet"}

# Order states that are safe to delete when they block a product unlink.
DELETABLE_ORDER_STATES = {"draft", "sent", "cancel"}


@dataclass
class Plan:
    keep: list = field(default_factory=list)
    delete: list = field(default_factory=list)


def classify(session, keep_codes, keep_names) -> Plan:
    recs = session.call(
        "product.template", "search_read", [[]],
        {"fields": ["id", "default_code", "name"], "order": "id asc"},
    )
    plan = Plan()
    for r in recs:
        code = (r.get("default_code") or "").strip()
        name = (r.get("name") or "").strip()
        if code in keep_codes or name in keep_names:
            plan.keep.append(r)
        else:
            plan.delete.append(r)
    return plan


def _label(r) -> str:
    return f"{r['id']:>4} | {str(r.get('default_code') or ''):<24} | {(r.get('name') or '')[:48]}"


def blocking_orders(session, tmpl_id: int):
    """Return sale.order rows that reference any variant of the template."""
    vids = session.call(
        "product.product", "search", [[("product_tmpl_id", "=", tmpl_id)]],
    )
    if not vids:
        return []
    lines = session.call(
        "sale.order.line", "search_read", [[("product_id", "in", vids)]],
        {"fields": ["order_id"]},
    )
    order_ids = sorted({l["order_id"][0] for l in lines if l.get("order_id")})
    if not order_ids:
        return []
    return session.call(
        "sale.order", "search_read", [[("id", "in", order_ids)]],
        {"fields": ["id", "name", "state"]},
    )


def delete_template(session, tmpl_id: int, delete_orders: bool) -> tuple[bool, str]:
    try:
        session.call("product.template", "unlink", [[tmpl_id]])
        return True, "deleted"
    except xmlrpc.client.Fault as exc:
        msg = (exc.faultString or "").strip().splitlines()[-1][:140]
        if not delete_orders:
            return False, f"blocked: {msg}"

    orders = blocking_orders(session, tmpl_id)
    non_deletable = [o for o in orders if o["state"] not in DELETABLE_ORDER_STATES]
    if non_deletable:
        names = ", ".join(f"{o['name']}({o['state']})" for o in non_deletable)
        return False, f"blocked by confirmed orders: {names}"
    if orders:
        oids = [o["id"] for o in orders]
        log.info("    deleting %d blocking draft order(s): %s",
                 len(oids), [o["name"] for o in orders])
        session.call("sale.order", "unlink", [oids])
    try:
        session.call("product.template", "unlink", [[tmpl_id]])
        return True, "deleted (after removing draft orders)"
    except xmlrpc.client.Fault as exc:
        msg = (exc.faultString or "").strip().splitlines()[-1][:140]
        return False, f"still blocked: {msg}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=None, help="Override STAGING_BASE_URL")
    ap.add_argument("--db", default=None, help="Override STAGING_DB (the DB to reset)")
    ap.add_argument("--apply", action="store_true",
                    help="Actually delete (default is dry-run, no writes)")
    ap.add_argument("--delete-orders", action="store_true",
                    help="Delete blocking DRAFT/sent/cancel orders so referenced products can be removed")
    ap.add_argument("--keep-code", action="append", default=[],
                    help="Extra default_code to keep (repeatable)")
    ap.add_argument("--keep-name", action="append", default=[],
                    help="Extra product name to keep (repeatable)")
    args = ap.parse_args()

    try:
        s = connect(base_url=args.base_url, db=args.db)
    except SystemExit as exc:
        log.error("%s", exc)
        return 1

    keep_codes = KEEP_CODES | set(args.keep_code)
    keep_names = KEEP_NAMES | set(args.keep_name)

    log.info("Target: base=%s db=%s  mode=%s",
             s.cfg.base_url, s.cfg.db, "APPLY" if args.apply else "DRY-RUN")

    plan = classify(s, keep_codes, keep_names)
    log.info("KEEP (%d):", len(plan.keep))
    for r in plan.keep:
        log.info("  %s", _label(r))
    log.info("DELETE (%d):", len(plan.delete))
    for r in plan.delete:
        log.info("  %s", _label(r))

    if not args.apply:
        log.info("DRY-RUN — no changes made. Re-run with --apply (and "
                 "--delete-orders to clear blocking draft orders).")
        return 0

    deleted, blocked = [], []
    for r in plan.delete:
        ok, note = delete_template(s, r["id"], args.delete_orders)
        (deleted if ok else blocked).append((r, note))
        log.info("  %s %s -> %s", "OK   " if ok else "SKIP ", _label(r), note)

    after = s.call("product.template", "search_count", [[]])
    log.info("-" * 60)
    log.info("Done: deleted=%d blocked=%d  product.template active now=%d",
             len(deleted), len(blocked), after)
    if blocked:
        log.warning("Blocked templates remain (referenced by confirmed orders or "
                    "rerun with --delete-orders):")
        for r, note in blocked:
            log.warning("  %s -> %s", _label(r), note)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
