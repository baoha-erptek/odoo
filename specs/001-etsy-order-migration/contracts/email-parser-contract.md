# Contract: Email Parser Service

**Module**: `addons/etsy_integration/services/email_parser.py`
**Type**: Pure Python service (no Odoo ORM dependency)

## Interface

### Input

```python
@dataclass
class RawEmail:
    message_id: str
    subject: str
    date: str
    text_body: str   # base64-decoded plain text
    html_body: str   # base64-decoded HTML

```

### Output

```python
@dataclass
class ShippingAddress:
    name: str
    address1: str
    address2: str
    city: str
    state: str
    zipcode: str
    country: str       # Raw country name
    country_code: str  # ISO Alpha-2 (mapped)
    phone: str
    email: str

@dataclass
class Transaction:
    transaction_id: str
    product_name: str
    sku: str
    quantity: int
    price: float           # Parsed from EUR string
    personalisation: str
    option: str
    color: str
    size: str
    side: str
    face_mask_size: str
    image_url: str
    design_link_front: str
    design_link_back: str

@dataclass
class ParseResult:
    order_id: str
    shop: str
    date: str
    note_from_buyer: str
    gift_message: str
    shipping_address: ShippingAddress
    shipping_service: str
    processing_time: str
    shipping_cost: float
    discount_code: str
    subtotal: float
    transactions: list[Transaction]

@dataclass
class ParseError:
    message_id: str
    error: str
    raw_text: str
    raw_html: str
```

### Functions

```python
def parse_etsy_email(raw_email: RawEmail) -> ParseResult | ParseError:
    """
    Main entry point. Parses an Etsy order notification email.
    Returns ParseResult on success or ParseError on failure.
    Never raises exceptions — all errors are captured in ParseError.
    """

def parse_eur_amount(text: str) -> float:
    """Parse EUR price string to float. Examples: '€19.70' -> 19.70, '€3.96  ' -> 3.96"""
```

## Behavior

1. If email has no "Order details" / "Order Details" marker, return ParseError
2. If email has transactions but some fields are missing, fill with empty string (not None)
3. Country names are mapped to ISO Alpha-2 codes using a bundled lookup dict (replacing Excel file)
4. Price strings are parsed by stripping currency symbol and whitespace, then float conversion
5. Image URLs have '75x75' replaced with '300x300' for higher resolution
6. Google Sheets formulas (`=image(...)`) are not generated (Odoo doesn't need them)
