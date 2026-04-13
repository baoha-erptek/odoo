# Implementation Plan: Etsy Config Fixes

**Branch**: `002-etsy-config-fixes` | **Date**: 2026-04-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-etsy-config-fixes/spec.md`

## Summary

Fix all product configuration mismatches, sale order incomplete setup, and Odoo configuration gaps in the etsy_integration module. The existing Phase 1 MVP correctly ingests and parses Etsy order emails/Excel, but imported data lacks financial configuration (taxes, shipping lines, payment terms), products are misconfigured (non-storable, uncategorized), customer dedup is fragile, and all 17,659 orders are stuck in draft. This plan addresses 17 issues across 4 priority levels with a data migration wizard to remediate existing records.

## Technical Context

**Language/Version**: Python 3.12+ (Odoo 19 CE)
**Primary Dependencies**: Odoo 19 CE (sale_management, stock, contacts, mail), openpyxl
**Storage**: PostgreSQL 16+ via Odoo ORM
**Testing**: Odoo TransactionCase, tagged tests (`--test-tags /etsy_integration`)
**Target Platform**: Docker container (namco_odoo19), Linux server
**Project Type**: Odoo module extension (custom_addons/etsy_integration)
**Performance Goals**: Migration wizard is **batch-resumable** (runs overnight if needed) with `last_processed_id` checkpoint; processes in 500-row savepoint batches so a single bad row never rolls back the whole run. Import wizard handles 20K rows without browser timeout. *(Revised 2026-04-10 per master-plan review — the previous "<30 min" SLA was dropped because 423 $0-price orders and state-transition side effects make it unrealistic; resumability is more important than raw speed.)*
**Constraints**: Odoo 19 CE only (no Enterprise), single-threaded workers, must not break existing etsy_integration module
**Scale/Scope**: 17,659 existing orders, 2,294 products, 19 shops, 48 countries

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Odoo-Native First | PASS | All fixes use standard Odoo models (fiscal.position, payment.term, product.category, sales.team). No custom parallel structures. |
| II. Email Parser Isolation | PASS | Parser changes are limited to price detection (multi-currency). Parser remains ORM-free. |
| III. Data Integrity First | PASS | Migration wizard uses savepoints. Import wizard moves from cr.commit() to savepoint-based batching. |
| IV. Test-Driven Development | PASS | Each fix will have corresponding tests. Migration wizard testable via TransactionCase. |
| V. Incremental Migration | PASS | This is Phase 2 work (product catalog, customer CRM, reporting) per constitution. Builds on Phase 1. |
| VI. Security by Default | PASS | No new credentials. Shop-level record rules add security. |
| VII. Simplicity Over Completeness | PASS | JSON keyword file over DB model for categories. No product variants (deferred). No auto-merge of partners. |

## Project Structure

### Documentation (this feature)

```text
specs/002-etsy-config-fixes/
├── spec.md              # Feature specification (done)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit-tasks)
```

### Source Code (repository root)

```text
custom_addons/etsy_integration/
├── __manifest__.py                          # Add new data files
├── models/
│   ├── sale_order.py                        # Add etsy_has_discount computed field
│   ├── sale_order_line.py                   # Add etsy_design_status field
│   ├── product_product.py                   # Add category assignment helper
│   └── res_users.py                         # NEW: Add etsy_shop_ids M2M for record rules
├── services/
│   ├── order_creator.py                     # Multi-currency, shipping line, fiscal pos, categories, dedup
│   ├── image_downloader.py                  # Batch size limit
│   └── product_categorizer.py               # NEW: Keyword-based product categorization service
├── wizards/
│   ├── import_orders_wizard.py              # Header mapping, savepoints, multi-currency, auto-confirm
│   └── data_migration_wizard.py             # NEW: Batch fix existing records
├── views/
│   ├── data_migration_wizard_views.xml      # NEW: Migration wizard form
│   ├── etsy_discount_views.xml              # NEW: Discount analytics pivot/graph
│   ├── etsy_design_queue_views.xml          # Add status column and filter
│   └── menu.xml                             # Add migration wizard menu item
├── data/
│   ├── etsy_fiscal_data.xml                 # NEW: Fiscal position, tax, payment term, sales team, pricelists
│   ├── etsy_product_categories.xml          # NEW: Product category hierarchy
│   ├── product_category_keywords.json       # NEW: Keyword-to-category mapping
│   ├── ir_cron_data.xml                     # Add image download cron
│   └── etsy_shipping_product.xml            # NEW: Shipping service product
├── security/
│   ├── ir.model.access.csv                  # Add migration wizard ACL
│   └── etsy_security.xml                    # Add shop-level record rules
└── tests/
    ├── test_multi_currency_parsing.py       # NEW: EUR/USD/GBP price parsing
    ├── test_data_migration.py               # NEW: Migration wizard tests
    ├── test_product_categorizer.py          # NEW: Keyword categorization tests
    └── test_import_wizard_headers.py        # NEW: Header-based mapping tests
