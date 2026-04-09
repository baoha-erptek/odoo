# Data Model: Fulfillment Routing, Production Assignment, and Partner Integration

## New Model: fulfillment.partner

External fulfillment partner configuration.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | Char | Yes | Partner company name |
| active | Boolean | Yes | Default: True. Inactive partners hidden from routing dropdown |
| contact_person | Char | No | Primary contact name |
| email | Char | No | Contact email |
| phone | Char | No | Contact phone |
| supported_formats | Char | No | Comma-separated: png,pdf,ai,jpg |
| sync_method | Selection | Yes | manual / api (default: manual) |
| api_endpoint | Char | No | REST API URL (required when sync_method = 'api') |
| api_key | Char | No | API authentication key (stored encrypted) |
| webhook_secret | Char | No | HMAC secret for validating partner callbacks |
| notes | Text | No | Internal notes about this partner |
| order_count | Integer | No | Computed: count of orders routed to this partner |

**Inherits**: mail.thread (for chatter audit trail)

**Constraints**:
- api_endpoint required when sync_method = 'api'
- api_key required when sync_method = 'api'

**Security**:
- Full CRUD: group_sale_manager
- Read only: group_sale_salesman, group_production_team

---

## New Model: partner.sync.log

Audit log for each API sync attempt (push or callback).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| sale_order_id | Many2one(sale.order) | Yes | Order being synced (ondelete='cascade') |
| partner_id | Many2one(fulfillment.partner) | Yes | Target partner (ondelete='restrict') |
| sync_type | Selection | Yes | push / callback |
| sync_status | Selection | Yes | pending / success / failed / escalated |
| partner_ref | Char | No | Reference returned by partner API |
| request_payload | Text | No | JSON payload sent (for debugging) |
| response_payload | Text | No | JSON response received |
| error_message | Text | No | Error details on failure |
| retry_count | Integer | Yes | Default: 0. Max 3 retries |
| next_retry_at | Datetime | No | Scheduled time for next retry |
| tracking_number | Char | No | Tracking number from callback |
| carrier | Char | No | Carrier name from callback |

**Indexes**: sale_order_id, partner_id, sync_status

**Security**:
- Full CRUD: group_sale_manager
- Read only: group_sale_salesman

---

## New Model: order.return

Customer return/refund request on a shipped order.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| sale_order_id | Many2one(sale.order) | Yes | Original order (ondelete='restrict') |
| return_reason | Selection | Yes | loi_san_pham / sai_san_pham / khach_doi_y / khac |
| return_action | Selection | Yes | hoan_tien / gui_lai / giam_gia |
| return_notes | Text | No | Additional details from customer/operator |
| resolution_status | Selection | Yes | moi / dang_xu_ly / hoan_thanh (default: moi) |
| credit_note_id | Many2one(account.move) | No | Linked credit note (for refund actions) |
| replacement_order_id | Many2one(sale.order) | No | Linked replacement order (for replacement actions) |
| resolved_by | Many2one(res.users) | No | User who resolved the return |
| resolved_date | Datetime | No | Timestamp of resolution |

**Inherits**: mail.thread (for chatter audit trail)

**Constraints**:
- return_notes required when return_reason = 'khac' (Other)
- credit_note_id auto-set when return_action = 'hoan_tien' and confirmed
- replacement_order_id auto-set when return_action = 'gui_lai' and confirmed

**Security**:
- Full CRUD: group_sale_manager
- Read + Create: group_sale_salesman

---

## Extended Model: sale.order

New fields for fulfillment routing, production tracking, and returns.

### Fulfillment Routing Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| fulfillment_route | Selection | No | | internal / partner |
| fulfillment_partner_id | Many2one(fulfillment.partner) | No | | Set when route = 'partner' |
| routed_by | Many2one(res.users) | No | | User who made the routing decision |
| routed_date | Datetime | No | | When the routing decision was made |

### Internal Production Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| production_stage | Selection | No | | queued / in_progress / qc_check / completed |
| production_blocked | Boolean | No | False | True when blocked by material shortage |
| production_block_reason | Text | No | | Reason for production block |

