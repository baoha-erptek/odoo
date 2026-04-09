# Quickstart: Operational Dashboard, Design File Workflow, Multi-Channel Foundation

## Prerequisites

- Docker containers running: `docker compose up -d`
- Etsy Integration module installed with existing orders (Spec 001)
- Spec 002 fixes applied (recommended but not blocking)

## Verification Steps

### 1. Module Update

```bash
docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init
```

Verify: No errors in output, module updates cleanly.

### 2. Operational Dashboard

1. Navigate to: Etsy Integration > Dashboard > Operational Dashboard
2. Verify: 21-column list view loads with existing orders
3. Verify: Columns A-F (shipping date, tracking, carrier, label, status, note) are editable inline
4. Verify: Columns G-T (order data) are read-only
5. Try: Edit a fulfillment status to "Cho file" on any order
6. Try: Assign a PIC user to an order
7. Try: Filter by fulfillment status "Cho file"
8. Try: Group by shop
9. Verify: Page loads in <3 seconds with 17,000+ orders

### 3. Design File Upload

1. Open any sale order form
2. Navigate to: "Design Files" tab
3. Click "Add a line" to create a new design file entry
4. Upload a test PNG file (design_file field)
5. Upload a preview image (preview_file field)
6. Verify: File appears with filename, upload date
7. Verify: Preview image displays inline

### 4. Design Approval Workflow

1. Navigate to: Etsy Integration > Design Queue
2. Switch to Kanban view
3. Verify: 3 columns appear: Cho duyet, Duyet, Can chinh lai
4. Find the design file from step 3 (should be in "Cho duyet")
5. Open the record, change approval_status to "Duyet"
6. Verify: approved_by and approval_date are auto-populated
7. Create another design file, set to "Can chinh lai"
8. Verify: rejection_note field is required

### 5. Security: Production Team Group

1. Go to Settings > Users & Companies > Groups
2. Verify: "Production Team" group exists under Etsy Integration
3. Add a test user to the Production Team group
4. Log in as that user
5. Verify: Can view orders and approve/reject design files
6. Verify: Cannot modify sales order amounts or confirm orders
7. Log in as a basic sales user
8. Verify: Can view design files but cannot change approval status

### 6. Sales Channel

1. Open any existing Etsy order
2. Verify: sales_channel field shows "Etsy"
3. Verify: channel_order_ref field shows the Etsy order ID value
4. Open the dashboard, filter by "Sales Channel = Etsy"
5. Verify: All orders appear
6. Group by Sales Channel
7. Verify: "Etsy" group shows correct order count

### 7. Run Tests

```bash
docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init
```

Verify: All tests pass with no errors.
