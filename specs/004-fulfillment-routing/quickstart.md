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
3. Fill in: Name = "Manual Partner", Priority = "Secondary", Sync Method = "Manual"
4. Save and verify the record is created
5. Create Gearment partner: Name = "Gearment", Priority = "Primary", Sync Method = "API"
6. Set Adapter Type = "Gearment", Auth Method = "Header Keys"
7. Enter Client Key and Client Secret from Gearment dashboard
8. Set API Endpoint = `https://apiv2.gearment.com/integration-handler`, API Version = "v3"
9. Set Rate Limit: 100 requests / 10 seconds
10. Click "Test Connection" and verify it succeeds using header-key auth
11. Click "Register Webhooks" and verify webhook subscriptions are created at Gearment

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

### 5. Partner API Sync (Gearment)

1. Route an order to "Gearment"
2. Click "Sync Now" button on the sale order form
3. Verify: system creates a draft order at Gearment and retrieves a price quote
4. Verify: gearment_price_quote is populated on the sale order
5. Review the price, then click "Approve & Confirm" to confirm the order at Gearment
6. Verify: partner.sync.log record created with sync_type = "push", sync_status = "success"
7. Verify: gearment_order_id is stored on the sale order

### 5b. Shipping Carrier Configuration

1. Navigate to: Etsy Integration > Configuration > Shipping Carriers
2. Verify 3 pre-configured carriers exist: USPS, UniUni, YunExpress
3. Open USPS: Verify tracking pattern = `^\d{20,22}$`, no prefix
4. Open UniUni: Verify tracking prefix = "UU"
5. Open YunExpress: Verify tracking prefix = "YT"
6. Optionally: Create a test carrier "FedEx" with prefix "FEDEX"

### 5c. Tracking Import from Excel

1. Navigate to: Etsy Integration > Operations > Import Tracking
2. Click "Upload Excel" and select a GKE Logistics file (19 or 20 columns)
3. Verify: system parses the file and shows a preview (N rows found, N orders matched)
4. Click "Import" to write tracking numbers to matched orders
5. Open a matched sale order and verify:
   - tracking_number is populated
   - shipping_carrier is auto-detected (e.g., "UniUni" for "UU..." tracking)
   - label_url and qrcode_url are stored
   - fulfillment_status transitioned to "Da gui" (Shipped) if applicable
6. Check the import log: Etsy Integration > Operations > Tracking Import Logs
7. Verify: summary shows matched/unmatched counts and carrier detection breakdown

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
