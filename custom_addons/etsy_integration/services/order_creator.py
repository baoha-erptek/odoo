"""Odoo ORM service for creating sale orders from parsed Etsy email data.

Takes a ParseResult (from email_parser) and creates the corresponding
res.partner, product.product, etsy.shop, and sale.order + lines.
"""
import logging
import unicodedata
from email.utils import parsedate_to_datetime

from odoo import fields as odoo_fields

_logger = logging.getLogger(__name__)

# Country names we map to ISO alpha-2 before searching res.country. Covers
# Etsy buyer-country naming variations the standard res.country lookup misses
# (T030). Keep entries lower-cased lookup is case-insensitive at the call
# site; here we keep canonical title-case for readability.
_COUNTRY_NAME_OVERRIDES = {
    'United States': 'US',
    'United States of America': 'US',
    'USA': 'US',
    'U.S.A.': 'US',
    'United Kingdom': 'GB',
    'UK': 'GB',
    'Great Britain': 'GB',
    # Common Etsy buyer-country naming variations (T030).
    'Czechia': 'CZ',
    'Czech Republic': 'CZ',
    'Republic of Korea': 'KR',
    'South Korea': 'KR',
    'Korea, South': 'KR',
    "Korea, Democratic People's Republic of": 'KP',
    'North Korea': 'KP',
    'Russia': 'RU',
    'Russian Federation': 'RU',
    'Vietnam': 'VN',
    'Viet Nam': 'VN',
    'Iran': 'IR',
    'Iran, Islamic Republic of': 'IR',
    'Bolivia': 'BO',
    'Bolivia, Plurinational State of': 'BO',
    'Venezuela': 'VE',
    'Venezuela, Bolivarian Republic of': 'VE',
    'Tanzania': 'TZ',
    'Tanzania, United Republic of': 'TZ',
    'Moldova': 'MD',
    'Moldova, Republic of': 'MD',
    'Macedonia': 'MK',
    'North Macedonia': 'MK',
    'Macao': 'MO',
    'Macau': 'MO',
    'Hong Kong': 'HK',
    'Taiwan': 'TW',
    'Taiwan, Province of China': 'TW',
    'Palestine': 'PS',
    'Palestine, State of': 'PS',
    'Syria': 'SY',
    'Syrian Arab Republic': 'SY',
    'Laos': 'LA',
    "Lao People's Democratic Republic": 'LA',
    'Brunei': 'BN',
    'Brunei Darussalam': 'BN',
    'Cape Verde': 'CV',
    'Cabo Verde': 'CV',
    'Ivory Coast': 'CI',
    "Côte d'Ivoire": 'CI',
    "Cote d'Ivoire": 'CI',
    'East Timor': 'TL',
    'Timor-Leste': 'TL',
    'Burma': 'MM',
    'Myanmar': 'MM',
    'Swaziland': 'SZ',
    'Eswatini': 'SZ',
    'Holy See': 'VA',
    'Vatican City': 'VA',
}


# German transliterations applied before NFD decomposition. Without these,
# "Müller" → "Muller" rather than "Mueller", which breaks dedup against
# customers who entered the ASCII form on a different order.
_GERMAN_TRANSLIT = {
    'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
    'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
}


def _normalize_text(value):
    """Lowercase, strip accents, collapse whitespace, apply German translit.

    Used by partner dedup tier 2 to compare addresses ignoring case and
    accent variations (e.g. "Müller" vs "Mueller", "Lyon" vs "LYON",
    "Françoise" vs "Francoise").
    """
    if not value:
        return ''
    transliterated = value
    for src, dst in _GERMAN_TRANSLIT.items():
        transliterated = transliterated.replace(src, dst)
    decomposed = unicodedata.normalize('NFD', transliterated)
    stripped = ''.join(ch for ch in decomposed if unicodedata.category(ch) != 'Mn')
    return ' '.join(stripped.lower().split())

# Currency markers detected in raw price text. Order matters: longer / more
# specific tokens first so "EUR" doesn't shadow "E", etc.
_CURRENCY_MARKERS = (
    ('EUR', 'EUR'),
    ('USD', 'USD'),
    ('GBP', 'GBP'),
    ('$', 'USD'),
    ('€', 'EUR'),
    ('£', 'GBP'),
)
_DEFAULT_CURRENCY = 'EUR'


