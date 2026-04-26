"""Wizard for importing historical Etsy orders from an Excel file.

Reads an .xlsx file with up to 34 columns matching the original Google Sheets
layout, groups rows by ORDER_ID, and creates sale.order records via the
OrderCreator service.

Header detection (Spec 002 US5 T031): when the first row contains
recognizable header names (case- and separator-insensitive), columns are
mapped by header position. Otherwise the legacy 34-column positional layout
is used. Missing required headers raise UserError; missing optional headers
log a warning to ``validation_notes``.

Transaction safety (Spec 002 US5 T032 / R4): per-order savepoints inside a
500-order observability batch. ``etsy.sync.health`` is updated after each
batch; the prior ``cr.commit()`` calls are removed (forbidden inside
``TransactionCase`` and unnecessary thanks to savepoint isolation).
"""
import base64
import io
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Required headers per Spec 002 US5 R6 — UserError when any are missing
# from a detected header row.
_REQUIRED_HEADERS = (
    'TRANSACTION_ID', 'ORDER_ID', 'PRODUCT_NAME', 'PRICE', 'QUANTITY',
)

# Legacy 34-column positional layout — used when no header row is detected
# (preserves backward compatibility for raw-data uploads and the existing
# test_import_wizard fixtures).
_LEGACY_COLUMNS = (
    'TRANSACTION_ID', 'IMG_URL', 'IMG', 'DATE', 'NOTE_FROM_BUYER',
    'GIFT_MESSAGE', 'PERSONALISATION', 'SKU', 'SHOP', 'ORDER_ID',
    'SHIPPING_NAME', 'SHIPPING_ADDRESS1', 'SHIPPING_ADDRESS2',
    'SHIPPING_CITY', 'SHIPPING_STATE', 'SHIPPING_ZIPCODE',
    'SHIPPING_COUNTRY', 'SHIPPING_PHONE', 'SHIPPING_EMAIL',
    'PRODUCT_NAME', 'OPTION', 'COLOR', 'SIZE', 'SIDE', 'FACE_MASK_SIZE',
    'QUANTITY', 'DESIGN_LINK_FRONT', 'DESIGN_LINK_BACK',
    'SHIPPING_SERVICE', 'PROCESSING_TIME', 'SHIPPING_COST', 'PRICE',
    'DISCOUNT_CODE', 'SUBTOTAL',
)
_LEGACY_HEADER_MAP = {name: idx for idx, name in enumerate(_LEGACY_COLUMNS)}

# Batch size for sync.health reporting (Spec 002 US5 R4).
_IMPORT_BATCH_SIZE = 500

# etsy.sync.health integration name.
_HEALTH_INTEGRATION = 'import_wizard'


def _normalize_header(value):
    """Normalize a header cell: strip, uppercase, spaces -> underscores."""
    if value is None:
        return ''
    return str(value).strip().upper().replace(' ', '_')


def _looks_like_header_row(row):
    """Return True when at least one cell normalizes to a known column name."""
    cells = {_normalize_header(c) for c in row if c is not None}
    return bool(cells & set(_LEGACY_COLUMNS))


def _cell_str(value):
    """Convert a cell value to a stripped string."""
    if value is None:
        return ''
    return str(value).strip()


def _parse_price(value):
    """Parse a multi-currency price cell to ``(amount, currency_code)``.

    Delegates to ``order_creator._parse_price`` to keep the parsing rules
    consistent across the email and Excel paths. Returns ``(0.0, 'EUR')`` on
    empty / unparseable input.
    """
    from ..services.order_creator import _parse_price as _service_parse
    return _service_parse(value)


def _parse_eur_price(value):
    """Backwards-compatible amount-only wrapper for old call sites."""
    amount, _ = _parse_price(value)
    return amount


def _parse_quantity(value):
    """Parse a quantity value; default to 1 if not parseable."""
    text = _cell_str(value)
    if not text:
        return 1
    try:
        return max(1, int(float(text)))
    except (ValueError, TypeError):
        return 1


def _cell_at(row, header_map, key, default=''):
    """Read ``row`` cell by logical column ``key`` using ``header_map``.

    Returns ``default`` when the column is absent from ``header_map`` or the
    row is shorter than the resolved index. Always returns a stripped string
    (caller can convert to numeric via ``_parse_*``).
    """
    idx = header_map.get(key)
    if idx is None or idx >= len(row):
        return default
    return _cell_str(row[idx])


