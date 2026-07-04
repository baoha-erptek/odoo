"""P-LIST-PUBLISH-DIFF-RUN — read-only diff: what we send vs what Etsy has.

Slice: P-LIST-PUBLISH-DIFF-RUN (S-0 of plan
`/home/odoo/.claude/plans/check-for-publish-to-dazzling-pond.md`).

Purpose: validate the field-source matrix from the plan against real staging
data, for a published listing on the Etsy channel. Outputs a JSON snapshot
of (a) raw staging field values, (b) the reconstructed publisher payload,
and (c) the live Etsy GET response when accessible. Findings doc consumes
this JSON.

Usage:
    python3 scripts/etsy_publish_diff.py
        [--listing-id ETSY_LISTING_ID]   # default = newest published
        [--shop SHOP_NAME]                # default = pick from the listing's PCS row
        [--out PATH]                      # default = stdout

Reads STAGING_BASE_URL / STAGING_DB / STAGING_ADMIN_LOGIN /
STAGING_ADMIN_PASSWORD from `.env`. DB must be `esty_odoo19` per memory
`reference_staging_db_name.md`.

Outputs JSON; the findings doc author classifies each field row as one of:
  - confirmed-gap: we don't send it, Etsy doesn't have it
  - silent-default: we don't send it, Etsy filled a default
  - mapping-bug: we sent A, Etsy stored B (transform error)
  - not-modelled: Etsy has a field we don't track at all
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import xmlrpc.client
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
ETSY_API_BASE = "https://openapi.etsy.com/v3/application"

load_dotenv(REPO_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("etsy_publish_diff")


@dataclass(frozen=True)
class StagingConfig:
    base_url: str
    db: str
    login: str
    password: str

    @classmethod
    def from_env(cls) -> "StagingConfig":
        return cls(
            base_url=os.environ["STAGING_BASE_URL"].rstrip("/"),
            db=os.environ["STAGING_DB"],
            login=os.environ["STAGING_ADMIN_LOGIN"],
            password=os.environ["STAGING_ADMIN_PASSWORD"],
        )


@dataclass
class DiffReport:
    metadata: dict[str, Any] = field(default_factory=dict)
    listing_record: dict[str, Any] = field(default_factory=dict)
    product_record: dict[str, Any] = field(default_factory=dict)
    shop_record: dict[str, Any] = field(default_factory=dict)
    pcs_record: dict[str, Any] = field(default_factory=dict)
    reconstructed_payload: dict[str, Any] = field(default_factory=dict)
    reconstructed_payload_if_casing_were_fixed: dict[str, Any] = field(default_factory=dict)
    etsy_live_payload: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# XMLRPC client
# --------------------------------------------------------------------------


class StagingClient:
    """Thin XMLRPC wrapper. Reuses pattern from scripts/e2e_product_listing.py."""

    def __init__(self, cfg: StagingConfig) -> None:
        self.cfg = cfg
        common = xmlrpc.client.ServerProxy(f"{cfg.base_url}/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(cfg.db, cfg.login, cfg.password, {})
        if not self.uid:
            raise RuntimeError("Staging XMLRPC auth failed — check STAGING_ADMIN_* env")
        self.models = xmlrpc.client.ServerProxy(f"{cfg.base_url}/xmlrpc/2/object", allow_none=True)
        log.info("XMLRPC authenticated to %s db=%s uid=%s", cfg.base_url, cfg.db, self.uid)

    def execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        return self.models.execute_kw(
            self.cfg.db, self.uid, self.cfg.password, model, method, list(args), kwargs or {}
        )

    def search_read(self, model: str, domain: list, fields_: list[str], limit: int = 0, order: str = "") -> list[dict]:
        kw: dict[str, Any] = {"fields": fields_}
        if limit:
            kw["limit"] = limit
        if order:
            kw["order"] = order
        return self.execute(model, "search_read", domain, **kw)

    def read_one(self, model: str, rec_id: int, fields_: list[str]) -> dict | None:
        rows = self.execute(model, "read", [rec_id], **{"fields": fields_})
        return rows[0] if rows else None


# --------------------------------------------------------------------------
# Pickers
# --------------------------------------------------------------------------


def pick_published_pcs(client: StagingClient, explicit_listing_id: str | None) -> dict:
    """Pick the published Etsy product.channel.status row to diff against."""
    channel = client.search_read(
        "multichannel.sales.channel", [("code", "=", "etsy")], ["id", "name"], limit=1
    )
    if not channel:
        raise RuntimeError("No multichannel.sales.channel code='etsy' on staging — abort")
    ch_id = channel[0]["id"]
    # Note (S-0 finding 2026-06-08): on staging esty_odoo19 ALL 61 PCS rows
    # have state='draft' even with external_ref populated — the publisher
    # creates listings on Etsy but never advances PCS.state. Predicate
    # 'state=published' yields zero rows. Use external_ref as the proxy
    # for "this row has a real Etsy listing on the other side."
    domain: list = [("channel_id", "=", ch_id), ("external_ref", "!=", False)]
    if explicit_listing_id:
        domain.append(("external_ref", "=", explicit_listing_id))
    rows = client.search_read(
        "product.channel.status",
        domain,
        ["id", "product_tmpl_id", "channel_id", "external_ref", "state", "last_sync_at"],
        limit=1,
        order="id desc",
    )
    if not rows:
        raise RuntimeError(
            "No product.channel.status row with external_ref matched — "
            "no Etsy listings tracked on staging at all."
        )
    return rows[0]


def resolve_shop(client: StagingClient, shop_name: str | None, pcs: dict) -> dict:
    """Find the etsy.shop tied to this publish. Prefer explicit --shop arg,
    else fall back to single-shop-on-staging or pick the first active shop."""
    if shop_name:
        rows = client.search_read("etsy.shop", [("name", "=", shop_name)], ["id", "name"], limit=1)
        if rows:
            return rows[0]
    rows = client.search_read("etsy.shop", [("active_source", "=", "api")], ["id", "name"], limit=2)
    if not rows:
        rows = client.search_read("etsy.shop", [], ["id", "name"], limit=1)
    if not rows:
        raise RuntimeError("No etsy.shop on staging — abort")
    if len(rows) > 1:
        log.warning("Multiple active shops on staging; picked %r — override with --shop", rows[0]["name"])
    return rows[0]


# --------------------------------------------------------------------------
# Field readers — mirror EtsyListingPublisher._build_create_draft_payload
# --------------------------------------------------------------------------

# Field lists below are the closure of what _build_create_draft_payload reads.
# Source: custom_addons/etsy_integration/services/etsy_listing_publisher.py:528
LISTING_FIELDS = [
    "id", "product_tmpl_id", "channel_id", "shop_ref", "etsy_shop_id",
    "title", "description", "image_1920", "video_attachment_id",
    "etsy_who_made", "etsy_when_made", "etsy_is_supply",
    "etsy_taxonomy_id", "etsy_shipping_profile_id",
    "state", "external_ref",
]
TEMPLATE_FIELDS = [
    "id", "name", "default_code", "description_sale", "image_1920",
    "list_price", "qty_available",
    "x_who_made", "x_when_made", "x_taxonomy_id",
    "product_tag_ids", "x_extra_image_ids",
    "x_is_personalizable", "x_personalization_required",
    "x_personalization_char_count", "x_personalization_instructions",
    "x_sku_v2_suggested", "x_sku_v2_status", "weight",
    "attribute_line_ids",
]
SHOP_FIELDS = [
    "id", "name", "etsy_api_shop_id", "active_source",
    "default_taxonomy_id", "default_shipping_profile_id", "default_return_policy_id",
    "default_who_made", "default_when_made", "default_is_supply",
    "default_title", "default_description", "default_image_1920",
    "listing_currency_id", "default_readiness_state_id",
    "weight_unit_pref", "dimensions_unit_pref",
]


def reconstruct_payload(listing: dict | None, tmpl: dict, shop: dict, notes: list[str]) -> dict:
    """Reconstruct the publisher payload using the same fallback rules as
    EtsyListingPublisher._build_create_draft_payload (line 528).

    NOTE: this is a faithful re-implementation, not the actual call. Any drift
    is a finding for the diff. The annotations in the output JSON identify
    which tier (listing/template/shop/hardcoded) each value came from.
    """
    def listing_val(key: str) -> Any:
        return (listing or {}).get(key) if listing else None

    def tier(listing_v: Any, tmpl_v: Any, shop_v: Any, hardcoded: Any = None) -> dict:
        if listing_v not in (None, False, "", 0):
            return {"value": listing_v, "tier": "listing"}
        if tmpl_v not in (None, False, "", 0):
            return {"value": tmpl_v, "tier": "template"}
        if shop_v not in (None, False, "", 0):
            return {"value": shop_v, "tier": "shop"}
        return {"value": hardcoded, "tier": "hardcoded"}

    payload: dict[str, Any] = {}

    # title — listing.title → tmpl.name → shop.default_title
    payload["title"] = tier(listing_val("title"), tmpl.get("name"), shop.get("default_title"), "")

    # description — listing.description → tmpl.description_sale → shop.default_description → tmpl.name
    desc = tier(
        listing_val("description"),
        tmpl.get("description_sale"),
        shop.get("default_description"),
        tmpl.get("name") or "",
    )
    payload["description"] = desc

    # sku — tmpl.x_sku_v2_suggested if status != 'ba_approved_legacy' else default_code
    sku_status = tmpl.get("x_sku_v2_status")
    sku_v2 = tmpl.get("x_sku_v2_suggested")
    if sku_status and sku_status != "ba_approved_legacy" and sku_v2:
        payload["sku"] = {"value": sku_v2, "tier": "template (v2_suggested)"}
    else:
        payload["sku"] = {"value": tmpl.get("default_code") or "", "tier": "template (default_code)"}

    # price — min positive variant lst_price → tmpl.list_price (shop-currency conversion handled server-side; reported raw here)
    payload["price"] = {"value": tmpl.get("list_price"), "tier": "template (raw, pre-currency-conversion)"}

    # quantity — max(tmpl.qty_available, 1)
    payload["quantity"] = {
        "value": max(int(tmpl.get("qty_available") or 0), 1),
        "tier": "template",
    }

    # who_made — listing.etsy_who_made → tmpl.x_who_made → shop.default_who_made → 'i_did'
    payload["who_made"] = tier(
        listing_val("etsy_who_made"),
        tmpl.get("x_who_made"),
        shop.get("default_who_made"),
        "i_did",
    )

    # when_made — listing.etsy_when_made → tmpl.x_when_made → shop.default_when_made → 'made_to_order'
    payload["when_made"] = tier(
        listing_val("etsy_when_made"),
        tmpl.get("x_when_made"),
        shop.get("default_when_made"),
        "made_to_order",
    )

    # is_supply — listing override only → shop default → False
    payload["is_supply"] = tier(
        listing_val("etsy_is_supply"),
        None,
        shop.get("default_is_supply"),
        False,
    )

    # taxonomy_id — listing.etsy_taxonomy_id.etsy_id → tmpl.x_taxonomy_id → shop.default_taxonomy_id → 0
    payload["taxonomy_id"] = tier(
        listing_val("etsy_taxonomy_id"),
        tmpl.get("x_taxonomy_id"),
        shop.get("default_taxonomy_id"),
        0,
    )

    # shipping_profile_id — listing.etsy_shipping_profile_id → shop.default_shipping_profile_id → 0
    payload["shipping_profile_id"] = tier(
        listing_val("etsy_shipping_profile_id"),
        None,
        shop.get("default_shipping_profile_id"),
        0,
    )

    # return_policy_id — shop only
    payload["return_policy_id"] = {"value": shop.get("default_return_policy_id") or 0, "tier": "shop"}

    # tags — tmpl.product_tag_ids.mapped('name')[:13] (only if non-empty)
    tag_count = len(tmpl.get("product_tag_ids") or [])
    payload["tags"] = {"value_count": tag_count, "tier": "template (product_tag_ids cap 13)"}

    # materials — derived from variant Material attribute values
    payload["materials"] = {
        "value": "derived from variant Material attribute values (server-side compute)",
        "tier": "template (variant-derived, not introspected via XMLRPC)",
    }

    # weight / dimensions — tmpl.weight + Size attribute regex; server-side compute
    payload["weight_dimensions"] = {
        "value": f"raw weight={tmpl.get('weight')}; dims parsed from Size attribute server-side",
        "tier": "template",
    }

    # images — tmpl.image_1920 + tmpl.x_extra_image_ids; listing.image_1920 is ORPHAN
    listing_has_hero = bool(listing_val("image_1920"))
    tmpl_has_hero = bool(tmpl.get("image_1920"))
    extra_count = len(tmpl.get("x_extra_image_ids") or [])
    payload["images"] = {
        "value": {
            "publisher_reads": "tmpl.image_1920 + tmpl.x_extra_image_ids",
            "listing_image_1920_set": listing_has_hero,
            "listing_image_1920_status": "ORPHAN — publisher ignores it (etsy_listing_publisher.py:973)",
            "tmpl_image_1920_set": tmpl_has_hero,
            "tmpl_x_extra_image_count": extra_count,
            "shop_default_image_set": bool(shop.get("default_image_1920")),
            "etsy_cap": 10,
        },
        "tier": "template",
    }
    if listing_has_hero and not tmpl_has_hero:
        notes.append(
            "WARN: listing.image_1920 is set but tmpl.image_1920 is empty — "
            "publisher will fall back to shop.default_image_1920, NOT the "
            "listing hero. Confirms orphan field finding."
        )

    # video — listing.video_attachment_id (only)
    payload["video_attachment_id"] = {
        "value": bool(listing_val("video_attachment_id")),
        "tier": "listing-only",
    }

    # personalization — all four on tmpl only
    payload["personalization"] = {
        "value": {
            "is_personalizable": tmpl.get("x_is_personalizable"),
            "required": tmpl.get("x_personalization_required"),
            "char_count_max": tmpl.get("x_personalization_char_count"),
            "instructions_set": bool(tmpl.get("x_personalization_instructions")),
        },
        "tier": "template-only (NO listing override field exists today)",
        "note": "Sent via separate push_personalization() endpoint, not in createDraft payload (Etsy 2026 deprecation).",
    }

    # not-modelled
    payload["NOT_MODELLED"] = {
        "shop_section_id": "not on any Odoo model",
        "production_partner_ids": "not on any Odoo model",
        "listing_type": "hardcoded 'physical' in publisher",
    }

    return payload


# --------------------------------------------------------------------------
# Live Etsy GET — attempted; falls back gracefully if blocked
# --------------------------------------------------------------------------


def try_fetch_etsy_listing(
    client: StagingClient, shop_id: int, listing_id: str, notes: list[str]
) -> dict:
    """Attempt to fetch the live Etsy listing JSON via XMLRPC-invoked
    decryption helper. Falls back to a documented gap when blocked."""
    try:
        # _get_access_token is a model method; Odoo XMLRPC allows underscore-
        # prefixed method calls when authenticated as admin.
        access_token = client.execute("etsy.shop", "_get_access_token", [shop_id])
        if not access_token:
            notes.append("Etsy GET skipped: shop has no OAuth access token on staging.")
            return {"_skipped": "no access token"}
    except xmlrpc.client.Fault as exc:
        notes.append(f"Etsy GET skipped: cannot read access token via XMLRPC ({exc.faultString[:200]}).")
        return {"_skipped": "decryption helper blocked over XMLRPC", "_error": str(exc)[:300]}

    # client_id + client_secret live in secrets/credentials.json on staging;
    # not reachable via XMLRPC. The diff-side Etsy call needs both. We try
    # the alternate ENV-injected path if the operator pre-loaded them locally
    # (rare); otherwise document the gap.
    client_id = os.environ.get("ETSY_CLIENT_ID")
    client_secret = os.environ.get("ETSY_CLIENT_SECRET")
    if not (client_id and client_secret):
        notes.append(
            "Etsy GET skipped: ETSY_CLIENT_ID/SECRET not in local env. "
            "Staging holds them in secrets/credentials.json under ir.config_parameter "
            "'etsy.oauth.credentials_path' — not reachable from this script. "
            "Run live diff from staging shell instead, or paste the two values "
            "into .env (read from credentials.json on staging once)."
        )
        return {"_skipped": "client credentials not local"}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-api-key": f"{client_id}:{client_secret}",
    }
    url = f"{ETSY_API_BASE}/listings/{listing_id}?includes=Images,Videos,Inventory"
    try:
        r = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        notes.append(f"Etsy GET network error: {exc}")
        return {"_error": str(exc)}
    return {"http_status": r.status_code, "body": r.json() if r.ok else r.text[:2000]}


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listing-id", help="Etsy listing_id; default = newest published on staging")
    parser.add_argument("--shop", help="etsy.shop.name override; default = picked from data")
    parser.add_argument("--out", help="Output JSON path; default = stdout")
    args = parser.parse_args(argv)

    cfg = StagingConfig.from_env()
    if cfg.db != "esty_odoo19":
        log.warning(
            "STAGING_DB=%r — expected 'esty_odoo19' per memory "
            "reference_staging_db_name.md. Continuing anyway.", cfg.db
        )
    client = StagingClient(cfg)

    report = DiffReport()
    report.metadata = {
        "script": "scripts/etsy_publish_diff.py",
        "slice": "P-LIST-PUBLISH-DIFF-RUN",
        "staging_base_url": cfg.base_url,
        "staging_db": cfg.db,
    }

    pcs = pick_published_pcs(client, args.listing_id)
    report.pcs_record = pcs
    log.info("Picked PCS id=%s external_ref=%s last_sync=%s", pcs["id"], pcs.get("external_ref"), pcs.get("last_sync_at"))

    tmpl_id = pcs["product_tmpl_id"][0] if isinstance(pcs["product_tmpl_id"], list) else pcs["product_tmpl_id"]
    tmpl = client.read_one("product.template", tmpl_id, TEMPLATE_FIELDS) or {}
    report.product_record = {k: _scalar(v) for k, v in tmpl.items()}

    shop = resolve_shop(client, args.shop, pcs)
    shop_full = client.read_one("etsy.shop", shop["id"], SHOP_FIELDS) or {}
    report.shop_record = {k: _scalar(v) for k, v in shop_full.items()}
    log.info("Using shop %r (id=%s)", shop_full.get("name"), shop_full.get("id"))

    # Find the multichannel.listing row by (tmpl, channel, shop_ref=shop.name)
    # MIRROR the publisher's exact match (etsy_listing_publisher.py:515) first.
    ch_id = pcs["channel_id"][0] if isinstance(pcs["channel_id"], list) else pcs["channel_id"]
    shop_name = shop_full.get("name") or ""
    listing_rows = client.search_read(
        "multichannel.listing",
        [("product_tmpl_id", "=", tmpl_id), ("channel_id", "=", ch_id), ("shop_ref", "=", shop_name)],
        LISTING_FIELDS,
        limit=1,
    )
    resolution_tier = "publisher-exact-match" if listing_rows else None
    if not listing_rows:
        # Publisher fallback #1: NULL/empty shop_ref (template-wide intent).
        listing_rows = client.search_read(
            "multichannel.listing",
            [("product_tmpl_id", "=", tmpl_id), ("channel_id", "=", ch_id), "|", ("shop_ref", "=", False), ("shop_ref", "=", "")],
            LISTING_FIELDS,
            limit=1,
        )
        if listing_rows:
            resolution_tier = "publisher-empty-shop-ref-fallback"
            report.notes.append(
                "Publisher would resolve listing via empty-shop_ref fallback — per-shop intent row not found."
            )
    # Diagnostic-only: try case-insensitive match. If this finds a row that the
    # publisher's exact match missed, that's a CONFIRMED BUG finding.
    case_insensitive_match = None
    if not listing_rows and shop_name:
        ci = client.search_read(
            "multichannel.listing",
            [("product_tmpl_id", "=", tmpl_id), ("channel_id", "=", ch_id), ("shop_ref", "=ilike", shop_name)],
            LISTING_FIELDS,
            limit=1,
        )
        if ci:
            case_insensitive_match = ci[0]
            report.notes.append(
                f"CONFIRMED-BUG: publisher's exact-match on shop_ref MISSED a listing row "
                f"(id={ci[0]['id']}, shop_ref={ci[0].get('shop_ref')!r}) that would have matched "
                f"case-insensitively against shop.name={shop_name!r}. The listing's overrides "
                f"are silently bypassed by EtsyListingPublisher._resolve_listing_intent "
                f"(etsy_listing_publisher.py:515). Casing drift here = 100% override miss."
            )
    listing = listing_rows[0] if listing_rows else None
    if listing is None and case_insensitive_match is None:
        report.notes.append("No multichannel.listing row at all — publisher would skip all listing-tier overrides.")
    report.listing_record = {
        "publisher_resolution_tier": resolution_tier,
        "row_publisher_would_use": {k: _scalar(v) for k, v in (listing or {}).items()},
        "case_insensitive_diagnostic_match": (
            {k: _scalar(v) for k, v in case_insensitive_match.items()} if case_insensitive_match else None
        ),
    }
    # If diagnostic match found, ALSO reconstruct the payload as if it had matched
    # — that's the "what overrides WOULD have applied" view.
    if case_insensitive_match and not listing:
        report.reconstructed_payload_if_casing_were_fixed = reconstruct_payload(
            case_insensitive_match, tmpl, shop_full, report.notes
        )

    report.reconstructed_payload = reconstruct_payload(listing, tmpl, shop_full, report.notes)

    etsy_listing_id = pcs.get("external_ref")
    if etsy_listing_id:
        report.etsy_live_payload = try_fetch_etsy_listing(client, shop_full["id"], etsy_listing_id, report.notes)
    else:
        report.notes.append("PCS row has no external_ref — cannot GET from Etsy.")

    output = json.dumps(asdict(report), indent=2, default=str, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        log.info("Wrote diff to %s", args.out)
    else:
        sys.stdout.write(output + "\n")
    return 0


def _scalar(v: Any) -> Any:
    """Compact Many2one/Many2many tuples for cleaner JSON output. Image
    Binary fields land as base64 strings — we don't want those in the
    findings doc, so summarize as a boolean."""
    if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int) and isinstance(v[1], str):
        return {"id": v[0], "name": v[1]}
    if isinstance(v, list) and all(isinstance(x, int) for x in v):
        return {"ids_count": len(v), "ids": v[:10]}
    if isinstance(v, str) and len(v) > 400:
        return f"<truncated {len(v)} chars: {v[:200]}…>"
    return v


if __name__ == "__main__":
    sys.exit(main())