```

**Structure Decision**: All changes within the existing `custom_addons/etsy_integration/` module. No new modules needed. New files are added to existing directories following the established pattern.

---

## Phase 0: Research

### R1: Odoo 19 Fiscal Position and Tax Setup

**Decision**: Create fiscal position + 0% tax via XML data file (`noupdate="1"`)
**Rationale**: Standard Odoo pattern for module-provided master data. Fiscal position maps no tax to the 0% "Etsy Tax Collected" tax. Applied to orders during creation.
**Alternatives considered**: Manual setup via UI (rejected: not reproducible), ir.config_parameter (rejected: not the right model for tax config)

### R2: Odoo 19 Product Category Hierarchy

**Decision**: Create category tree via XML data file. Keyword mapping via JSON file loaded by a service.
**Rationale**: XML for categories provides stable xmlids for referencing. JSON for keywords allows easy editing without XML escaping issues. Service layer keeps logic testable.
**Alternatives considered**: Dedicated etsy.category.keyword model (rejected: over-engineering per constitution VII), hardcoded Python dict (rejected: hard to maintain)

### R3: Multi-Currency Price Parsing

**Decision**: Extend the existing `_parse_eur_price()` to detect currency symbol/prefix and return `(amount, currency_code)` tuple. Set `currency_id` on the sale order based on detected currency.
**Rationale**: Minimal change to existing parser. Odoo handles multi-currency natively once currency_id is set correctly.
**Alternatives considered**: Convert all to EUR at import time (rejected: loses original price information), separate parsers per currency (rejected: unnecessary duplication)

### R4: Savepoint-Based Batch Processing with Checkpointing

**Decision**: Replace `self.env.cr.commit()` with `self.env.cr.savepoint()` context manager per batch of **500 orders**. Persist a `last_processed_id` checkpoint on the wizard (or `ir.config_parameter`) after each successful batch. On batch failure, rollback that batch only, log failing order IDs to `etsy.sync.health`, and continue. If the wizard is killed mid-run (worker timeout, OOM, deploy), the next invocation reads the checkpoint and resumes from the next id.
**Rationale**: Preserves Odoo's transaction model. Partial failures are recoverable. No orphaned records. **Resumability is critical** — a 17K-row run with state transitions + stock moves + accounting entries realistically takes 3-8 hours; the wizard must survive interruptions. 500-row batches balance savepoint overhead against memory use.
**Alternatives considered**: Single transaction for all (rejected: 17K records in one transaction risks OOM); 100-row batches (rejected: too much savepoint overhead on 17K rows); keep cr.commit with better error handling (rejected: still breaks Odoo patterns); queue_job (rejected: not in CE).

### R5: Order Confirmation + Delivery Completion for Historical Data (No Auto-Invoice)

**Decision**: Migration wizard calls `order.action_confirm()` then `picking.button_validate()` (with immediate transfer wizard auto-processing) for each order. Process in batches of 500 with savepoints. **Explicitly skip invoice creation** — these orders were already paid through Etsy months ago. After confirmation, set `invoice_status = 'invoiced'` via a direct write so historical orders don't show "to invoice" forever.
**Rationale**: Standard Odoo workflow. action_confirm creates stock.picking. button_validate completes the delivery with proper stock moves and audit trail. Skipping invoice creation avoids creating 17K phantom invoices for money already collected.
**Alternatives considered**: Direct SQL state update (rejected: bypasses ORM constraints and stock moves), background job via queue_job (rejected: not in CE), confirm + auto-invoice (rejected: creates duplicate accounting artifacts for money already received by Etsy).

### R6: Header-Based Column Mapping

**Decision**: Read first row of Excel, build `{normalized_header: column_index}` dictionary. Normalize by stripping whitespace, uppercasing. Required headers: TRANSACTION_ID, ORDER_ID, PRODUCT_NAME. Optional headers: all others (default to empty/zero if missing).
**Rationale**: Robust against column reordering. Clear error if required columns missing.
**Alternatives considered**: Regex fuzzy matching on headers (rejected: over-engineering), user-configurable mapping UI (rejected: one-time import, not worth the UI)

### R7: Shop-Level Record Rules

**Decision**: Add `etsy_shop_ids` Many2many field on `res.users`. Create `ir.rule` on `sale.order` with domain `[('etsy_shop_id', 'in', user.etsy_shop_ids.ids)]` for the Etsy User group. Managers see all. Apply same pattern to `etsy.email.log`.
**Rationale**: Standard Odoo record rule pattern. M2M on users allows assigning multiple shops. Products and partners remain shared (per clarification).
**Alternatives considered**: Separate group per shop (rejected: doesn't scale to 19+ shops), company-based isolation (rejected: overkill, only one company)

### R8: Observability — `etsy.sync.health` Model

**Decision**: Add a small `etsy.sync.health` model (one row per integration/cron: `email_ingestion`, `historical_import`, `data_migration`) with fields `last_run_at`, `last_successful_run_at`, `last_run_row_count`, `last_run_error_count`, `last_error_message`, `state` (`ok`/`warning`/`error`). The migration wizard writes a row at the start, updates after each 500-row batch, and finalizes at the end. Future integrations (Gmail cron, Spec 005 API sync, Spec 004 partner sync, Spec 004 tracking import) will write to the same model via a common helper. A single dashboard tile on the Etsy menu displays the table.
**Rationale**: Devil's advocate review flagged that outages are currently invisible — BA only notices when "orders stopped coming in" days later. A 5-field model + 1 tile is cheap insurance that pays off on every subsequent integration. Named `etsy.sync.health` for now; it will be renamed/moved to `multichannel.sync.health` in the Phase 1 module decomposition (master-plan §4).
**Alternatives considered**: External monitoring (rejected: out of scope for CE without additional infra); cron logs only (rejected: nobody reads them); chatter messages (rejected: too chatty, no rollup view).

### R9: 423 $0-Price Order Triage

**Decision**: Before running the migration wizard over the full dataset, the wizard must identify and **quarantine** the 423 orders with `amount_total <= 0`. Strategy: (1) flag them via a new `etsy_price_anomaly` computed boolean; (2) export them to a CSV for manual review; (3) migration wizard skips anomalies by default (configurable via `include_anomalies` Boolean on the wizard). Anomalies are resolved in a separate follow-up pass: either manually corrected from source Excel by an operator, re-parsed with a relaxed regex, or archived with `active=False` if unrecoverable.
**Rationale**: Mixing broken and good rows in the same run will cause hard-to-interpret batch failures. Quarantine-first keeps the 17,236 good-row migration clean, and the 423 become a smaller, auditable follow-up task.
**Alternatives considered**: Fix-in-wizard with price defaulting (rejected: guesses at data we don't have); archive all 423 immediately (rejected: may be recoverable from source); skip silently (rejected: creates the same silent-failure problem the team is trying to fix).

### R10: Customer Dedup — CSV for BA Approval, Never Auto-Merge

**Decision**: The migration wizard's customer dedup pass **does not auto-merge** historical partners. Instead, it runs the normalized-name+address heuristic over all existing Etsy partners and produces a CSV report (`proposed_partner_merges.csv`) with columns `keep_partner_id, keep_name, merge_partner_id, merge_name, confidence, reason`. The BA lead reviews the CSV, approves rows (or rejects), and a **second wizard action** (`action_apply_merges`) reads the approved subset and executes merges one by one inside a savepoint per row. Future (post-migration) dedup is handled in the `order_creator.find_or_create_partner()` email-first strategy (R6 / §R6 in spec.md).
**Rationale**: Devil's advocate review flagged **GDPR risk from false merges** — two unrelated "Nguyen Van A" customers in Hanoi would become one. A reversible, BA-approved process eliminates the risk and creates an audit trail. The 0% email coverage means any auto-merge is a guess.
**Alternatives considered**: Auto-merge with high-confidence threshold (rejected: no reliable signal without email); defer historical dedup entirely (rejected: BA asked for it); fuzzy-match UI inside Odoo (rejected: Excel is already in the team's workflow, lower friction).

---

## Phase 1: Design

### Data Files to Create

#### 1. `data/etsy_shipping_product.xml`
- `product.product` record: name="Etsy Shipping", type="service", sale_ok=True, purchase_ok=False
- xmlid: `etsy_integration.product_etsy_shipping`

#### 2. `data/etsy_fiscal_data.xml`
- `account.tax`: name="Etsy Tax Collected (0%)", amount=0, type_tax_use="sale"
- `account.fiscal.position`: name="Etsy Marketplace"
- `account.fiscal.position.tax`: maps all sale taxes to the 0% Etsy tax
- `account.payment.term`: name="Etsy Prepaid", line_ids with days=0 (immediate)
- `crm.team`: name="Etsy", use_quotations=True
- `product.pricelist`: name="Etsy EUR", currency_id=EUR
- `product.pricelist`: name="Etsy USD", currency_id=USD

#### 3. `data/etsy_product_categories.xml`
Category hierarchy:
```
Etsy Products (parent)
├── Ring Dishes
├── Temporary Tattoos
├── Mugs & Drinkware
├── Jewelry
├── Home Decor
├── Personalized Gifts
├── Stickers
├── Clothing & Accessories
├── Pet Products
└── Uncategorized
```

#### 4. `data/product_category_keywords.json`
```json
{
  "ring_dishes": ["ring dish", "jewelry dish", "trinket dish", "ring holder"],
  "temporary_tattoos": ["tattoo", "temporary tattoo", "fake tattoo"],
  "mugs_drinkware": ["mug", "cup", "tumbler", "drinkware", "coffee"],
  "jewelry": ["necklace", "bracelet", "earring", "ring", "pendant"],
  "home_decor": ["pillow", "candle", "wall art", "frame", "ornament"],
  "personalized_gifts": ["personalized", "custom", "engraved", "monogram"],
  "stickers": ["sticker", "decal", "label"],
  "clothing": ["shirt", "hoodie", "hat", "scarf", "clothing"],
  "pet_products": ["pet", "dog", "cat", "collar", "leash"]
}
```
Categories matched in order; first match wins. "personalized_gifts" is intentionally broad as a catch-all before "uncategorized".

### Service Changes

#### `services/order_creator.py` Changes:
1. **`_parse_price(text)`** -- new method replacing `_parse_eur()`:
   - Detects `$`, `EUR`, `GBP`, `\u20ac`, `\u00a3` symbols
   - Returns `(float_amount, currency_code)` tuple
   - Falls back to EUR if no symbol detected
   - Logs warning for truly unparseable values

2. **`_get_shipping_product()`** -- returns the Etsy Shipping service product (cached via xmlid lookup)

3. **`_get_fiscal_position()`** -- returns Etsy Marketplace fiscal position (cached)

4. **`_get_payment_term()`** -- returns Etsy Prepaid payment term (cached)

5. **`_get_sales_team()`** -- returns Etsy sales team (cached)

6. **`_get_pricelist(currency_code)`** -- returns EUR or USD pricelist

7. **`process_parse_result()`** -- updated to:
   - Set fiscal_position_id, payment_term_id, team_id, pricelist_id on order
   - Add shipping cost as order line (Etsy Shipping product)
   - Set currency_id based on detected price currency
   - Set is_storable=True on new products

8. **`find_or_create_product()`** -- updated to:
   - Set `is_storable=True`
   - Call `product_categorizer.categorize(product_name)` for category assignment

9. **`find_or_create_partner()`** -- improved dedup:
   - Primary: email (if available)
   - Secondary: name + address1 + city + zip (normalized)
   - Tertiary: name + zip (current fallback)
   - State resolution: check `code` field first, then `name` with ilike

#### `services/product_categorizer.py` (NEW):
- Loads `data/product_category_keywords.json` at init
- `categorize(product_name) -> product.category`: matches product name against keywords
- Returns xmlid-referenced category or "Uncategorized" default
- Case-insensitive matching, checks all keywords per category

### Wizard Changes

#### `wizards/import_orders_wizard.py` Changes:
1. **Header-based mapping**: Read row 1, build header dict, replace all `_COL_*` constants
2. **Multi-currency `_parse_price()`**: Detect currency, return `(amount, currency_code)`
3. **Savepoint batching**: Replace `cr.commit()` with `cr.savepoint()` per 100-order batch
4. **Auto-confirm option**: Add `auto_confirm` Boolean field (default True for historical)
5. **Shipping line**: Add Etsy Shipping product line for each order with shipping cost
6. **Financial config**: Set fiscal position, payment term, sales team, pricelist, currency
7. **Validation report**: Add `warning_count` and `validation_notes` fields to wizard result

#### `wizards/data_migration_wizard.py` (NEW):
TransientModel `etsy.data.migration.wizard` with:
- `excel_file` (Binary, optional) -- for USD price re-parsing
- `auto_confirm` (Boolean, default=True) -- confirm draft orders; does NOT auto-invoice
- `fix_shipping_lines` (Boolean, default=True)
- `fix_financial_config` (Boolean, default=True)
- `fix_product_config` (Boolean, default=True)
- `generate_dedup_report` (Boolean, default=True)
- `include_anomalies` (Boolean, default=False) -- include 423 $0-price orders (R9)
- `resume_from_checkpoint` (Boolean, default=True) -- read `last_processed_id` and resume (R4)
- `batch_size` (Integer, default=500) -- savepoint batch size (R4)
- `last_processed_id` (Integer, readonly) -- checkpoint written after each batch
- `status_message` (Text, readonly) -- results summary
- `sync_health_id` (Many2one `etsy.sync.health`) -- link to observability row (R8)

**`action_migrate()`** pipeline:
1. Create/update `etsy.sync.health` row for `data_migration` (R8). State=`running`.
2. Quarantine anomalies (R9): flag `etsy_price_anomaly=True` on orders with `amount_total <= 0`; export CSV; exclude unless `include_anomalies=True`.
3. Build the working domain: `[('is_etsy_order','=',True), ('etsy_price_anomaly','=',include_anomalies)]`; if resuming, add `('id','>', last_processed_id)`.
4. Iterate in 500-order batches (ordered by id). For each batch inside a `env.cr.savepoint()`:
   - If `fix_financial_config`: Set `fiscal_position_id`, `payment_term_id`, `team_id`, `pricelist_id`, `currency_id`
   - If `fix_shipping_lines`: For orders with `etsy_shipping_cost > 0` and no shipping line, add one
   - If `fix_product_config`: Set `is_storable=True`, run categorizer on all Etsy products touched by this batch
   - If `excel_file` provided: Re-parse USD prices from Excel, match by `etsy_transaction_id`
   - If `auto_confirm`: Confirm draft orders, validate `stock.picking` to "done", **set `invoice_status='invoiced'` via direct write** (R5 — do not generate invoices)
   - Update `last_processed_id = batch.ids[-1]`
   - Update `etsy.sync.health`: increment `last_run_row_count`, bump `last_run_at`
   - Commit savepoint
5. On batch failure: rollback savepoint, log failing order IDs to `etsy.sync.health.last_error_message`, increment `last_run_error_count`, **continue to next batch** (do not abort run).
6. After all batches complete:
   - If `generate_dedup_report`: Produce `proposed_partner_merges.csv` for BA approval (R10). **Do not auto-merge.**
   - Finalize `etsy.sync.health` state to `ok` (0 errors) or `warning` (errors < 5%) or `error` (>= 5%)
   - Display summary counts
7. A separate `action_apply_merges()` method (invoked manually after BA review) reads the approved CSV and executes merges in per-row savepoints.

**Resumability**: If the Odoo worker is killed mid-run, the next invocation with `resume_from_checkpoint=True` reads `last_processed_id` and skips already-processed orders. Idempotent by design — re-running over processed orders is a no-op because the fields are already set.

### Model Changes

#### `models/sale_order.py`:
- Add `etsy_has_discount` Boolean computed field: `@api.depends('etsy_discount_code')`
- Add `etsy_price_anomaly` Boolean computed field: `@api.depends('amount_total')` — `True` when `amount_total <= 0`. Indexed. (R9)

#### `models/sale_order_line.py`:
- Add `etsy_design_status` Selection field: `[('pending','Pending'),('in_progress','In Progress'),('completed','Completed')]`, default='pending'

#### `models/res_users.py` (NEW):
- Extend `res.users` with `etsy_shop_ids` Many2many to `etsy.shop`

#### `models/etsy_sync_health.py` (NEW — R8):
Model `etsy.sync.health` with fields:
- `name` (Char, required) — integration identifier (e.g. `email_ingestion`, `data_migration`, `historical_import`)
- `state` (Selection: `idle`/`running`/`ok`/`warning`/`error`, default=`idle`)
- `last_run_at` (Datetime)
- `last_successful_run_at` (Datetime)
- `last_run_row_count` (Integer)
- `last_run_error_count` (Integer)
- `last_error_message` (Text)
- `last_processed_id` (Integer) — checkpoint for resumable jobs
- `notes` (Text) — free-form operator notes

Helper method `report_run(integration_name, row_count, error_count, error_message=None, last_id=None)` creates/updates the row. Used by the migration wizard now; reused by future crons (R8 forward compatibility).

### View Changes

#### `views/data_migration_wizard_views.xml` (NEW):
- Form view with checkboxes for each fix type, file upload for Excel, action button, status display, batch_size, include_anomalies, resume_from_checkpoint, last_processed_id (readonly), sync_health_id smart button

#### `views/etsy_sync_health_views.xml` (NEW — R8):
- List view: integration name, state (with decoration-danger for `error`, decoration-warning for `warning`, decoration-success for `ok`), last_run_at, last_run_row_count, last_run_error_count
- Form view: readonly except `notes`
- Menu item under Etsy menu: "Sync Health"

#### `views/etsy_discount_views.xml` (NEW):
- Pivot view: rows=etsy_discount_code, measures=order count + amount_total
- Graph view: bar chart of discount code usage
- Search view: filter "Has Discount"
- Action: menu item under Etsy menu

#### `views/etsy_design_queue_views.xml`:
- Add `etsy_design_status` column and filter

#### `data/ir_cron_data.xml`:
- Add second cron record for `image_downloader.cron_download_pending_images()`, interval=30min

### Security Changes

#### `security/etsy_security.xml`:
- Add `ir.rule` on `sale.order`: domain `['|',('etsy_shop_id','=',False),('etsy_shop_id','in',user.etsy_shop_ids.ids)]` for group `base.group_user`
- Add `ir.rule` on `etsy.email.log` with similar shop-based filtering
- Manager group bypasses (global=True for managers)

#### `security/ir.model.access.csv`:
- Add `etsy.data.migration.wizard` ACL for sales_team.group_sale_manager
- Add `etsy.sync.health` ACL: read for `base.group_user`, write for `sales_team.group_sale_manager` (R8)

---

## Verification Plan

1. **Module update**: `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init`
2. **Data files loaded**: Verify fiscal position, tax, payment term, sales team, pricelists, product categories exist
3. **Pre-migration freeze**: Take a 500-order known-good sample (random `is_etsy_order=true` rows with `amount_total > 0`) and snapshot it to a fixture for regression baselines. Anomaly count matches expected (~423).
4. **Resumability smoke test**: Run migration wizard on the known-good sample, interrupt mid-run (kill worker), re-run with `resume_from_checkpoint=True`, verify it skips already-processed rows and finishes.
5. **Run migration wizard**: Execute from Odoo UI, verify all counts in summary, verify `etsy.sync.health` row updated.
6. **Financial reconciliation sign-off** (mandatory — master-plan decision): Produce a per-shop reconciliation report comparing:
   - Odoo `SUM(amount_total)` vs Etsy source-data totals (from Excel)
   - Odoo order count vs Etsy source-data row count
   - Odoo confirmed count vs expected (anomalies excluded)
   BA lead must sign off before declaring Phase 0 complete.
7. **Order states**: `SELECT state, COUNT(*) FROM sale_order WHERE is_etsy_order = true AND etsy_price_anomaly = false GROUP BY state` shows all "sale" or "done" (anomalies remain in draft by design).
8. **Invoice status**: `SELECT invoice_status, COUNT(*) FROM sale_order WHERE is_etsy_order = true GROUP BY invoice_status` shows no "to invoice" (R5).
9. **Product config**: `SELECT COUNT(*) FROM product_template WHERE is_etsy_product = true AND is_storable = true` matches total Etsy products
10. **Dedup CSV review**: `proposed_partner_merges.csv` generated, BA reviews, approves a subset, `action_apply_merges()` runs successfully on approved rows (R10).
11. **Sync health tile visible**: Menu shows "Sync Health" entry, `data_migration` row reports `state=ok`.
12. **Run tests**: `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init`
13. **Ruff check**: `ruff check custom_addons/etsy_integration/`

## Complexity Tracking

No constitution violations. All changes use standard Odoo patterns.

## Revision History

- **2026-04-04**: Initial plan authored.
- **2026-04-10**: Updated per master-plan review (`specs/006-master-plan/MASTER_PLAN.md`):
  - Dropped "<30 min" SLA; replaced with batch-resumable overnight run
  - R4: batch size changed from 100 to 500 with `last_processed_id` checkpoint
  - R5: do not auto-invoice — set `invoice_status='invoiced'` directly
  - R8 added: `etsy.sync.health` observability model
  - R9 added: quarantine 423 $0-price anomalies before migration
  - R10 added: customer dedup is CSV-for-BA-approval, never auto-merge
  - Wizard pipeline rewritten for resumability and anomaly handling
  - Verification plan adds reconciliation sign-off as mandatory gate