### Partner Sync Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| partner_sync_status | Selection | No | | pending / synced / failed / escalated |
| partner_sync_date | Datetime | No | | Last successful sync timestamp |
| partner_ref | Char | No | | Reference from partner system |

### Computed Fields

| Field | Type | Stored | Notes |
|-------|------|--------|-------|
| sync_log_ids | One2many(partner.sync.log) | - | Reverse relation |
| sync_log_count | Integer | No | Count of sync attempts |
| return_ids | One2many(order.return) | - | Reverse relation |
| return_count | Integer | No | Count of returns |
| has_active_return | Boolean | No | True if any return is moi/dang_xu_ly |

**Indexes**: fulfillment_route, fulfillment_partner_id, production_stage, partner_sync_status

---

## Automation Rules

### Auto-Transition: Route Assignment -> Fulfillment Status

When `fulfillment_route` is set (and design files are all approved):
- Set `fulfillment_status` = 'dang_san_xuat' (In Production)
- If route = 'internal': Set `production_stage` = 'queued'
- If route = 'partner': Set `partner_sync_status` = 'pending'

### Auto-Transition: Production Completed -> Fulfillment Status

When `production_stage` changes to 'completed':
- Set `fulfillment_status` = 'da_san_xuat' (Produced)

### Auto-Transition: Partner Callback with Tracking -> Fulfillment Status

When partner callback provides tracking_number:
- Set `tracking_number` on sale.order (Spec 003 field)
- Set `shipping_carrier` on sale.order (Spec 003 field)
- Set `fulfillment_status` = 'da_gui' (Shipped)

---

## Security: Updated ACLs

### ir.model.access.csv additions

| Model | Group | Read | Write | Create | Unlink |
|-------|-------|------|-------|--------|--------|
| fulfillment.partner | group_sale_manager | 1 | 1 | 1 | 1 |
| fulfillment.partner | sale_team.group_sale_salesman | 1 | 0 | 0 | 0 |
| fulfillment.partner | etsy_integration.group_production_team | 1 | 0 | 0 | 0 |
| partner.sync.log | group_sale_manager | 1 | 1 | 1 | 1 |
| partner.sync.log | sale_team.group_sale_salesman | 1 | 0 | 0 | 0 |
| order.return | group_sale_manager | 1 | 1 | 1 | 1 |
| order.return | sale_team.group_sale_salesman | 1 | 0 | 1 | 0 |

---

## Entity Relationship Summary

```
sale.order
  |-- fulfillment_partner_id --> fulfillment.partner
  |-- routed_by --> res.users
  |-- sync_log_ids <-- partner.sync.log (One2many)
  |-- return_ids <-- order.return (One2many)
  |-- design_file_ids <-- order.design.file (Spec 003)
  |-- pic_user_id --> res.users (Spec 003)
  |-- etsy_shop_id --> etsy.shop (Spec 001)
  |
  +-- order.return
  |    |-- credit_note_id --> account.move
  |    |-- replacement_order_id --> sale.order
  |    |-- resolved_by --> res.users
  |
  +-- partner.sync.log
  |    |-- partner_id --> fulfillment.partner
  |
  +-- fulfillment.partner
       |-- (standalone configuration model)

Spec 003 models (context):
  +-- order.design.file (approval must be complete before routing)
```

---

## Webhook Controller Endpoint

```
POST /fulfillment/partner/callback
Headers:
  Content-Type: application/json
  X-Webhook-Signature: sha256={hmac_signature}
Body: {
  "partner_ref": "P-789",
  "order_ref": "SO12345",
  "status": "shipped",
  "tracking_number": "1Z999AA10123456784",
  "carrier": "UPS"
}
Response: {"status": "ok"} or {"status": "error", "message": "..."}
```

**Validation**:
1. Verify HMAC signature against partner's webhook_secret
2. Look up sale.order by order_ref (name field)
3. Verify order is routed to the partner matching the webhook secret
4. Create partner.sync.log record (type=callback)
5. Update tracking/carrier/fulfillment_status on sale.order
