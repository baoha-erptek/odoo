"""Pure-function GKE Excel parser.

Returns ParseResult(schema_hash, headers, rows). No ORM access.

Header normalization (must match build_fixtures.compute_schema_hash):
- strip + uppercase per cell
- join with `|`
- SHA-256 hex of UTF-8 bytes

Row hash: same algorithm over `|`-joined str values.

openpyxl is loaded with read_only=True, data_only=True, keep_links=False
to defend against XLSX-bomb / formula-injection / external-link probes.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover — manifest external_dependencies catches this
    load_workbook = None


@dataclass(frozen=True)
class ParseResult:
    schema_hash: str
    headers: tuple[str, ...]
    rows: tuple[tuple, ...]


def normalize_headers(headers) -> tuple[str, ...]:
    """Stripped + uppercased header tuple."""
    return tuple((h or '').strip().upper() for h in headers)


def compute_schema_hash(headers) -> str:
    normalized = normalize_headers(headers)
    return hashlib.sha256('|'.join(normalized).encode('utf-8')).hexdigest()


def compute_source_row_hash(row_values) -> str:
    parts = [str(v) if v is not None else '' for v in row_values]
    return hashlib.sha256('|'.join(parts).encode('utf-8')).hexdigest()


def parse(file_bytes: bytes) -> ParseResult:
    """Parse XLSX bytes into header + rows.

    First worksheet, first row treated as headers. Empty rows skipped.
    Raises ValueError on malformed file (no sheet, no headers).
    """
    if load_workbook is None:
        raise ImportError(
            "openpyxl required — declare in __manifest__ external_dependencies.")
    if not file_bytes:
        raise ValueError("Empty file bytes.")

    wb = load_workbook(
        io.BytesIO(file_bytes),
        read_only=True,
        data_only=True,
        keep_links=False,
    )
    try:
        ws = wb.active
        if ws is None:
            raise ValueError("Workbook has no active sheet.")

        rows_iter = ws.iter_rows(values_only=True)
        try:
            first = next(rows_iter)
        except StopIteration as exc:
            raise ValueError("Workbook is empty.") from exc

        headers = tuple(str(h) if h is not None else '' for h in first)
        if not any(h.strip() for h in headers):
            raise ValueError("First row contains no headers.")

        data_rows = tuple(
            row for row in rows_iter
            if row and any(cell is not None and str(cell).strip() for cell in row)
        )
    finally:
        wb.close()

    schema_hash = compute_schema_hash(headers)
    return ParseResult(schema_hash=schema_hash, headers=headers, rows=data_rows)