def _parse_price(value):
    """Parse a multi-currency price value to ``(amount, currency_code)``.

    Detects ``$``/``USD``, ``€``/``EUR``, ``£``/``GBP`` markers; falls back to
    EUR when no marker is present. Tolerates either ``,`` or ``.`` as decimal
    separator. Returns ``(0.0, 'EUR')`` for unparseable / empty input.
    """
    if value is None:
        return 0.0, _DEFAULT_CURRENCY
    if isinstance(value, (int, float)):
        return float(value), _DEFAULT_CURRENCY
    text = str(value).strip()
    if not text:
        return 0.0, _DEFAULT_CURRENCY

    upper = text.upper()
    currency = _DEFAULT_CURRENCY
    for marker, code in _CURRENCY_MARKERS:
        if marker in upper if marker.isalpha() else marker in text:
            currency = code
            break

    cleaned = text
    for marker, _ in _CURRENCY_MARKERS:
        cleaned = cleaned.replace(marker, '').replace(marker.lower(), '')
    cleaned = cleaned.replace(',', '.').strip().lstrip('-')
    try:
        return (float(cleaned) if cleaned else 0.0), currency
    except ValueError:
        return 0.0, currency


def _parse_eur(value):
    """Backwards-compatible EUR-only wrapper around _parse_price."""
    amount, _ = _parse_price(value)
    return amount


