# Quickstart: Etsy Config Fixes

**Branch**: `002-etsy-config-fixes` | **Date**: 2026-04-04

## Prerequisites

1. Docker containers running: `docker compose up -d`
2. Module `etsy_integration` installed on `namco_odoo19` database
3. Excel file available: `Esty main 2 - 15h VN 06 08 2025.xlsx`

## Quick Verification Steps

### 1. Update module after code changes
```bash
docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init
```

### 2. Verify data files loaded
```bash
docker exec namco_odoo19 psql -U odoo -d namco_odoo19 -c "
  SELECT 'fiscal_pos' as type, name FROM account_fiscal_position WHERE name LIKE 'Etsy%'
  UNION ALL
  SELECT 'tax', name FROM account_tax WHERE name LIKE 'Etsy%'
  UNION ALL
  SELECT 'payment_term', name FROM account_payment_term WHERE name LIKE 'Etsy%'
  UNION ALL
  SELECT 'team', name FROM crm_team WHERE name = 'Etsy'
  UNION ALL
  SELECT 'pricelist', name FROM product_pricelist WHERE name LIKE 'Etsy%'
  UNION ALL
  SELECT 'category', name FROM product_category WHERE name LIKE 'Etsy%' OR parent_id IN (SELECT id FROM product_category WHERE name = 'Etsy Products');
"
```

### 3. Run data migration wizard
- Navigate to Etsy > Data Migration in Odoo UI
- Upload the Excel file (for USD price fixing)
- Check all fix options
- Click "Run Migration"
- Verify summary counts

### 4. Verify financial data
```bash
docker exec namco_odoo19 psql -U odoo -d namco_odoo19 -c "
  SELECT
    COUNT(*) as total_orders,
    SUM(amount_total) as total_revenue,
    COUNT(CASE WHEN state = 'done' THEN 1 END) as done_orders,
    COUNT(CASE WHEN state = 'draft' THEN 1 END) as draft_orders
  FROM sale_order WHERE is_etsy_order = true;
"
```

### 5. Verify product configuration
```bash
docker exec namco_odoo19 psql -U odoo -d namco_odoo19 -c "
  SELECT pc.name as category, COUNT(*) as product_count
  FROM product_template pt
  JOIN product_category pc ON pt.categ_id = pc.id
  WHERE pt.is_etsy_product = true
  GROUP BY pc.name
  ORDER BY product_count DESC;
"
```

### 6. Run tests
```bash
docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init
```

### 7. Lint check
```bash
ruff check custom_addons/etsy_integration/
```

## Test Scenarios

### Scenario 1: Multi-currency import
1. Create a small Excel with 3 rows: 1 EUR, 1 USD, 1 mixed
2. Import via wizard
3. Verify each order has correct currency_id and price_unit

### Scenario 2: Migration wizard idempotency
1. Run migration wizard once
2. Note all counts
3. Run migration wizard again
4. Verify counts show 0 changes (all already fixed)

### Scenario 3: Header reordering
1. Copy Excel, swap PRICE and QUANTITY columns
2. Import via wizard
3. Verify prices and quantities are correct (not swapped)

### Scenario 4: Shop isolation
1. Create user "test_viktor", assign shop "Viktor"
2. Log in as test_viktor
3. Verify only Viktor's orders are visible
