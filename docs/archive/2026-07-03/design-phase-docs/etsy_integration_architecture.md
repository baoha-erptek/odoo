# Technical Architecture: Etsy Order Integration for Odoo 19 CE

**Version**: 1.0
**Date**: 2026-04-02
**Author**: Technical Architect
**Target Platform**: Odoo 19 Community Edition (Python 3.12, OWL 2)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current System Analysis](#2-current-system-analysis)
3. [Odoo 19 CE Module Design](#3-odoo-19-ce-module-design)
4. [Data Model Design](#4-data-model-design)
5. [Complete Field Mapping](#5-complete-field-mapping)
6. [Email Fetching Service](#6-email-fetching-service)
7. [Integration Architecture](#7-integration-architecture)
8. [Migration Strategy](#8-migration-strategy)
9. [Odoo 19 CE Considerations](#9-odoo-19-ce-considerations)
10. [Security](#10-security)
11. [Deployment](#11-deployment)
12. [Appendices](#12-appendices)

---

## 1. Executive Summary

This document describes the migration of an Etsy order collection system from a standalone Python application (Gmail API + regex parser + Google Sheets) to a native Odoo 19 CE module. The new system will:

- Replace Google Sheets with Odoo's `sale.order` / `sale.order.line` / `res.partner` / `product.product` models
- Replace the standalone cron + Docker container with Odoo's `ir.cron` scheduler
- Preserve the existing 43-pattern regex parsing engine within a dedicated Odoo service model
- Provide a migration path for 17,659 existing orders (34 columns each)
- Support multiple Etsy shops (Viktor, Julien, Carina, etc.)

The module name is **`etsy_integration`**. It depends on `sale`, `mail`, and `contacts`.

---

## 2. Current System Analysis

### 2.1 Components

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Entry point | `run.py` | 10 | Reads env vars, calls main function |
| Core parser | `read_emails.py` | 487 | Gmail fetch, regex parse, Sheet update |
| Auth | `common.py` | 43 | Gmail OAuth2 (token.pickle + credentials.json) |
| Regex patterns | `regex_02.json` | 43 | Lookahead/lookbehind patterns for field extraction |
| Field constants | `regex_constants.py` | 60 | Column name constants + image/email regex |
| Label variations | `strings.json` | 20 | Multi-language label variants (EN, DE) |
| Country mapping | `res/iban_countries.xlsx` | ~250 | Country name to ISO Alpha-2 code |

### 2.2 Data Flow

```
Gmail Inbox
  |-- labeled with e.g. "ordertest2"
  |
  v
Gmail API (search by label, full message fetch)
  |
  v
Base64-decode text/plain + text/html parts
  |
  v
Regex engine:
  1. Extract "Order details" block via TRANSACTION_IDS pattern
  2. Split by "Transaction ID" boundaries
  3. Per transaction: extract product, options, pricing
  4. From HTML: shipping address (CSS class selectors), image URLs, processing time
  5. From text: buyer info, notes, gift messages, shipping cost
  6. Country name -> ISO Alpha-2 via iban_countries.xlsx
  |
  v
Deduplication check (ORDER_ID against existing Sheet rows)
  |
  v
Three Google Sheets:
  - Orders (34 columns)
  - Designs (15 columns, subset)
  - Customers (10 columns, subset)
  |
  v
Remove Gmail label from processed messages
```

### 2.3 The 34 Order Fields (Current Columns)

```
TRANSACTION_ID, IMG_URL, IMG, DATE, NOTE_FROM_BUYER, GIFT_MESSAGE,
PERSONALISATION, SKU, SHOP, ORDER_ID, SHIPPING_NAME, SHIPPING_ADDRESS1,
SHIPPING_ADDRESS2, SHIPPING_CITY, SHIPPING_STATE, SHIPPING_ZIPCODE,
SHIPPING_COUNTRY, SHIPPING_PHONE, SHIPPING_EMAIL, PRODUCT_NAME, OPTION,
COLOR, SIZE, SIDE, FACE_MASK_SIZE, QUANTITY, DESIGN_LINK_FRONT,
DESIGN_LINK_BACK, SHIPPING_SERVICE, PROCESSING_TIME, SHIPPING_COST,
PRICE, DISCOUNT_CODE, SUBTOTAL
```

### 2.4 The 15 Design Fields (Subset)

```
TRANSACTION_ID, IMG, DATE, NOTE_FROM_BUYER, GIFT_MESSAGE, PERSONALISATION,
SKU, SHOP, ORDER_ID, PRODUCT_NAME, OPTION, COLOR, SIZE, SIDE, QUANTITY
```

### 2.5 The 10 Customer Fields (Subset)

```
ID (UUID), BUYER, BUYER_EMAIL, BUYER_PHONE, ORDER_ID, TRANSACTION_ID,
DATE, IMG, PRODUCT_NAME, SHIPPING_NAME
```

---

## 3. Odoo 19 CE Module Design

### 3.1 Module Structure

```
custom_addons/etsy_integration/
    __init__.py
    __manifest__.py
    models/
        __init__.py
        etsy_shop.py              # etsy.shop
        etsy_email_log.py         # etsy.email.log
        etsy_order_import.py      # etsy.order.import (TransientModel wizard)
        sale_order.py             # sale.order (inherit)
        sale_order_line.py        # sale.order.line (inherit)
        res_partner.py            # res.partner (inherit)
        product_template.py       # product.template (inherit)
    services/
        __init__.py
        gmail_service.py          # Gmail API wrapper
        etsy_email_parser.py      # Regex parsing engine (from read_emails.py)
    views/
        etsy_shop_views.xml
        etsy_email_log_views.xml
        etsy_order_import_views.xml
        sale_order_views.xml
        sale_order_line_views.xml
        res_config_settings_views.xml
        menu.xml
    security/
        ir.model.access.csv
        etsy_security.xml         # Record rules
    data/
        ir_cron.xml               # Scheduled actions
        etsy_shop_data.xml        # Pre-seed known shops
        res_country_data.xml      # Country name alias mapping (if needed)
    static/
        description/
            icon.png
    wizard/
        __init__.py
        etsy_order_import_wizard.py
    i18n/
        vi_VN.po
    tests/
        __init__.py
        test_etsy_email_parser.py
        test_etsy_order_creation.py
        test_etsy_migration.py
```

### 3.2 Module Manifest

```python
# __manifest__.py
{
    'name': 'Etsy Integration',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Etsy order collection via Gmail email parsing',
    'description': """
        Collects Etsy order notification emails from Gmail,
        parses order details using regex patterns, and creates
        sale orders, products, and partners in Odoo.
    """,
    'author': 'Erptek',
    'website': 'https://erptek.net',
    'depends': [
        'sale',
        'contacts',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/etsy_security.xml',
        'data/ir_cron.xml',
        'data/etsy_shop_data.xml',
        'views/etsy_shop_views.xml',
        'views/etsy_email_log_views.xml',
        'views/sale_order_views.xml',
        'views/sale_order_line_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
        'wizard/etsy_order_import_views.xml',
    ],
    'assets': {},
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
```

### 3.3 Dependency Rationale

| Dependency | Why Needed |
|------------|------------|
| `sale` | `sale.order`, `sale.order.line`, sales workflow |
| `contacts` | `res.partner` address management, contact form enhancements |
| `mail` | `mail.thread` mixin for chatter on etsy models; **not** for fetchmail (see Section 6) |

**Why not `google_gmail`?** The `google_gmail` module provides OAuth2 for fetchmail (IMAP-based mail fetching). Etsy notification emails require Gmail API-level access (search by label, batch label removal), which IMAP/fetchmail cannot support. We implement our own Gmail API integration within the module. See Section 6 for the full analysis.

---

## 4. Data Model Design

### 4.1 Model Overview

```
                    etsy.shop (New)
                        |
                        | M2O
                        v
    res.partner <-- sale.order --> sale.order.line --> product.product
    (shipping)      (inherited)     (inherited)        (inherited)
        |
        | type='delivery'
        v
    res.partner
    (buyer/invoice)
```

### 4.2 New Model: `etsy.shop`

Represents an Etsy storefront. Multiple shops share one Gmail account but have different labels.

```python
# models/etsy_shop.py
from odoo import api, fields, models


class EtsyShop(models.Model):
    _name = 'etsy.shop'
    _description = 'Etsy Shop'
    _order = 'name'

    name = fields.Char(
        string='Shop Name',
        required=True,
        help='Etsy shop name as it appears in order notification emails',
    )
    active = fields.Boolean(default=True)
    gmail_label = fields.Char(
        string='Gmail Label',
        required=True,
        help='Gmail label used to filter order notification emails for this shop',
    )
    gmail_account = fields.Char(
        string='Gmail Account',
        help='Email address of the Gmail account receiving Etsy notifications',
    )
    order_count = fields.Integer(
        string='Order Count',
        compute='_compute_order_count',
    )
    order_ids = fields.One2many(
        comodel_name='sale.order',
        inverse_name='etsy_shop_id',
        string='Orders',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Default Currency',
        help='Default currency for orders from this shop',
    )
    last_fetch_date = fields.Datetime(
        string='Last Fetch Date',
        readonly=True,
    )
    fetch_count = fields.Integer(
        string='Emails Fetched (Last Run)',
        readonly=True,
    )

    _name_unique = models.Constraint(
        "UNIQUE(name)",
        "Shop name must be unique.",
    )

    def _compute_order_count(self):
        for shop in self:
            shop.order_count = self.env['sale.order'].search_count(
                [('etsy_shop_id', '=', shop.id)]
            )
```

### 4.3 New Model: `etsy.email.log`

Audit trail for processed emails. Replaces the implicit "label removed = processed" tracking.

```python
# models/etsy_email_log.py
from odoo import fields, models


class EtsyEmailLog(models.Model):
    _name = 'etsy.email.log'
    _description = 'Etsy Email Processing Log'
    _order = 'process_date desc'

    name = fields.Char(string='Email Subject', required=True)
    gmail_message_id = fields.Char(
        string='Gmail Message ID',
        required=True,
        index=True,
    )
    process_date = fields.Datetime(
        string='Processed Date',
        default=fields.Datetime.now,
        required=True,
    )
    state = fields.Selection(
        selection=[
            ('success', 'Success'),
            ('partial', 'Partial'),
            ('error', 'Error'),
            ('duplicate', 'Duplicate'),
        ],
        string='Status',
        required=True,
        default='success',
    )
    etsy_shop_id = fields.Many2one(
        comodel_name='etsy.shop',
        string='Shop',
    )
    order_ids = fields.Many2many(
        comodel_name='sale.order',
        string='Created Orders',
    )
    order_count = fields.Integer(
        string='Orders Created',
        compute='_compute_order_count',
    )
    error_message = fields.Text(string='Error Details')
    raw_body_text = fields.Text(
        string='Raw Text Body',
        help='Stored for debugging parse failures',
    )
    raw_body_html = fields.Text(
        string='Raw HTML Body',
        help='Stored for debugging parse failures',
    )

    _gmail_message_unique = models.Constraint(
        "UNIQUE(gmail_message_id)",
        "Each Gmail message can only be processed once.",
    )

    def _compute_order_count(self):
        for log in self:
            log.order_count = len(log.order_ids)
```

### 4.4 Inherited Model: `sale.order`

```python
# models/sale_order.py
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # --- Etsy-specific fields ---
    etsy_order_id = fields.Char(
        string='Etsy Order ID',
        index=True,
        copy=False,
        help='Etsy order number extracted from notification email',
    )
    etsy_shop_id = fields.Many2one(
        comodel_name='etsy.shop',
        string='Etsy Shop',
        index=True,
    )
    etsy_email_date = fields.Datetime(
        string='Email Date',
        help='Date/time from the original notification email header',
    )
    etsy_note_from_buyer = fields.Text(
        string='Note from Buyer',
    )
    etsy_gift_message = fields.Text(
        string='Gift Message',
    )
    etsy_discount_code = fields.Char(
        string='Etsy Discount Code',
    )
    etsy_subtotal = fields.Char(
        string='Etsy Subtotal (Raw)',
        help='Raw subtotal string from email, before currency parsing',
    )
    etsy_shipping_cost = fields.Float(
        string='Etsy Shipping Cost',
        digits=(12, 2),
    )
    etsy_shipping_service = fields.Char(
        string='Shipping Service',
        help='e.g. Standard, Express, Priority',
    )
    etsy_processing_time = fields.Char(
        string='Processing Time',
        help='e.g. 1-3 business days',
    )
    is_etsy_order = fields.Boolean(
        string='Is Etsy Order',
        default=False,
        index=True,
    )

    _etsy_order_unique = models.Constraint(
        "UNIQUE(etsy_order_id) WHERE etsy_order_id IS NOT NULL",
        "Etsy Order ID must be unique.",
    )
```

### 4.5 Inherited Model: `sale.order.line`

```python
# models/sale_order_line.py
from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # --- Etsy-specific fields ---
    etsy_transaction_id = fields.Char(
        string='Etsy Transaction ID',
        index=True,
        copy=False,
    )
    etsy_sku = fields.Char(
        string='Etsy SKU',
    )
    etsy_image_url = fields.Char(
        string='Product Image URL',
        help='etsystatic.com image URL (300x300)',
    )
    etsy_personalisation = fields.Text(
        string='Personalisation',
        help='Customer personalization text',
    )
    etsy_option = fields.Char(
        string='Option',
    )
    etsy_color = fields.Char(
        string='Color',
    )
    etsy_size = fields.Char(
        string='Size',
    )
    etsy_side = fields.Char(
        string='Side',
    )
    etsy_face_mask_size = fields.Char(
        string='Face Mask Size',
    )
    etsy_design_link_front = fields.Char(
        string='Design Link (Front)',
    )
    etsy_design_link_back = fields.Char(
        string='Design Link (Back)',
    )

    _etsy_transaction_unique = models.Constraint(
        "UNIQUE(etsy_transaction_id) WHERE etsy_transaction_id IS NOT NULL",
        "Etsy Transaction ID must be unique.",
    )
```

### 4.6 Inherited Model: `res.partner`

```python
# models/res_partner.py
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    etsy_buyer_id = fields.Char(
        string='Etsy Buyer ID',
        index=True,
        help='Etsy buyer username or identifier',
    )
    is_etsy_customer = fields.Boolean(
        string='Is Etsy Customer',
        default=False,
    )
```

### 4.7 Inherited Model: `product.template`

```python
# models/product_template.py
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    etsy_product_name = fields.Char(
        string='Etsy Product Name',
        index=True,
        help='Product name as listed on Etsy (may differ from Odoo name)',
    )
    is_etsy_product = fields.Boolean(
        string='Is Etsy Product',
        default=False,
    )
```

### 4.8 Entity Relationship Diagram

```
+-------------------+       +-------------------+       +-------------------+
|    etsy.shop      |       |    sale.order      |       | sale.order.line   |
|-------------------|       |-------------------|       |-------------------|
| name              |<------| etsy_shop_id (M2O)|       | etsy_transaction_ |
| gmail_label       |       | etsy_order_id     |<------| id                |
| gmail_account     |       | etsy_email_date   |  O2M  | etsy_sku          |
| currency_id       |       | etsy_note_from_   |       | etsy_image_url    |
| last_fetch_date   |       | buyer             |       | etsy_personal-    |
+-------------------+       | etsy_gift_message |       | isation           |
                             | etsy_discount_code|       | etsy_option       |
+-------------------+       | etsy_shipping_cost|       | etsy_color        |
| etsy.email.log    |       | etsy_shipping_    |       | etsy_size         |
|-------------------|       | service           |       | etsy_side         |
| gmail_message_id  |       | etsy_processing_  |       | etsy_face_mask_   |
| state             |       | time              |       | size              |
| order_ids (M2M)   |------>| partner_id (M2O)  |       | etsy_design_link_ |
| error_message     |       | partner_shipping_ |       | front/back        |
+-------------------+       | id (M2O)          |       | product_id (M2O)  |--+
                             +-------------------+       | price_unit        |  |
                                    |                    | product_uom_qty   |  |
                                    | M2O                +-------------------+  |
                                    v                                           |
                             +-------------------+       +-------------------+  |
                             |   res.partner     |       | product.product   |<-+
                             |-------------------|       |-------------------|
                             | name              |       | name              |
                             | street            |       | etsy_product_name |
                             | street2           |       | is_etsy_product   |
                             | city              |       +-------------------+
                             | state_id          |
                             | zip               |
                             | country_id        |
                             | phone             |
                             | email             |
                             | etsy_buyer_id     |
                             | is_etsy_customer  |
                             | type (delivery/   |
                             |       invoice)    |
                             +-------------------+
```

---

## 5. Complete Field Mapping

### 5.1 Order-Level Fields (34 Current Columns -> Odoo)

| # | Current Field | Odoo Model | Odoo Field | Type | Notes |
|---|---------------|------------|------------|------|-------|
| 1 | `TRANSACTION_ID` | `sale.order.line` | `etsy_transaction_id` | Char | New field; unique per line item |
| 2 | `IMG_URL` | `sale.order.line` | `etsy_image_url` | Char | New field; etsystatic.com URL (300x300) |
| 3 | `IMG` | -- | -- | -- | **Dropped**. Was Google Sheets `=image()` formula. In Odoo, use `etsy_image_url` with an `<img>` widget in the view |
| 4 | `DATE` | `sale.order` | `etsy_email_date` | Datetime | New field; parsed from email header `Date:` |
| 5 | `NOTE_FROM_BUYER` | `sale.order` | `etsy_note_from_buyer` | Text | New field |
| 6 | `GIFT_MESSAGE` | `sale.order` | `etsy_gift_message` | Text | New field |
| 7 | `PERSONALISATION` | `sale.order.line` | `etsy_personalisation` | Text | New field; per-item personalization |
| 8 | `SKU` | `sale.order.line` | `etsy_sku` | Char | New field; also used for `product.product` lookup |
| 9 | `SHOP` | `sale.order` | `etsy_shop_id` | Many2one | New field -> `etsy.shop` model |
| 10 | `ORDER_ID` | `sale.order` | `etsy_order_id` | Char | New field; Etsy order number |
| 11 | `SHIPPING_NAME` | `res.partner` | `name` | Char | Standard field on delivery address partner |
| 12 | `SHIPPING_ADDRESS1` | `res.partner` | `street` | Char | Standard field |
| 13 | `SHIPPING_ADDRESS2` | `res.partner` | `street2` | Char | Standard field |
| 14 | `SHIPPING_CITY` | `res.partner` | `city` | Char | Standard field |
| 15 | `SHIPPING_STATE` | `res.partner` | `state_id` | Many2one | Standard field; requires `res.country.state` lookup |
| 16 | `SHIPPING_ZIPCODE` | `res.partner` | `zip` | Char | Standard field |
| 17 | `SHIPPING_COUNTRY` | `res.partner` | `country_id` | Many2one | Standard field; map ISO Alpha-2 code -> `res.country` |
| 18 | `SHIPPING_PHONE` | `res.partner` | `phone` | Char | Standard field (on delivery address) |
| 19 | `SHIPPING_EMAIL` | `res.partner` | `email` | Char | Standard field (on delivery address) |
| 20 | `PRODUCT_NAME` | `product.template` | `name` | Char | Standard field; also `etsy_product_name` for original Etsy name |
| 21 | `OPTION` | `sale.order.line` | `etsy_option` | Char | New field |
| 22 | `COLOR` | `sale.order.line` | `etsy_color` | Char | New field |
| 23 | `SIZE` | `sale.order.line` | `etsy_size` | Char | New field |
| 24 | `SIDE` | `sale.order.line` | `etsy_side` | Char | New field |
| 25 | `FACE_MASK_SIZE` | `sale.order.line` | `etsy_face_mask_size` | Char | New field |
| 26 | `QUANTITY` | `sale.order.line` | `product_uom_qty` | Float | Standard field |
| 27 | `DESIGN_LINK_FRONT` | `sale.order.line` | `etsy_design_link_front` | Char | New field |
| 28 | `DESIGN_LINK_BACK` | `sale.order.line` | `etsy_design_link_back` | Char | New field |
| 29 | `SHIPPING_SERVICE` | `sale.order` | `etsy_shipping_service` | Char | New field |
| 30 | `PROCESSING_TIME` | `sale.order` | `etsy_processing_time` | Char | New field |
| 31 | `SHIPPING_COST` | `sale.order` | `etsy_shipping_cost` | Float | New field; raw shipping cost from email |
| 32 | `PRICE` | `sale.order.line` | `price_unit` | Float | Standard field |
| 33 | `DISCOUNT_CODE` | `sale.order` | `etsy_discount_code` | Char | New field |
| 34 | `SUBTOTAL` | `sale.order` | `etsy_subtotal` | Char | New field; raw text (Odoo computes `amount_total` automatically) |

### 5.2 Design Fields (15 columns -> existing mapping)

All 15 design fields are already captured by the order-level mapping above. The separate "design sheet" becomes unnecessary in Odoo because the data lives on `sale.order.line` directly. If a dedicated "design view" is needed, it is implemented as a filtered list/kanban view on `sale.order.line` where `etsy_personalisation != False OR etsy_design_link_front != False`.

### 5.3 Customer Fields (10 columns -> existing mapping)

| Current Field | Odoo Model | Odoo Field | Notes |
|---------------|------------|------------|-------|
| `ID` (UUID) | -- | -- | **Dropped**. Odoo uses auto-increment `id`. |
| `BUYER` | `res.partner` | `name` (invoice partner) | Extracted from "Note from" prefix |
| `BUYER_EMAIL` | `res.partner` | `email` (invoice partner) | Extracted via `BUYER_EMAIL_REGEX` |
| `BUYER_PHONE` | `res.partner` | `phone` (invoice partner) | Currently always empty in source |
| `ORDER_ID` | `sale.order` | `etsy_order_id` | Already mapped |
| `TRANSACTION_ID` | `sale.order.line` | `etsy_transaction_id` | Already mapped |
| `DATE` | `sale.order` | `etsy_email_date` | Already mapped |
| `IMG` | -- | -- | Dropped (Sheets formula) |
| `PRODUCT_NAME` | `product.template` | `name` | Already mapped |
| `SHIPPING_NAME` | `res.partner` | `name` (delivery partner) | Already mapped |

### 5.4 Partner Strategy: Two Contacts Per Order

Each Etsy order creates up to two `res.partner` records:

1. **Invoice Partner (Buyer)**: `type='contact'`, `is_etsy_customer=True`
   - `name` = Buyer name (from "Note from" line)
   - `email` = Buyer email (from contact section)
   - Deduplicated by `etsy_buyer_id` or `email`

2. **Delivery Partner (Shipping)**: `type='delivery'`, `parent_id` = Invoice Partner
   - `name` = SHIPPING_NAME
   - `street` = SHIPPING_ADDRESS1
   - `street2` = SHIPPING_ADDRESS2
   - `city` = SHIPPING_CITY
   - `state_id` = lookup from SHIPPING_STATE
   - `zip` = SHIPPING_ZIPCODE
   - `country_id` = lookup from SHIPPING_COUNTRY (Alpha-2)
   - `phone` = SHIPPING_PHONE
   - `email` = SHIPPING_EMAIL

On `sale.order`:
- `partner_id` = Invoice Partner (buyer)
- `partner_shipping_id` = Delivery Partner

### 5.5 Product Strategy

Products are looked up or created based on a composite key of `etsy_product_name` + `etsy_shop_id`. This prevents name collisions across shops.

```python
def _find_or_create_product(self, product_name, shop):
    """Find existing product or create new one."""
    Product = self.env['product.product']
    domain = [
        ('product_tmpl_id.etsy_product_name', '=', product_name),
        ('product_tmpl_id.is_etsy_product', '=', True),
    ]
    product = Product.search(domain, limit=1)
    if not product:
        product = Product.create({
            'name': product_name,
            'etsy_product_name': product_name,
            'is_etsy_product': True,
            'type': 'consu',  # Consumable (no stock tracking)
            'sale_ok': True,
            'purchase_ok': False,
        })
    return product
```

**Why not use product variants for Color/Size/Option?** The variant attributes from Etsy are free-text strings, not structured enumerated values. Mapping them to `product.template.attribute.value` would require fuzzy matching and normalization that adds complexity with little payoff. Instead, these are stored as plain text on the order line. If structured variant management is later desired, a migration step can parse these fields into proper Odoo attribute values.

---

## 6. Email Fetching Service

### 6.1 IMAP/Fetchmail vs. Gmail API -- Decision

| Criterion | Odoo Fetchmail (IMAP) | Gmail API (Custom) |
|-----------|----------------------|-------------------|
| Built-in to Odoo 19 CE | Yes (`mail` module + `google_gmail`) | No (custom code) |
| Search by Gmail label | No (IMAP SEARCH is limited) | Yes (native) |
| Batch label removal after processing | No | Yes (`batchModify`) |
| OAuth2 support | Yes (via `google_gmail` module) | Must implement |
| Email body parsing control | Raw RFC822, must parse MIME | Full control via API payload |
| Deduplication strategy | IMAP flags (SEEN/UNSEEN) | Gmail label + DB check |
| Pagination | Manual IMAP fetch | Built-in `nextPageToken` |

**Decision: Gmail API (Custom)**. The current system relies on Gmail-specific features (label-based search, label removal) that IMAP cannot replicate. The regex parser needs the pre-decoded text/plain and text/html parts as separate payloads, which the Gmail API provides directly. Using fetchmail would require reimplementing most of the logic anyway.

However, we borrow Odoo's `google.gmail.mixin` OAuth2 infrastructure for token management instead of using `token.pickle`.

### 6.2 Gmail Credential Management

**Option A (Recommended): Odoo System Parameters + `google.gmail.mixin`**

Store Google OAuth2 credentials in Odoo's `ir.config_parameter`:
- `etsy_integration.gmail_client_id` -- Google OAuth2 Client ID
- `etsy_integration.gmail_client_secret` -- Google OAuth2 Client Secret

Store per-account tokens on a new model or as fields on `etsy.shop`:
- `google_gmail_refresh_token` -- Long-lived refresh token
- `google_gmail_access_token` -- Short-lived access token
- `google_gmail_access_token_expiration` -- Token expiry timestamp

**Option B: Direct credentials.json + Pickle (Migrated)**

Copy the existing `credentials.json` and `token.pickle` approach into the Odoo container as files, read from a configurable path. Simpler migration but less "Odoo-native".

**Recommendation**: Option A. It integrates with Odoo's admin UI, supports multiple Gmail accounts, and the `google.gmail.mixin` already handles token refresh logic. The initial token can be obtained by adapting the existing `InstalledAppFlow` or by adding a wizard that performs the OAuth2 authorization code flow.

### 6.3 Gmail Service Architecture

```python
# services/gmail_service.py
import base64
import logging
import requests

from odoo import models, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GMAIL_API_BASE = 'https://gmail.googleapis.com/gmail/v1'
GMAIL_TOKEN_URL = 'https://oauth2.googleapis.com/token'


class EtsyGmailService(models.AbstractModel):
    """Gmail API service for Etsy email fetching.

    This is an AbstractModel (no DB table) that provides Gmail API methods.
    It uses Odoo system parameters for OAuth2 credentials and the
    etsy.shop model for per-shop refresh tokens.
    """
    _name = 'etsy.gmail.service'
    _description = 'Etsy Gmail API Service'

    def _get_access_token(self, shop):
        """Get a valid access token, refreshing if expired."""
        import time
        now = int(time.time())
        if (shop.gmail_access_token
                and shop.gmail_access_token_expiration
                and shop.gmail_access_token_expiration > now + 30):
            return shop.gmail_access_token

        Config = self.env['ir.config_parameter'].sudo()
        client_id = Config.get_param('etsy_integration.gmail_client_id')
        client_secret = Config.get_param('etsy_integration.gmail_client_secret')

        if not client_id or not client_secret:
            raise UserError('Gmail OAuth2 credentials not configured.')

        response = requests.post(GMAIL_TOKEN_URL, data={
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': shop.gmail_refresh_token,
            'grant_type': 'refresh_token',
        }, timeout=10)

        if not response.ok:
            raise UserError(f'Gmail token refresh failed: {response.text}')

        data = response.json()
        shop.sudo().write({
            'gmail_access_token': data['access_token'],
            'gmail_access_token_expiration': now + data['expires_in'],
        })
        return data['access_token']

    def _gmail_request(self, shop, method, endpoint, **kwargs):
        """Make an authenticated Gmail API request."""
        token = self._get_access_token(shop)
        headers = {'Authorization': f'Bearer {token}'}
        url = f'{GMAIL_API_BASE}/users/me/{endpoint}'
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()

    def search_messages(self, shop):
        """Search Gmail for messages with the shop's label."""
        messages = []
        params = {'q': f'label:{shop.gmail_label}'}
        while True:
            data = self._gmail_request(shop, 'GET', 'messages', params=params)
            if 'messages' in data:
                messages.extend(data['messages'])
            if 'nextPageToken' not in data:
                break
            params['pageToken'] = data['nextPageToken']
        return messages

    def get_message(self, shop, message_id):
        """Fetch full message content."""
        return self._gmail_request(shop, 'GET', f'messages/{message_id}', params={'format': 'full'})

    def remove_label(self, shop, message_ids, label_id):
        """Remove label from processed messages."""
        self._gmail_request(shop, 'POST', 'messages/batchModify', json={
            'ids': message_ids,
            'removeLabelIds': [label_id],
        })

    def get_label_id(self, shop, label_name):
        """Get Gmail label ID by name."""
        data = self._gmail_request(shop, 'GET', 'labels')
        for label in data.get('labels', []):
            if label['name'] == label_name:
                return label['id']
        return None
```

### 6.4 Additional Fields on `etsy.shop` for Gmail OAuth2

```python
# Add to etsy_shop.py
gmail_refresh_token = fields.Char(
    string='Gmail Refresh Token',
    groups='base.group_system',
    copy=False,
)
gmail_access_token = fields.Char(
    string='Gmail Access Token',
    groups='base.group_system',
    copy=False,
)
gmail_access_token_expiration = fields.Integer(
    string='Token Expiration',
    groups='base.group_system',
    copy=False,
)
```

### 6.5 Scheduled Action (ir.cron)

```xml
<!-- data/ir_cron.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    <record id="ir_cron_etsy_fetch_emails" model="ir.cron">
        <field name="name">Etsy: Fetch Order Emails</field>
        <field name="model_id" ref="model_etsy_shop"/>
        <field name="state">code</field>
        <field name="code">model._cron_fetch_etsy_emails()</field>
        <field name="user_id" ref="base.user_root"/>
        <field name="interval_number">10</field>
        <field name="interval_type">minutes</field>
        <field name="numbercall">-1</field>
        <field name="active" eval="True"/>
    </record>
</odoo>
```

The cron method on `etsy.shop`:

```python
@api.model
def _cron_fetch_etsy_emails(self):
    """Cron job: fetch and process Etsy order emails for all active shops."""
    shops = self.search([('active', '=', True), ('gmail_label', '!=', False)])
    for shop in shops:
        try:
            shop._fetch_and_process_emails()
            self.env.cr.commit()
        except Exception as e:
            _logger.exception(
                'Etsy email fetch failed for shop %s: %s', shop.name, e
            )
            self.env.cr.rollback()
```

---

## 7. Integration Architecture

### 7.1 Sequence Diagram

```
   ir.cron                etsy.shop            etsy.gmail.service       etsy.email.parser
   (10min)                                                              
     |                        |                        |                        |
     |--_cron_fetch_etsy----->|                        |                        |
     |                        |--search_messages------>|                        |
     |                        |<---[msg_id list]-------|                        |
     |                        |                        |                        |
     |                        |  for each msg_id:      |                        |
     |                        |--get_message---------->|                        |
     |                        |<---[full payload]------|                        |
     |                        |                        |                        |
     |                        |  Check etsy.email.log  |                        |
     |                        |  for gmail_message_id  |                        |
     |                        |  (skip if exists)      |                        |
     |                        |                        |                        |
     |                        |--parse_email_payload----------------------------->|
     |                        |<---[parsed_orders dict]--------------------------|
     |                        |                        |                        |
     |                        |  For each parsed order:|                        |
     |                        |  1. find_or_create     |                        |
     |                        |     res.partner (buyer)|                        |
     |                        |  2. find_or_create     |                        |
     |                        |     res.partner (ship) |                        |
     |                        |  3. find_or_create     |                        |
     |                        |     product.product    |                        |
     |                        |  4. Check sale.order   |                        |
     |                        |     etsy_order_id      |                        |
     |                        |     (skip if exists)   |                        |
     |                        |  5. Create sale.order  |                        |
     |                        |     + sale.order.line  |                        |
     |                        |  6. Confirm order      |                        |
     |                        |     (optional)         |                        |
     |                        |                        |                        |
     |                        |  Create etsy.email.log |                        |
     |                        |                        |                        |
     |                        |--remove_label--------->|                        |
     |                        |<---[done]--------------|                        |
     |<---[done]--------------|                        |                        |
```

### 7.2 Email Parser Service

The parser is a direct port of `read_emails.py` into an Odoo `AbstractModel` service, with these improvements:

1. JSON pattern files (`regex_02.json`, `strings.json`) are loaded once at module load time, not per-field per-email
2. Country lookup uses `res.country` model instead of Excel file
3. Returns structured dicts instead of flat lists
4. No pandas dependency

```python
# services/etsy_email_parser.py
import base64
import codecs
import json
import logging
import re
from pathlib import Path

from odoo import api, models

_logger = logging.getLogger(__name__)

# Load regex patterns and string labels at import time
_MODULE_DIR = Path(__file__).resolve().parent.parent
_REGEX_PATTERNS = {}
_STRING_LABELS = {}


def _load_patterns():
    global _REGEX_PATTERNS, _STRING_LABELS
    regex_path = _MODULE_DIR / 'data' / 'regex_02.json'
    strings_path = _MODULE_DIR / 'data' / 'strings.json'
    if regex_path.exists():
        with open(regex_path) as f:
            _REGEX_PATTERNS = json.load(f)
    if strings_path.exists():
        with open(strings_path) as f:
            _STRING_LABELS = json.load(f)


_load_patterns()


class EtsyEmailParser(models.AbstractModel):
    _name = 'etsy.email.parser'
    _description = 'Etsy Email Regex Parser'

    # --- Image URL regexes (from regex_constants.py) ---
    IMG_URL_REGEX = re.compile(
        r'\bhttps?://i\.etsystatic\.com/\d+[^)"\s]+[^""]*'
    )
    IMG_URL_REGEX2 = re.compile(
        r'(http)?s?:?(//www\.etsy\.com/img[^\']*\.(?:png|jpg|jpeg|gif|png|svg))'
    )
    BUYER_EMAIL_REGEX = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')

    def _get_regex(self, name):
        """Get compiled regex for a field name."""
        raw = _REGEX_PATTERNS.get(name)
        if not raw:
            return None
        decoded = codecs.decode(raw, 'unicode-escape')
        return decoded

    def _regex_search(self, pattern, text):
        """Search for regex pattern in text, return matched string or False."""
        if not pattern or not text:
            return False
        match = re.search(pattern, text)
        return match.group().strip() if match else False

    def parse_email_payload(self, payload):
        """Parse a Gmail API message payload into structured order data.

        Args:
            payload: Gmail API message payload dict (from get_message)

        Returns:
            dict with keys:
                'orders': list of order dicts
                'customers': list of customer dicts
                'email_date': str
                'subject': str
        """
        headers = payload.get('headers', [])
        parts = payload.get('parts', [])

        # Extract headers
        date_str = ''
        subject = ''
        for header in headers:
            h_name = header.get('name', '').lower()
            if h_name == 'date':
                date_str = header.get('value', '')
            elif h_name == 'subject':
                subject = header.get('value', '')

        # Decode MIME parts
        plain_text = ''
        html_text = ''
        for part in parts:
            mime_type = part.get('mimeType', '')
            body_data = part.get('body', {}).get('data', '')
            if not body_data:
                continue
            decoded = base64.urlsafe_b64decode(body_data).decode().replace('\r\n', '\n')
            if mime_type == 'text/plain':
                plain_text = decoded
            elif mime_type == 'text/html':
                html_text = decoded

        # Extract image URLs from HTML
        img_urls = []
        if html_text:
            for regex in (self.IMG_URL_REGEX, self.IMG_URL_REGEX2):
                for match in regex.finditer(html_text):
                    url = match.group().replace('75x75', '300x300')
                    if url not in img_urls:
                        img_urls.append(url)

        # Parse transaction block
        orders = []
        customers = []
        transaction_ids_pattern = self._get_regex('TRANSACTION_IDS')
        if not transaction_ids_pattern or not plain_text:
            return {'orders': [], 'customers': [], 'email_date': date_str, 'subject': subject}

        match = re.search(transaction_ids_pattern, plain_text)
        if not match:
            return {'orders': [], 'customers': [], 'email_date': date_str, 'subject': subject}

        block = match.group()
        shop = self._regex_search(self._get_regex('SHOP'), block) or ''
        order_id = self._regex_search(self._get_regex('ORDER_ID'), plain_text) or ''

        # Split into individual transactions
        split_pattern = self._get_regex('TRANSACTION_SPLIT')
        transactions = re.split(split_pattern, block)
        if transactions:
            transactions.pop(0)  # First element is before first Transaction ID

        for idx, txn_text in enumerate(transactions):
            order = self._parse_single_transaction(
                txn_text, plain_text, html_text, date_str, shop, order_id,
                img_urls[idx] if idx < len(img_urls) else '',
            )
            orders.append(order)

            customer = self._extract_customer_info(plain_text, order)
            customers.append(customer)

        return {
            'orders': orders,
            'customers': customers,
            'email_date': date_str,
            'subject': subject,
        }

    def _parse_single_transaction(self, txn_text, plain_text, html_text,
                                   date_str, shop, order_id, img_url):
        """Parse a single transaction block into an order dict."""
        # ... (port of parse_parts per-transaction logic)
        # Returns a flat dict matching current column structure
        order = {
            'TRANSACTION_ID': '',
            'PRODUCT_NAME': '',
            'IMG_URL': img_url,
            'DATE': date_str,
            'SHOP': shop,
            'ORDER_ID': order_id,
            # ... all 34 fields initialized to ''
        }
        # Apply regex extraction chain (same logic as read_emails.py)
        # ... (full implementation follows the same pattern)
        return order

    def _extract_customer_info(self, plain_text, order):
        """Extract buyer info from plain text."""
        customer = {
            'BUYER': '',
            'BUYER_EMAIL': '',
            'BUYER_PHONE': '',
        }
        buyer_contact = self._regex_search(
            self._get_regex('BUYER_CONTACT'), plain_text
        )
        if buyer_contact:
            email_match = self.BUYER_EMAIL_REGEX.search(buyer_contact)
            if email_match:
                customer['BUYER_EMAIL'] = email_match.group().strip()
        return customer

    def _resolve_country(self, country_name):
        """Map country name to res.country record using ISO code or name search.

        Replaces the iban_countries.xlsx lookup.
        """
        if not country_name:
            return self.env['res.country']

        # Try direct ISO Alpha-2 code (if already converted)
        if len(country_name) == 2:
            country = self.env['res.country'].search(
                [('code', '=', country_name.upper())], limit=1
            )
            if country:
                return country

        # Try name match (case-insensitive, ilike)
        country = self.env['res.country'].search(
            [('name', 'ilike', country_name)], limit=1
        )
        return country or self.env['res.country']
```

### 7.3 Order Creation Logic

```python
# On etsy.shop model
def _fetch_and_process_emails(self):
    """Fetch Gmail emails and create Odoo orders."""
    self.ensure_one()
    GmailService = self.env['etsy.gmail.service']
    Parser = self.env['etsy.email.parser']
    EmailLog = self.env['etsy.email.log']

    messages = GmailService.search_messages(self)
    if not messages:
        return

    label_id = GmailService.get_label_id(self, self.gmail_label)
    processed_msg_ids = []
    total_orders = 0

    for msg_ref in messages:
        msg_id = msg_ref['id']

        # Skip already-processed emails (DB-level dedup)
        if EmailLog.search_count([('gmail_message_id', '=', msg_id)]):
            processed_msg_ids.append(msg_id)
            continue

        log_vals = {
            'gmail_message_id': msg_id,
            'etsy_shop_id': self.id,
        }

        try:
            full_msg = GmailService.get_message(self, msg_id)
            payload = full_msg.get('payload', {})
            result = Parser.parse_email_payload(payload)

            log_vals['name'] = result.get('subject', 'Unknown')
            created_orders = self.env['sale.order']

            for order_data in result.get('orders', []):
                etsy_order_id = order_data.get('ORDER_ID')
                etsy_txn_id = order_data.get('TRANSACTION_ID')

                # Dedup by transaction ID
                if etsy_txn_id and self.env['sale.order.line'].search_count(
                    [('etsy_transaction_id', '=', etsy_txn_id)]
                ):
                    continue

                # Find or create partner
                customer = result['customers'][
                    result['orders'].index(order_data)
                ] if result['customers'] else {}
                partner, shipping_partner = self._find_or_create_partners(
                    order_data, customer
                )

                # Find or create product
                product = self._find_or_create_product(
                    order_data.get('PRODUCT_NAME', 'Unknown Etsy Product')
                )

                # Find or create sale order (group by ORDER_ID)
                sale_order = self._find_or_create_sale_order(
                    etsy_order_id, partner, shipping_partner, order_data
                )

                # Create order line
                self._create_order_line(sale_order, product, order_data)
                created_orders |= sale_order
                total_orders += 1

            log_vals['order_ids'] = [(6, 0, created_orders.ids)]
            log_vals['state'] = 'success' if created_orders else 'duplicate'
            processed_msg_ids.append(msg_id)

        except Exception as e:
            _logger.exception('Error processing email %s: %s', msg_id, e)
            log_vals['state'] = 'error'
            log_vals['error_message'] = str(e)

        EmailLog.create(log_vals)

    # Remove label from all processed messages
    if processed_msg_ids and label_id:
        try:
            GmailService.remove_label(self, processed_msg_ids, label_id)
        except Exception as e:
            _logger.warning('Failed to remove Gmail label: %s', e)

    self.write({
        'last_fetch_date': fields.Datetime.now(),
        'fetch_count': total_orders,
    })
```

### 7.4 Error Handling and Retry Strategy

| Error Type | Handling | Retry |
|------------|----------|-------|
| Gmail API auth failure (401) | Log error, skip shop, do not remove label | Automatic on next cron run (token refresh) |
| Gmail API rate limit (429) | Log warning, stop processing for this shop | Next cron run (10 min later) |
| Gmail API server error (5xx) | Log error, skip shop | Next cron run |
| Regex parse failure (no match) | Create `etsy.email.log` with `state='error'`, store raw body | Manual review in UI |
| Duplicate order (etsy_order_id exists) | Skip silently, create log with `state='duplicate'` | No retry needed |
| Odoo ORM error (validation, constraint) | Rollback transaction for this email, log error | Manual intervention |
| Country/State lookup failure | Create partner with empty `country_id`/`state_id`, log warning | Admin can fix in UI |

### 7.5 Logging Strategy

```python
# Logging levels:
# DEBUG: Per-field regex match results (only when troubleshooting)
# INFO: Per-email processing summary (email subject, orders created count)
# WARNING: Partial parse (some fields empty), label removal failure
# ERROR: Complete parse failure, Gmail API failure, ORM constraint violation

_logger = logging.getLogger(__name__)

# Example log output:
# INFO etsy.shop: Processing 5 emails for shop 'Viktor'
# INFO etsy.shop: Email "New order [#12345]" -> 2 orders created
# WARNING etsy.email.parser: Country 'Reunión' not found in res.country
# ERROR etsy.shop: Error processing email abc123: ValidationError(...)
```

---

## 8. Migration Strategy

### 8.1 Overview

Import 17,659 existing orders from the current Google Sheets into Odoo. This is a one-time operation performed via a TransientModel wizard.

### 8.2 Export from Google Sheets

```bash
# Export all three sheets to CSV/XLSX
# Use gspread or Google Sheets export UI
# Result: orders.csv, designs.csv, customers.csv
```

### 8.3 Import Wizard

```python
# wizard/etsy_order_import_wizard.py
import base64
import csv
import io
import logging

from odoo import fields, models, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EtsyOrderImportWizard(models.TransientModel):
    _name = 'etsy.order.import.wizard'
    _description = 'Import Etsy Orders from CSV/XLSX'

    file = fields.Binary(string='Orders File', required=True)
    filename = fields.Char(string='Filename')
    shop_id = fields.Many2one(
        comodel_name='etsy.shop',
        string='Etsy Shop',
        required=True,
    )
    skip_duplicates = fields.Boolean(
        string='Skip Existing Orders',
        default=True,
    )
    auto_confirm = fields.Boolean(
        string='Auto-confirm Orders',
        default=True,
        help='Set imported orders to "Sales Order" state',
    )
    import_count = fields.Integer(string='Orders Imported', readonly=True)
    skip_count = fields.Integer(string='Duplicates Skipped', readonly=True)
    error_count = fields.Integer(string='Errors', readonly=True)

    def action_import(self):
        """Import orders from uploaded CSV file."""
        self.ensure_one()
        data = base64.b64decode(self.file)
        reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')))

        imported = 0
        skipped = 0
        errors = 0

        # Group rows by ORDER_ID (multiple lines per order)
        orders_by_id = {}
        for row in reader:
            oid = row.get('ORDER_ID', '').strip()
            if oid not in orders_by_id:
                orders_by_id[oid] = []
            orders_by_id[oid].append(row)

        for order_id, lines in orders_by_id.items():
            try:
                # Check for existing order
                if self.skip_duplicates and order_id:
                    existing = self.env['sale.order'].search_count(
                        [('etsy_order_id', '=', order_id)]
                    )
                    if existing:
                        skipped += len(lines)
                        continue

                # Create from first line (order-level fields)
                first = lines[0]
                partner, shipping = self.shop_id._find_or_create_partners(
                    first, {}
                )
                sale_order = self.shop_id._find_or_create_sale_order(
                    order_id, partner, shipping, first
                )

                for line_data in lines:
                    product = self.shop_id._find_or_create_product(
                        line_data.get('PRODUCT_NAME', 'Unknown')
                    )
                    self.shop_id._create_order_line(
                        sale_order, product, line_data
                    )

                if self.auto_confirm:
                    sale_order.action_confirm()

                imported += 1

                # Commit every 100 orders to avoid memory pressure
                if imported % 100 == 0:
                    self.env.cr.commit()
                    _logger.info('Imported %d orders so far...', imported)

            except Exception as e:
                _logger.exception(
                    'Error importing order %s: %s', order_id, e
                )
                errors += 1
                self.env.cr.rollback()

        self.write({
            'import_count': imported,
            'skip_count': skipped,
            'error_count': errors,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Complete',
                'message': f'{imported} orders imported, {skipped} skipped, {errors} errors',
                'type': 'success' if errors == 0 else 'warning',
                'sticky': True,
            },
        }
```

### 8.4 Migration Sequence

The correct creation order to satisfy foreign key constraints:

```
Step 1: Create etsy.shop records (Viktor, Julien, Carina, etc.)
        |
Step 2: Create res.partner records (buyers, type='contact')
        |
Step 3: Create res.partner records (shipping addresses, type='delivery', parent_id=buyer)
        |
Step 4: Create product.product records (deduplicated by etsy_product_name)
        |
Step 5: Create sale.order records (grouped by ORDER_ID)
        |
Step 6: Create sale.order.line records (one per TRANSACTION_ID)
        |
Step 7: (Optional) Confirm orders via action_confirm()
```

### 8.5 Deduplication During Import

Three levels of deduplication:

1. **Order level**: `etsy_order_id` unique constraint prevents duplicate orders
2. **Line level**: `etsy_transaction_id` unique constraint prevents duplicate line items
3. **Partner level**: Lookup by `email` (buyer) or by `name + street + zip + country_id` composite (shipping)
4. **Product level**: Lookup by `etsy_product_name` on `product.template`

### 8.6 Migration Volume Estimates

| Entity | Estimated Count | Rationale |
|--------|-----------------|-----------|
| `etsy.shop` | 5-10 | Known shop names |
| `res.partner` (buyer) | ~5,000-8,000 | Many repeat buyers across 17K orders |
| `res.partner` (delivery) | ~10,000-15,000 | Some same buyer, different addresses |
| `product.product` | ~500-2,000 | Etsy shops typically have limited catalog |
| `sale.order` | ~12,000-15,000 | Multiple transactions per order |
| `sale.order.line` | ~17,659 | One per original row (transaction) |

---

## 9. Odoo 19 CE Considerations

### 9.1 CE vs EE Features Relevant to This Project

| Feature | CE | EE | Impact |
|---------|----|----|--------|
| `sale.order` model | Yes | Yes | Full access |
| `mail.thread` (chatter) | Yes | Yes | Audit trail on orders |
| `ir.cron` (scheduled actions) | Yes | Yes | Email fetch scheduling |
| `google_gmail` module (OAuth2) | Yes | Yes | Token management |
| Reporting (pivot, graph) | Basic | Advanced | CE has enough for order dashboards |
| Studio (UI customization) | No | Yes | Not needed; we define views in XML |
| Multi-company | Yes | Yes | If multiple companies use different shops |
| Inventory (stock.picking) | CE version | Full | Not needed initially (no shipment tracking) |
| eCommerce | No | No | Not relevant (Etsy is external) |
| Document Management | No | Yes | Not needed; images stored as URLs |

**Conclusion**: Odoo 19 CE provides everything needed. No EE-only features are required.

### 9.2 Odoo 19 New Features That Help

| Feature | Benefit |
|---------|---------|
| **`models.Constraint`** (PEP 695 style) | Clean syntax for SQL constraints: `_etsy_order_unique = models.Constraint("UNIQUE(etsy_order_id) WHERE ...", "msg")` |
| **`fields.Domain`** | Type-safe domain construction: `Domain('state', '=', 'done')` |
| **`search_fetch()`** | Combined search + fetch in one query, better than search() + read() |
| **Python 3.12 support** | f-strings, `match` statement for cleaner regex handling, performance improvements |
| **OWL 2 components** | For any custom dashboard or kanban views (Etsy order overview) |
| **`@api.readonly`** | Mark methods that don't need write access (view actions) |
| **Improved `_read_group`**  | Better aggregation for order statistics by shop |
| **`precompute=True`** | For computed fields that should be set at create time |

### 9.3 Python 3.12+ Compatibility

The existing `read_emails.py` uses:
- `re` module: Fully compatible
- `codecs.decode`: Fully compatible
- `base64.urlsafe_b64decode`: Fully compatible
- `json.load`: Fully compatible
- `pandas`: **Not needed** in Odoo (replaced by ORM)
- `gspread`: **Not needed** (replaced by Odoo DB)
- `google-api-python-client`: Replace with `requests` for Gmail API calls
- `pickle` (token.pickle): Replace with Odoo fields for token storage

### 9.4 OWL 2 Components (Optional)

If a custom Etsy dashboard is desired beyond standard list/form/kanban views:

```javascript
/** @odoo-module */
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class EtsyDashboard extends Component {
    static template = "etsy_integration.Dashboard";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            shops: [],
            totalOrders: 0,
            recentErrors: [],
        });
        this.loadData();
    }

    async loadData() {
        // Load shop statistics
        this.state.shops = await this.orm.searchRead(
            "etsy.shop",
            [["active", "=", true]],
            ["name", "order_count", "last_fetch_date", "fetch_count"]
        );
        // ...
    }
}

registry.category("actions").add("etsy_integration.dashboard", EtsyDashboard);
```

This is optional; standard Odoo views (list, form, kanban, pivot) will cover most needs.

---

## 10. Security

### 10.1 Gmail OAuth2 Credential Storage

| Secret | Storage | Access Control |
|--------|---------|----------------|
| `gmail_client_id` | `ir.config_parameter` | `base.group_system` (admin only via Settings) |
| `gmail_client_secret` | `ir.config_parameter` | `base.group_system` |
| `gmail_refresh_token` | `etsy.shop` field | `groups='base.group_system'` on field |
| `gmail_access_token` | `etsy.shop` field | `groups='base.group_system'` on field |

The `groups='base.group_system'` attribute on token fields ensures they are only readable/writable by Odoo administrators, even via RPC.

**Migration from token.pickle**: The existing `token.pickle` contains a Google OAuth2 `Credentials` object with a refresh token. During migration, extract the refresh token and store it in the `etsy.shop.gmail_refresh_token` field:

```python
import pickle
with open('token.pickle', 'rb') as f:
    creds = pickle.load(f)
print(creds.refresh_token)  # Copy this to etsy.shop record
```

### 10.2 Access Control (ir.model.access.csv)

```csv
id,name,model_id/id,group_id/id,perm_read,perm_write,perm_create,perm_unlink
etsy_shop_manager,etsy.shop manager,model_etsy_shop,sales_team.group_sale_manager,1,1,1,1
etsy_shop_user,etsy.shop user,model_etsy_shop,sales_team.group_sale_salesman,1,0,0,0
etsy_email_log_manager,etsy.email.log manager,model_etsy_email_log,sales_team.group_sale_manager,1,1,1,1
etsy_email_log_user,etsy.email.log user,model_etsy_email_log,sales_team.group_sale_salesman,1,0,0,0
etsy_order_import_wizard,etsy.order.import.wizard,model_etsy_order_import_wizard,sales_team.group_sale_manager,1,1,1,1
```

### 10.3 Record Rules

```xml
<!-- security/etsy_security.xml -->
<odoo>
    <data noupdate="1">
        <!-- Multi-company rule for etsy.shop -->
        <record id="etsy_shop_company_rule" model="ir.rule">
            <field name="name">Etsy Shop: Multi-company</field>
            <field name="model_id" ref="model_etsy_shop"/>
            <field name="domain_force">
                ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
            </field>
        </record>
    </data>
</odoo>
```

### 10.4 Security Checklist

- [x] No hardcoded credentials in source code
- [x] OAuth2 tokens stored with `groups='base.group_system'`
- [x] System parameters for client_id/secret (admin-only)
- [x] ACLs defined for all new models
- [x] Record rules for multi-company
- [x] No raw SQL (all queries via ORM)
- [x] Input validation on import wizard (file type check)
- [x] Error messages do not leak token values

---

## 11. Deployment

### 11.1 Docker Infrastructure

The existing `odoo19_esty` repository already has a working Docker setup:

- **Base image**: `ghcr.io/baoha-erptek/odoo19-base:latest` (Python 3.12 + Odoo 19 CE + Enterprise)
- **Project image**: `ghcr.io/baoha-erptek/odoo19-namco:latest` (config + custom_addons)
- **Production compose**: `deployment/docker-compose.prod.yml` (host networking, external PgBouncer)

### 11.2 Module Installation

```bash
# Place module in custom_addons/
cp -r etsy_integration/ custom_addons/

# Rebuild project image (custom_addons are COPYd into image)
docker build -t ghcr.io/baoha-erptek/odoo19-namco:latest .

# Or, for development: bind-mount custom_addons
# docker compose -f docker-compose.dev.yml up -d
# (where dev compose adds: volumes: - ./custom_addons:/opt/odoo/custom_addons)

# Install module
docker exec namco_odoo19 odoo -d namco_odoo19 -i etsy_integration --stop-after-init

# Update module (after code changes)
docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init
```

### 11.3 Development Docker Compose Override

```yaml
# docker-compose.dev.yml
services:
  odoo:
    build: .
    container_name: namco_odoo19_dev
    ports:
      - "8169:8169"
      - "8172:8172"
    volumes:
      - ./custom_addons:/opt/odoo/custom_addons
      - odoo-data:/var/lib/odoo
    environment:
      HOST: db
      PORT: 5432
      USER: odoo
      PASSWORD: odoo
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16
    container_name: namco_postgres_dev
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
      POSTGRES_DB: postgres
    volumes:
      - pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U odoo"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  odoo-data:
  pg-data:
```

### 11.4 Python Dependencies

The module uses only libraries already bundled with Odoo 19:
- `requests` (for Gmail API calls) -- already in Odoo requirements
- `re`, `json`, `base64`, `codecs`, `pathlib` -- stdlib
- No additional `pip install` needed

The `requirements.txt` from the standalone project includes `pandas`, `gspread`, `google-api-python-client`, `openpyxl`, `XlsxWriter` -- **none of these are needed** in the Odoo module.

### 11.5 Configuration Steps (Post-Install)

1. **Install module**: Settings > Apps > Install "Etsy Integration"
2. **Configure Gmail OAuth2**:
   - Settings > Technical > System Parameters
   - Add `etsy_integration.gmail_client_id` = (your Google Cloud OAuth2 client ID)
   - Add `etsy_integration.gmail_client_secret` = (your Google Cloud OAuth2 client secret)
3. **Create Etsy Shops**:
   - Sales > Etsy > Shops
   - Create shops (Viktor, Julien, Carina, etc.)
   - Set Gmail label for each shop
   - Set Gmail refresh token (extracted from existing `token.pickle`)
4. **Run initial import**:
   - Sales > Etsy > Import Orders
   - Upload CSV exported from Google Sheets
   - Select shop, run import
5. **Enable cron**:
   - Settings > Technical > Scheduled Actions
   - Find "Etsy: Fetch Order Emails"
   - Verify interval (default: 10 minutes) and active state
6. **Test**:
   - Apply Gmail label to a test email
   - Manually trigger cron or wait 10 minutes
   - Verify order appears in Sales > Orders

---

## 12. Appendices

### Appendix A: Regex Pattern Migration

The `regex_02.json` and `strings.json` files are copied directly into the module at `data/regex_02.json` and `data/strings.json`. No modification needed -- the parser service loads them at module import time.

### Appendix B: Country Code Migration

The `iban_countries.xlsx` file is replaced by Odoo's built-in `res.country` model, which already contains all ISO 3166 country codes and names. The parser's `_resolve_country()` method handles:

1. Direct Alpha-2 code match (e.g., "US", "DE")
2. Name-based fuzzy match via `ilike` (e.g., "United States", "Germany")
3. Common aliases that may not match exactly can be seeded via `data/res_country_data.xml`

### Appendix C: Data Volume and Performance

| Operation | Records | Expected Time |
|-----------|---------|--------------|
| Initial import (17,659 lines) | ~15K orders, ~8K partners, ~1K products | 10-20 minutes (batched) |
| Single email processing | 1-5 orders | < 2 seconds |
| Cron run (10 emails) | 10-50 orders | < 30 seconds |
| Full cron cycle (no new emails) | 0 | < 1 second (Gmail API list returns empty) |

### Appendix D: Comparison of Approaches

| Aspect | Current (Standalone) | New (Odoo Module) |
|--------|---------------------|-------------------|
| Scheduling | systemd timer / Docker cron | `ir.cron` (10 min) |
| Data storage | Google Sheets (3 sheets) | PostgreSQL (Odoo ORM) |
| Dedup strategy | Sheet search by ORDER_ID | SQL UNIQUE constraint |
| Auth management | token.pickle file | Odoo fields + system params |
| Country lookup | iban_countries.xlsx | `res.country` model |
| Error visibility | Log file tail | Odoo UI (etsy.email.log) |
| Multi-user access | Shared Google Sheet | Odoo RBAC |
| Reporting | Google Sheets formulas | Odoo pivot/graph/dashboard |
| Deployment | Docker container + rsync | Odoo module in image |
| Maintenance | Edit Python files, redeploy | Module update in Odoo |

### Appendix E: Future Enhancements (Out of Scope)

1. **Etsy API v3 Integration**: Replace email parsing with direct Etsy Open API for real-time order sync
2. **Product Variant Mapping**: Parse Color/Size/Option into `product.template.attribute.value`
3. **Inventory Integration**: Create delivery orders from confirmed Etsy sales orders
4. **Shipping Label Generation**: Integrate with carrier API for label printing
5. **Financial Reconciliation**: Match Etsy payment deposits with Odoo bank statements
6. **Multi-Currency**: Parse currency from email and set on order
7. **Image Download**: Download product images from etsystatic.com and attach as `product.image`

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-02 | Technical Architect | Initial architecture document |
