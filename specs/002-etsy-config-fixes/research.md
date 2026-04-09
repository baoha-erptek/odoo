# Research: Etsy Config Fixes

**Branch**: `002-etsy-config-fixes` | **Date**: 2026-04-04

## R1: Fiscal Position and Tax in Odoo 19 CE

**Decision**: Create via XML data file with `noupdate="1"`
**Rationale**: Standard pattern for module-provided master data. `account.fiscal.position` with a tax mapping from any sale tax to our 0% "Etsy Tax Collected" tax. This allows orders to show tax lines for reporting without affecting amounts.
**Alternatives considered**:
- Manual UI setup (rejected: not reproducible across environments)
- `ir.config_parameter` (rejected: wrong model type for fiscal data)

**Key implementation notes**:
- Fiscal position requires `account` module installed (auto-installed with `sale_management`)
- Tax with `amount=0` and `type_tax_use='sale'` is the standard Odoo pattern for marketplace-collected tax
- Payment term with `value='balance'` and `days=0` represents immediate payment

## R2: Product Category Hierarchy

**Decision**: XML for categories, JSON for keyword mappings
**Rationale**: XML provides stable xmlids. JSON avoids XML escaping issues for keyword lists and is easily editable.
**Alternatives considered**:
- Dedicated `etsy.category.keyword` model (rejected: over-engineering per constitution VII)
- Hardcoded Python dict (rejected: harder to maintain than JSON file)

**Category list** (derived from analyzing 2,294 unique product names in the Excel):
- Ring Dishes (910+ products matching "ring dish")
- Temporary Tattoos (500+ matching "tattoo")
- Mugs & Drinkware (200+ matching "mug", "cup", "tumbler")
- Jewelry (150+ matching "necklace", "bracelet", "earring")
- Home Decor (100+ matching "pillow", "candle", "ornament")
- Personalized Gifts (broad catch-all for "personalized", "custom")
- Stickers, Clothing, Pet Products (smaller categories)
- Uncategorized (fallback)

## R3: Multi-Currency Price Parsing

**Decision**: Extend existing parser to return `(amount, currency_code)` tuple
**Rationale**: Minimal change. 97.6% of orders are EUR, 2.4% are USD. No GBP detected in current data but parser should handle it for future-proofing.
**Alternatives considered**:
- Convert all to EUR at import (rejected: loses original transaction currency)
- Separate parser per currency (rejected: duplicated code)

**Currency detection logic**:
1. Strip whitespace
2. Check prefix: `$` -> USD, `\u00a3` -> GBP, `\u20ac` -> EUR
3. Check text prefix: `EUR` -> EUR, `USD` -> USD, `GBP` -> GBP
4. Default: EUR (dominant currency in the data)
5. Extract numeric value after symbol removal

## R4: Savepoint-Based Batching

**Decision**: `self.env.cr.savepoint()` context manager per 100-order batch
**Rationale**: Odoo ORM supports nested savepoints. On failure, only the current batch rolls back. Successfully committed batches persist.
**Alternatives considered**:
- Single transaction (rejected: OOM risk for 17K records)
- Keep `cr.commit()` with better error handling (rejected: violates Odoo transaction model)

**Implementation pattern**:
```python
for batch in batched(orders, 100):
    try:
        with self.env.cr.savepoint():
            for order_data in batch:
                self._create_order(order_data)
    except Exception as e:
        failed_ids.extend([o['order_id'] for o in batch])
        _logger.error("Batch failed: %s", e)
```

## R5: Historical Order Confirmation + Delivery Completion

**Decision**: `action_confirm()` + `picking.button_validate()` in batches
**Rationale**: Standard Odoo workflow creates proper stock moves and audit trail. Confirmed per clarification: historical orders go to "done" state since already shipped.
**Alternatives considered**:
- Direct SQL state update (rejected: bypasses ORM, no stock moves)
- `queue_job` background processing (rejected: not in CE)

**Key consideration**: `button_validate()` may trigger immediate transfer wizard for products without tracking. Need to handle this by setting the `immediate_transfer` context or using `_action_done()` directly on the picking.

## R6: Header-Based Column Mapping

**Decision**: Build header dict from first row, normalize headers
**Rationale**: Robust against reordering. Required headers fail fast with clear error.
**Required headers**: TRANSACTION_ID, ORDER_ID, PRODUCT_NAME, PRICE, QUANTITY
**Optional headers**: All 29 others (default to empty string or 0.0)

## R7: Shop-Level Record Rules

**Decision**: M2M `etsy_shop_ids` on `res.users`, record rules on `sale.order` + `etsy.email.log`
**Rationale**: Standard Odoo record rule pattern. Scales to 19+ shops.
**Scope**: sale.order and etsy.email.log only (per clarification). Products and partners remain shared.
