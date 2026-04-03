# Data Model: Etsy Order Migration

**Feature**: 001-etsy-order-migration
**Date**: 2026-04-02

## Model Definitions

### 1. etsy.shop

Represents an Etsy storefront. One shop has many orders.

```python
class EtsyShop(models.Model):
    _name = 'etsy.shop'
    _description = 'Etsy Shop'

    name = fields.Char(string='Shop Name', required=True, index=True)
    active = fields.Boolean(default=True)
    order_count = fields.Integer(compute='_compute_order_count')
    order_ids = fields.One2many('sale.order', 'etsy_shop_id', string='Orders')
```

### 2. etsy.email.log

Audit trail for every email processed. Enables failed parse recovery.

```python
class EtsyEmailLog(models.Model):
    _name = 'etsy.email.log'
    _description = 'Etsy Email Processing Log'
    _order = 'create_date desc'

    gmail_message_id = fields.Char(string='Gmail Message ID', required=True, index=True)
    subject = fields.Char(string='Email Subject')
    date_received = fields.Datetime(string='Date Received')
    raw_body_text = fields.Text(string='Raw Body (Text)')
    raw_body_html = fields.Text(string='Raw Body (HTML)')
    parse_status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped (Duplicate)'),
    ], string='Status', required=True, index=True)
    error_message = fields.Text(string='Error Message')
    sale_order_id = fields.Many2one('sale.order', string='Created Order')
    retry_count = fields.Integer(string='Retry Count', default=0)
```

### 3. sale.order (extension)

Extends standard sale order with Etsy-specific fields.

```python
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    etsy_order_id = fields.Char(
        string='Etsy Order ID', index=True, copy=False,
        help='Unique Etsy order identifier')
    etsy_shop_id = fields.Many2one(
        'etsy.shop', string='Etsy Shop', index=True)
    etsy_note_from_buyer = fields.Text(string='Note from Buyer')
    etsy_gift_message = fields.Text(string='Gift Message')
    etsy_shipping_service = fields.Char(string='Shipping Service')
    etsy_processing_time = fields.Char(string='Processing Time')
    etsy_shipping_cost = fields.Float(string='Etsy Shipping Cost')
    etsy_discount_code = fields.Char(string='Discount Code')
    etsy_subtotal = fields.Float(string='Etsy Subtotal')
    etsy_email_log_id = fields.Many2one(
        'etsy.email.log', string='Source Email')
    is_etsy_order = fields.Boolean(
        string='Is Etsy Order', compute='_compute_is_etsy_order', store=True)

    _sql_constraints = [
        ('etsy_order_id_unique', 'UNIQUE(etsy_order_id)',
         'Etsy Order ID must be unique!'),
    ]
```

### 4. sale.order.line (extension)

Extends order lines with per-item Etsy fields.

```python
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    etsy_transaction_id = fields.Char(
        string='Etsy Transaction ID', index=True, copy=False)
    etsy_personalisation = fields.Text(string='Personalisation')
    etsy_sku = fields.Char(string='Etsy SKU')
    etsy_option = fields.Char(string='Option')
    etsy_color = fields.Char(string='Color')
    etsy_size = fields.Char(string='Size')
    etsy_side = fields.Char(string='Side')
    etsy_face_mask_size = fields.Char(string='Face Mask Size')
    etsy_image_url = fields.Char(string='Image URL')
    etsy_design_link_front = fields.Char(string='Design Link (Front)')
    etsy_design_link_back = fields.Char(string='Design Link (Back)')

    _sql_constraints = [
        ('etsy_transaction_id_unique',
         'UNIQUE(etsy_transaction_id)',
         'Etsy Transaction ID must be unique!'),
    ]
```

### 5. product.product (extension)

Extension for Etsy image tracking. Images are downloaded from etsystatic.com
and stored in Odoo's filestore (product image_1920 field).

```python
class ProductProduct(models.Model):
    _inherit = 'product.product'

    etsy_image_url = fields.Char(string='Etsy Image URL')
    is_etsy_product = fields.Boolean(string='Is Etsy Product', default=False)
    # image_1920 (standard Odoo field) populated by image_downloader service
```

