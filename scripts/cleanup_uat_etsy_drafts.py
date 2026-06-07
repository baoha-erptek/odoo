#!/usr/bin/env python3
"""Bulk-delete Etsy draft listings created by the Wave-2/3 UAT run.

Strategy:
  1. XML-RPC into staging Odoo (admin) to read etsy.shop credentials +
     etsy_oauth_access_token for JaHandmadeArt.
  2. GET /v3/application/shops/{shop_id}/listings?state=draft (paginated) and
     filter Python-side for titles starting with `[UAT-2026-06-07]`.
  3. DELETE /v3/application/listings/{listing_id} for each match.

Idempotent: re-running after a partial failure simply finds fewer matches.
Safe by default: --dry-run prints the deletion plan without touching Etsy.

Usage:
    python3 scripts/cleanup_uat_etsy_drafts.py                    # dry-run
    python3 scripts/cleanup_uat_etsy_drafts.py --apply             # destructive
    python3 scripts/cleanup_uat_etsy_drafts.py --prefix '[UAT-X]'  # custom tag

Reads from .env:
  STAGING_BASE_URL    (default: https://odoo.hatafax.com)
  STAGING_DB          (default: esty_odoo19)
  STAGING_ADMIN_LOGIN (default: admin)
  STAGING_ADMIN_PASSWORD
  ETSY_CLIENT_ID
  ETSY_CLIENT_SECRET

The Etsy API key header (`x-api-key`) requires the combined `client_id:secret`
form per the 2026-02-09 enforcement (memory: reference_etsy_api_credentials).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import xmlrpc.client
from pathlib import Path
from typing import Iterable

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PREFIX = "UAT 2026-06-07"


def parse_dotenv(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}
    out: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.strip()
        if val and val[0] in ("'", '"') and val[-1] == val[0]:
            val = val[1:-1]
        out[key.strip()] = val
    return out


def get_env(key: str, dotenv: dict[str, str], default: str | None = None) -> str:
    val = os.environ.get(key) or dotenv.get(key) or default
    if val is None:
        sys.exit(f"missing env var: {key} (set in .env or export)")
    return val


def load_etsy_app_credentials() -> tuple[str, str]:
    """Read Etsy OAuth app client_id + client_secret.

    Same source-of-truth as `etsy_api_client._read_credentials`:
      1. env vars ETSY_CLIENT_ID / ETSY_CLIENT_SECRET (highest)
      2. .env file
      3. secrets/etsy_credentials.json (matches in-container path)
      4. secrets/credentials.json (legacy fallback)
    """
    env_id = os.environ.get("ETSY_CLIENT_ID")
    env_secret = os.environ.get("ETSY_CLIENT_SECRET")
    if env_id and env_secret:
        return env_id, env_secret
    dotenv = parse_dotenv(REPO_ROOT / ".env")
    dotenv_id = dotenv.get("ETSY_CLIENT_ID")
    dotenv_secret = dotenv.get("ETSY_CLIENT_SECRET")
    if dotenv_id and dotenv_secret:
        return dotenv_id, dotenv_secret
    for candidate in ("etsy_credentials.json", "credentials.json"):
        path = REPO_ROOT / "secrets" / candidate
        if not path.exists():
            continue
        try:
            data = __import__("json").loads(path.read_text())
        except Exception:
            continue
        if data.get("client_id") and data.get("client_secret"):
            return data["client_id"], data["client_secret"]
    sys.exit("Etsy client_id/client_secret not found (.env or secrets/etsy_credentials.json)")


def odoo_login(base_url: str, db: str, login: str, password: str) -> tuple[xmlrpc.client.ServerProxy, int]:
    common = xmlrpc.client.ServerProxy(f"{base_url}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, login, password, {})
    if not uid:
        sys.exit(f"Odoo auth failed for {login}@{db}")
    models = xmlrpc.client.ServerProxy(f"{base_url}/xmlrpc/2/object", allow_none=True)
    return models, uid


def load_jahandmadeart_shop(models, db: str, uid: int, password: str) -> dict:
    shops = models.execute_kw(
        db, uid, password,
        "etsy.shop", "search_read",
        [[["etsy_api_shop_id", "=", "60752333"]]],
        {"fields": ["id", "name", "etsy_api_shop_id", "etsy_oauth_access_token", "etsy_oauth_token_expires_at"], "limit": 1},
    )
    if not shops:
        sys.exit("JaHandmadeArt shop (etsy_api_shop_id=60752333) not found")
    shop = shops[0]
    if not shop.get("etsy_oauth_access_token"):
        sys.exit(f"shop {shop['name']} has no etsy_oauth_access_token — re-authorize OAuth and re-run")
    return shop


def get_token(shop: dict) -> str:
    return shop["etsy_oauth_access_token"]


def etsy_headers(etsy_oauth_access_token: str, api_key_combined: str) -> dict[str, str]:
    # Per reference_etsy_api_credentials memory: x-api-key MUST be `id:secret`.
    return {
        "Authorization": f"Bearer {etsy_oauth_access_token}",
        "x-api-key": api_key_combined,
        "Accept": "application/json",
    }


def iter_draft_listings(shop_id: str, headers: dict[str, str]) -> Iterable[dict]:
    """Page through all draft listings for the shop (state=draft)."""
    base = f"https://openapi.etsy.com/v3/application/shops/{shop_id}/listings"
    offset = 0
    limit = 100
    while True:
        params = {"state": "draft", "limit": limit, "offset": offset}
        r = requests.get(base, headers=headers, params=params, timeout=30)
        if r.status_code != 200:
            sys.exit(f"etsy GET listings failed {r.status_code}: {r.text[:300]}")
        body = r.json()
        results = body.get("results", []) or []
        if not results:
            break
        yield from results
        if len(results) < limit:
            break
        offset += limit


def delete_listing(listing_id: int, headers: dict[str, str]) -> tuple[bool, str]:
    r = requests.delete(
        f"https://openapi.etsy.com/v3/application/listings/{listing_id}",
        headers=headers, timeout=30,
    )
    if r.status_code in (200, 204):
        return True, ""
    return False, f"{r.status_code}: {r.text[:200]}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prefix", default=DEFAULT_PREFIX, help=f"title prefix to match (default: {DEFAULT_PREFIX!r})")
    p.add_argument("--apply", action="store_true", help="actually DELETE (default is dry-run)")
    p.add_argument("--db", default=None, help="override STAGING_DB")
    args = p.parse_args()

    dotenv = parse_dotenv(REPO_ROOT / ".env")
    base_url = get_env("STAGING_BASE_URL", dotenv, "https://odoo.hatafax.com")
    db = args.db or get_env("STAGING_DB", dotenv, "esty_odoo19")
    login = get_env("STAGING_ADMIN_LOGIN", dotenv, "admin")
    password = get_env("STAGING_ADMIN_PASSWORD", dotenv)
    client_id, client_secret = load_etsy_app_credentials()

    print(f"[cleanup] connecting to {base_url} (db={db}) as {login}")
    models, uid = odoo_login(base_url, db, login, password)

    shop = load_jahandmadeart_shop(models, db, uid, password)
    print(f"[cleanup] loaded shop name={shop['name']} api_shop_id={shop['etsy_api_shop_id']}")

    headers = etsy_headers(shop["etsy_oauth_access_token"], f"{client_id}:{client_secret}")
    print(f"[cleanup] scanning draft listings for prefix={args.prefix!r}")

    matches: list[dict] = []
    for listing in iter_draft_listings(shop["etsy_api_shop_id"], headers):
        title = (listing.get("title") or "").strip()
        if title.startswith(args.prefix):
            matches.append(listing)

    if not matches:
        print(f"[cleanup] no drafts match prefix — nothing to do")
        return 0

    print(f"[cleanup] found {len(matches)} draft(s) matching prefix:")
    for m in matches:
        print(f"  - listing_id={m['listing_id']} title={m.get('title', '')!r}")

    if not args.apply:
        print(f"[cleanup] DRY-RUN — pass --apply to delete the {len(matches)} draft(s)")
        return 0

    ok = 0
    fail = 0
    for m in matches:
        success, err = delete_listing(m["listing_id"], headers)
        if success:
            ok += 1
            print(f"  DELETED listing_id={m['listing_id']}")
        else:
            fail += 1
            print(f"  FAILED  listing_id={m['listing_id']} — {err}")
        time.sleep(0.3)  # gentle on Etsy rate limit

    print(f"[cleanup] done: deleted={ok} failed={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
