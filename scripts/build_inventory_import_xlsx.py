"""Convert owner's inventory Excel files to standard Odoo `base_import` XLSX.

Generates 4 ready-to-import XLSX files that the owner uploads via the
standard Odoo Import UI (Settings → Technical → Import, or each model
list view's ⋮ → Import records). No custom Odoo wizard is built —
this is the Standard-Odoo-First path per MP006 slice P-INV-INITIAL-LOAD.

Inputs (read-only, expected under `.0temp/raw/inventory/`):

* ``Tồn kho PD_Hatafa.xlsx`` — primary on-hand snapshot
  (133 rows, columns: SẢN PHẨM + TỒN CUỐI (SL THỰC TẾ)).
* ``File Vat dung - QUẢN LÝ XUẤT NHẬP KHO.xlsx`` — enrichment source
  (sheet ``TỔNG XUẤT - NHẬP Quy IV2025``: PHÂN LOẠI SP, ĐƠN VỊ,
  Tồn kho an toàn, Điểm đặt hàng, Số lượng đặt hàng).

Outputs (written to ``--output-dir`` / default ``.0temp/import/inventory/<ts>/``):

* ``01_product_categories.xlsx``  →  ``product.category``
* ``02_product_templates.xlsx``   →  ``product.template``
* ``03_initial_on_hand.xlsx``     →  ``stock.quant`` (set inventory_quantity → Apply)
* ``04_reorder_rules.xlsx``       →  ``stock.warehouse.orderpoint``

Plus ``conversion_report.txt`` summarising rows, name-match misses,
and MSC fallbacks for the owner to review before import.

External-ID anchor: ``inv_initial_load.<slug>`` for idempotency —
re-importing the same XLSX updates-in-place via Odoo's standard
``ir.model.data`` resolution (no duplicates).

Usage::

    python3 scripts/build_inventory_import_xlsx.py
    python3 scripts/build_inventory_import_xlsx.py --dry-run
    python3 scripts/build_inventory_import_xlsx.py \\
        --input-dir .0temp/raw/inventory \\
        --output-dir /tmp/inv_test
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

import openpyxl
from openpyxl.workbook import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sku_classifier import MSC, classify, validate_v2_sku  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
_logger = logging.getLogger('build_inventory_import_xlsx')


DEFAULT_INPUT_DIR: Final[Path] = Path('.0temp/raw/inventory')
DEFAULT_OUTPUT_ROOT: Final[Path] = Path('.0temp/import/inventory')

TON_KHO_FILE: Final[str] = 'Tồn kho PD_Hatafa.xlsx'
VAT_DUNG_FILE: Final[str] = 'File Vat dung - QUẢN LÝ XUẤT NHẬP KHO.xlsx'
VAT_DUNG_SHEET: Final[str] = 'TỔNG XUẤT - NHẬP Quy IV2025'

EXTID_MODULE: Final[str] = 'inv_initial_load'
WAREHOUSE_XMLID: Final[str] = 'stock.warehouse0'
STOCK_LOCATION_XMLID: Final[str] = 'stock.stock_location_stock'
UOM_UNITS_XMLID: Final[str] = 'uom.product_uom_unit'

# Default material code used in the SKU SIZE-anchored fallback. 'MX' = mixed.
DEFAULT_MAT2: Final[str] = 'MX'


# --- Data classes --------------------------------------------------------

@dataclass(frozen=True)
class EnrichmentRow:
    """One row from File Vat dung's TỔNG XUẤT - NHẬP Quy IV2025 sheet."""

    category_vi: str            # 'ĐĨA', 'TẠP DỀ', etc.
    uom: str                    # 'PCS'
    safety: float | None        # Tồn kho an toàn
    reorder_point: float | None  # Điểm đặt hàng
    reorder_qty: float | None   # Số lượng đặt hàng


@dataclass
class ProductRow:
    """One row destined for the four output XLSX files."""

    row_idx: int                          # 1-based position in Tồn kho
    name: str                             # Vietnamese product name
    on_hand: float                        # TỒN CUỐI (SL THỰC TẾ)
    enrichment: EnrichmentRow | None      # may be missing if name not in Vat dung
    fam_code: str = MSC
    default_code: str = ''
    category_extid: str = ''