### 6. res.partner (extension)

Tag partners as Etsy customers.

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_etsy_customer = fields.Boolean(string='Is Etsy Customer', default=False)
    etsy_buyer_name = fields.Char(
        string='Etsy Buyer Name',
        help='Original buyer name from Etsy (may differ from shipping name)')
```

### 7. res.config.settings (extension)

Settings page for Gmail configuration.

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    etsy_gmail_label = fields.Char(
        string='Gmail Label',
        config_parameter='etsy_integration.gmail_label',
        default='ordertest2')
    etsy_gmail_client_id = fields.Char(
        string='Gmail Client ID',
        config_parameter='etsy_integration.gmail_client_id')
    etsy_gmail_client_secret = fields.Char(
        string='Gmail Client Secret',
        config_parameter='etsy_integration.gmail_client_secret')
    etsy_gmail_refresh_token = fields.Char(
        string='Gmail Refresh Token',
        config_parameter='etsy_integration.gmail_refresh_token')
    etsy_cron_interval = fields.Integer(
        string='Fetch Interval (minutes)',
        config_parameter='etsy_integration.cron_interval',
        default=10)
```

## Relationships Diagram

```
                    ┌─────────────┐
                    │  etsy.shop  │
                    │  name       │
                    └──────┬──────┘
                           │ 1:N
                           │
┌──────────────┐    ┌──────┴──────────────────────┐    ┌─────────────────┐
│etsy.email.log│    │        sale.order            │    │   res.partner   │
│gmail_msg_id  ├───>│  etsy_order_id (unique)      │<───┤   name          │
│raw_body      │    │  etsy_shop_id                │    │   street        │
│parse_status  │    │  partner_id                  │    │   city, zip     │
│error_message │    │  etsy_note_from_buyer        │    │   country_id    │
└──────────────┘    │  etsy_gift_message           │    │   is_etsy_cust  │
                    │  etsy_shipping_service        │    └─────────────────┘
                    │  etsy_shipping_cost           │
                    │  etsy_discount_code           │
                    └──────┬──────────────────────-─┘
                           │ 1:N
                           │
                    ┌──────┴──────────────────────┐    ┌─────────────────┐
                    │     sale.order.line           │    │ product.product │
                    │  etsy_transaction_id (unique) │───>│   name          │
                    │  product_id                   │    │   etsy_image_url│
                    │  etsy_personalisation         │    │   is_etsy_prod  │
                    │  etsy_sku                     │    └─────────────────┘
                    │  etsy_option, color, size     │
                    │  etsy_image_url               │
                    │  etsy_design_link_front/back  │
                    │  price_unit, product_uom_qty  │
                    └──────────────────────────────-┘
```

## Index Strategy

| Model | Field | Index Type | Justification |
|-------|-------|-----------|---------------|
| sale.order | etsy_order_id | UNIQUE + BTREE | Deduplication lookup on every email |
| sale.order.line | etsy_transaction_id | UNIQUE + BTREE | Deduplication per transaction |
| sale.order | etsy_shop_id | BTREE | Frequent filter by shop |
| etsy.email.log | gmail_message_id | UNIQUE + BTREE | Prevent reprocessing |
| etsy.email.log | parse_status | BTREE | Filter failed parses |
| etsy.shop | name | UNIQUE | Lookup by shop name |

## Security Model

### Access Control (ir.model.access.csv)

| Model | Group | Read | Write | Create | Unlink |
|-------|-------|------|-------|--------|--------|
| etsy.shop | base.group_user | 1 | 0 | 0 | 0 |
| etsy.shop | sales_team.group_sale_manager | 1 | 1 | 1 | 1 |
| etsy.email.log | base.group_user | 1 | 0 | 0 | 0 |
| etsy.email.log | sales_team.group_sale_manager | 1 | 1 | 1 | 1 |

Sale orders, products, and partners use existing Odoo security rules (no custom rules needed for extended fields).