class ImportOrdersWizard(models.TransientModel):
    _name = 'etsy.import.orders.wizard'
    _description = 'Import Etsy Orders from Excel'

    excel_file = fields.Binary(string='Excel File', required=True)
    excel_filename = fields.Char(string='Filename')
    auto_confirm = fields.Boolean(
        string='Auto-confirm imported orders', default=True,
        help='When enabled, each imported order is confirmed, its picking '
             'validated, and marked as invoiced (per R5).')
    status_message = fields.Text(string='Status', readonly=True)
    warning_count = fields.Integer(
        string='Warnings', readonly=True, default=0,
        help='Number of zero-price rows or missing-optional-header warnings '
             'observed during the last import (Spec 002 US5 T033).')
    validation_notes = fields.Text(
        string='Validation Notes', readonly=True,
        help='Human-readable summary of warnings emitted during the last '
             'import. Empty when no warnings were raised.')

    def action_import(self):
        """Parse the uploaded Excel file and create sale orders."""
        self.ensure_one()
        if not self.excel_file:
            self.status_message = 'No file uploaded.'
            return self._return_form()

        try:
            import openpyxl
        except ImportError:
            self.status_message = (
                'The openpyxl library is required but not installed.')
            return self._return_form()

        from ..services.order_creator import OrderCreator

        # Decode uploaded file
        try:
            file_data = base64.b64decode(self.excel_file)
            wb = openpyxl.load_workbook(
                io.BytesIO(file_data), read_only=True, data_only=True)
            ws = wb.active
        except Exception as exc:
            self.status_message = f'Failed to read Excel file: {exc}'
            return self._return_form()

        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            self.status_message = 'Excel file is empty.'
            return self._return_form()

        warnings = []
        warning_count = 0

        # T031: header detection + required-column validation.
        if _looks_like_header_row(rows[0]):
            header_map = {}
            for idx, cell in enumerate(rows[0]):
                key = _normalize_header(cell)
                if key:
                    header_map[key] = idx
            missing_required = [
                h for h in _REQUIRED_HEADERS if h not in header_map]
            if missing_required:
                raise UserError(_(
                    "Missing required column(s) in the uploaded file: "
                    "%(missing)s.\nRequired headers are: %(required)s.",
                    missing=', '.join(missing_required),
                    required=', '.join(_REQUIRED_HEADERS),
                ))
            for legacy in _LEGACY_COLUMNS:
                if legacy not in header_map:
                    warning_count += 1
                    warnings.append(
                        f'Optional column "{legacy}" missing — '
                        f'using empty default.')
            data_rows = rows[1:]
        else:
            header_map = dict(_LEGACY_HEADER_MAP)
            data_rows = rows

        if not data_rows:
            self.status_message = 'No data rows found.'
            self.warning_count = warning_count
            self.validation_notes = (
                '\n'.join(warnings) if warnings else False)
            return self._return_form()

        # Group rows by ORDER_ID — header_map['ORDER_ID'] is guaranteed
        # present (either via required-header check or legacy map).
        order_id_idx = header_map['ORDER_ID']
        orders_by_id = {}
        for row in data_rows:
            if order_id_idx >= len(row):
                continue
            order_id = _cell_str(row[order_id_idx])
            if not order_id:
                continue
            orders_by_id.setdefault(order_id, []).append(tuple(row))

        creator = OrderCreator(self.env)
        SyncHealth = self.env['etsy.sync.health']
        SyncHealth.report_run(
            _HEALTH_INTEGRATION, state='running',
            row_count=0, error_count=0)

        imported = 0
        skipped = 0
        errors = 0
        error_details = []

        order_items = list(orders_by_id.items())
        total = len(order_items)

        # T032: per-order savepoint for failure isolation; per-500-batch
        # observability checkpoint to ``etsy.sync.health``. No ``cr.commit()``.
        for batch_start in range(0, total, _IMPORT_BATCH_SIZE):
            batch = order_items[batch_start:batch_start + _IMPORT_BATCH_SIZE]
            for order_id, order_rows in batch:
                try:
                    with self.env.cr.savepoint():
                        if creator.is_duplicate_order(order_id):
                            skipped += 1
                            continue
                        result = self._create_order_from_rows(
                            creator, order_id, order_rows, header_map)
                        if not result:
                            skipped += 1
                            continue
                        if self.auto_confirm:
                            result._etsy_auto_confirm()
                        imported += 1
                        zero_price_lines = result.order_line.filtered(
                            lambda line: line.price_unit == 0
                            and not (line.product_id.default_code or '')
                            .startswith('SHIPPING'))
                        if zero_price_lines:
                            warning_count += len(zero_price_lines)
                            warnings.append(
                                f'Order {order_id}: '
                                f'{len(zero_price_lines)} zero-price line(s).')
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    error_details.append(f'Order {order_id}: {exc}')
                    _logger.exception(
                        'Excel import error for order %s', order_id)

            SyncHealth.report_run(
                _HEALTH_INTEGRATION,
                row_count=imported,
                error_count=errors,
                error_message=(
                    '\n'.join(error_details[-5:])
                    if error_details else None),
                last_id=batch_start + len(batch),
            )

        # Finalize health state per error ratio.
        if total == 0 or errors == 0:
            final_state = 'ok'
        elif errors / total < 0.05:
            final_state = 'warning'
        else:
            final_state = 'error'
        SyncHealth.report_run(
            _HEALTH_INTEGRATION,
            row_count=imported,
            error_count=errors,
            state=final_state,
            error_message=(
                '\n'.join(error_details[-5:]) if error_details else None),
        )

        # Build summary.
        summary_parts = [
            f'Import complete: {imported} orders imported, '
            f'{skipped} skipped, {errors} errors.',
        ]
        if warnings:
            summary_parts.append(f'\nWarnings ({warning_count}):')
            for warning in warnings[:10]:
                summary_parts.append(f'  - {warning}')
            if len(warnings) > 10:
                summary_parts.append(
                    f'  ... and {len(warnings) - 10} more.')
        if error_details:
            summary_parts.append('\nErrors:')
            for detail in error_details[:20]:
                summary_parts.append(f'  - {detail}')
            if len(error_details) > 20:
                summary_parts.append(
                    f'  ... and {len(error_details) - 20} more.')

        self.status_message = '\n'.join(summary_parts)
        self.warning_count = warning_count
        self.validation_notes = (
            '\n'.join(warnings) if warnings else False)
        _logger.debug(
            'Excel import: %d imported, %d skipped, %d errors, %d warnings',
            imported, skipped, errors, warning_count)
        return self._return_form()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_order_from_rows(self, creator, order_id, rows, header_map):
        """Create a single sale.order from grouped Excel rows.

        ``rows`` are tuples of cell values; ``header_map`` resolves logical
        column names (e.g. 'PRODUCT_NAME') to the row index for this file.
        Returns the created sale.order or None.
        """
        first = rows[0]

        # Shipping / partner data
        shipping_name = _cell_at(first, header_map, 'SHIPPING_NAME')
        shipping_email = _cell_at(first, header_map, 'SHIPPING_EMAIL')
        shipping_phone = _cell_at(first, header_map, 'SHIPPING_PHONE')
        shipping_address1 = _cell_at(first, header_map, 'SHIPPING_ADDRESS1')
        shipping_address2 = _cell_at(first, header_map, 'SHIPPING_ADDRESS2')
        shipping_city = _cell_at(first, header_map, 'SHIPPING_CITY')
        shipping_state = _cell_at(first, header_map, 'SHIPPING_STATE')
        shipping_zipcode = _cell_at(first, header_map, 'SHIPPING_ZIPCODE')
        shipping_country = _cell_at(first, header_map, 'SHIPPING_COUNTRY')

        shipping = _ShippingData(
            name=shipping_name,
            email=shipping_email,
            phone=shipping_phone,
            address1=shipping_address1,
            address2=shipping_address2,
            city=shipping_city,
            state=shipping_state,
            zipcode=shipping_zipcode,
            country_code=(
                shipping_country if len(shipping_country) == 2 else ''),
            country_name=(
                shipping_country if len(shipping_country) != 2 else ''),
        )

        note_text = _cell_at(first, header_map, 'NOTE_FROM_BUYER')
        buyer_name = note_text.split('-')[0].strip() if note_text else ''

        partner = creator.find_or_create_partner(shipping, buyer_name)
        shop = creator.find_or_create_shop(
            _cell_at(first, header_map, 'SHOP'))

        date_str = _cell_at(first, header_map, 'DATE')
        date_order = self._parse_date(date_str)

        # Detect currency from the first PRICE cell that carries a marker.
        order_currency = None
        price_idx = header_map.get('PRICE')
        if price_idx is not None:
            for row in rows:
                if price_idx >= len(row):
                    continue
                _, code = _parse_price(row[price_idx])
                if code and code != 'EUR':
                    order_currency = code
                    break
        if not order_currency:
            order_currency = 'EUR'

        shipping_cost, _ = _parse_price(
            self._raw_cell(first, header_map, 'SHIPPING_COST'))
        subtotal, _ = _parse_price(
            self._raw_cell(first, header_map, 'SUBTOTAL'))

        order_vals = {
            'partner_id': partner.id,
            'date_order': date_order or fields.Datetime.now(),
            'etsy_order_id': order_id,
            'etsy_shop_id': shop.id if shop else False,
            'etsy_note_from_buyer': note_text,
            'etsy_gift_message': _cell_at(first, header_map, 'GIFT_MESSAGE'),
            'etsy_shipping_service': _cell_at(
                first, header_map, 'SHIPPING_SERVICE'),
            'etsy_processing_time': _cell_at(
                first, header_map, 'PROCESSING_TIME'),
            'etsy_shipping_cost': shipping_cost,
            'etsy_discount_code': _cell_at(
                first, header_map, 'DISCOUNT_CODE'),
            'etsy_subtotal': subtotal,
            'order_line': [],
        }

        # Financial config (US1).
        currency = creator._get_currency(order_currency)
        pricelist = creator._get_pricelist(order_currency)
        fiscal_position = creator._get_fiscal_position()
        payment_term = creator._get_payment_term()
        sales_team = creator._get_sales_team()
        if currency:
            order_vals['currency_id'] = currency.id
        if pricelist:
            order_vals['pricelist_id'] = pricelist.id
        if fiscal_position:
            order_vals['fiscal_position_id'] = fiscal_position.id
        if payment_term:
            order_vals['payment_term_id'] = payment_term.id
        if sales_team:
            order_vals['team_id'] = sales_team.id

        for row in rows:
            transaction_id = _cell_at(row, header_map, 'TRANSACTION_ID')
            if not transaction_id:
                continue
            if creator.is_duplicate_transaction(transaction_id):
                continue

            product_name = _cell_at(row, header_map, 'PRODUCT_NAME')
            image_url = _cell_at(row, header_map, 'IMG_URL')
            product = creator.find_or_create_product(product_name, image_url)
            price, _ = _parse_price(
                self._raw_cell(row, header_map, 'PRICE'))

            line_vals = {
                'product_id': product.id,
                'product_uom_qty': _parse_quantity(
                    self._raw_cell(row, header_map, 'QUANTITY')),
                'price_unit': price,
                'etsy_transaction_id': transaction_id,
                'etsy_personalisation': _cell_at(
                    row, header_map, 'PERSONALISATION'),
                'etsy_sku': _cell_at(row, header_map, 'SKU'),
                'etsy_option': _cell_at(row, header_map, 'OPTION'),
                'etsy_color': _cell_at(row, header_map, 'COLOR'),
                'etsy_size': _cell_at(row, header_map, 'SIZE'),
                'etsy_side': _cell_at(row, header_map, 'SIDE'),
                'etsy_face_mask_size': _cell_at(
                    row, header_map, 'FACE_MASK_SIZE'),
                'etsy_image_url': image_url,
                'etsy_design_link_front': _cell_at(
                    row, header_map, 'DESIGN_LINK_FRONT'),
                'etsy_design_link_back': _cell_at(
                    row, header_map, 'DESIGN_LINK_BACK'),
            }
            order_vals['order_line'].append((0, 0, line_vals))

        if not order_vals['order_line']:
            return None

        # Add Etsy Shipping line when shipping_cost > 0.
        shipping_product = creator._get_shipping_product()
        if shipping_cost > 0 and shipping_product:
            order_vals['order_line'].append((0, 0, {
                'product_id': shipping_product.id,
                'product_uom_qty': 1.0,
                'price_unit': shipping_cost,
                'name': shipping_product.display_name,
            }))

        order = self.env['sale.order'].create(order_vals)
        _logger.debug(
            'Excel import: created order %s (Etsy #%s)',
            order.name, order_id)
        return order

    @staticmethod
    def _raw_cell(row, header_map, key):
        """Return the raw cell value (preserves type for price parsers)."""
        idx = header_map.get(key)
        if idx is None or idx >= len(row):
            return ''
        return row[idx]

    @staticmethod
    def _parse_date(date_str):
        """Parse various date formats from the Excel DATE column.

        Handles both email-style dates:
            "Thu, 05 Jun 2025 16:14:27 +0000 (UTC)"
        and simple date strings:
            "2025-06-05", "06/05/2025", etc.
        """
        if not date_str:
            return False
        try:
            from email.utils import parsedate_to_datetime
            cleaned = date_str.strip()
            paren_idx = cleaned.rfind('(')
            if paren_idx > 0:
                cleaned = cleaned[:paren_idx].strip()
            dt = parsedate_to_datetime(cleaned)
            return fields.Datetime.to_string(dt.replace(tzinfo=None))
        except Exception:
            pass

        from datetime import datetime as dt_cls
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y',
                    '%Y-%m-%d %H:%M:%S', '%d-%m-%Y'):
            try:
                dt = dt_cls.strptime(date_str.strip(), fmt)
                return fields.Datetime.to_string(dt)
            except (ValueError, TypeError):
                continue
        return False

    def _return_form(self):
        """Return an action that keeps the wizard form open."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class _ShippingData:
    """Lightweight data holder mimicking the email parser ShippingAddress.

    Used by the Excel import to pass shipping info to
    OrderCreator.find_or_create_partner without depending on the
    email_parser dataclass.
    """

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
