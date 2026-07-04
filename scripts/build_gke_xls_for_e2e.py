"""Generate a GKE-format .xlsx tracking file for the E2E runner.

Replicates the canonical 19-column schema from
``.0temp/sample_bc_don_hang2026_04_08.xls`` so the
``tracking.import.wizard`` schema fingerprint stays predictable. Header
row order matches the sample byte-for-byte (uppercased + stripped on
parse, per multichannel_hub_fulfillment.services.gke_excel_parser).

Outputs ``.xlsx`` (openpyxl). The file is read by both the wizard
import path and the ``logistics.partner.gke`` GDrive inbox poller —
both consume xlsx via openpyxl.

Optional ``--upload-to-drive`` drops the file in the Drive folder used
by P2-06 so the polling cron picks it up.

Usage::

    python3 scripts/build_gke_xls_for_e2e.py \\
        --out .0temp/gke_e2e_2026_05_10.xlsx \\
        --receipts 3703975562,3711793551,3710809073,3708041263

    # Upload to the Drive folder owner provided
    python3 scripts/build_gke_xls_for_e2e.py \\
        --out .0temp/gke_e2e_2026_05_10.xlsx \\
        --upload-to-drive
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from openpyxl import Workbook

REPO_ROOT = Path(__file__).resolve().parent.parent

# Header order + names lifted verbatim from
# .0temp/sample_bc_don_hang2026_04_08.xls (R0). Trailing space on
# 'CREATIVE ' is intentional — replicates the source.
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

# Carrier rotation: USPS / UniUni / YunExpress / 4PX exercises P2-02
# carrier auto-detect prefix matching. Tracking-number prefixes are
# realistic patterns; carrier seed regexes anchor on these.
TRACKING_BY_CARRIER: dict[str, str] = {
    # 18 chars + 4-digit suffix = 22 total — the carrier-seed USPS regex
    # ^(9[0-9]{15,21}|...)$ caps at 22 digits; 23 silently fails detection
    # (MF-E2E-3a 2026-07-04).
    "USPS": "940011120255556000",
    "UniUni": "UUS6482620070",
    "YunExpress": "YT24202000020",
    "4PX": "4PX2024020000",
}
CARRIER_ROTATION: tuple[str, ...] = ("USPS", "UniUni", "YunExpress", "4PX")

DEFAULT_DRIVE_FOLDER_ID = "1-cY65RDkUGqpUxs8gPrvzV8xuLv56ogW"
DEFAULT_RECEIPTS = "3703975562,3711793551,3710809073,3708041263"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger("build_gke_xls")


@dataclass(frozen=True)
class TrackingRow:
    order_number: str
    tracking_number: str
    carrier: str
    consignee: str
    country: str
    state: str
    city: str
    address: str
    postcode: str
    product_name: str
    received_at: str

    def to_excel_row(self) -> tuple:
        # Column order MUST match GKE_HEADERS.
        return (
            self.order_number,                 # ORDER NUMBER
            self.tracking_number,              # TRACKING NUMBER
            self.country,                      # COUNTRY
            self.consignee,                    # SONSIGNEE NAME
            self.state,                        # STATE
            self.city,                         # CITY
            self.address,                      # ADDRESS
            self.postcode,                     # POSTCODE
            self.product_name,                 # PRODUCT NAME
            5000.0,                            # VALUE
            1.0,                               # QUANTITY
            50.0,                              # WEIGHT AT COSTOMER
            "",                                # WEIGHT AT GKE
            131276.0,                          # COST
            self.received_at,                  # CREATIVE  (yes, trailing space)
            "",                                # Ngày nhận tại kho
            "Get label",                       # Tình trạng đơn hàng
            f"https://example.invalid/label/{self.tracking_number}.pdf",
            f"https://example.invalid/qr/{self.tracking_number}",
        )


def _build_rows(receipts: tuple[str, ...]) -> tuple[TrackingRow, ...]:
    today = date.today().strftime("%d/%m/%Y")
    rows = []
    for i, receipt in enumerate(receipts):
        carrier = CARRIER_ROTATION[i % len(CARRIER_ROTATION)]
        prefix = TRACKING_BY_CARRIER[carrier]
        tracking = f"{prefix}{i + 1:04d}"
        rows.append(
            TrackingRow(
                order_number=receipt,
                tracking_number=tracking,
                carrier=carrier,
                consignee=f"E2E Buyer {i + 1}",
                country="US",
                state="CA",
                city="DEMO CITY",
                address=f"{100 + i} Demo Street",
                postcode="90001",
                product_name="Demo Product",
                received_at=today,
            )
        )
    return tuple(rows)


def _emit_xlsx(rows: tuple[TrackingRow, ...], out_path: Path) -> bytes:
    wb = Workbook()
    ws = wb.active
    if ws is None:  # pragma: no cover — openpyxl guarantees an active sheet
        raise RuntimeError("openpyxl returned a workbook with no active sheet")
    ws.title = "ĐƠN HÀNG"
    ws.append(list(GKE_HEADERS))
    for row in rows:
        ws.append(list(row.to_excel_row()))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path.read_bytes()


def _resolve_service_account_path(explicit: str | None) -> Path:
    """Return the SA JSON path, with fallback discovery.

    Order of resolution:
      1. ``--service-account`` CLI override
      2. ``$GDRIVE_SERVICE_ACCOUNT_JSON``
      3. ``secrets/service-account.json`` (canonical name)
      4. Any ``secrets/*.json`` whose ``type`` field is ``service_account``
         (catches the legacy ``regal-cursor-369422-*.json`` filename
         currently checked into the repo)
    """
    if explicit:
        return Path(explicit).resolve()
    env_override = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON")
    if env_override:
        return Path(env_override).resolve()
    canonical = REPO_ROOT / "secrets" / "service-account.json"
    if canonical.exists():
        return canonical
    secrets_dir = REPO_ROOT / "secrets"
    if secrets_dir.is_dir():
        import json as _json
        for cand in sorted(secrets_dir.glob("*.json")):
            try:
                data = _json.loads(cand.read_text())
            except Exception:
                continue
            if data.get("type") == "service_account":
                return cand.resolve()
    raise FileNotFoundError(
        "Drive service-account JSON not found. Set "
        "$GDRIVE_SERVICE_ACCOUNT_JSON, pass --service-account, or place "
        "the SA JSON at secrets/service-account.json."
    )


def _upload_to_drive(out_path: Path, folder_id: str, sa_path: Path) -> str:
    """Upload xlsx to the GDrive folder via service-account JSON.

    Uses ``supportsAllDrives=True`` because the staging Drive folder
    lives on a Shared Drive (per memory feedback_staging_gdrive_provisioning).
    Returns the new file id.
    """
    if not sa_path.exists():
        raise FileNotFoundError(f"SA JSON not found at {sa_path}")
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise RuntimeError(
            "google-api-python-client + google-auth must be installed to upload. "
            "pip install google-api-python-client google-auth"
        ) from exc

    creds = service_account.Credentials.from_service_account_file(
        str(sa_path),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    media = MediaFileUpload(
        str(out_path),
        mimetype=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        resumable=False,
    )
    body = {"name": out_path.name, "parents": [folder_id]}
    result = service.files().create(  # type: ignore[no-untyped-call]
        body=body,
        media_body=media,
        fields="id,name,parents",
        supportsAllDrives=True,
    ).execute()
    return result.get("id", "")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out",
        default=str(REPO_ROOT / ".0temp" / f"gke_e2e_{date.today().isoformat()}.xlsx"),
        help="Output xlsx path (default: .0temp/gke_e2e_<today>.xlsx)",
    )
    p.add_argument(
        "--receipts",
        default=DEFAULT_RECEIPTS,
        help="Comma-separated etsy receipt IDs (default: the 4 ordertest2 receipts)",
    )
    p.add_argument(
        "--upload-to-drive",
        action="store_true",
        help="Upload the generated xlsx into the GDrive folder via service account.",
    )
    p.add_argument(
        "--drive-folder-id",
        default=DEFAULT_DRIVE_FOLDER_ID,
        help=f"GDrive folder ID to drop file into (default: {DEFAULT_DRIVE_FOLDER_ID})",
    )
    p.add_argument(
        "--service-account", default="",
        help="Path to service-account JSON (default: autodiscover under "
             "secrets/ — picks the first file with type=='service_account').",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    receipts = tuple(r.strip() for r in args.receipts.split(",") if r.strip())
    if not receipts:
        _log.error("--receipts produced an empty list")
        return 2

    out_path = Path(args.out).resolve()
    rows = _build_rows(receipts)
    _emit_xlsx(rows, out_path)
    try:
        display_path = out_path.relative_to(REPO_ROOT)
    except ValueError:
        display_path = out_path
    _log.info(
        "wrote %s (%d row(s); receipts=%s)",
        display_path, len(rows), ",".join(receipts),
    )

    if args.upload_to_drive:
        try:
            sa_path = _resolve_service_account_path(args.service_account or None)
            _log.info("using SA JSON: %s", sa_path)
            file_id = _upload_to_drive(out_path, args.drive_folder_id, sa_path)
        except Exception as exc:
            _log.error("Drive upload failed: %s", exc)
            return 3
        _log.info("uploaded to Drive folder=%s file_id=%s", args.drive_folder_id, file_id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
