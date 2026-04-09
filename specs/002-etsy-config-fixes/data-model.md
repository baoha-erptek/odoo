# Data Model: Etsy Config Fixes

**Branch**: `002-etsy-config-fixes` | **Date**: 2026-04-04

## New Records (via XML data files)

### Etsy Shipping Product
- **Model**: `product.product`
- **xmlid**: `etsy_integration.product_etsy_shipping`
- **Fields**: name="Etsy Shipping", type="service", sale_ok=True, list_price=0.0

### Etsy Tax
- **Model**: `account.tax`
- **xmlid**: `etsy_integration.tax_etsy_collected`
- **Fields**: name="Etsy Tax Collected (0%)", amount=0.0, type_tax_use="sale"

### Etsy Fiscal Position
- **Model**: `account.fiscal.position`
- **xmlid**: `etsy_integration.fiscal_pos_etsy_marketplace`
- **Fields**: name="Etsy Marketplace", auto_apply=False

### Etsy Payment Term
- **Model**: `account.payment.term`
- **xmlid**: `etsy_integration.payment_term_etsy_prepaid`
- **Fields**: name="Etsy Prepaid", note="Payment collected by Etsy at checkout"

### Etsy Sales Team
- **Model**: `crm.team`
- **xmlid**: `etsy_integration.team_etsy`
- **Fields**: name="Etsy"

### Etsy Pricelists
- **Model**: `product.pricelist`
- **xmlids**: `etsy_integration.pricelist_etsy_eur`, `etsy_integration.pricelist_etsy_usd`
- **Fields**: name="Etsy EUR"/"Etsy USD", currency_id=EUR/USD

### Product Categories
- **Model**: `product.category`
- **Parent xmlid**: `etsy_integration.product_cat_etsy`
- **Children**: ring_dishes, temporary_tattoos, mugs_drinkware, jewelry, home_decor, personalized_gifts, stickers, clothing, pet_products, uncategorized

## Model Extensions (new fields)

### sale.order (existing extension)
| Field | Type | Notes |
|-------|------|-------|
| `etsy_has_discount` | Boolean | Computed, stored. `@api.depends('etsy_discount_code')`. True if discount_code is non-empty. |

### sale.order.line (existing extension)
| Field | Type | Notes |
|-------|------|-------|
| `etsy_design_status` | Selection | Choices: pending, in_progress, completed. Default: pending. |

### res.users (NEW extension)
| Field | Type | Notes |
|-------|------|-------|
| `etsy_shop_ids` | Many2many | Relation to `etsy.shop`. Defines which shops the user can access. |

## New Models

### etsy.data.migration.wizard (TransientModel)
| Field | Type | Notes |
|-------|------|-------|
| `excel_file` | Binary | Optional. For re-parsing USD prices from source Excel. |
| `excel_filename` | Char | Original filename. |
| `auto_confirm` | Boolean | Default True. Confirm orders and complete deliveries. |
| `fix_shipping_lines` | Boolean | Default True. Add shipping service lines. |
| `fix_financial_config` | Boolean | Default True. Set fiscal pos, payment term, team. |
| `fix_product_config` | Boolean | Default True. Set is_storable, categorize. |
| `generate_dedup_report` | Boolean | Default True. Find suspected duplicate partners. |
| `status_message` | Text | Readonly. Summary of actions taken. |

**Methods**:
- `action_migrate()` -- Main entry point. Executes selected fixes in order.
- `_fix_financial_config(orders)` -- Sets fiscal position, payment term, sales team, pricelist.
- `_fix_shipping_lines(orders)` -- Adds shipping product lines where missing.
- `_fix_prices_from_excel(orders)` -- Re-parses USD prices from uploaded Excel.
- `_fix_product_config(products)` -- Sets is_storable, runs categorizer.
- `_confirm_and_complete(orders)` -- Confirms draft orders, validates deliveries to done.
- `_generate_dedup_report(partners)` -- Finds duplicates by normalized name+zip.

## Record Rules

### Sale Order Shop Isolation
- **Model**: `sale.order`
- **Domain**: `['|', ('etsy_shop_id', '=', False), ('etsy_shop_id', 'in', user.etsy_shop_ids.ids)]`
- **Groups**: `base.group_user` (bypassed by sales managers)

### Email Log Shop Isolation
- **Model**: `etsy.email.log`
- **Domain**: `['|', ('sale_order_id', '=', False), ('sale_order_id.etsy_shop_id', 'in', user.etsy_shop_ids.ids)]`
- **Groups**: `base.group_user` (bypassed by sales managers)

## Relationships

```
res.users --M2M--> etsy.shop (via etsy_shop_ids)

sale.order
  |-- fiscal_position_id --> account.fiscal.position (Etsy Marketplace)
  |-- payment_term_id --> account.payment.term (Etsy Prepaid)
  |-- team_id --> crm.team (Etsy)
  |-- pricelist_id --> product.pricelist (Etsy EUR / Etsy USD)
  |-- currency_id --> res.currency (EUR / USD)
  +-- order_line --> sale.order.line
        |-- product_id --> product.product (Etsy Shipping for shipping lines)
        |-- etsy_design_status (pending/in_progress/completed)

product.template
  |-- categ_id --> product.category (Etsy Products / subcategory)
  |-- is_storable = True
```
