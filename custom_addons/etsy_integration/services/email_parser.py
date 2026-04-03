"""Pure Python email parser for Etsy order notification emails.

No Odoo ORM dependency. Extracts order data from Gmail message bodies
using regex patterns. Can be tested standalone.
"""
import codecs
import json
import logging
import os
import re
from dataclasses import dataclass, field

_logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RawEmail:
    message_id: str
    subject: str
    date: str
    text_body: str
    html_body: str


@dataclass
class ShippingAddress:
    name: str = ''
    address1: str = ''
    address2: str = ''
    city: str = ''
    state: str = ''
    zipcode: str = ''
    country: str = ''
    country_code: str = ''
    phone: str = ''
    email: str = ''


@dataclass
class Transaction:
    transaction_id: str = ''
    product_name: str = ''
    sku: str = ''
    quantity: int = 1
    price: float = 0.0
    personalisation: str = ''
    option: str = ''
    color: str = ''
    size: str = ''
    side: str = ''
    face_mask_size: str = ''
    image_url: str = ''
    design_link_front: str = ''
    design_link_back: str = ''


@dataclass
class ParseResult:
    order_id: str = ''
    shop: str = ''
    date: str = ''
    note_from_buyer: str = ''
    gift_message: str = ''
    shipping_address: ShippingAddress = field(default_factory=ShippingAddress)
    shipping_service: str = ''
    processing_time: str = ''
    shipping_cost: float = 0.0
    discount_code: str = ''
    subtotal: float = 0.0
    transactions: list = field(default_factory=list)


@dataclass
class ParseError:
    message_id: str = ''
    error: str = ''
    raw_text: str = ''
    raw_html: str = ''


# ---------------------------------------------------------------------------
# Country mapping (replaces iban_countries.xlsx)
# ---------------------------------------------------------------------------

COUNTRY_MAP = {
    'Afghanistan': 'AF', 'Albania': 'AL', 'Algeria': 'DZ', 'Argentina': 'AR',
    'Armenia': 'AM', 'Australia': 'AU', 'Austria': 'AT', 'Azerbaijan': 'AZ',
    'Bahamas': 'BS', 'Bahrain': 'BH', 'Bangladesh': 'BD', 'Barbados': 'BB',
    'Belarus': 'BY', 'Belgium': 'BE', 'Belize': 'BZ', 'Bolivia': 'BO',
    'Bosnia and Herzegovina': 'BA', 'Brazil': 'BR', 'Brunei': 'BN',
    'Bulgaria': 'BG', 'Cambodia': 'KH', 'Cameroon': 'CM', 'Canada': 'CA',
    'Chile': 'CL', 'China': 'CN', 'Colombia': 'CO', 'Costa Rica': 'CR',
    'Croatia': 'HR', 'Cuba': 'CU', 'Cyprus': 'CY', 'Czech Republic': 'CZ',
    'Czechia': 'CZ', 'Denmark': 'DK', 'Dominican Republic': 'DO',
    'Ecuador': 'EC', 'Egypt': 'EG', 'El Salvador': 'SV', 'Estonia': 'EE',
    'Ethiopia': 'ET', 'Finland': 'FI', 'France': 'FR', 'Georgia': 'GE',
    'Germany': 'DE', 'Ghana': 'GH', 'Greece': 'GR', 'Guatemala': 'GT',
    'Honduras': 'HN', 'Hong Kong': 'HK', 'Hungary': 'HU', 'Iceland': 'IS',
    'India': 'IN', 'Indonesia': 'ID', 'Iran': 'IR', 'Iraq': 'IQ',
    'Ireland': 'IE', 'Israel': 'IL', 'Italy': 'IT', 'Jamaica': 'JM',
    'Japan': 'JP', 'Jordan': 'JO', 'Kazakhstan': 'KZ', 'Kenya': 'KE',
    'Kuwait': 'KW', 'Latvia': 'LV', 'Lebanon': 'LB', 'Lithuania': 'LT',
    'Luxembourg': 'LU', 'Macao': 'MO', 'Malaysia': 'MY', 'Maldives': 'MV',
    'Malta': 'MT', 'Mexico': 'MX', 'Moldova': 'MD', 'Monaco': 'MC',
    'Mongolia': 'MN', 'Montenegro': 'ME', 'Morocco': 'MA', 'Myanmar': 'MM',
    'Nepal': 'NP', 'Netherlands': 'NL', 'New Zealand': 'NZ',
    'Nicaragua': 'NI', 'Nigeria': 'NG', 'North Macedonia': 'MK',
    'Norway': 'NO', 'Oman': 'OM', 'Pakistan': 'PK', 'Panama': 'PA',
    'Paraguay': 'PY', 'Peru': 'PE', 'Philippines': 'PH', 'Poland': 'PL',
    'Portugal': 'PT', 'Puerto Rico': 'PR', 'Qatar': 'QA', 'Romania': 'RO',
    'Russia': 'RU', 'Saudi Arabia': 'SA', 'Senegal': 'SN', 'Serbia': 'RS',
    'Singapore': 'SG', 'Slovakia': 'SK', 'Slovenia': 'SI',
    'South Africa': 'ZA', 'South Korea': 'KR', 'Spain': 'ES',
    'Sri Lanka': 'LK', 'Sweden': 'SE', 'Switzerland': 'CH', 'Taiwan': 'TW',
    'Tanzania': 'TZ', 'Thailand': 'TH', 'Trinidad and Tobago': 'TT',
    'Tunisia': 'TN', 'Turkey': 'TR', 'Ukraine': 'UA',
    'United Arab Emirates': 'AE', 'United Kingdom': 'GB',
    'United States': 'US', 'Uruguay': 'UY', 'Uzbekistan': 'UZ',
    'Venezuela': 'VE', 'Vietnam': 'VN',
}

