# Data Model: Operational Dashboard, Design File Workflow, Multi-Channel Foundation

## New Model: order.design.file

Design file attached to a sale order line with production team approval tracking.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | Char | Yes | File description / label |
| sale_order_id | Many2one(sale.order) | Yes | Parent sale order (ondelete='cascade') |
| sale_line_id | Many2one(sale.order.line) | No | Specific order line (ondelete='cascade') |
| design_file | Binary | Yes | The design file content |
| design_filename | Char | Yes | Original filename (for download) |
| preview_file | Binary | No | Preview/thumbnail image |
| preview_filename | Char | No | Preview filename |
| file_type | Selection | Yes | design / preview / label |
| approval_status | Selection | Yes | cho_duyet / duyet / can_chinh_lai (default: cho_duyet) |
| approved_by | Many2one(res.users) | No | User who approved (auto-set on approval) |
| approval_date | Datetime | No | Timestamp of approval (auto-set) |
| rejection_note | Text | No | Required when status = can_chinh_lai |

**Inherits**: mail.thread (for chatter audit trail on approval changes)

**Constraints**:
- rejection_note is required when approval_status = 'can_chinh_lai'
- approved_by and approval_date are auto-set when approval_status = 'duyet'

**Security**:
- Full CRUD: group_production_team, group_sale_manager
- Read only: group_sale_salesman

**Indexes**: sale_order_id, sale_line_id, approval_status

---

## Extended Model: sale.order

New fields for operational dashboard and multi-channel.

### Operational Dashboard Fields (Manual Entry)

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| shipping_date | Date | No | | Column A: Ngay di hang |
| tracking_number | Char | No | | Column B |
| shipping_carrier | Char | No | | Column C: Don vi van chuyen (free text for flexibility) |
| shipping_label_status | Selection | No | | Column D: khong_can / can_get_label / da_get |
| fulfillment_status | Selection | No | moi | Column E: moi / cho_file / dang_san_xuat / da_san_xuat / da_dong_goi / da_gui / huy |
| fulfillment_note | Text | No | | Column F: Note |

### Multi-Channel Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| sales_channel | Selection | No | | etsy / amazon / website / other |
| channel_order_ref | Char | No | | Generic external order reference |

### Management Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| pic_user_id | Many2one(res.users) | No | | PIC: Person In Charge |
| order_priority | Selection | No | normal | normal / high / urgent |

### Computed Fields

| Field | Type | Stored | Notes |
|-------|------|--------|-------|
| design_file_ids | One2many(order.design.file) | - | Reverse relation |
| design_file_count | Integer | No | Count of design files |
| has_pending_designs | Boolean | No | True if any file is cho_duyet |

**Indexes**: fulfillment_status, sales_channel, pic_user_id, order_priority

---

## Extended Model: sale.order.line

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| design_file_ids | One2many(order.design.file) | - | Design files for this line |
| design_status | Selection | No | Computed: cho_duyet / duyet / can_chinh_lai. Reflects least-approved file. |
| product_type_id | Many2one(product.category) | No | Loai san pham (product type classification) |

**design_status computation logic**:
- If any file is `can_chinh_lai` -> line status = `can_chinh_lai`
- Else if any file is `cho_duyet` -> line status = `cho_duyet`
- Else if all files are `duyet` -> line status = `duyet`
- If no files -> no status

---

## Security: New Group

| Group | XML ID | Inherits | Purpose |
|-------|--------|----------|---------|
| Production Team | etsy_integration.group_production_team | base.group_user | Approve/reject design files |

### ACL: ir.model.access.csv

| Model | Group | Read | Write | Create | Unlink |
|-------|-------|------|-------|--------|--------|
| order.design.file | group_production_team | 1 | 1 | 1 | 1 |
| order.design.file | sale_team.group_sale_salesman | 1 | 0 | 1 | 0 |
| order.design.file | sale_team.group_sale_manager | 1 | 1 | 1 | 1 |

---

## Data Migration: Channel Backfill

Post-init migration or wizard to backfill existing orders:

```
UPDATE sale_order
SET sales_channel = 'etsy',
    channel_order_ref = etsy_order_id
WHERE etsy_order_id IS NOT NULL
  AND sales_channel IS NULL;
```

**Idempotent**: Only updates orders where sales_channel is NULL.

---

## Entity Relationship Summary

```
sale.order
  |-- pic_user_id --> res.users
  |-- etsy_shop_id --> etsy.shop (existing)
  |-- design_file_ids <-- order.design.file (One2many)
  |
  +-- sale.order.line
       |-- design_file_ids <-- order.design.file (One2many)
       |-- product_type_id --> product.category
       |
       +-- order.design.file
            |-- approved_by --> res.users
            |-- sale_order_id --> sale.order
            |-- sale_line_id --> sale.order.line
```