class OrderCreator:
    """Stateless service that converts parsed email data into Odoo records."""

    # XMLIDs of the master data records loaded by data/etsy_*.xml. Looked up
    # lazily and memoized per-instance via the helpers below.
    _XMLID_SHIPPING_PRODUCT = 'etsy_integration.product_etsy_shipping'
    _XMLID_FISCAL_POSITION = 'etsy_integration.fiscal_pos_etsy_marketplace'
    _XMLID_PAYMENT_TERM = 'etsy_integration.payment_term_etsy_prepaid'
    _XMLID_SALES_TEAM = 'etsy_integration.team_etsy'
    _PRICELIST_XMLIDS = {
        'EUR': 'etsy_integration.pricelist_etsy_eur',
        'USD': 'etsy_integration.pricelist_etsy_usd',
        'GBP': 'etsy_integration.pricelist_etsy_gbp',
    }

    def __init__(self, env):
        self._env = env
        self._cache = {}
        self._categorizer = None  # lazy: avoid loading JSON for callers that never categorize

    def _ref(self, key, xmlid):
        """Resolve and memoize an xmlid lookup; returns False if missing."""
        if key in self._cache:
            return self._cache[key]
        rec = self._env.ref(xmlid, raise_if_not_found=False)
        self._cache[key] = rec
        return rec

    def _get_shipping_product(self):
        """Returns the product.product variant of the Etsy Shipping template."""
        if 'shipping_product' in self._cache:
            return self._cache['shipping_product']
        tmpl = self._ref('shipping_template', self._XMLID_SHIPPING_PRODUCT)
        product = tmpl.product_variant_id if tmpl else False
        self._cache['shipping_product'] = product
        return product

    def _get_fiscal_position(self):
        return self._ref('fiscal_position', self._XMLID_FISCAL_POSITION)

    def _get_payment_term(self):
        return self._ref('payment_term', self._XMLID_PAYMENT_TERM)

    def _get_sales_team(self):
        return self._ref('sales_team', self._XMLID_SALES_TEAM)

    def _get_pricelist(self, currency_code):
        """Returns the Etsy pricelist for the supplied currency code.

        Falls back to EUR pricelist when the code is unknown.
        """
        xmlid = self._PRICELIST_XMLIDS.get(
            currency_code, self._PRICELIST_XMLIDS[_DEFAULT_CURRENCY])
        return self._ref(f'pricelist_{currency_code}', xmlid)

    def _get_currency(self, currency_code):
        """Resolve a res.currency from an ISO code (e.g. 'USD'); cached."""
        key = f'currency_{currency_code}'
        if key in self._cache:
            return self._cache[key]
        currency = self._env['res.currency'].with_context(active_test=False).search(
            [('name', '=', currency_code)], limit=1)
        self._cache[key] = currency
        return currency

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

        # Email parser is EUR-only by design (per ADR-008, maintenance mode).
        # Detect from any raw-text marker that may have leaked through, fall
        # back to EUR. Wizard path does richer detection from Excel cells.
        currency_code = getattr(parse_result, 'currency', None) or _DEFAULT_CURRENCY
        currency = self._get_currency(currency_code)
        pricelist = self._get_pricelist(currency_code)
        fiscal_position = self._get_fiscal_position()
        payment_term = self._get_payment_term()
        sales_team = self._get_sales_team()

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
            # Multichannel foundation (mhc FR-024). Without these, Operations
            # Dashboard etsy filters skip the order and Gearment auto-push
            # never fires. Surfaced 2026-05-08 staging E2E run.
            'sales_channel': 'etsy',
            'channel_order_ref': parse_result.order_id,
            'order_line': [],
        }
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

        # Etsy collects shipping at checkout; surface it as an order line so
        # amount_total reflects the gross, not just product subtotal.
        shipping_cost = parse_result.shipping_cost or 0.0
        shipping_product = self._get_shipping_product()
        if shipping_cost > 0 and shipping_product:
            order_vals['order_line'].append((0, 0, {
                'product_id': shipping_product.id,
                'product_uom_qty': 1.0,
                'price_unit': shipping_cost,
                'name': shipping_product.display_name,
            }))

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

        Three-tier matching strategy (T028):
          Tier 1 — Email (exact). When email is provided, it is authoritative:
            an unknown email creates a *new* partner rather than falling
            through to address-based tiers (prevents false matches when two
            people share a household address but have separate accounts).
          Tier 2 — Normalized name + address1 + city + zip (no email).
            Accent and case insensitive; matches "José García / 123 Café"
            against "jose garcia / 123 cafe".
          Tier 3 — Name + zip fallback (no email, partial address).
            Catches the case where the address line is missing or differs
            but the buyer is the same person ordering to the same zip.
          Tier 4 — Create new.
        """
        Partner = self._env['res.partner']
        email = (getattr(shipping, 'email', '') or '').strip()
        name = (getattr(shipping, 'name', '') or '').strip()
        address1 = (getattr(shipping, 'address1', '') or '').strip()
        city = (getattr(shipping, 'city', '') or '').strip()
        zipcode = (getattr(shipping, 'zipcode', '') or '').strip()
        phone = getattr(shipping, 'phone', '') or ''

        if email:
            partner = Partner.search([('email', '=', email)], limit=1)
            if partner:
                return partner
            # Email present but unknown → skip address tiers, create new.
        else:
            partner = self._search_partner_normalized(
                name=name, address1=address1, city=city, zipcode=zipcode)
            if partner:
                return partner
            if name and zipcode:
                partner = Partner.search([
                    ('name', '=', name),
                    ('zip', '=', zipcode),
                ], limit=1)
                if partner:
                    return partner

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
            'street': address1,
            'street2': getattr(shipping, 'address2', '') or '',
            'city': city,
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

    def _search_partner_normalized(self, name, address1, city, zipcode):
        """Tier 2 partner dedup: normalized name+address+city+zip match.

        Returns the matching partner recordset (possibly empty). Filters
        candidates by exact zip first to keep the in-Python normalization
        loop bounded.
        """
        if not (name and address1 and city and zipcode):
            return self._env['res.partner'].browse()
        target = (
            _normalize_text(name),
            _normalize_text(address1),
            _normalize_text(city),
        )
        candidates = self._env['res.partner'].search([('zip', '=', zipcode)])
        for cand in candidates:
            if (
                _normalize_text(cand.name or '') == target[0]
                and _normalize_text(cand.street or '') == target[1]
                and _normalize_text(cand.city or '') == target[2]
            ):
                return cand
        return self._env['res.partner'].browse()

    # ------------------------------------------------------------------
    # Product
    # ------------------------------------------------------------------

    def find_or_create_product(self, product_name, image_url=''):
        """Find or create a product.product by exact name match.

        New products are storable (T025) and auto-categorized via keyword
        matching against ``product_category_keywords.json`` (T026). Existing
        products are returned unchanged — never re-categorized.
        """
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
            'is_storable': True,
            'etsy_image_url': image_url or False,
        }
        category = self._get_categorizer().categorize(name)
        if category:
            vals['categ_id'] = category.id
        product = Product.create(vals)
        _logger.info('Created product %s (id=%d)', product.name, product.id)
        return product

    def _get_categorizer(self):
        """Lazy-construct the ProductCategorizer (loads JSON on first use)."""
        if self._categorizer is None:
            from .product_categorizer import ProductCategorizer
            self._categorizer = ProductCategorizer(self._env)
        return self._categorizer

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
    # API-channel ingestion (Spec 005 P0-16b1)
    # ------------------------------------------------------------------

    def process_etsy_payload(self, payload, shop):
        """Create a `sale.order` from a canonical `EtsyOrderPayload`.

        Peer entry point to `process_parse_result`: same write logic
        (partner-dedup, product creation, xmlid resolution, shipping
        line) but the input shape is the canonical payload instead of
        an email-derived `ParseResult`. Caller is `EtsyOrderIngestor`
        (P0-16b1) or any future channel that emits `EtsyOrderPayload`.

        Returns the created `sale.order` record, or `None` if the
        receipt is already in Odoo (dedup by `etsy_order_id`).

        Note: status-only re-sync (FR-009) is NOT implemented here —
        when an existing order is re-ingested the call is a no-op
        returning None. The syncer (P0-16c) will add the
        update-on-existing path in a follow-up slice.
        """
        if self.is_duplicate_order(payload.etsy_order_id):
            _logger.info(
                'Skipping duplicate order %s (api ingest)',
                payload.etsy_order_id,
            )
            return None

        partner = self._payload_partner(payload)
        currency = self._get_currency(payload.currency)
        pricelist = self._get_pricelist(payload.currency)
        fiscal_position = self._get_fiscal_position()
        payment_term = self._get_payment_term()
        sales_team = self._get_sales_team()

        order_vals = {
            'partner_id': partner.id,
            'date_order': payload.order_date or odoo_fields.Datetime.now(),
            'etsy_order_id': payload.etsy_order_id,
            'etsy_shop_id': shop.id if shop else False,
            'etsy_note_from_buyer': payload.buyer_message or '',
            'etsy_gift_message': payload.gift_message or '',
            'etsy_shipping_cost': payload.shipping_total or 0.0,
            'sync_source': payload.source,
            'etsy_raw_source_id': payload.raw_source_id,
            'payment_status': payload.payment_status or False,
            'etsy_last_modified': payload.last_modified or False,
            # P0-22 — channel-agnostic fields lifted onto sale.order so both
            # ingest paths produce identical orders. Adapters set None when
            # the source channel doesn't carry the value; write False so the
            # column stays unset rather than empty-string.
            'etsy_shipping_service': payload.shipping_service or '',
            'etsy_processing_time': payload.processing_time or '',
            'etsy_discount_code': payload.discount_code or '',
            'etsy_subtotal': payload.subtotal or 0.0,
            # Multichannel foundation (mhc FR-024) — see process_parse_result
            # for rationale. Both ingest paths must stamp these consistently.
            'sales_channel': 'etsy',
            'channel_order_ref': payload.etsy_order_id,
            'order_line': [],
        }
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

        for item in payload.line_items:
            if self.is_duplicate_transaction(item.transaction_id):
                _logger.info(
                    'Skipping duplicate transaction %s (api ingest)',
                    item.transaction_id,
                )
                continue
            product = self.find_or_create_product(item.title, '')
            line_vals = {
                'product_id': product.id,
                'product_uom_qty': item.quantity or 1,
                'price_unit': item.unit_price or 0.0,
                'etsy_transaction_id': str(item.transaction_id),
                'etsy_personalisation': item.personalisation or '',
                'etsy_sku': item.sku or '',
            }
            # P0-22 — when the adapter supplied a custom display name (email
            # path uses the buyer-facing product_name with rendered options),
            # honour it. None means "use product.display_name" (default).
            if getattr(item, 'name_override', None):
                line_vals['name'] = item.name_override
            order_vals['order_line'].append((0, 0, line_vals))

        if not order_vals['order_line']:
            _logger.warning(
                'Order %s has no new transaction lines; skipping (api ingest).',
                payload.etsy_order_id,
            )
            return None

        shipping_total = payload.shipping_total or 0.0
        shipping_product = self._get_shipping_product()
        if shipping_total > 0 and shipping_product:
            order_vals['order_line'].append((0, 0, {
                'product_id': shipping_product.id,
                'product_uom_qty': 1.0,
                'price_unit': shipping_total,
                'name': shipping_product.display_name,
            }))

        order = self._env['sale.order'].create(order_vals)
        _logger.info(
            'Created sale.order %s (Etsy #%s, source=api) with %d lines',
            order.name, payload.etsy_order_id, len(order.order_line),
        )
        return order

    def _payload_partner(self, payload):
        """Map `EtsyOrderPayload.shipping_address` into the namespace
        shape that `find_or_create_partner` already accepts.

        This adapter is intentionally local: `find_or_create_partner`
        is currently coupled to an email-shaped duck-typed object
        (attributes `email`, `address1`, `country_code`, ...). Rather
        than refactor the email path in this slice, we adapt at the
        boundary. A future slice can normalize `find_or_create_partner`
        to take explicit kwargs and drop this shim.

        Gap noted: `EtsyAddressPayload` does not carry `phone` or
        `country_name`. We pass empty strings; the partner record
        will have no phone, and country resolution falls back to ISO
        alpha-2 only. Phone is rarely critical for fulfillment via
        Gearment (carriers use the address); add to the payload schema
        only when an operator workflow surfaces the need.

        Trust boundary: the `payload` MUST be either (a) hand-crafted
        in test code, or (b) emitted by an adapter that has fetched it
        from a trusted source (Etsy receipt API in P0-16b2; webhook
        validator in P1). Webhook payloads must be validated against a
        receipt re-fetch BEFORE calling `process_etsy_payload` —
        `_payload_partner` does NOT re-validate the payload contents.
        """
        from types import SimpleNamespace
        addr = payload.shipping_address
        return self.find_or_create_partner(
            SimpleNamespace(
                email=payload.buyer_email or '',
                name=addr.name,
                address1=addr.street_1,
                address2=addr.street_2 or '',
                city=addr.city,
                zipcode=addr.zip,
                phone='',
                country_code=addr.country_code,
                country_name='',
                state=addr.state or '',
            ),
            payload.buyer_name,
        )

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
        """Resolve a res.country from a code or name (T030).

        Lookup order: ISO alpha-2 code → name override → exact name → fuzzy
        name. Returns ``None`` when nothing matches.
        """
        Country = self._env['res.country']

        if code and len(code) == 2:
            country = Country.search([('code', '=', code.upper())], limit=1)
            if country:
                return country

        if name and name in _COUNTRY_NAME_OVERRIDES:
            mapped_code = _COUNTRY_NAME_OVERRIDES[name]
            country = Country.search([('code', '=', mapped_code)], limit=1)
            if country:
                return country

        if name:
            country = Country.search([('name', 'ilike', name)], limit=1)
            if country:
                return country

        return None

    def _resolve_state(self, state_name, country):
        """Resolve a res.country.state from a code or name (T029).

        Tries ISO state code first (e.g. 'CA' → California, not Carolina);
        falls back to fuzzy name match. Returns ``None`` when nothing
        matches.
        """
        if not state_name or not country:
            return None
        State = self._env['res.country.state']
        cleaned = state_name.strip()
        if not cleaned:
            return None
        # Try by code first when input looks like a code (≤5 chars).
        # Prevents 'CA' name-substring match shadowing California with Carolina.
        if len(cleaned) <= 5:
            state = State.search([
                ('code', '=', cleaned.upper()),
                ('country_id', '=', country.id),
            ], limit=1)
            if state:
                return state
        return State.search([
            ('name', 'ilike', cleaned),
            ('country_id', '=', country.id),
        ], limit=1) or None

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
