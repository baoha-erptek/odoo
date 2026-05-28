"""Re-apply the ``ordertest2`` Gmail label to messages whose Subject line
references the given Etsy receipt IDs.

Background: ``etsy_integration.models.sale_order`` strips the label after
successful ingest (``gmail.remove_label(processed_ids, label)``). After a
local cleanup wipes the resulting sale.orders, the Gmail messages have no
label left for a fresh re-ingest — the cron's ``q=label:ordertest2``
returns nothing and §1 of the E2E runner ends up in the FALLBACK path.

This script reads the Gmail OAuth tokens currently configured on staging
``demo_esty`` (via XML-RPC ``ir.config_parameter``) plus the OAuth client
metadata from ``secrets/credentials.json``, builds a Gmail service, and
re-applies the label to messages matching ``subject:<receipt_id>``.

Usage::

    python3 scripts/relabel_ordertest2.py \\
        --receipts 3703975562,3711793551,3710809073,3708041263

By default queries ``demo_esty`` on ``https://odoo.hatafax.com`` for the
OAuth credentials. Override with ``--db`` / ``--base-url`` if needed.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import xmlrpc.client
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_BASE_URL = "https://odoo.hatafax.com"
DEFAULT_DB = "demo_esty"
DEFAULT_LABEL = "ordertest2"
DEFAULT_RECEIPTS = "3703975562,3711793551,3710809073,3708041263"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger("relabel_ordertest2")


def _icp(models, db: str, uid: int, pw: str, key: str) -> str:
    return models.execute_kw(
        db, uid, pw, "ir.config_parameter", "get_param", [key]) or ""


def _refresh_access_token(
    client_id: str, client_secret: str, refresh_token: str,
) -> str:
    """Manual OAuth refresh — mirrors etsy_integration.services.gmail_client.

    Goes raw to ``oauth2.googleapis.com`` so we don't have to declare
    scopes (the refresh token is already authorized for whatever scope
    set was granted at consent — typically ``gmail.modify`` for the
    staging integration).
    """
    import requests
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


_GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


class GmailDirect:
    """Tiny pinhole client (auth + 4 calls) — avoids googleapiclient's
    refresh path that demands declared scopes.
    """
    def __init__(self, access_token: str):
        import requests
        self._sess = requests.Session()
        self._sess.headers["Authorization"] = f"Bearer {access_token}"

    def list_labels(self) -> list[dict]:
        r = self._sess.get(f"{_GMAIL_API}/labels", timeout=30)
        r.raise_for_status()
        return r.json().get("labels", [])

    def create_label(self, name: str) -> str:
        r = self._sess.post(
            f"{_GMAIL_API}/labels", timeout=30,
            json={"name": name, "labelListVisibility": "labelShow",
                  "messageListVisibility": "show"},
        )
        r.raise_for_status()
        return r.json()["id"]

    def search_message_ids(self, query: str, page_size: int = 50) -> list[str]:
        ids: list[str] = []
        params = {"q": query, "maxResults": page_size}
        while True:
            r = self._sess.get(
                f"{_GMAIL_API}/messages", params=params, timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            ids.extend(m["id"] for m in data.get("messages", []))
            tok = data.get("nextPageToken")
            if not tok:
                break
            params = {"q": query, "maxResults": page_size, "pageToken": tok}
        return ids

    def batch_add_label(self, message_ids: list[str], label_id: str) -> None:
        for i in range(0, len(message_ids), 500):
            chunk = message_ids[i:i + 500]
            r = self._sess.post(
                f"{_GMAIL_API}/messages/batchModify", timeout=30,
                json={"ids": chunk, "addLabelIds": [label_id]},
            )
            r.raise_for_status()


def _get_label_id(client: "GmailDirect", label_name: str) -> str | None:
    for lbl in client.list_labels():
        if lbl.get("name") == label_name:
            return lbl["id"]
    return None


def _search_messages_for_receipt(client: "GmailDirect", receipt_id: str) -> list[str]:
    return client.search_message_ids(f'subject:{receipt_id} newer_than:90d')


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--login", default="admin")
    p.add_argument("--password", default=os.environ.get("DEMO_ADMIN_PASSWORD", "admin"))
    p.add_argument("--label", default=DEFAULT_LABEL)
    p.add_argument(
        "--receipts", default=DEFAULT_RECEIPTS,
        help="Comma-separated etsy receipt IDs whose Subject line should "
             "be re-labelled (default: 3703975562,...).",
    )
    p.add_argument(
        "--credentials-json",
        default=str(REPO_ROOT / "secrets" / "credentials.json"),
        help="Path to OAuth credentials.json (client_id + client_secret).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    base = args.base_url.rstrip("/")
    receipts = tuple(r.strip() for r in args.receipts.split(",") if r.strip())
    if not receipts:
        _log.error("--receipts produced an empty list")
        return 2

    # 1) Fetch staging Gmail OAuth refresh_token (the long-lived secret).
    common = xmlrpc.client.ServerProxy(f"{base}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(args.db, args.login, args.password, {})
    if not uid:
        _log.error("XML-RPC authenticate failed for %s@%s", args.login, args.db)
        return 3
    models = xmlrpc.client.ServerProxy(f"{base}/xmlrpc/2/object", allow_none=True)
    refresh_token = _icp(models, args.db, uid, args.password,
                         "etsy_integration.gmail_refresh_token")
    if not refresh_token:
        _log.error("etsy_integration.gmail_refresh_token ICP is empty on %s", args.db)
        return 4

    # 2) Read OAuth client_id + client_secret from local credentials.json.
    creds_path = Path(args.credentials_json)
    if not creds_path.exists():
        _log.error("credentials.json not found at %s", creds_path)
        return 5
    creds_doc = json.loads(creds_path.read_text())
    client_block = creds_doc.get("installed") or creds_doc.get("web") or {}
    client_id = client_block.get("client_id") or ""
    client_secret = client_block.get("client_secret") or ""
    if not (client_id and client_secret):
        _log.error("credentials.json missing client_id/client_secret")
        return 6

    # 3) Refresh access token + build pinhole client + ensure label exists.
    access_token = _refresh_access_token(client_id, client_secret, refresh_token)
    client = GmailDirect(access_token)
    label_id = _get_label_id(client, args.label)
    if not label_id:
        _log.info("label %r missing; creating", args.label)
        label_id = client.create_label(args.label)

    # 4) Per receipt, find matching messages + apply the label.
    total_relabeled = 0
    misses = []
    for receipt in receipts:
        msg_ids = _search_messages_for_receipt(client, receipt)
        if not msg_ids:
            misses.append(receipt)
            _log.warning("receipt %s: no Gmail messages match subject", receipt)
            continue
        client.batch_add_label(msg_ids, label_id)
        _log.info("receipt %s: relabelled %d message(s) ids=%s",
                  receipt, len(msg_ids), msg_ids)
        total_relabeled += len(msg_ids)

    _log.info("done. %d message(s) carry label %r; misses=%s",
              total_relabeled, args.label, misses)
    return 0 if not misses else 7


if __name__ == "__main__":
    sys.exit(main())
