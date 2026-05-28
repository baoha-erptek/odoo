"""Idempotent UAT seed for the v1.2 product-creation suite (ESTY-183).

Ensures the staging DB has the data the standard-form UAT depends on:
  1. Family-wired product categories  Mug->MUG, Apron->APR, Doormat->DMT
     (auto-SKU resolves categ_id._get_sku_family_chain()).
  2. A legacy-SKU product for the SKU-Drift TCs (TC-003/004):
     name 'UAT-TAOSP Legacy Mug', default_code 'UAT-MUG-001'
     -> x_sku_v2_status = 'non_canonical'.
  3. product.tag rows for the tag-rule TC (TC-008): uat-tag-01..15 (valid)
     plus one 21-char tag (length-violation fixture). The form field is
     no_create_edit, so tags must pre-exist to be selectable.

Safe to re-run: every step checks for existing records first. Teardown is
handled by cleanup_uat_data.py (archives UAT products) — tags/categories are
left in place (cheap, reusable across runs).

Usage:
    python3 fixtures/seed_uat_data.py --db esty_odoo19
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _xmlrpc_session import connect  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed_uat")

ETSY_PARENT_NAME = "Etsy Products"
CATEGORY_FAMILY = [
    ("Mug", "mhc_sku_family_mug"),
    ("Apron", "mhc_sku_family_apr"),
    ("Doormat", "mhc_sku_family_dmt"),
]
LEGACY_NAME = "UAT-TAOSP Legacy Mug"
LEGACY_CODE = "UAT-MUG-001"
VALID_TAGS = [f"uat-tag-{i:02d}" for i in range(1, 16)]   # 15 valid tags
LONG_TAG = "uat" + "a" * 18                               # 21 chars (>20 -> violation)


def _fam_resid(s, xmlid: str) -> int | None:
    d = s.call("ir.model.data", "search_read",
               [[("model", "=", "mhc.sku.family"),
                 ("module", "=", "multichannel_hub_core"),
                 ("name", "=", xmlid)]],
               {"fields": ["res_id"], "limit": 1})
    return d[0]["res_id"] if d else None


def seed_categories(s) -> dict[str, int]:
    parents = s.call("product.category", "search", [[("name", "=", ETSY_PARENT_NAME)]], {"limit": 1})
    parent_id = parents[0] if parents else False
    out: dict[str, int] = {}
    for name, fam_xmlid in CATEGORY_FAMILY:
        fam_id = _fam_resid(s, fam_xmlid)
        if not fam_id:
            log.warning("family xmlid %s not found — skipping %s", fam_xmlid, name)
            continue
        existing = s.call("product.category", "search_read", [[("name", "=", name)]],
                          {"fields": ["id", "x_sku_family_id"], "limit": 1})
        if existing:
            cid = existing[0]["id"]
            cur = existing[0].get("x_sku_family_id")
            if not cur or cur[0] != fam_id:
                s.call("product.category", "write", [[cid], {"x_sku_family_id": fam_id}])
                log.info("category %-10s re-wired -> family %s", name, fam_xmlid)
            else:
                log.info("category %-10s already wired", name)
        else:
            vals = {"name": name, "x_sku_family_id": fam_id}
            if parent_id:
                vals["parent_id"] = parent_id
            cid = s.call("product.category", "create", [vals])
            log.info("category %-10s created id=%s -> family %s", name, cid, fam_xmlid)
        out[name] = cid
    return out


def seed_legacy_product(s, mug_categ_id: int) -> int:
    existing = s.call("product.template", "search",
                      [[("default_code", "=", LEGACY_CODE)]],
                      {"context": {"active_test": False}})
    if existing:
        log.info("legacy product %s already present (id=%s)", LEGACY_CODE, existing[0])
        return existing[0]
    tid = s.call("product.template", "create", [{
        "name": LEGACY_NAME,
        "default_code": LEGACY_CODE,
        "categ_id": mug_categ_id,
        "list_price": 9.99,
    }])
    rec = s.call("product.template", "read", [[tid], ["default_code", "x_sku_v2_status"]])[0]
    log.info("legacy product created id=%s code=%s status=%s",
             tid, rec["default_code"], rec.get("x_sku_v2_status"))
    return tid


def seed_tags(s) -> None:
    for name in VALID_TAGS + [LONG_TAG]:
        found = s.call("product.tag", "search", [[("name", "=", name)]], {"limit": 1})
        if not found:
            s.call("product.tag", "create", [{"name": name}])
    log.info("product.tag fixtures present: %d valid + 1 long (21-char)", len(VALID_TAGS))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    s = connect(base_url=args.base_url, db=args.db)
    log.info("Seeding UAT data on base=%s db=%s", s.cfg.base_url, s.cfg.db)

    cats = seed_categories(s)
    if "Mug" in cats:
        seed_legacy_product(s, cats["Mug"])
    seed_tags(s)
    log.info("UAT seed complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
