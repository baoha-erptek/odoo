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

# Flow-2 + Flow-3 order fixtures (P-UAT-AUTOMATION-2FLOWS, 2026-05-31).
# Naming convention `UAT-2026-05-31-{kind}-NNN` so cleanup can sweep via
# `name ilike 'UAT-2026-05-31-'` without touching real orders. Teardown
# archives only draft/cancel state; confirmed orders are left for review.
UAT_ORDER_PREFIX = "UAT-2026-05-31"
UAT_MTO_PRODUCT_CODE = "UAT-MTO-RDISH"      # MTO: no Gearment SKU -> manual route
UAT_DROP_PRODUCT_CODE = "UAT-DROP-MUG"       # Dropship: x_gearment_sku populated
UAT_DROP_GEARMENT_SKU = "GEAR-UAT-MUG-001"
UAT_ADDR_PRODUCT_CODE = "UAT-ADDR-DOORMAT"   # any product; partner needs an Etsy-shaped address
UAT_PARTNER_NAME = "UAT Buyer Auto"
UAT_EMAIL_DEDUP_GMAIL_ID = "uat-2026-05-31-dedupe-fixture-msg-id"


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


def _ensure_partner(s) -> int:
    """Idempotent: returns an existing or freshly created res.partner suitable
    as an Etsy buyer (street + city + country populated, so address-change TC
    has something to diff against).
    """
    existing = s.call("res.partner", "search",
                      [[("name", "=", UAT_PARTNER_NAME)]],
                      {"limit": 1, "context": {"active_test": False}})
    if existing:
        s.call("res.partner", "write", [existing, {"active": True}])
        return existing[0]
    country_ids = s.call("res.country", "search", [[("code", "=", "US")]], {"limit": 1})
    vals = {
        "name": UAT_PARTNER_NAME,
        "street": "123 UAT Lane",
        "city": "Springfield",
        "zip": "62704",
        "email": "uat-buyer@hatafax.demo",
        "phone": "+1-555-0100",
    }
    if country_ids:
        vals["country_id"] = country_ids[0]
    pid = s.call("res.partner", "create", [vals])
    log.info("partner created id=%s name=%s", pid, UAT_PARTNER_NAME)
    return pid


def _ensure_simple_product(s, code: str, name: str, list_price: float,
                           gearment_sku: str | None = None,
                           categ_id: int | None = None) -> int:
    """Idempotent product.template fixture for the SO-line backing product."""
    existing = s.call("product.template", "search",
                      [[("default_code", "=", code)]],
                      {"context": {"active_test": False}})
    if existing:
        s.call("product.template", "write", [existing, {"active": True}])
        return existing[0]
    vals = {
        "name": name,
        "default_code": code,
        "list_price": list_price,
        "type": "consu",
        "sale_ok": True,
    }
    if categ_id:
        vals["categ_id"] = categ_id
    if gearment_sku:
        vals["x_gearment_sku"] = gearment_sku
    tid = s.call("product.template", "create", [vals])
    log.info("product created id=%s code=%s gearment_sku=%s", tid, code, gearment_sku or "(none)")
    return tid


def _product_variant_for_template(s, template_id: int) -> int:
    """Returns the first product.product variant for the given template."""
    rec = s.call("product.template", "read", [[template_id], ["product_variant_id"]])[0]
    variant = rec.get("product_variant_id")
    if isinstance(variant, list) and variant:
        return variant[0]
    pids = s.call("product.product", "search", [[("product_tmpl_id", "=", template_id)]], {"limit": 1})
    if pids:
        return pids[0]
    raise RuntimeError(f"template {template_id} has no product.product variant")


def _ensure_uat_order(s, name: str, partner_id: int, product_id: int,
                      quantity: float = 1.0,
                      price_unit: float | None = None) -> int:
    """Idempotent sale.order keyed by `client_order_ref` (we use the UAT name
    there because sale.order.name is auto-numbered).
    """
    existing = s.call("sale.order", "search",
                      [[("client_order_ref", "=", name)]],
                      {"context": {"active_test": False}})
    if existing:
        return existing[0]
    line_vals = {"product_id": product_id, "product_uom_qty": quantity}
    if price_unit is not None:
        line_vals["price_unit"] = price_unit
    oid = s.call("sale.order", "create", [{
        "partner_id": partner_id,
        "client_order_ref": name,
        "order_line": [(0, 0, line_vals)],
    }])
    log.info("UAT order created id=%s ref=%s partner=%s", oid, name, partner_id)
    return oid