# Image URL patterns
_IMG_URL_RE = re.compile(
    r'\bhttps?://i\.etsystatic\.com/\d+[^)"\s]+[^""]*')
_IMG_URL_RE2 = re.compile(
    r'(http)?s?:(//www\.etsy\.com/img[^\']*.(?:png|jpg|jpeg|gif|svg))')

# Buyer email extraction
_BUYER_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')

# Shipping service inside parentheses
_SHIPPING_SVC_RE = re.compile(r'\((.*?)\)')


# ---------------------------------------------------------------------------
# Pattern loading
# ---------------------------------------------------------------------------

_patterns_cache = None
_labels_cache = None


def _load_patterns():
    global _patterns_cache
    if _patterns_cache is not None:
        return _patterns_cache
    path = os.path.join(_DATA_DIR, 'regex_patterns.json')
    try:
        with open(path, encoding='utf-8') as f:
            _patterns_cache = json.load(f)
    except FileNotFoundError:
        _logger.warning('regex_patterns.json not found at %s', path)
        _patterns_cache = {}
    return _patterns_cache


def _load_string_labels():
    global _labels_cache
    if _labels_cache is not None:
        return _labels_cache
    path = os.path.join(_DATA_DIR, 'string_labels.json')
    try:
        with open(path, encoding='utf-8') as f:
            _labels_cache = json.load(f)
    except FileNotFoundError:
        _logger.warning('string_labels.json not found at %s', path)
        _labels_cache = {}
    return _labels_cache


def _rx(name):
    """Get a decoded regex pattern by name from the patterns file."""
    patterns = _load_patterns()
    raw = patterns.get(name, '')
    if not raw:
        return ''
    try:
        return codecs.decode(raw, 'unicode-escape')
    except Exception:
        return raw


def _rx_search(regex, text):
    """Search for a regex pattern in text, return match string or ''."""
    if not regex or not text:
        return ''
    match = re.search(regex, text)
    return match.group().strip() if match else ''


# ---------------------------------------------------------------------------
# Price parsing
# ---------------------------------------------------------------------------

