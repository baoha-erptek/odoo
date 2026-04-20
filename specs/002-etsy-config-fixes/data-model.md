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
| `etsy_price_anomaly` | Boolean | Computed, stored, indexed. `@api.depends('amount_total')`. True when `amount_total <= 0`. Used by migration wizard to quarantine the 423 $0-price orders (R9). |

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
| `generate_dedup_report` | Boolean | Default True. Produce `proposed_partner_merges.csv` for BA approval. Never auto-merges (R10). |
| `include_anomalies` | Boolean | Default False. When False, skips orders with `etsy_price_anomaly=True` (R9). |
| `resume_from_checkpoint` | Boolean | Default True. If True and a previous run left a `last_processed_id`, resume after that id (R4). |
| `batch_size` | Integer | Default 500. Savepoint batch size for resumable overnight run (R4). |
| `last_processed_id` | Integer | Readonly. Highest `sale.order.id` successfully processed in the last batch; checkpoint for resume. |
| `sync_health_id` | Many2one | To `etsy.sync.health`. Smart button link to live observability row (R8). |
| `status_message` | Text | Readonly. Summary of actions taken. |

**Methods**:
- `action_migrate()` -- Main entry point. Quarantines anomalies, iterates 500-row savepoint batches, updates checkpoint + health row per batch.
- `action_apply_merges()` -- Separate action. Reads BA-approved rows from `proposed_partner_merges.csv` and applies each merge in its own per-row savepoint (R10).
- `_fix_financial_config(orders)` -- Sets fiscal position, payment term, sales team, pricelist.
- `_fix_shipping_lines(orders)` -- Adds shipping product lines where missing.
- `_fix_prices_from_excel(orders)` -- Re-parses USD prices from uploaded Excel.
- `_fix_product_config(products)` -- Sets is_storable, runs categorizer.
- `_confirm_and_complete(orders)` -- Confirms draft orders, validates deliveries to done, sets `invoice_status='invoiced'` (R5 — no invoice records).
- `_generate_dedup_report(partners)` -- Writes `proposed_partner_merges.csv` for BA approval. Never modifies partners.
- `_quarantine_anomalies()` -- Flags `etsy_price_anomaly=True` on `amount_total <= 0` orders and exports them to CSV (R9).

### etsy.sync.health (NEW — R8)
Observability row per integration (one row per `name`). Written by migration wizard, Gmail cron, and future Spec 004/005 syncers.

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char (required, unique) | Integration identifier (`email_ingestion`, `historical_import`, `data_migration`, future `etsy_api_sync`, `gearment_sync`, `gke_tracking_import`). |
| `state` | Selection | `idle` / `running` / `ok` / `warning` / `error`. Default `idle`. Drives list-view decoration. |
| `last_run_at` | Datetime | Wallclock start of the most recent run. |
| `last_successful_run_at` | Datetime | Wallclock end of the most recent run that finished with state `ok` or `warning`. Used by future health alerts (e.g., detect stalled API sync). |
| `last_run_row_count` | Integer | Rows processed (batches × batch_size, updated incrementally). |
| `last_run_error_count` | Integer | Rows or batches that raised exceptions. |
| `last_error_message` | Text | Truncated last exception message. |
| `last_processed_id` | Integer | Checkpoint for resumable jobs (writes here, migration wizard reads here). |
| `notes` | Text | Free-form operator notes. |

**Helper**: class method `report_run(integration_name, *, row_count=None, error_count=None, error_message=None, last_id=None, state=None)` creates or updates the row. Future integrations call this helper instead of writing fields directly.

**Forward-compat**: this model will be renamed / relocated to `multichannel.sync.health` in `multichannel_hub_core` during the Phase 1 module decomposition (ADR-003). No schema changes at rename time — only `_name`, `_table`, and the ir.model.data xmlid migrate.

## Record Rules

### Sale Order Shop Isolation
- **Model**: `sale.order`
- **Domain**: `['|', ('etsy_shop_id', '=', False), ('etsy_shop_id', 'in', user.etsy_shop_ids.ids)]`
- **Groups**: `base.group_user` (bypassed by sales managers)

### Email Log Shop Isolation
- **Model**: `etsy.email.log`
- **Domain**: `['|', ('sale_order_id', '=', False), ('sale_order_id.etsy_shop_id', 'in', user.etsy_shop_ids.ids)]`
- **Groups**: `base.group_user` (bypassed by sales managers)

## ACL (ir.model.access.csv additions)

| Model | Group | R | W | C | U |
|---|---|---|---|---|---|
| `etsy.data.migration.wizard` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |
| `etsy.sync.health` | `base.group_user` | 1 | 0 | 0 | 0 |
| `etsy.sync.health` | `sales_team.group_sale_manager` | 1 | 1 | 1 | 1 |

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