def seed_uat_orders(s, cats: dict[str, int]) -> dict[str, int]:
    """Seed the 4 UAT-2026-05-31-* orders required by Flow-2 + Flow-3 specs."""
    partner_id = _ensure_partner(s)
    mug_categ = cats.get("Mug")

    mto_tmpl = _ensure_simple_product(
        s, UAT_MTO_PRODUCT_CODE, "UAT MTO Ring Dish (auto-seeded)",
        list_price=29.99, gearment_sku=None, categ_id=mug_categ,
    )
    drop_tmpl = _ensure_simple_product(
        s, UAT_DROP_PRODUCT_CODE, "UAT Dropship Mug (auto-seeded)",
        list_price=14.99, gearment_sku=UAT_DROP_GEARMENT_SKU, categ_id=mug_categ,
    )
    addr_tmpl = _ensure_simple_product(
        s, UAT_ADDR_PRODUCT_CODE, "UAT Address-Change Doormat (auto-seeded)",
        list_price=39.99, gearment_sku=None, categ_id=mug_categ,
    )

    mto_v = _product_variant_for_template(s, mto_tmpl)
    drop_v = _product_variant_for_template(s, drop_tmpl)
    addr_v = _product_variant_for_template(s, addr_tmpl)

    return {
        f"{UAT_ORDER_PREFIX}-MTO-001": _ensure_uat_order(s, f"{UAT_ORDER_PREFIX}-MTO-001", partner_id, mto_v),
        f"{UAT_ORDER_PREFIX}-MTO-002": _ensure_uat_order(s, f"{UAT_ORDER_PREFIX}-MTO-002", partner_id, mto_v),
        f"{UAT_ORDER_PREFIX}-DROP-001": _ensure_uat_order(s, f"{UAT_ORDER_PREFIX}-DROP-001", partner_id, drop_v),
        f"{UAT_ORDER_PREFIX}-ADDR-001": _ensure_uat_order(s, f"{UAT_ORDER_PREFIX}-ADDR-001", partner_id, addr_v),
    }


def seed_email_dedupe_fixture(s) -> int | None:
    """Idempotent etsy.email.log row used by Flow-2 TC-008 (active_source dedupe).
    The row carries a deterministic gmail_message_id so the test can assert the
    parser refuses to re-create an order on a second run.
    """
    if "etsy.email.log" not in (s.call("ir.model", "search_read",
                                       [[("model", "=", "etsy.email.log")]],
                                       {"fields": ["model"], "limit": 1}) or [{}])[0].get("model", ""):
        # Model not installed yet (etsy_integration absent); skip silently.
        log.info("etsy.email.log model not present on staging — skipping dedupe fixture")
        return None
    existing = s.call("etsy.email.log", "search",
                      [[("gmail_message_id", "=", UAT_EMAIL_DEDUP_GMAIL_ID)]],
                      {"limit": 1, "context": {"active_test": False}})
    if existing:
        return existing[0]
    eid = s.call("etsy.email.log", "create", [{
        "gmail_message_id": UAT_EMAIL_DEDUP_GMAIL_ID,
        "subject": "Etsy order #UAT-DEDUP — auto-seeded fixture",
        "parse_status": "skipped",
        "raw_body_text": "UAT dedupe fixture (auto-seeded). Do not retry-parse on production.",
    }])
    log.info("email-log dedup fixture created id=%s gmail_id=%s", eid, UAT_EMAIL_DEDUP_GMAIL_ID)
    return eid


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
    try:
        seed_uat_orders(s, cats)
    except Exception as e:
        # Non-fatal: Flow-2/3 spec TCs skip when fixtures missing.
        log.warning("UAT order seeding skipped: %s", e)
    try:
        seed_email_dedupe_fixture(s)
    except Exception as e:
        log.warning("Email dedupe fixture skipped: %s", e)
    log.info("UAT seed complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
