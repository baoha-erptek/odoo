"""Odoo ORM service for creating sale orders from parsed Etsy email data.

Takes a ParseResult (from email_parser) and creates the corresponding
res.partner, product.product, etsy.shop, and sale.order + lines.
"""
import logging
from email.utils import parsedate_to_datetime

from odoo import fields as odoo_fields

_logger = logging.getLogger(__name__)

# Country codes we look up by ISO alpha-2 first; fallback to name.
_COUNTRY_NAME_OVERRIDES = {
    'United States': 'US',
    'United Kingdom': 'GB',
}


def _parse_eur(value):
    """Parse a EUR price value (string or float) to float."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace('€', '').replace(',', '.').strip()
    text = text.lstrip('-')
    try:
        return float(text) if text else 0.0
    except ValueError:
        return 0.0


class OrderCreator:
    """Stateless service that converts parsed email data into Odoo records."""

    def __init__(self, env):
        self._env = env

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_parse_result(self, parse_result, email_log_id):
        """Create a complete sale.order from a ParseResult.

        Returns the created sale.order record, or None if the order is a
        duplicate.
        """
        if self.is_duplicate_order(parse_result.order_id):
            _logger.info('Skipping duplicate order %s', parse_result.order_id)
            return None

        shipping = parse_result.shipping_address
        buyer_name = parse_result.note_from_buyer_name if hasattr(
            parse_result, 'note_from_buyer_name') else ''
        partner = self.find_or_create_partner(shipping, buyer_name)
        shop = self.find_or_create_shop(parse_result.shop)
        date_order = self._parse_email_date(parse_result.date)

        order_vals = {
            'partner_id': partner.id,
            'date_order': date_order or odoo_fields.Datetime.now(),
            'etsy_order_id': parse_result.order_id,
            'etsy_shop_id': shop.id if shop else False,
            'etsy_note_from_buyer': parse_result.note_from_buyer or '',
            'etsy_gift_message': getattr(parse_result, 'gift_message', '') or '',
            'etsy_shipping_service': parse_result.shipping_service or '',
            'etsy_processing_time': getattr(parse_result, 'processing_time', '') or '',
            'etsy_shipping_cost': parse_result.shipping_cost or 0.0,
            'etsy_discount_code': getattr(parse_result, 'discount_code', '') or '',
            'etsy_subtotal': parse_result.subtotal or 0.0,
            'etsy_email_log_id': email_log_id,
            'order_line': [],
        }

        for txn in parse_result.transactions:
            if self.is_duplicate_transaction(txn.transaction_id):
                _logger.info(
                    'Skipping duplicate transaction %s', txn.transaction_id)
                continue
            product = self.find_or_create_product(
                txn.product_name, getattr(txn, 'image_url', ''))
            line_vals = self._build_line_vals(txn, product)
            order_vals['order_line'].append((0, 0, line_vals))

        if not order_vals['order_line']:
            _logger.warning(
                'Order %s has no new transaction lines; skipping.',
                parse_result.order_id)
            return None

        order = self._env['sale.order'].create(order_vals)
        _logger.info(
            'Created sale.order %s (Etsy #%s) with %d lines',
            order.name, parse_result.order_id, len(order.order_line))
        return order

    # ------------------------------------------------------------------
    # Partner
    # ------------------------------------------------------------------

    def find_or_create_partner(self, shipping, buyer_name):
        """Find or create a res.partner from shipping address data.

        Matching priority:
        1. By email (if non-empty)
        2. By name + zip
        3. Create new
        """
        Partner = self._env['res.partner']
        email = getattr(shipping, 'email', '') or ''
        name = getattr(shipping, 'name', '') or ''
        zipcode = getattr(shipping, 'zipcode', '') or ''
        phone = getattr(shipping, 'phone', '') or ''

        # 1. Match by email
        if email:
            partner = Partner.search([('email', '=', email)], limit=1)
            if partner:
                return partner

        # 2. Match by name + zip
        if name and zipcode:
            partner = Partner.search([
                ('name', '=', name),
                ('zip', '=', zipcode),
            ], limit=1)
            if partner:
                return partner

        # 3. Create new partner
        country = self._resolve_country(
            getattr(shipping, 'country_code', '') or '',
            getattr(shipping, 'country_name', '') or '',
        )
        state = self._resolve_state(
            getattr(shipping, 'state', '') or '', country)

        vals = {
            'name': name or buyer_name or 'Etsy Customer',
            'is_etsy_customer': True,
            'etsy_buyer_name': buyer_name or '',
            'street': getattr(shipping, 'address1', '') or '',
            'street2': getattr(shipping, 'address2', '') or '',
            'city': getattr(shipping, 'city', '') or '',
            'zip': zipcode,
            'phone': phone,
            'email': email,
            'country_id': country.id if country else False,
            'state_id': state.id if state else False,
            'customer_rank': 1,
        }
        partner = Partner.create(vals)
        _logger.info('Created partner %s (id=%d)', partner.name, partner.id)
        return partner

    # ------------------------------------------------------------------
    # Product
    # ------------------------------------------------------------------

    def find_or_create_product(self, product_name, image_url=''):
        """Find or create a product.product by exact name match."""
        Product = self._env['product.product']
        name = (product_name or '').strip()
        if not name:
            name = 'Etsy Product (unnamed)'

        product = Product.search([('name', '=', name)], limit=1)
        if product:
            return product

        vals = {
            'name': name,
            'is_etsy_product': True,
            'type': 'consu',
            'etsy_image_url': image_url or False,
        }
        product = Product.create(vals)
        _logger.info('Created product %s (id=%d)', product.name, product.id)
        return product

    # ------------------------------------------------------------------
    # Shop
    # ------------------------------------------------------------------

    def find_or_create_shop(self, shop_name):
        """Find or create an etsy.shop by name."""
        if not shop_name:
            return None
        Shop = self._env['etsy.shop']
        name = shop_name.strip()
        shop = Shop.search([('name', '=', name)], limit=1)
        if shop:
            return shop
        shop = Shop.create({'name': name})
        _logger.info('Created etsy.shop %s (id=%d)', shop.name, shop.id)
        return shop

    # ------------------------------------------------------------------
    # Duplicate checks
    # ------------------------------------------------------------------

    def is_duplicate_transaction(self, transaction_id):
        """Return True if a sale.order.line with this transaction_id exists."""
        if not transaction_id:
            return False
        return bool(self._env['sale.order.line'].search(
            [('etsy_transaction_id', '=', str(transaction_id))], limit=1))

    def is_duplicate_order(self, order_id):
        """Return True if a sale.order with this etsy_order_id exists."""
        if not order_id:
            return False
        return bool(self._env['sale.order'].search(
            [('etsy_order_id', '=', str(order_id))], limit=1))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_line_vals(self, txn, product):
        """Build a dict of vals for a sale.order.line."""
        return {
            'product_id': product.id,
            'product_uom_qty': txn.quantity or 1,
            'price_unit': txn.price or 0.0,
            'etsy_transaction_id': str(txn.transaction_id),
            'etsy_personalisation': getattr(txn, 'personalisation', '') or '',
            'etsy_sku': getattr(txn, 'sku', '') or '',
            'etsy_option': getattr(txn, 'option', '') or '',
            'etsy_color': getattr(txn, 'color', '') or '',
            'etsy_size': getattr(txn, 'size', '') or '',
            'etsy_side': getattr(txn, 'side', '') or '',
            'etsy_face_mask_size': getattr(txn, 'face_mask_size', '') or '',
            'etsy_image_url': getattr(txn, 'image_url', '') or '',
            'etsy_design_link_front': getattr(txn, 'design_link_front', '') or '',
            'etsy_design_link_back': getattr(txn, 'design_link_back', '') or '',
        }

    def _resolve_country(self, code, name):
        """Resolve a res.country from a code or name."""
        Country = self._env['res.country']

        # Try override mapping first
        if name and name in _COUNTRY_NAME_OVERRIDES:
            code = _COUNTRY_NAME_OVERRIDES[name]

        # By ISO code
        if code and len(code) == 2:
            country = Country.search([('code', '=', code.upper())], limit=1)
            if country:
                return country

        # By name fallback
        if name:
            country = Country.search([('name', 'ilike', name)], limit=1)
            if country:
                return country

        return None

    def _resolve_state(self, state_name, country):
        """Resolve a res.country.state from name and country."""
        if not state_name or not country:
            return None
        return self._env['res.country.state'].search([
            ('name', 'ilike', state_name),
            ('country_id', '=', country.id),
        ], limit=1)

    @staticmethod
    def _parse_email_date(date_str):
        """Parse an email Date header into an Odoo-compatible datetime string.

        Example input: "Thu, 05 Jun 2025 16:14:27 +0000 (UTC)"
        """
        if not date_str:
            return False
        try:
            # Strip trailing parenthesized timezone name, e.g. "(UTC)"
            cleaned = date_str.strip()
            paren_idx = cleaned.rfind('(')
            if paren_idx > 0:
                cleaned = cleaned[:paren_idx].strip()
            dt = parsedate_to_datetime(cleaned)
            return odoo_fields.Datetime.to_string(dt.replace(tzinfo=None))
        except Exception:
            _logger.debug('Could not parse date "%s"', date_str, exc_info=True)
            return False
