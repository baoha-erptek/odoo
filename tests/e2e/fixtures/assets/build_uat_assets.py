"""Generate UAT fixture assets on-demand (Flow-2 + Flow-3).

The XLSX outputs are NOT committed to git (see assets/.gitignore). Generate
them locally before running the Playwright suite, or wire this script into
globalSetup so it runs once per CI/staging session.

Generated files:
  - gke_excel_sample.xlsx           — happy-path GKE tracking import (4 rows)
  - gke_excel_broken_schema.xlsx    — header drift (drops "TRACKING NUMBER"
                                      column) so wizard preview returns
                                      `is_new_schema=True` and import is
                                      gated by approve_schema.

Usage:
    python3 tests/e2e/fixtures/assets/build_uat_assets.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

try:
    from openpyxl import Workbook
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "build_uat_assets.py requires openpyxl. Install: pip install openpyxl"
    ) from exc

ASSETS_DIR = Path(__file__).resolve().parent

# Header order must match
# multichannel_hub_fulfillment.services.gke_excel_parser GKE_HEADERS verbatim.
# Trailing space on 'CREATIVE ' is INTENTIONAL — schema fingerprint includes it.
GKE_HEADERS: tuple[str, ...] = (
    "ORDER NUMBER",
    "TRACKING NUMBER",
    "COUNTRY",
    "SONSIGNEE NAME",
    "STATE",
    "CITY",
    "ADDRESS",
    "POSTCODE",
    "PRODUCT NAME",
    "VALUE",
    "QUANTITY",
    "WEIGHT AT COSTOMER",
    "WEIGHT AT GKE",
    "COST",
    "CREATIVE ",
    "Ngày nhận tại kho",
    "Tình trạng đơn hàng",
    "Đường dẫn link label",
    "Đường dẫn link qrcode",
)

# Two rows per UAT MTO seed order, plus 2 unmatched rows so wizard surfaces
# the unmatched-bucket UX. Order numbers reference seed_uat_data.py output;
# fixtures script seeds sale.order with client_order_ref = UAT-2026-05-31-*.
UAT_ROWS: tuple[tuple, ...] = (
    ("UAT-2026-05-31-MTO-001", "9400111202555560000001", "USPS"),
    ("UAT-2026-05-31-MTO-002", "UUS64826200700002",      "UniUni"),
    ("UAT-2026-05-31-UNMATCH-X", "YT242020000200003",    "YunExpress"),
    ("UAT-2026-05-31-UNMATCH-Y", "4PX20240200004",       "4PX"),
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("build_uat_assets")


def _common_row(order_number: str, tracking_number: str) -> tuple:
    return (
        order_number,
        tracking_number,
        "US",
        "UAT Buyer Auto",
        "IL",
        "Springfield",
        "123 UAT Lane",
        "62704",
        "UAT Demo Product",
        5000.0,
        1.0,
        50.0,
        "",
        131276.0,
        "01/06/2026",     # CREATIVE  date in DD/MM/YYYY (Vietnamese date format)
        "",
        "Get label",
        f"https://example.invalid/label/{tracking_number}.pdf",
        f"https://example.invalid/qr/{tracking_number}",
    )


def build_happy_path(target: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Tracking"
    ws.append(list(GKE_HEADERS))
    for order_number, tracking_number, _carrier in UAT_ROWS:
        ws.append(list(_common_row(order_number, tracking_number)))
    wb.save(target)
    log.info("wrote happy-path GKE: %s (rows=%d)", target, len(UAT_ROWS))


def build_broken_schema(target: Path) -> None:
    """Same data layout BUT drops 'TRACKING NUMBER' column so the schema
    fingerprint changes — wizard must flag `is_new_schema=True`.
    """
    headers = tuple(h for h in GKE_HEADERS if h != "TRACKING NUMBER")
    wb = Workbook()
    ws = wb.active
    ws.title = "Tracking"
    ws.append(list(headers))
    for order_number, tracking_number, _carrier in UAT_ROWS:
        full = _common_row(order_number, tracking_number)
        broken = tuple(v for i, v in enumerate(full) if GKE_HEADERS[i] != "TRACKING NUMBER")
        ws.append(list(broken))
    wb.save(target)
    log.info("wrote broken-schema GKE: %s (one column removed)", target)


def main() -> int:
    happy = ASSETS_DIR / "gke_excel_sample.xlsx"
    broken = ASSETS_DIR / "gke_excel_broken_schema.xlsx"
    build_happy_path(happy)
    build_broken_schema(broken)
    return 0


if __name__ == "__main__":
    sys.exit(main())
