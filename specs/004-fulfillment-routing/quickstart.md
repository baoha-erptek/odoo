# Quickstart: Fulfillment Routing, Production Assignment, and Partner Integration

## Prerequisites

- Docker containers running: `docker compose up -d`
- Etsy Integration module installed with Spec 001 + 002 + 003 functionality
- Design file workflow operational (Spec 003)

## Verification Steps

### 1. Module Update

```bash
docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init
```

Verify: No errors in output, module updates cleanly.

### 2. Partner Configuration

1. Navigate to: Etsy Integration > Configuration > Fulfillment Partners
2. Click "Create"
3. Fill in: Name = "Test Partner", Sync Method = "Manual"
4. Save and verify the record is created
5. Create another: Name = "API Partner", Sync Method = "API", API Endpoint = "https://httpbin.org/post", API Key = "test-key"
6. Click "Test Connection" and verify it succeeds

### 3. Fulfillment Route Assignment

1. Open any sale order with approved design files
2. In the "Fulfillment" tab, set Fulfillment Route = "Partner"
3. Select "Test Partner" from the Partner dropdown
4. Save
5. Verify: fulfillment_status automatically changed to "Dang san xuat"
6. Verify: routed_by and routed_date are populated
7. Open the operational dashboard and filter by Fulfillment Route = "Partner"
8. Verify: the order appears in filtered results

### 4. Internal Production Queue

1. Open another sale order with approved design files
2. Set Fulfillment Route = "Internal"
3. Save
4. Navigate to: Etsy Integration > Production > Internal Queue
5. Verify: the order appears with production_stage = "Xep hang" (Queued)
6. Switch to Kanban view
7. Drag the order card from "Xep hang" to "Dang lam" (In Progress)
8. Verify: production_stage updated
9. Move to "Hoan thanh" (Completed)
10. Verify: fulfillment_status automatically changed to "Da san xuat"

### 5. Partner API Sync (if API partner configured)

1. Route an order to "API Partner"
2. Click "Sync Now" button on the sale order form
3. Verify: partner.sync.log record created with sync_type = "push"
4. Check sync_status (should be "success" or "failed" depending on endpoint)

### 6. Returns Workflow

1. Open a shipped order (fulfillment_status = 'da_gui')
2. Click "Initiate Return" button
3. Select reason: "Loi san pham" (Defective)
4. Select action: "Hoan tien" (Refund)
5. Add notes and confirm
6. Verify: order.return record created
7. Verify: credit note created and linked
8. Open dashboard, filter by "Returned orders"
9. Verify: the order appears

### 7. Run Tests

```bash
docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init
```

Verify: All tests pass with no errors.
