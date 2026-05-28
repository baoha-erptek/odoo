"""Extract a catalog row's embedded images into base64 fixture files.

The product catalog (`.0temp/raw/[2025] Product Catalog.xlsx`) stores product
photos as drawing objects anchored to cells, not as cell URLs. This helper maps
the images anchored to a given (sheet, row) to their `xl/media/*` parts, then
writes each as a base64 text file the Playwright real-product UAT injects onto a
`product.template` via JSON-RPC (`image_1920` + `x_extra_image_ids`).

Row numbering is 1-based to match the spreadsheet UI (the apron `APF` is row 5
of the Apparel sheet). The first anchored image becomes `<prefix>_main.b64`; the
rest become `<prefix>_extra1.b64`, `<prefix>_extra2.b64`, ... in anchor order.

Usage:
    python3 fixtures/extract_catalog_images.py \
        --sheet Apparel --row 5 --prefix apf
"""
from __future__ import annotations

import argparse
import base64
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_XLSX = REPO_ROOT / ".0temp" / "raw" / "[2025] Product Catalog.xlsx"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"

_NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _sheet_to_drawing(z: zipfile.ZipFile, sheet_name: str) -> str | None:
    """Resolve a sheet display name to its drawing part path (or None)."""
    wb = z.read("xl/workbook.xml").decode("utf-8", "ignore")
    rid = None
    for m in re.finditer(r'<sheet [^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wb):
        if m.group(1) == sheet_name:
            rid = m.group(2)
            break
    if not rid:
        return None
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "ignore")
    target = None
    for m in re.finditer(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels):
        if m.group(1) == rid:
            target = m.group(2)
            break
    if not target:
        return None
    sheet_path = "xl/" + target.replace("../", "")
    srels_path = sheet_path.replace("worksheets/", "worksheets/_rels/") + ".rels"
    if srels_path not in z.namelist():
        return None
    srels = z.read(srels_path).decode("utf-8", "ignore")
    dm = re.search(r'Target="([^"]*drawing[^"]*)"', srels)
    if not dm:
        return None
    return "xl/" + dm.group(1).replace("../", "")


def _images_at_row(z: zipfile.ZipFile, drawing_path: str, row0: int) -> list[str]:
    """Return media part paths for images anchored with from-row == row0 (0-based)."""
    dxml = z.read(drawing_path).decode("utf-8", "ignore")
    drels_path = drawing_path.replace("drawings/", "drawings/_rels/") + ".rels"
    drels = z.read(drels_path).decode("utf-8", "ignore") if drels_path in z.namelist() else ""
    rid_to_media = {
        m.group(1): "xl/" + m.group(2).replace("../", "")
        for m in re.finditer(r'Id="([^"]+)"[^>]*Target="([^"]*media[^"]*)"', drels)
    }
    anchors = re.findall(
        r"<xdr:from>.*?<xdr:row>(\d+)</xdr:row>.*?</xdr:from>.*?r:embed=\"([^\"]+)\"",
        dxml,
        re.S,
    )
    return [rid_to_media[rid] for row, rid in anchors if int(row) == row0 and rid in rid_to_media]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=str(DEFAULT_XLSX))
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--row", type=int, required=True, help="1-based spreadsheet row")
    ap.add_argument("--prefix", required=True, help="output filename prefix, e.g. 'apf'")
    ap.add_argument("--out-dir", default=str(ASSETS_DIR))
    args = ap.parse_args()

    xlsx = Path(args.xlsx)
    if not xlsx.exists():
        print(f"ERROR: catalog not found: {xlsx}", file=sys.stderr)
        return 2

    z = zipfile.ZipFile(xlsx)
    drawing = _sheet_to_drawing(z, args.sheet)
    if not drawing:
        print(f"ERROR: no drawing for sheet {args.sheet!r}", file=sys.stderr)
        return 2

    media = _images_at_row(z, drawing, args.row - 1)
    if not media:
        print(f"ERROR: no images anchored at {args.sheet!r} row {args.row}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for idx, part in enumerate(media):
        raw = z.read(part)
        name = f"{args.prefix}_main.b64" if idx == 0 else f"{args.prefix}_extra{idx}.b64"
        out_path = out_dir / name
        out_path.write_text(base64.b64encode(raw).decode("ascii"))
        written.append(f"{name} <- {part} ({len(raw)} bytes)")

    print(f"Extracted {len(written)} image(s) from {args.sheet!r} row {args.row}:")
    for line in written:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