def parse_eur_amount(text):
    """Parse a EUR price string to float. E.g. '€19.70' -> 19.70."""
    if not text:
        return 0.0
    s = str(text).strip()
    s = s.replace('\u20ac', '').replace('EUR', '').strip()
    s = s.lstrip('-').strip()
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_etsy_email(raw_email):
    """Parse an Etsy order notification email.

    Returns ParseResult on success, ParseError on failure.
    Never raises exceptions.
    """
    try:
        return _do_parse(raw_email)
    except Exception as e:
        _logger.exception('Parser error for message %s', raw_email.message_id)
        return ParseError(
            message_id=raw_email.message_id,
            error=str(e),
            raw_text=raw_email.text_body[:2000] if raw_email.text_body else '',
            raw_html=raw_email.html_body[:2000] if raw_email.html_body else '',
        )


def _do_parse(raw_email):
    text = raw_email.text_body or ''
    html = raw_email.html_body or ''

    # Find the transaction block
    txn_ids_rx = _rx('TRANSACTION_IDS')
    if not txn_ids_rx:
        return ParseError(
            message_id=raw_email.message_id,
            error='No TRANSACTION_IDS pattern loaded',
            raw_text=text[:2000], raw_html=html[:2000],
        )

    match = re.search(txn_ids_rx, text)
    if not match:
        return ParseError(
            message_id=raw_email.message_id,
            error='No "Order details" block found in email body',
            raw_text=text[:2000], raw_html=html[:2000],
        )

    order_block = match.group()

    # Extract shop
    shop = _rx_search(_rx('SHOP'), order_block).strip()

    # Split into individual transactions
    split_rx = _rx('TRANSACTION_SPLIT')
    txn_texts = re.split(split_rx, order_block) if split_rx else []
    if txn_texts and txn_texts[0]:
        txn_texts.pop(0)

    # Extract image URLs from HTML
    img_urls = _extract_image_urls(html)

    # Parse each transaction
    transactions = []
    labels = _load_string_labels()

    for idx, txn_text in enumerate(txn_texts):
        txn = _parse_transaction(txn_text, labels, text)

        # Assign image URL if available
        if idx < len(img_urls):
            txn.image_url = img_urls[idx]

        transactions.append(txn)

    if not transactions:
        return ParseError(
            message_id=raw_email.message_id,
            error='No transactions found after splitting',
            raw_text=text[:2000], raw_html=html[:2000],
        )

    # Order-level fields
    order_id = _rx_search(_rx('ORDER_ID'), text)
    note_from_buyer = _extract_note_from_buyer(text)
    gift_message = _extract_gift_message(text)
    shipping = _extract_shipping_from_html(html)
    shipping_cost_raw = _rx_search(_rx('SHIPPING_COST'), text)
    shipping_cost = parse_eur_amount(
        shipping_cost_raw.split('(')[0] if '(' in shipping_cost_raw else shipping_cost_raw)
    shipping_service = 'Standard'
    svc_match = _SHIPPING_SVC_RE.search(shipping_cost_raw)
    if svc_match and svc_match.group(1):
        shipping_service = svc_match.group(1)

    processing_time_raw = _rx_search(_rx('PROCESSING_TIME'), html)
    processing_time = processing_time_raw.replace('&ndash;', '-').replace('=', '').strip()

    subtotal_raw = _rx_search(_rx('SUBTOTAL'), text)
    subtotal = parse_eur_amount(subtotal_raw)

    discount_code = _rx_search(_rx('DISCOUNT_CODE'), text)

    return ParseResult(
        order_id=order_id,
        shop=shop,
        date=raw_email.date,
        note_from_buyer=note_from_buyer,
        gift_message=gift_message,
        shipping_address=shipping,
        shipping_service=shipping_service,
        processing_time=processing_time,
        shipping_cost=shipping_cost,
        discount_code=discount_code,
        subtotal=subtotal,
        transactions=transactions,
    )


# ---------------------------------------------------------------------------
# Transaction parsing
# ---------------------------------------------------------------------------

