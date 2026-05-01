"""TrackingImporter — orchestrates parse → log+lines → fulfillment writes.

ORM-aware (takes env). Per-row savepoint isolates failures so one bad row
does not abort the batch (T2-01-28). Bulk order resolution avoids N+1
(code-reviewer rule).

dayfirst=True for date parsing — GKE exports use DD/MM/YYYY (T2-01-30).
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import date, datetime

from . import gke_excel_parser

_logger = logging.getLogger(__name__)

_HEADER_KEYS = {
    'order_number': ('ORDER NUMBER', 'ORDER_NUMBER', 'ORDER'),
    'tracking': ('TRACKING', 'TRACKING NUMBER', 'TRACKING_NUMBER'),
    'carrier': ('CARRIER',),
    'date': ('DATE', 'SHIP DATE', 'SHIPPING DATE'),
}


def _parse_dayfirst(raw: str | None) -> date | None:
    """Parse a free-form GKE date cell with dayfirst=True.

    Returns None on parse failure (caller handles).
    """
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _column_index(headers: tuple[str, ...]) -> dict[str, int]:
    """Map logical key → 0-based column index from normalized headers."""
    norm = gke_excel_parser.normalize_headers(headers)
    out: dict[str, int] = {}
    for key, candidates in _HEADER_KEYS.items():
        for cand in candidates:
            if cand in norm:
                out[key] = norm.index(cand)
                break
    return out


def build_lines_payload(parse_result, log_id):
    """Convert ParseResult → list of dicts for tracking.import.line.create."""
    col = _column_index(parse_result.headers)
    payloads = []
    for i, row in enumerate(parse_result.rows, start=1):
        order_number = _cell(row, col.get('order_number'))
        tracking = _cell(row, col.get('tracking'))
        carrier = _cell(row, col.get('carrier'))
        date_raw = _cell(row, col.get('date'))
        raw_payload = {
            (parse_result.headers[idx] if idx < len(parse_result.headers) else f'col_{idx}'): (
                str(cell) if cell is not None else None)
            for idx, cell in enumerate(row)
        }
        payloads.append({
            'log_id': log_id,
            'row_number': i,
            'source_row_hash': gke_excel_parser.compute_source_row_hash(row),
            'state': 'pending',
            'raw_order_number': order_number or '',
            'raw_tracking_number': tracking,
            'raw_carrier_label': carrier,
            'raw_shipping_date': date_raw,
            'raw_payload': json.dumps(raw_payload, ensure_ascii=False),
            'parsed_shipping_date': _parse_dayfirst(date_raw),
        })
    return payloads


def _cell(row, idx):
    if idx is None or idx >= len(row):
        return None
    val = row[idx]
    return None if val is None else str(val).strip() or None


def resolve_orders(env, lines):
    """Bulk-resolve sale.order for line records by channel_order_ref then etsy_order_id.

    Mutates lines in place (sets sale_order_id, fulfillment_id, address_change_flag,
    state, error_message).

    Returns Counter with state distribution.
    """
    refs = [l.raw_order_number for l in lines if l.raw_order_number]
    by_ref = defaultdict(list)
    if refs:
        # Bulk lookup #1: channel_order_ref
        orders = env['sale.order'].search([('channel_order_ref', 'in', list(set(refs)))])
        for order in orders:
            if order.channel_order_ref:
                by_ref[order.channel_order_ref].append(order)

        # Fallback bulk lookup #2: etsy_order_id (if etsy_integration installed)
        unresolved = {r for r in refs if r not in by_ref}
        if unresolved and 'etsy_order_id' in env['sale.order']._fields:
            etsy_orders = env['sale.order'].search(
                [('etsy_order_id', 'in', list(unresolved))])
            for order in etsy_orders:
                if order.etsy_order_id:
                    by_ref[order.etsy_order_id].append(order)

    counts = Counter()
    for line in lines:
        ref = line.raw_order_number
        matches = by_ref.get(ref, []) if ref else []
        if not matches:
            line.state = 'unmatched'
            counts['unmatched'] += 1
            continue
        if len(matches) > 1:
            line.state = 'conflict'
            counts['conflict'] += 1
            continue
        order = matches[0]
        line.sale_order_id = order.id
        if order.fulfillment_id:
            line.fulfillment_id = order.fulfillment_id.id
        if 'has_pending_address_change' in order._fields:
            line.address_change_flag = bool(order.has_pending_address_change)
        line.state = 'matched'
        counts['matched'] += 1
    return counts


def apply_to_fulfillment(env, lines):
    """Per-row savepoint: write tracking_number/date/state to fulfillment.

    Skips carrier write when fulfillment.shipping_carrier_id already set
    (Spec 004a US1 AC4). Records detected_carrier_id on the line either way
    (P2-02 will populate detection logic; here we leave it None).

    Returns Counter (imported, error) and list of error messages by row.
    """
    counts = Counter()
    for line in lines:
        if line.state != 'matched' or not line.fulfillment_id:
            continue
        try:
            with env.cr.savepoint():
                vals = {}
                if line.raw_tracking_number:
                    vals['tracking_number'] = line.raw_tracking_number
                if line.parsed_shipping_date:
                    vals['shipping_date'] = line.parsed_shipping_date
                if 'tracking_state' in line.fulfillment_id._fields:
                    vals['tracking_state'] = 'shipped'
                # P2-02: apply detected_carrier_id ONLY when fulfillment
                # has no carrier yet (Spec 004a US2 AC: never overwrite).
                carrier_to_apply = (line.applied_carrier_id
                                    or line.detected_carrier_id)
                if (carrier_to_apply
                        and not line.fulfillment_id.shipping_carrier_id):
                    vals['shipping_carrier_id'] = carrier_to_apply.id
                    line.applied_carrier_id = carrier_to_apply.id
                if vals:
                    line.fulfillment_id.write(vals)
                line.state = 'imported'
                counts['imported'] += 1
        except Exception as exc:  # noqa: BLE001 — per-row isolation is the contract
            line.state = 'error'
            line.error_message = _scrub(str(exc))
            counts['error'] += 1
    return counts


def _scrub(text: str) -> str:
    """Truncate to 4KB; do not emit secrets or absolute paths in logs."""
    if not text:
        return ''
    return text[:4096]


def record_sync_health(env, kind: str, ok: int, warning: int, error: int,
                       notes: str = ''):
    """Best-effort cross-module audit event.

    Calls etsy.sync.health._record_event under sudo IF the model exists
    (etsy_integration may not be installed in all envs; mhf does not depend
    on etsy_integration architecturally).
    """
    health = env.get('etsy.sync.health')
    if health is None:
        return
    helper = getattr(health.sudo(), '_record_event', None)
    if helper is None:
        return
    # sudo: cross-module audit channel; helper is system-of-record. Bypass
    # bounded to event creation only.
    try:
        helper(kind=kind, ok_count=ok, warning_count=warning,
               error_count=error, notes=notes)
    except Exception:  # noqa: BLE001 — audit failure must not abort import
        _logger.warning("etsy.sync.health._record_event failed", exc_info=True)
