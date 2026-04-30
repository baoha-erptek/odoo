"""
Fixture builders for tracking import tests.

Generates XLSX files in-memory using openpyxl without requiring binary files in repo.
Fixtures are deterministically built in test setUpClass.
"""

import hashlib
import io
from datetime import datetime

try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None


def normalize_headers(headers):
    """Normalize header list for schema fingerprinting.

    Args:
        headers: List of column header strings

    Returns:
        Normalized list: uppercase, trimmed, case-folded
    """
    return [h.strip().upper() for h in headers]


def compute_schema_hash(headers):
    """Compute SHA-256 hash of normalized header sequence.

    Args:
        headers: List of column header strings

    Returns:
        SHA-256 hex digest (64 chars)
    """
    normalized = normalize_headers(headers)
    header_str = '|'.join(normalized)
    return hashlib.sha256(header_str.encode('utf-8')).hexdigest()


def compute_source_row_hash(row_values):
    """Compute SHA-256 hash of row cell values for idempotency.

    Args:
        row_values: List of cell values (as strings)

    Returns:
        SHA-256 hex digest (64 chars)
    """
    row_str = '|'.join(str(v) if v is not None else '' for v in row_values)
    return hashlib.sha256(row_str.encode('utf-8')).hexdigest()


def build_known_schema_xlsx(matching_order_ref=None):
    """Build a known-schema XLSX fixture with 50 rows.

    Headers: ['ORDER NUMBER', 'TRACKING', 'CARRIER', 'DATE', 'WEIGHT', 'NOTES']

    Args:
        matching_order_ref: Optional channel_order_ref to include as first data row

    Returns:
        bytes: XLSX file content

    The fixture includes:
    - Header row with standard 6 columns
    - 50 data rows with mix of carriers (USPS/UniUni/YunExpress/Unknown)
    - At least one row with date 03/02/2026 (DD/MM/YYYY with day <= 12 to test dayfirst)
    - If matching_order_ref provided, first row uses it
    """
    if Workbook is None:
        raise ImportError("openpyxl is required to build fixtures")

    wb = Workbook()
    ws = wb.active
    ws.title = "Tracking Data"

    # Headers
    headers = ['ORDER NUMBER', 'TRACKING', 'CARRIER', 'DATE', 'WEIGHT', 'NOTES']
    ws.append(headers)

    # Carrier prefixes for variety
    carriers = {
        'USPS': ('9214', 'USPS'),
        'UniUni': ('UUS', 'UniUni'),
        'YunExpress': ('YT', 'YunExpress'),
    }

    # Generate 50 rows
    order_counter = 1000 if not matching_order_ref else 0
    for i in range(50):
        # First row uses matching_order_ref if provided
        if i == 0 and matching_order_ref:
            order_number = matching_order_ref
        else:
            order_number = f'ORD-{order_counter:06d}'
            order_counter += 1

        # Vary carriers
        carrier_choice = list(carriers.keys())[i % 3]
        prefix, carrier_name = carriers[carrier_choice]
        tracking_number = f'{prefix}{i:010d}'

        # Use 03/02/2026 (3 Feb, day <= 12) to test dayfirst parsing
        date_str = '03/02/2026' if i == 5 else f'{(i % 28) + 1:02d}/04/2026'

        weight = f'{2.5 + (i % 5):.2f}'
        notes = f'Tracking import test row {i + 1}'

        ws.append([order_number, tracking_number, carrier_name, date_str, weight, notes])

    # Save to BytesIO
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def build_unknown_schema_xlsx(matching_order_ref=None):
    """Build an unknown-schema XLSX with headers reordered.

    Same content as known schema but with columns reordered to trigger
    new schema hash detection. Headers become:
    ['TRACKING', 'ORDER NUMBER', 'CARRIER', 'WEIGHT', 'DATE', 'NOTES']

    Args:
        matching_order_ref: Optional channel_order_ref to include

    Returns:
        bytes: XLSX file content with different header order
    """
    if Workbook is None:
        raise ImportError("openpyxl is required to build fixtures")

    wb = Workbook()
    ws = wb.active
    ws.title = "Tracking Data"

    # Reordered headers (different from known schema)
    headers = ['TRACKING', 'ORDER NUMBER', 'CARRIER', 'WEIGHT', 'DATE', 'NOTES']
    ws.append(headers)

    carriers = {
        'USPS': ('9214', 'USPS'),
        'UniUni': ('UUS', 'UniUni'),
        'YunExpress': ('YT', 'YunExpress'),
    }

    order_counter = 1000 if not matching_order_ref else 0
    for i in range(50):
        if i == 0 and matching_order_ref:
            order_number = matching_order_ref
        else:
            order_number = f'ORD-{order_counter:06d}'
            order_counter += 1

        carrier_choice = list(carriers.keys())[i % 3]
        prefix, carrier_name = carriers[carrier_choice]
        tracking_number = f'{prefix}{i:010d}'

        date_str = '03/02/2026' if i == 5 else f'{(i % 28) + 1:02d}/04/2026'
        weight = f'{2.5 + (i % 5):.2f}'
        notes = f'Tracking import test row {i + 1}'

        # Data order matches new header order: TRACKING, ORDER NUMBER, CARRIER, WEIGHT, DATE, NOTES
        ws.append([tracking_number, order_number, carrier_name, weight, date_str, notes])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def build_partial_match_xlsx():
    """Build an XLSX with partial matches: 1 matched, 1 unmatched, 1 conflict.

    Used to test order resolution branches in tests.
    This fixture is minimal (3 data rows) and used with specific test orders.

    Returns:
        bytes: XLSX file content
    """
    if Workbook is None:
        raise ImportError("openpyxl is required to build fixtures")

    wb = Workbook()
    ws = wb.active
    ws.title = "Tracking Data"

    headers = ['ORDER NUMBER', 'TRACKING', 'CARRIER', 'DATE', 'WEIGHT', 'NOTES']
    ws.append(headers)

    # Row 1: matched (will be provided as matching_order_ref in test)
    ws.append(['MATCHED-ORDER-123', '9214000000001', 'USPS', '01/04/2026', '2.50', 'Matched row'])

    # Row 2: unmatched (no order exists with this reference)
    ws.append(['UNKNOWN-ORDER-999', 'UUS0000000002', 'UniUni', '02/04/2026', '3.00', 'Unmatched row'])

    # Row 3: conflict (will be created as duplicate in test setup)
    ws.append(['CONFLICT-ORDER-111', 'YT0000000003', 'YunExpress', '03/04/2026', '2.75', 'Conflict row'])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def build_oversized_xlsx():
    """Build a fixture that simulates an oversized file via header.

    Note: We don't actually generate a 10+ MB file. Instead, tests will mock
    file_size_bytes. This fixture is a minimal valid XLSX used with mocked size.

    Returns:
        bytes: Small valid XLSX file (size constraint tested via mock)
    """
    if Workbook is None:
        raise ImportError("openpyxl is required to build fixtures")

    wb = Workbook()
    ws = wb.active
    ws.title = "Tracking Data"

    headers = ['ORDER NUMBER', 'TRACKING', 'CARRIER', 'DATE', 'WEIGHT', 'NOTES']
    ws.append(headers)

    # Single data row
    ws.append(['ORD-000001', '9214000000001', 'USPS', '01/04/2026', '2.50', 'Oversized test'])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