def _parse_transaction(txn_text, labels, full_text):
    """Parse a single transaction block into a Transaction dataclass."""
    txn = Transaction()

    # Split the text into labeled items using the same approach as the original
    items = []
    remain = txn_text

    # Product name is always first
    remain = _split_item(items, 'PRODUCT_NAME', remain, labels)

    # Optional fields — check text for label presence before splitting
    _OPTIONAL_FIELDS = [
        ('FACE_MASK_SIZE', ['Face mask size:', 'Face Mask Size:', 'face mask size:']),
        ('SIZE', ['Size:', 'size:', 'SIZE:']),
        ('CAPACITY', ['Capacity:', 'capacity:', 'CAPACITY:']),
        ('VOLUME', ['Volume:', 'volume:', 'VOLUME:']),
        ('OPTION', ['Option:', 'option:', 'OPTION:']),
        ('STYLE', ['Style:', 'style:', 'STYLE:']),
        ('PACK', ['Pack:', 'pack:', 'PACK:']),
        ('SHAPE', ['Shape:', 'shape:', 'SHAPE:']),
        ('INCLUDES', ['Includes:', 'includes:', 'INCLUDES:']),
        ('DESIGN', ['Design:', 'design:', 'DESIGN:']),
        ('PERSONALISATION', [
            'Personalization:', 'Personalisation:', 'personalisation:',
            'Personalisierun:', 'Personalisierung:']),
        ('COLOR', ['Color:', 'Colour:', 'color:', 'COLOR:', 'COLOUR:']),
        ('SIDE', ['Side:', 'side:']),
        ('QUANTITY', ['Quantity:', 'quantity:']),
        ('DISCOUNT_CODE', ['Applied discounts']),
        ('PRICE', ['Item price:']),
    ]

    for field_name, triggers in _OPTIONAL_FIELDS:
        if any(trigger in remain for trigger in triggers):
            remain = _split_item(items, field_name, remain, labels)
            if field_name == 'PRICE' and remain:
                items.append(remain)

    # Extract values from items
    txn.transaction_id = _get_value_from_items(items, 'TRANSACTION_ID', labels)
    txn.product_name = _get_value_from_items(items, 'PRODUCT_NAME', labels)
    txn.quantity = _parse_int(_get_value_from_items(items, 'QUANTITY', labels))
    txn.price = parse_eur_amount(_get_value_from_items(items, 'PRICE', labels))
    txn.personalisation = _get_value_from_items(items, 'PERSONALISATION', labels)
    txn.option = _get_value_from_items(items, 'OPTION', labels)
    txn.color = _get_value_from_items(items, 'COLOR', labels)
    txn.size = _get_value_from_items(items, 'SIZE', labels)
    txn.side = _get_value_from_items(items, 'SIDE', labels)
    txn.face_mask_size = _get_value_from_items(items, 'FACE_MASK_SIZE', labels)
    txn.sku = _get_value_from_items(items, 'SKU', labels)

    # Transaction ID from the text block directly if not found in items
    if not txn.transaction_id:
        tid_rx = _rx('TRANSACTION_ID')
        if tid_rx:
            tid_match = re.search(tid_rx, txn_text)
            if tid_match:
                val = tid_match.group().strip()
                val = val.replace('Transaction ID:', '').strip()
                txn.transaction_id = val

    # Price fallback: remove dash prefix
    if txn.price and '-' in str(txn.price):
        txn.price = abs(txn.price)

    return txn


def _split_item(items, field_name, text, labels):
    """Split text at a field label boundary, appending the first part to items.

    Returns the remaining text after the split point.
    """
    rx = _rx(field_name)
    if not rx:
        return text

    count = len(re.findall(rx, text))
    if count == 0:
        return text

    if count > 1:
        field_labels = labels.get(field_name, [])
        trigger = next((lbl for lbl in field_labels if lbl in text), None)
        if trigger:
            parts = text.partition(trigger)
            if len(parts) > 2:
                items.append(parts[0])
                return parts[2]
        return text

    parts = re.split(rx, text)
    if parts:
        items.append(parts[0])
    return parts[1] if len(parts) > 1 else ''


