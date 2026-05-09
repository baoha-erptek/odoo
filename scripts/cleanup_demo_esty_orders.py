"""Wipe Etsy-channel sale.orders and order-derived state from demo_esty.

Used before a fresh E2E run on staging
(``https://odoo.hatafax.com / demo_esty``) so we can reingest a known
set of Etsy receipts without dedupe collisions or stale design files
left over from prior runs.

Spares users, products, partners, ICPs, and pipeline master data —
those are reseeded by ``deployment/scripts/seed-demo-esty.py`` and
should not be touched.

XML-RPC driven so it works against a remote container without needing
``docker exec``.

Usage::

    # Dry run (counts only) — recommended first
    python3 scripts/cleanup_demo_esty_orders.py --dry-run

    # Real cleanup
    python3 scripts/cleanup_demo_esty_orders.py

    # Keep email logs (re-ingest will treat them as already-seen)
    python3 scripts/cleanup_demo_esty_orders.py --keep-email-logs

The cleanup walks unlinks in dependency order so we don't trip foreign
key constraints. Each step is wrapped in its own try/except so a
missing model (e.g. etsy_integration not installed) skips cleanly.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import xmlrpc.client
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

DEFAULT_BASE_URL = "https://odoo.hatafax.com"
DEFAULT_DB = "demo_esty"
DEFAULT_LOGIN = "admin"
DEFAULT_PASSWORD = os.environ.get("DEMO_ADMIN_PASSWORD", "admin")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger("cleanup_demo_esty")


@dataclass
class Counts:
    by_model: dict[str, int] = field(default_factory=dict)

    def add(self, model: str, count: int) -> None:
        self.by_model[model] = self.by_model.get(model, 0) + count


@dataclass
class Client:
    base_url: str
    db: str
    login: str
    password: str
    common: xmlrpc.client.ServerProxy
    models: xmlrpc.client.ServerProxy
    uid: int

    @classmethod
    def connect(cls, base_url: str, db: str, login: str, password: str) -> "Client":
        common = xmlrpc.client.ServerProxy(f"{base_url}/xmlrpc/2/common", allow_none=True)
        uid = common.authenticate(db, login, password, {})
        if not uid:
            raise RuntimeError(f"XML-RPC authenticate failed for {login}@{db}")
        models = xmlrpc.client.ServerProxy(f"{base_url}/xmlrpc/2/object", allow_none=True)
        return cls(
            base_url=base_url, db=db, login=login, password=password,
            common=common, models=models, uid=uid,
        )

    def _execute(self, model: str, method: str, args: list, kwargs: dict | None = None):
        return self.models.execute_kw(
            self.db, self.uid, self.password, model, method, args, kwargs or {},
        )

    def model_exists(self, model: str) -> bool:
        rows = self._execute("ir.model", "search_read",
                             [[("model", "=", model)], ["model"]], {"limit": 1})
        return bool(rows)

    def search(self, model: str, domain: list, limit: int | None = None) -> list[int]:
        kw = {"limit": limit} if limit else {}
        return self._execute(model, "search", [domain], kw)

    def write(self, model: str, ids: list[int], vals: dict) -> bool:
        if not ids:
            return True
        return self._execute(model, "write", [ids, vals])

    def unlink(self, model: str, ids: list[int]) -> bool:
        if not ids:
            return True
        return self._execute(model, "unlink", [ids])


def _chunked(seq: Iterable[int], n: int = 500):
    buf: list[int] = []
    for x in seq:
        buf.append(x)
        if len(buf) == n:
            yield buf
            buf = []
    if buf:
        yield buf


def _resolve_etsy_order_ids(client: Client, channel_filter: str) -> list[int]:
    """Return sale.order ids in scope for the cleanup."""
    domain = [(channel_filter.split("=")[0], "=", channel_filter.split("=")[1])]
    return client.search("sale.order", domain)


def _wipe_design_files(client: Client, sale_order_ids: list[int],
                      counts: Counts, dry_run: bool) -> None:
    """Wipe design.file.route then design.file rows referencing the orders."""
    if not client.model_exists("design.file"):
        _log.info("design.file: model not installed, skipping")
        return

    file_ids = client.search(
        "design.file",
        ["|",
         ("order_id", "in", sale_order_ids),
         ("order_line_id.order_id", "in", sale_order_ids)],
    )
    if not file_ids:
        return

    if client.model_exists("design.file.route"):
        route_ids = client.search(
            "design.file.route", [("design_file_id", "in", file_ids)],
        )
        counts.add("design.file.route", len(route_ids))
        if route_ids and not dry_run:
            for chunk in _chunked(route_ids):
                client.unlink("design.file.route", chunk)

    counts.add("design.file", len(file_ids))
    if not dry_run:
        for chunk in _chunked(file_ids):
            client.unlink("design.file", chunk)


def _wipe_tracking_imports(client: Client, sale_order_ids: list[int],
                          counts: Counts, dry_run: bool) -> None:
    if client.model_exists("tracking.import.line"):
        line_ids = client.search(
            "tracking.import.line",
            [("sale_order_id", "in", sale_order_ids)],
        )
        if line_ids:
            log_ids = list(set(
                row["log_id"][0] for row in client._execute(
                    "tracking.import.line", "read",
                    [line_ids, ["log_id"]],
                ) if row.get("log_id")
            ))
            counts.add("tracking.import.line", len(line_ids))
            if not dry_run:
                for chunk in _chunked(line_ids):
                    client.unlink("tracking.import.line", chunk)
            # Drop the now-empty parent log rows so the cron view stays tidy.
            if client.model_exists("tracking.import.log") and log_ids:
                still_has_lines = client.search(
                    "tracking.import.line",
                    [("log_id", "in", log_ids)], limit=1,
                )
                if not still_has_lines:
                    counts.add("tracking.import.log", len(log_ids))
                    if not dry_run:
                        for chunk in _chunked(log_ids):
                            client.unlink("tracking.import.log", chunk)


def _wipe_audit_rows(client: Client, sale_order_ids: list[int],
                    counts: Counts, dry_run: bool) -> None:
    """Drop append-only audit rows (gearment.api.log, pipeline transitions)."""
    if client.model_exists("gearment.api.log"):
        ids = client.search(
            "gearment.api.log", [("sale_order_id", "in", sale_order_ids)],
        )
        counts.add("gearment.api.log", len(ids))
        if ids and not dry_run:
            for chunk in _chunked(ids):
                client.unlink("gearment.api.log", chunk)

    if client.model_exists("order.pipeline.transition.log"):
        ids = client.search(
            "order.pipeline.transition.log",
            [("sale_order_id", "in", sale_order_ids)],
        )
        counts.add("order.pipeline.transition.log", len(ids))
        if ids and not dry_run:
            for chunk in _chunked(ids):
                client.unlink("order.pipeline.transition.log", chunk)

    if client.model_exists("etsy.message.dedupe"):
        ids = client.search(
            "etsy.message.dedupe",
            [("target_sale_order_id", "in", sale_order_ids)],
        )
        counts.add("etsy.message.dedupe", len(ids))
        if ids and not dry_run:
            for chunk in _chunked(ids):
                client.unlink("etsy.message.dedupe", chunk)


def _detach_email_logs(client: Client, sale_order_ids: list[int],
                      counts: Counts, dry_run: bool, keep: bool) -> None:
    """Either unlink email logs or detach the FK so reingest can re-find them.

    Detach (the default) is preferred because the Gmail cron's idempotency
    is keyed on ``gmail_message_id``: if we keep the rows, the cron will
    skip them on the next run. Unlinking forces a true re-ingest.
    """
    if not client.model_exists("etsy.email.log"):
        return
    log_ids = client.search(
        "etsy.email.log", [("sale_order_id", "in", sale_order_ids)],
    )
    if not log_ids:
        return
    if keep:
        counts.add("etsy.email.log (kept)", len(log_ids))
        return
    counts.add("etsy.email.log", len(log_ids))
    if not dry_run:
        for chunk in _chunked(log_ids):
            client.unlink("etsy.email.log", chunk)


def _wipe_stock_moves(client: Client, sale_order_ids: list[int],
                     counts: Counts, dry_run: bool) -> None:
    """Drop our custom production_completion stock.move rows.

    P2-03 hook creates these on fulfillment_status='produced'. They'd
    otherwise stay orphaned referencing deleted sale.order rows.
    """
    if not client.model_exists("stock.move"):
        return
    sm_fields = client._execute(
        "stock.move", "fields_get",
        [["sale_order_id"]], {"attributes": ["string"]},
    )
    if "sale_order_id" not in sm_fields:
        return  # field never installed (multichannel_hub_fulfillment absent)
    ids = client.search(
        "stock.move",
        [("sale_order_id", "in", sale_order_ids),
         ("purpose", "=", "production_completion")],
    )
    counts.add("stock.move (production_completion)", len(ids))
    if ids and not dry_run:
        for chunk in _chunked(ids):
            client.unlink("stock.move", chunk)


def _wipe_purchase_orders(client: Client, sale_order_ids: list[int],
                         counts: Counts, dry_run: bool) -> None:
    """Cancel + unlink any dropship POs created for the SOs.

    P1-DROP-CALLSITE relocated Gearment push to ``button_confirm``
    on ``purchase.order``, so each dropship SO owns one PO.
    """
    if not client.model_exists("purchase.order"):
        return
    line_rows = client._execute(
        "purchase.order.line", "search_read",
        [[("sale_line_id.order_id", "in", sale_order_ids)],
         ["order_id"]],
    )
    po_ids = list({row["order_id"][0] for row in line_rows if row.get("order_id")})
    if not po_ids:
        return
    counts.add("purchase.order", len(po_ids))
    if dry_run:
        return
    # Cancel before unlink: confirmed POs raise UserError on direct
    # unlink. action_cancel is idempotent against draft POs.
    try:
        client._execute("purchase.order", "button_cancel", [po_ids])
    except xmlrpc.client.Fault as exc:
        _log.warning("purchase.order.button_cancel warning: %s",
                     exc.faultString.splitlines()[-1][:160])
    for chunk in _chunked(po_ids):
        try:
            client.unlink("purchase.order", chunk)
        except xmlrpc.client.Fault as exc:
            _log.warning("purchase.order unlink chunk warning: %s",
                         exc.faultString.splitlines()[-1][:160])


def _wipe_mrp_productions(client: Client, sale_order_ids: list[int],
                         counts: Counts, dry_run: bool) -> None:
    """Cancel + unlink MOs whose origin matches an SO's name.

    P1-MTO-SYNC walks origin-text to bind MOs to SOs.
    """
    if not client.model_exists("mrp.production"):
        return
    so_rows = client._execute(
        "sale.order", "read", [sale_order_ids, ["name"]],
    )
    so_names = [r["name"] for r in so_rows if r.get("name")]
    if not so_names:
        return
    mo_ids = client.search(
        "mrp.production", [("origin", "in", so_names)],
    )
    if not mo_ids:
        return
    counts.add("mrp.production", len(mo_ids))
    if dry_run:
        return
    try:
        client._execute("mrp.production", "action_cancel", [mo_ids])
    except xmlrpc.client.Fault as exc:
        _log.warning("mrp.production.action_cancel warning: %s",
                     exc.faultString.splitlines()[-1][:160])
    for chunk in _chunked(mo_ids):
        try:
            client.unlink("mrp.production", chunk)
        except xmlrpc.client.Fault as exc:
            _log.warning("mrp.production unlink chunk warning: %s",
                         exc.faultString.splitlines()[-1][:160])


def _cancel_and_unlink_orders(client: Client, sale_order_ids: list[int],
                             counts: Counts, dry_run: bool) -> None:
    counts.add("sale.order", len(sale_order_ids))
    if dry_run:
        return
    # Cancel first (sale.order with state='sale' won't unlink directly).
    try:
        client._execute(
            "sale.order", "action_cancel", [sale_order_ids],
        )
    except xmlrpc.client.Fault as exc:
        _log.warning("sale.order.action_cancel warning: %s",
                     exc.faultString.splitlines()[-1][:160])
    for chunk in _chunked(sale_order_ids):
        try:
            client.unlink("sale.order", chunk)
        except xmlrpc.client.Fault as exc:
            _log.error(
                "sale.order unlink chunk failed (size=%d): %s",
                len(chunk), exc.faultString.splitlines()[-1][:200],
            )
            raise


def _print_report(counts: Counts, dry_run: bool) -> None:
    label = "DRY-RUN" if dry_run else "DELETED"
    _log.info("=== %s SUMMARY ===", label)
    if not counts.by_model:
        _log.info("(nothing in scope)")
        return
    for model, count in sorted(counts.by_model.items()):
        _log.info("%-50s %s %d", model, label, count)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--login", default=DEFAULT_LOGIN)
    p.add_argument(
        "--password", default=DEFAULT_PASSWORD,
        help="(default: $DEMO_ADMIN_PASSWORD or 'admin')",
    )
    p.add_argument(
        "--filter", default="sales_channel=etsy",
        help="<field>=<value> domain on sale.order (default: sales_channel=etsy)",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--keep-email-logs", action="store_true",
        help="Skip etsy.email.log unlink (Gmail cron will treat them as seen)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    base = args.base_url.rstrip("/")
    client = Client.connect(base, args.db, args.login, args.password)
    sale_order_ids = _resolve_etsy_order_ids(client, args.filter)
    if not sale_order_ids:
        _log.info("no sale.order rows match filter %r — nothing to do", args.filter)
        return 0
    _log.info(
        "%s %d sale.order row(s) on %s/%s (filter=%s)",
        "DRY-RUN: would touch" if args.dry_run else "Touching",
        len(sale_order_ids), base, args.db, args.filter,
    )

    counts = Counts()
    _wipe_design_files(client, sale_order_ids, counts, args.dry_run)
    _wipe_tracking_imports(client, sale_order_ids, counts, args.dry_run)
    _wipe_audit_rows(client, sale_order_ids, counts, args.dry_run)
    _detach_email_logs(client, sale_order_ids, counts, args.dry_run,
                       args.keep_email_logs)
    _wipe_stock_moves(client, sale_order_ids, counts, args.dry_run)
    _wipe_mrp_productions(client, sale_order_ids, counts, args.dry_run)
    _wipe_purchase_orders(client, sale_order_ids, counts, args.dry_run)
    _cancel_and_unlink_orders(client, sale_order_ids, counts, args.dry_run)

    _print_report(counts, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
