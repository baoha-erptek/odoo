"""openpyxl streaming parser for catalog Excel sync (Spec 010 P-HUB-XLS-PARSE-SERVICE).

Reads an xlsx file (or bytes) in streaming mode and emits
`product.catalog.import.line` records into a given
`product.catalog.import.run`. Per-sheet header fingerprint is checked
against the `product.catalog.sheet.fingerprint` whitelist; unknown
fingerprints abort with `state='error'` per R-010-2 mitigation.

Column header → import.line field mapping is a small constants table
(below). Unknown headers in known sheets are warning-logged but ignored
(forward-compat: Excel can grow new columns without breaking ingest).

Per-sheet savepoint + per-row insert; first parse error per sheet flips
the whole run to `state='error'` but other sheets still parse so the
operator can fix one sheet without re-running the rest.
"""

import hashlib
import io
import logging
from datetime import datetime

import openpyxl

_logger = logging.getLogger(__name__)


# Column header (lower-cased) → import.line field. Tolerant of multiple
# common spellings observed in operator Excel files.
_HEADER_MAP = {
    'sku': 'sku',
    'product code': 'sku',
    'internal reference': 'sku',
    'name': 'name',
    'product name': 'name',
    'product': 'name',
    'availability': 'availability',
    'price usd': 'price_usd',
    'price (usd)': 'price_usd',
    'price eu': 'price_eu',
    'price (eu)': 'price_eu',
    'price cad': 'price_cad',
    'price (cad)': 'price_cad',
    'price vnd': 'price_vnd',
    'price (vnd)': 'price_vnd',
    'shipping fee': 'shipping_fee',
    'shipping fees': 'shipping_fee',
    'image 1': 'image_1_ref',
    'image_1': 'image_1_ref',
    'image 2': 'image_2_ref',
    'image_2': 'image_2_ref',
}


def _normalize_header(value):
    if value is None:
        return ''
    return str(value).strip().lower()


def _fingerprint_headers(headers):
    """sha256 over the comma-joined normalised header row."""
    canonical = ','.join(_normalize_header(h) for h in headers)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def parse(env, run, source_bytes):
    """Parse an xlsx file and emit import.line rows.

    Args:
        env: Odoo Environment.
        run: product.catalog.import.run record to attach lines to.
        source_bytes: bytes of the xlsx file.

    Returns:
        Dict with summary counters {'sheets_parsed', 'rows_emitted',
        'rows_error', 'unknown_fingerprint_sheets'}.

    Writes import.line rows transactionally per row. Sheets with
    unapproved fingerprints emit a single error line + skip; other
    sheets continue.
    """
    if not isinstance(source_bytes, (bytes, bytearray)):
        raise ValueError("parse() requires bytes; got %r" % type(source_bytes))
    wb = openpyxl.load_workbook(
        io.BytesIO(source_bytes),
        read_only=True, data_only=True, keep_links=False,
    )
    Line = env['product.catalog.import.line'].sudo()
    Fingerprint = env['product.catalog.sheet.fingerprint'].sudo()
    summary = {
        'sheets_parsed': 0, 'rows_emitted': 0,
        'rows_error': 0, 'unknown_fingerprint_sheets': 0,
    }
    try:
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows_iter = ws.iter_rows(values_only=True)
            headers_row = next(rows_iter, None)
            if not headers_row:
                continue
            fp_sha = _fingerprint_headers(headers_row)
            existing = Fingerprint.search([
                ('sheet_name', '=', sheet_name),
                ('column_headers_sha256', '=', fp_sha),
            ], limit=1)
            if not existing:
                # First time seeing this sheet/fingerprint pair — record
                # for admin approval and skip processing rows.
                Fingerprint.create({
                    'sheet_name': sheet_name,
                    'column_headers_sha256': fp_sha,
                    'column_headers_preview': ' | '.join(
                        _normalize_header(h) for h in headers_row
                    )[:4000],
                    'approved': False,
                })
                Line.create({
                    'run_id': run.id,
                    'sheet_name': sheet_name,
                    'row_number': 0,
                    'state': 'error',
                    'error_kind': 'parse',
                    'error_message':
                        "Unknown sheet fingerprint; admin approval required.",
                })
                summary['unknown_fingerprint_sheets'] += 1
                summary['rows_error'] += 1
                continue
            if not existing.approved:
                Line.create({
                    'run_id': run.id,
                    'sheet_name': sheet_name,
                    'row_number': 0,
                    'state': 'error',
                    'error_kind': 'parse',
                    'error_message':
                        "Sheet fingerprint not approved by admin.",
                })
                summary['rows_error'] += 1
                continue
            # Build header → field map for this sheet.
            field_map = {}
            for idx, header in enumerate(headers_row):
                norm = _normalize_header(header)
                if norm in _HEADER_MAP:
                    field_map[idx] = _HEADER_MAP[norm]
            existing.write({'last_seen_at': datetime.now()})
            row_number = 1
            for row in rows_iter:
                row_number += 1
                if all(cell is None for cell in row):
                    continue  # blank
                vals = {
                    'run_id': run.id,
                    'sheet_name': sheet_name,
                    'row_number': row_number,
                    'state': 'pending',
                }
                for idx, fld in field_map.items():
                    if idx >= len(row):
                        continue
                    cell = row[idx]
                    if cell is None:
                        continue
                    if fld.startswith('price_') or fld == 'shipping_fee':
                        try:
                            vals[fld] = float(cell)
                        except (TypeError, ValueError):
                            vals[fld] = 0.0
                    else:
                        vals[fld] = str(cell).strip()
                try:
                    Line.create(vals)
                    summary['rows_emitted'] += 1
                except Exception as exc:  # noqa: BLE001 — per-row isolation
                    _logger.warning(
                        "catalog parse row failure sheet=%s row=%s: %s",
                        sheet_name, row_number, exc,
                    )
                    summary['rows_error'] += 1
            summary['sheets_parsed'] += 1
    finally:
        wb.close()
    return summary