def _get_value_from_items(items, field_name, labels):
    """Extract a value from the items list using the string labels."""
    field_labels = labels.get(field_name, [])
    for label in field_labels:
        for item in items:
            if label in item:
                parts = re.split(re.escape(label), item)
                if len(parts) > 1:
                    val = parts[1].strip().replace('\n', '').replace('\r', '')
                    return val
    return ''


def _parse_int(text):
    """Parse text to int, default 1."""
    if not text:
        return 1
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return 1


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def _extract_image_urls(html):
    """Extract image URLs from HTML, replacing 75x75 with 300x300."""
    urls = []
    if not html:
        return urls
    for regex in (_IMG_URL_RE, _IMG_URL_RE2):
        for match in regex.finditer(html):
            url = match.group().replace('75x75', '300x300')
            if url not in urls:
                urls.append(url)
    return urls


def _extract_shipping_from_html(html):
    """Extract shipping address fields from HTML using CSS class selectors."""
    patterns = _load_patterns()
    addr = ShippingAddress()

    if not html:
        return addr

    def _html_field(key):
        rx = patterns.get(key, '')
        if not rx:
            return ''
        try:
            decoded = codecs.decode(rx, 'unicode-escape')
        except Exception:
            decoded = rx
        match = re.search(decoded, html)
        return match.group().strip() if match else ''

    addr.name = _html_field('SHIPPING_NAME')
    addr.address1 = _html_field('SHIPPING_ADDRESS1')
    addr.address2 = _html_field('SHIPPING_ADDRESS2')
    addr.city = _html_field('SHIPPING_CITY')
    addr.state = _html_field('SHIPPING_STATE')
    addr.zipcode = _html_field('SHIPPING_ZIPCODE')
    raw_country = _html_field('SHIPPING_COUNTRY')
    addr.country = raw_country
    addr.country_code = _map_country_code(raw_country)

    # Buyer contact info
    buyer_contact_rx = _rx('BUYER_CONTACT')
    if buyer_contact_rx:
        bc_match = re.search(buyer_contact_rx, html)
        if bc_match:
            bc_text = bc_match.group()
            email_match = _BUYER_EMAIL_RE.search(bc_text)
            if email_match:
                addr.email = email_match.group().strip()

    return addr


def _extract_note_from_buyer(text):
    """Extract the note from buyer, returning '' if no note was left."""
    rx = _rx('NOTE_FROM_BUYER')
    if not rx:
        return ''
    match = re.search(rx, text)
    if not match:
        return ''
    raw = match.group()
    # Format: "BuyerName: note text"
    parts = raw.split(':', 1)
    if len(parts) < 2:
        return ''
    note = parts[1].replace('-', '').replace('\n', '').replace('\r', '').strip()
    if 'The buyer did not leave a note' in note:
        return ''
    return note


def _extract_gift_message(text):
    """Extract gift message, handling multiple occurrences."""
    count = len(re.findall(r'Gift message', text))
    if count == 0:
        return ''

    if count > 1:
        parts = text.rpartition('Gift message')
        if parts[2]:
            segment = next(
                (x for x in parts if 'Shipping Address' in x), None)
            if segment:
                before_addr = segment.partition('Shipping Address')
                return before_addr[0].strip().replace('\n', '').replace('\r', '')
    else:
        rx = _rx('GIFT_MESSAGE')
        if rx:
            match = re.search(rx, text)
            if match:
                return match.group().strip().replace('\n', '').replace('\r', '')

    return ''


def _map_country_code(country_name):
    """Map a country name to ISO Alpha-2 code."""
    if not country_name:
        return ''
    name = country_name.strip()
    # Direct match
    if name in COUNTRY_MAP:
        return COUNTRY_MAP[name]
    # Case-insensitive search
    name_lower = name.lower()
    for key, code in COUNTRY_MAP.items():
        if key.lower() == name_lower:
            return code
    # If it's already a 2-letter code
    if len(name) == 2 and name.isalpha():
        return name.upper()
    return ''