@dataclass
class ConversionStats:
    total_rows: int = 0
    enriched_rows: int = 0
    unenriched_rows: list[str] = field(default_factory=list)
    msc_fallback_rows: list[str] = field(default_factory=list)
    invalid_skus: list[tuple[str, str]] = field(default_factory=list)
    categories: dict[str, str] = field(default_factory=dict)  # vi_name → extid


# --- Helpers -------------------------------------------------------------

def _normalise(text: str | None) -> str:
    """Strip + collapse whitespace; tolerate None."""
    if text is None:
        return ''
    return re.sub(r'\s+', ' ', str(text)).strip()


def _slug(text: str) -> str:
    """ASCII-safe lowercase slug for external IDs. Vietnamese-aware."""
    nfkd = unicodedata.normalize('NFKD', text)
    ascii_only = ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
    ascii_only = ascii_only.replace('đ', 'd').replace('Đ', 'd').lower()
    return re.sub(r'[^a-z0-9]+', '_', ascii_only).strip('_')


def _maybe_float(cell: object) -> float | None:
    if cell is None or cell == '':
        return None
    try:
        return float(cell)
    except (TypeError, ValueError):
        return None


# --- Parsing -------------------------------------------------------------

def parse_ton_kho(path: Path) -> list[tuple[int, str, float]]:
    """Read Tồn kho file → list of (row_idx, name, on_hand)."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True, keep_links=False)
    ws = wb.active
    out: list[tuple[int, str, float]] = []
    for idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=1):
        name = _normalise(row[0] if row else '')
        qty = _maybe_float(row[1] if len(row) > 1 else None)
        if not name:
            continue
        out.append((idx, name, qty if qty is not None else 0.0))
    wb.close()
    _logger.info('Tồn kho: %d product rows', len(out))
    return out


def parse_vat_dung(path: Path) -> dict[str, EnrichmentRow]:
    """Read Vat dung enrichment sheet → {normalised_name: EnrichmentRow}.

    Header row is row 3; data starts row 4. Columns indexed from 0:
      A=STT, B=PHÂN LOẠI SP, C=SẢN PHẨM, D=ĐƠN VỊ, E=TỒN ĐẦU,
      F=SL NHẬP, G=SL XUẤT, H=TỒN CUỐI, I=Tồn kho an toàn,
      J=Điểm đặt hàng, K=Số lượng đặt hàng.
    PHÂN LOẠI SP only appears on the first row of each group; we
    forward-fill so every product inherits its section's category.
    """
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True, keep_links=False)
    ws = wb[VAT_DUNG_SHEET]
    out: dict[str, EnrichmentRow] = {}
    current_category = ''
    for row in ws.iter_rows(min_row=4, values_only=True):
        if not row:
            continue
        # B / col index 1: PHÂN LOẠI SP (only on group-first row)
        cat = _normalise(row[1] if len(row) > 1 else '')
        if cat:
            current_category = cat
        # C / col 2: SẢN PHẨM
        name = _normalise(row[2] if len(row) > 2 else '')
        if not name:
            continue
        uom = _normalise(row[3] if len(row) > 3 else 'PCS') or 'PCS'
        safety = _maybe_float(row[8] if len(row) > 8 else None)
        reorder = _maybe_float(row[9] if len(row) > 9 else None)
        reorder_qty = _maybe_float(row[10] if len(row) > 10 else None)
        out[name.lower()] = EnrichmentRow(
            category_vi=current_category or 'CHƯA PHÂN LOẠI',
            uom=uom,
            safety=safety,
            reorder_point=reorder,
            reorder_qty=reorder_qty,
        )
    wb.close()
    _logger.info('Vat dung: %d enrichment rows (sheet %r)', len(out), VAT_DUNG_SHEET)
    return out


# --- Enrichment + SKU derivation ----------------------------------------

def enrich_and_classify(
    raw_rows: list[tuple[int, str, float]],
    enrichment: dict[str, EnrichmentRow],
    stats: ConversionStats,
) -> list[ProductRow]:
    """Merge Tồn kho rows with Vat dung enrichment + derive default_code."""
    rows: list[ProductRow] = []
    stats.total_rows = len(raw_rows)

    for row_idx, name, on_hand in raw_rows:
        enr = enrichment.get(name.lower())
        if enr:
            stats.enriched_rows += 1
        else:
            stats.unenriched_rows.append(name)

        fam = classify(name)
        if fam == MSC:
            stats.msc_fallback_rows.append(name)

        # Generic-size fallback per SKU_GRAMMAR §7.1 (S\d+ allowed in SIZE slot).
        default_code = f'{fam}-{DEFAULT_MAT2}-S{row_idx:03d}'
        if not validate_v2_sku(default_code):
            stats.invalid_skus.append((name, default_code))

        # Category external ID: build from enrichment Vietnamese category name,
        # or fallback to 'cat_uncategorised' for rows missing from Vat dung.
        cat_name = enr.category_vi if enr else 'CHƯA PHÂN LOẠI'
        cat_extid = f'{EXTID_MODULE}.cat_{_slug(cat_name)}'
        stats.categories.setdefault(cat_name, cat_extid)

        rows.append(ProductRow(
            row_idx=row_idx,
            name=name,
            on_hand=on_hand,
            enrichment=enr,
            fam_code=fam,
            default_code=default_code,
            category_extid=cat_extid,
        ))
    return rows


# --- XLSX writers --------------------------------------------------------

def _new_wb(headers: list[str]) -> tuple[Workbook, object]:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    return wb, ws


def write_categories(rows: list[ProductRow], stats: ConversionStats, path: Path) -> int:
    """One row per unique enrichment category (PHÂN LOẠI SP)."""
    wb, ws = _new_wb(['id', 'name'])
    written = 0
    for cat_name, cat_extid in sorted(stats.categories.items()):
        ws.append([cat_extid.split('.', 1)[1], cat_name])
        written += 1
    wb.save(path)
    return written


def write_templates(rows: list[ProductRow], path: Path) -> int:
    """133 rows for product.template."""
    headers = [
        'id', 'name', 'default_code', 'type', 'is_storable', 'tracking',
        'categ_id/id', 'uom_id/id', 'uom_po_id/id', 'sale_ok', 'purchase_ok',
    ]
    wb, ws = _new_wb(headers)
    for r in rows:
        ws.append([
            f'tonkho_pd_hatafa_{r.row_idx:03d}',
            r.name,
            r.default_code,
            'consu',          # Odoo 19: type+is_storable together
            'TRUE',
            'none',            # No Tracking per owner decision 2026-05-30
            r.category_extid,
            UOM_UNITS_XMLID,
            UOM_UNITS_XMLID,
            'TRUE',
            'TRUE',
        ])
    wb.save(path)
    return len(rows)


def write_on_hand(rows: list[ProductRow], path: Path) -> int:
    """stock.quant rows with inventory_quantity for the Physical Inventory flow."""
    headers = ['product_id/id', 'location_id/id', 'inventory_quantity']
    wb, ws = _new_wb(headers)
    for r in rows:
        ws.append([
            f'{EXTID_MODULE}.tonkho_pd_hatafa_{r.row_idx:03d}',
            STOCK_LOCATION_XMLID,
            r.on_hand,
        ])
    wb.save(path)
    return len(rows)


def write_reorder_rules(rows: list[ProductRow], path: Path) -> int:
    """One orderpoint per row that has BOTH safety AND reorder_point in Vat dung."""
    headers = [
        'product_id/id', 'warehouse_id/id', 'location_id/id',
        'product_min_qty', 'product_max_qty', 'qty_multiple',
    ]
    wb, ws = _new_wb(headers)
    written = 0
    for r in rows:
        enr = r.enrichment
        if not enr or enr.safety is None or enr.reorder_point is None:
            continue
        ws.append([
            f'{EXTID_MODULE}.tonkho_pd_hatafa_{r.row_idx:03d}',
            WAREHOUSE_XMLID,
            STOCK_LOCATION_XMLID,
            enr.safety,                          # product_min_qty
            enr.reorder_point,                   # product_max_qty (replenish up to)
            enr.reorder_qty or 1.0,              # qty_multiple
        ])
        written += 1
    wb.save(path)
    return written


def write_report(stats: ConversionStats, output_dir: Path, counts: dict[str, int]) -> None:
    lines: list[str] = [
        f'Inventory import conversion report — {datetime.now(timezone.utc).isoformat()}',
        '=' * 70,
        f'Total Tồn kho rows           : {stats.total_rows}',
        f'  enriched from Vat dung     : {stats.enriched_rows}',
        f'  not in Vat dung (no UoM/   : {len(stats.unenriched_rows)}',
        '    category/reorder data)',
        f'Categories created           : {len(stats.categories)}',
        f'MSC SKU fallbacks            : {len(stats.msc_fallback_rows)}',
        f'Invalid v2.1 SKUs produced   : {len(stats.invalid_skus)}',
        '',
        'Output XLSX file row counts:',
        *[f'  {name:30s}: {count}' for name, count in counts.items()],
        '',
        '-- Rows missing from Vat dung (owner: review UoM/category for these) --',
        *stats.unenriched_rows[:50],
        ('  ... and %d more' % (len(stats.unenriched_rows) - 50)
         if len(stats.unenriched_rows) > 50 else ''),
        '',
        '-- Rows that fell back to MSC family (owner: refine SKU in 02_*.xlsx if needed) --',
        *stats.msc_fallback_rows[:50],
        ('  ... and %d more' % (len(stats.msc_fallback_rows) - 50)
         if len(stats.msc_fallback_rows) > 50 else ''),
    ]
    (output_dir / 'conversion_report.txt').write_text('\n'.join(lines), encoding='utf-8')


# --- Orchestration -------------------------------------------------------

def run(input_dir: Path, output_dir: Path, dry_run: bool) -> None:
    ton_kho_path = input_dir / TON_KHO_FILE
    vat_dung_path = input_dir / VAT_DUNG_FILE
    for p in (ton_kho_path, vat_dung_path):
        if not p.exists():
            _logger.error('Input file missing: %s', p)
            sys.exit(2)

    raw_rows = parse_ton_kho(ton_kho_path)
    enrichment = parse_vat_dung(vat_dung_path)
    stats = ConversionStats()
    rows = enrich_and_classify(raw_rows, enrichment, stats)

    if dry_run:
        _logger.info('--dry-run set — skipping XLSX writes. Stats only:')
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        '01_product_categories.xlsx': output_dir / '01_product_categories.xlsx',
        '02_product_templates.xlsx': output_dir / '02_product_templates.xlsx',
        '03_initial_on_hand.xlsx': output_dir / '03_initial_on_hand.xlsx',
        '04_reorder_rules.xlsx': output_dir / '04_reorder_rules.xlsx',
    }
    counts: dict[str, int] = {}
    if dry_run:
        counts['01_product_categories.xlsx'] = len(stats.categories)
        counts['02_product_templates.xlsx'] = len(rows)
        counts['03_initial_on_hand.xlsx'] = len(rows)
        counts['04_reorder_rules.xlsx'] = sum(
            1 for r in rows
            if r.enrichment and r.enrichment.safety is not None
            and r.enrichment.reorder_point is not None
        )
    else:
        counts['01_product_categories.xlsx'] = write_categories(rows, stats, paths['01_product_categories.xlsx'])
        counts['02_product_templates.xlsx'] = write_templates(rows, paths['02_product_templates.xlsx'])
        counts['03_initial_on_hand.xlsx'] = write_on_hand(rows, paths['03_initial_on_hand.xlsx'])
        counts['04_reorder_rules.xlsx'] = write_reorder_rules(rows, paths['04_reorder_rules.xlsx'])
        write_report(stats, output_dir, counts)

    _logger.info('Conversion summary:')
    _logger.info('  total rows         : %d', stats.total_rows)
    _logger.info('  enriched           : %d', stats.enriched_rows)
    _logger.info('  un-enriched        : %d', len(stats.unenriched_rows))
    _logger.info('  categories         : %d', len(stats.categories))
    _logger.info('  MSC fallbacks      : %d', len(stats.msc_fallback_rows))
    _logger.info('  invalid v2.1 SKUs  : %d', len(stats.invalid_skus))
    for name, count in counts.items():
        _logger.info('  %-30s -> %d rows', name, count)
    if not dry_run:
        _logger.info('Output directory: %s', output_dir.resolve())
        _logger.info('Report: %s', (output_dir / 'conversion_report.txt').resolve())


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--input-dir', type=Path, default=DEFAULT_INPUT_DIR)
    p.add_argument('--output-dir', type=Path, default=None,
                   help=f'Default: {DEFAULT_OUTPUT_ROOT}/<UTC-timestamp>/')
    p.add_argument('--dry-run', action='store_true',
                   help='Parse + classify but skip XLSX writes.')
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    output_dir = args.output_dir or (
        DEFAULT_OUTPUT_ROOT / datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%SZ')
    )
    run(input_dir=args.input_dir, output_dir=output_dir, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
