"""Wizard for importing historical Etsy orders from an Excel file.

Reads an .xlsx file with 34 columns matching the original Google Sheets
layout, groups rows by ORDER_ID, and creates sale.order records via the
OrderCreator service.
"""
import base64
import io
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

# Column indices (0-based) matching the 34-column Excel layout
_COL_TRANSACTION_ID = 0
_COL_IMG_URL = 1
_COL_IMG = 2
_COL_DATE = 3
_COL_NOTE_FROM_BUYER = 4
_COL_GIFT_MESSAGE = 5
_COL_PERSONALISATION = 6
_COL_SKU = 7
_COL_SHOP = 8
_COL_ORDER_ID = 9
_COL_SHIPPING_NAME = 10
_COL_SHIPPING_ADDRESS1 = 11
_COL_SHIPPING_ADDRESS2 = 12
_COL_SHIPPING_CITY = 13
_COL_SHIPPING_STATE = 14
_COL_SHIPPING_ZIPCODE = 15
_COL_SHIPPING_COUNTRY = 16
_COL_SHIPPING_PHONE = 17
_COL_SHIPPING_EMAIL = 18
_COL_PRODUCT_NAME = 19
_COL_OPTION = 20
_COL_COLOR = 21
_COL_SIZE = 22
_COL_SIDE = 23
_COL_FACE_MASK_SIZE = 24
_COL_QUANTITY = 25
_COL_DESIGN_LINK_FRONT = 26
_COL_DESIGN_LINK_BACK = 27
_COL_SHIPPING_SERVICE = 28
_COL_PROCESSING_TIME = 29
_COL_SHIPPING_COST = 30
_COL_PRICE = 31
_COL_DISCOUNT_CODE = 32
_COL_SUBTOTAL = 33


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

        # Skip header row if present
        first_row = [_cell_str(c) for c in rows[0]]
        start_idx = 0
        if first_row and first_row[0].upper() in ('TRANSACTION_ID', 'ID'):
            start_idx = 1

        data_rows = rows[start_idx:]
        if not data_rows:
            self.status_message = 'No data rows found.'
            return self._return_form()

        # Group rows by ORDER_ID
        orders_by_id = {}
        for row in data_rows:
            cells = list(row) + [None] * max(0, 34 - len(row))
            order_id = _cell_str(cells[_COL_ORDER_ID])
            if not order_id:
                continue
            orders_by_id.setdefault(order_id, []).append(cells)

        creator = OrderCreator(self.env)
        imported = 0
        skipped = 0
        errors = 0
        error_details = []

        count = 0
        for order_id, order_rows in orders_by_id.items():
            try:
                # Skip if order already exists
                if creator.is_duplicate_order(order_id):
                    skipped += 1
                    continue

                result = self._create_order_from_rows(
                    creator, order_id, order_rows)
                if result:
                    if self.auto_confirm:
                        result._etsy_auto_confirm()
                    imported += 1
                else:
                    skipped += 1
            except Exception as exc:
                errors += 1
                error_details.append(f'Order {order_id}: {exc}')
                _logger.exception(
                    'Excel import error for order %s', order_id)

            count += 1
            # Commit every 100 orders to avoid large transactions
            if count % 100 == 0:
                self.env.cr.commit()  # pylint: disable=invalid-commit

        # Final commit
        if count % 100 != 0:
            self.env.cr.commit()  # pylint: disable=invalid-commit

        summary_parts = [
            f'Import complete: {imported} orders imported, '
            f'{skipped} skipped, {errors} errors.',
        ]
        if error_details:
            summary_parts.append('\nErrors:')
            # Show at most 20 error details
            for detail in error_details[:20]:
                summary_parts.append(f'  - {detail}')
            if len(error_details) > 20:
                summary_parts.append(
                    f'  ... and {len(error_details) - 20} more.')

        self.status_message = '\n'.join(summary_parts)
        _logger.info(
            'Excel import: %d imported, %d skipped, %d errors',
            imported, skipped, errors)
        return self._return_form()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_order_from_rows(self, creator, order_id, rows):
        """Create a single sale.order from grouped Excel rows.

        Returns the created sale.order or None.
        """
        # Use the first row for order-level data
        first = rows[0]

        # Shipping / partner data
        shipping_name = _cell_str(first[_COL_SHIPPING_NAME])
        shipping_email = _cell_str(first[_COL_SHIPPING_EMAIL])
        shipping_phone = _cell_str(first[_COL_SHIPPING_PHONE])
        shipping_address1 = _cell_str(first[_COL_SHIPPING_ADDRESS1])
        shipping_address2 = _cell_str(first[_COL_SHIPPING_ADDRESS2])
        shipping_city = _cell_str(first[_COL_SHIPPING_CITY])
        shipping_state = _cell_str(first[_COL_SHIPPING_STATE])
        shipping_zipcode = _cell_str(first[_COL_SHIPPING_ZIPCODE])
        shipping_country = _cell_str(first[_COL_SHIPPING_COUNTRY])

        # Build a lightweight shipping object for find_or_create_partner
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

        note_text = _cell_str(first[_COL_NOTE_FROM_BUYER])
        buyer_name = note_text.split('-')[0].strip() if note_text else ''

        partner = creator.find_or_create_partner(shipping, buyer_name)
        shop = creator.find_or_create_shop(_cell_str(first[_COL_SHOP]))

        # Parse the date from the first row
        date_str = _cell_str(first[_COL_DATE])
        date_order = self._parse_date(date_str)

        # Detect currency from the first PRICE cell that carries a marker.
        # Most rows in a single order share the same currency; first non-empty
        # detection wins. Falls back to EUR.
        order_currency = None
        for row in rows:
            _, code = _parse_price(row[_COL_PRICE])
            if code and code != 'EUR':
                order_currency = code
                break
        if not order_currency:
            order_currency = 'EUR'

        shipping_cost, _ = _parse_price(first[_COL_SHIPPING_COST])
        subtotal, _ = _parse_price(first[_COL_SUBTOTAL])

        order_vals = {
            'partner_id': partner.id,
            'date_order': date_order or fields.Datetime.now(),
            'etsy_order_id': order_id,
            'etsy_shop_id': shop.id if shop else False,
            'etsy_note_from_buyer': note_text,
            'etsy_gift_message': _cell_str(first[_COL_GIFT_MESSAGE]),
            'etsy_shipping_service': _cell_str(first[_COL_SHIPPING_SERVICE]),
            'etsy_processing_time': _cell_str(first[_COL_PROCESSING_TIME]),
            'etsy_shipping_cost': shipping_cost,
            'etsy_discount_code': _cell_str(first[_COL_DISCOUNT_CODE]),
            'etsy_subtotal': subtotal,
            'order_line': [],
        }

        # Financial config (US1): currency, pricelist, fiscal position,
        # payment term, sales team.
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
            transaction_id = _cell_str(row[_COL_TRANSACTION_ID])
            if not transaction_id:
                continue
            # Skip duplicate transactions
            if creator.is_duplicate_transaction(transaction_id):
                continue

            product_name = _cell_str(row[_COL_PRODUCT_NAME])
            image_url = _cell_str(row[_COL_IMG_URL])
            product = creator.find_or_create_product(product_name, image_url)
            price, _ = _parse_price(row[_COL_PRICE])

            line_vals = {
                'product_id': product.id,
                'product_uom_qty': _parse_quantity(row[_COL_QUANTITY]),
                'price_unit': price,
                'etsy_transaction_id': transaction_id,
                'etsy_personalisation': _cell_str(row[_COL_PERSONALISATION]),
                'etsy_sku': _cell_str(row[_COL_SKU]),
                'etsy_option': _cell_str(row[_COL_OPTION]),
                'etsy_color': _cell_str(row[_COL_COLOR]),
                'etsy_size': _cell_str(row[_COL_SIZE]),
                'etsy_side': _cell_str(row[_COL_SIDE]),
                'etsy_face_mask_size': _cell_str(row[_COL_FACE_MASK_SIZE]),
                'etsy_image_url': image_url,
                'etsy_design_link_front': _cell_str(
                    row[_COL_DESIGN_LINK_FRONT]),
                'etsy_design_link_back': _cell_str(
                    row[_COL_DESIGN_LINK_BACK]),
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
        _logger.info(
            'Excel import: created order %s (Etsy #%s)',
            order.name, order_id)
        return order

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

        # Fallback: try common date formats
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
