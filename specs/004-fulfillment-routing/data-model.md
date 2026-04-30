# Data Model: Fulfillment Routing, Production Assignment, and Partner Integration

## New Model: fulfillment.partner

External fulfillment partner configuration.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | Char | Yes | Partner company name |
| active | Boolean | Yes | Default: True. Inactive partners hidden from routing dropdown |
| partner_priority | Selection | Yes | primary / secondary (default: secondary). At most one partner can be primary |
| contact_person | Char | No | Primary contact name |
| email | Char | No | Contact email |
| phone | Char | No | Contact phone |
| supported_formats | Char | No | Comma-separated: png,pdf,ai,jpg |
| sync_method | Selection | Yes | manual / api (default: manual) |
| auth_method | Selection | Yes | bearer / header_keys (default: bearer). Determines authentication approach |
| adapter_type | Selection | Yes | generic / gearment (default: generic). Determines which sync adapter class to use |
| api_endpoint | Char | No | REST API URL (required when sync_method = 'api') |
| api_version | Char | No | API version string (e.g., "v3") |
| api_key | Char | No | Bearer token (used when auth_method = 'bearer'). Stored encrypted |
| api_client_key | Char | No | Client key header (used when auth_method = 'header_keys', e.g., X-Gearment-Client-Key). Stored encrypted |
| api_client_secret | Char | No | Client secret header (used when auth_method = 'header_keys', e.g., X-Gearment-Client-Secret). Stored encrypted |
| webhook_secret | Char | No | HMAC secret for validating partner callbacks |
| webhook_endpoint | Char | No | Partner's webhook management endpoint (e.g., /api/v3/webhooks) |
| webhook_ids_json | Text | No | JSON list of registered webhook IDs at the partner |
| rate_limit_requests | Integer | No | Max requests per rate window (e.g., 100) |
| rate_limit_window | Integer | No | Rate limit window in seconds (e.g., 10) |
| platform_code | Char | No | Platform identifier sent to partner (e.g., "etsy") |
| store_id | Char | No | Store ID sent to partner API |
| notes | Text | No | Internal notes about this partner |
| order_count | Integer | No | Computed: count of orders routed to this partner |

**Inherits**: mail.thread (for chatter audit trail)

**Constraints**:
- api_endpoint required when sync_method = 'api'
- api_key required when auth_method = 'bearer' and sync_method = 'api'
- api_client_key + api_client_secret required when auth_method = 'header_keys' and sync_method = 'api'
- At most one partner can have partner_priority = 'primary' (SQL constraint or Python constraint)

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

## New Model: shipping.carrier

Shipping carrier configuration for tracking number auto-detection.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | Char | Yes | Carrier display name (e.g., "USPS", "UniUni", "YunExpress") |
| code | Char | Yes | Unique short code for programmatic use (e.g., "usps", "uniuni", "yunexpress") |
| active | Boolean | Yes | Default: True |
| tracking_prefix | Char | No | Simple prefix match (e.g., "UU" for UniUni). Checked before regex |
| tracking_pattern | Char | No | Regex pattern for tracking numbers (e.g., `^\d{20,22}$` for USPS) |

**Inherits**: mail.thread (for chatter audit trail)

**Constraints**:
- code must be unique
- At least one of tracking_prefix or tracking_pattern should be set

**Pre-seeded Data** (via `data/shipping_carrier_data.xml`):
- USPS: code="usps", tracking_pattern=`^\d{20,22}$`
- UniUni: code="uniuni", tracking_prefix="UU"
- YunExpress: code="yunexpress", tracking_prefix="YT"

**Security**:
- Full CRUD: group_sale_manager
- Read only: group_sale_salesman

---

## New Model: logistics.partner

External logistics company that provides tracking data via Google Drive Excel files.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | Char | Yes | Logistics partner name (e.g., "GKE Logistics") |
| active | Boolean | Yes | Default: True |
| gdrive_folder_id | Char | No | Google Drive folder ID containing tracking files |
| gdrive_sync_enabled | Boolean | No | Default: False. Whether to auto-sync from Google Drive |
| gdrive_last_sync | Datetime | No | Timestamp of last successful Google Drive sync |
| notes | Text | No | Internal notes |

**Inherits**: mail.thread (for chatter audit trail)

**Configuration**:
- Google Drive service account credentials stored in `ir.config_parameter` (key: `etsy_integration.gdrive_service_account_path`)

**Security**:
- Full CRUD: group_sale_manager
- Read only: group_sale_salesman

---

## New Model: tracking.import.log

Audit log for each tracking Excel file import session.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | Char | Yes | Auto-generated reference (e.g., "TRACK-IMP-00001") |
| import_date | Datetime | Yes | When the import ran |
| source | Selection | Yes | manual_upload / google_drive |
| source_filename | Char | No | Original filename |
| logistics_partner_id | Many2one(logistics.partner) | No | If imported from a logistics partner's Drive folder |
| total_rows | Integer | Yes | Total data rows in the file |
| matched_count | Integer | Yes | Orders successfully matched |
| unmatched_count | Integer | Yes | ORDER NUMBERs not found |
| tracking_written | Integer | Yes | Tracking numbers actually written (new or updated) |
| carrier_summary_json | Text | No | JSON summary of carrier detection counts, e.g., {"usps": 45, "uniuni": 12} |
| error_details | Text | No | Error/warning details |
| imported_by | Many2one(res.users) | Yes | User who triggered the import |
| state | Selection | Yes | draft / done / error (default: draft) |
| line_ids | One2many(tracking.import.line) | - | Per-row import details |

**Inherits**: mail.thread (for chatter audit trail)

**Security**:
- Full CRUD: group_sale_manager
- Read only: group_sale_salesman

---

## New Model: tracking.import.line

Per-row detail for each tracking import (child of tracking.import.log).

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| import_log_id | Many2one(tracking.import.log) | Yes | Parent import log (ondelete='cascade') |
| row_number | Integer | Yes | Excel row number (for debugging) |
| order_number | Char | No | ORDER NUMBER from Excel |
| tracking_number | Char | No | TRACKING NUMBER from Excel |
| sale_order_id | Many2one(sale.order) | No | Matched sale order (ondelete='set null') |
| carrier_id | Many2one(shipping.carrier) | No | Detected or explicit carrier |
| match_status | Selection | Yes | matched / unmatched / duplicate / replacement |
| is_replacement | Boolean | No | Default: False. True if ORDER NUMBER had "-replace" suffix |
| consignee_name | Char | No | CONSIGNEE NAME from Excel (for verification) |
| country | Char | No | COUNTRY from Excel |
| gke_cost_vnd | Float | No | COST column from Excel (VND) |
| label_url | Char | No | Label PDF URL from Excel |
| qrcode_url | Char | No | QR code URL from Excel |
| notes | Text | No | Any warnings or issues for this row |

**Security**:
- Full CRUD: group_sale_manager
- Read only: group_sale_salesman

---

## Extended Model: sale.order

New fields for fulfillment routing, production tracking, tracking import, and returns.

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

### Gearment-Specific Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| gearment_order_id | Char | No | | Gearment's order ID returned on draft creation |
| gearment_price_quote | Float | No | | Price quoted by Gearment for this order (for manual approval) |

### Tracking Import Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| label_url | Char | No | | Shipping label PDF URL from logistics partner import |
| qrcode_url | Char | No | | QR code URL from logistics partner import |
| gke_shipping_cost_vnd | Float | No | | Shipping cost in VND from GKE Excel (reference only, not reconciled) |
| tracking_import_date | Datetime | No | | When tracking was imported from Excel |
| is_replacement_order | Boolean | No | False | True if imported with "-replace" suffix |
| original_order_id | Many2one(sale.order) | No | | Link to original order if this is a replacement |

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

### Auto-Transition: Tracking Import -> Fulfillment Status

When `tracking_number` is written via Excel import and was previously empty:
- Set `fulfillment_status` = 'da_gui' (Shipped) if currently in 'dang_san_xuat' or 'da_san_xuat' or 'da_dong_goi'
- Set `shipping_date` = import date (if not already set)
- Auto-detect carrier from tracking pattern and write `shipping_carrier`

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
| shipping.carrier | group_sale_manager | 1 | 1 | 1 | 1 |
| shipping.carrier | sale_team.group_sale_salesman | 1 | 0 | 0 | 0 |
| logistics.partner | group_sale_manager | 1 | 1 | 1 | 1 |
| logistics.partner | sale_team.group_sale_salesman | 1 | 0 | 0 | 0 |
| tracking.import.log | group_sale_manager | 1 | 1 | 1 | 1 |
| tracking.import.log | sale_team.group_sale_salesman | 1 | 0 | 0 | 0 |
| tracking.import.line | group_sale_manager | 1 | 1 | 1 | 1 |
| tracking.import.line | sale_team.group_sale_salesman | 1 | 0 | 0 | 0 |

---

## Entity Relationship Summary

```
sale.order
  |-- fulfillment_partner_id --> fulfillment.partner
  |-- routed_by --> res.users
  |-- original_order_id --> sale.order (self-ref, for replacements)
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
  |    |-- partner_priority (primary/secondary)
  |    |-- adapter_type (generic/gearment)
  |    |-- auth_method (bearer/header_keys)
  |
  +-- shipping.carrier
  |    |-- tracking_prefix, tracking_pattern
  |    |-- (standalone config, pre-seeded: USPS, UniUni, YunExpress)
  |
  +-- logistics.partner
  |    |-- gdrive_folder_id, gdrive_sync_enabled
  |    |-- (standalone config for Google Drive sources)
  |
  +-- tracking.import.log
  |    |-- logistics_partner_id --> logistics.partner
  |    |-- imported_by --> res.users
  |    |-- line_ids <-- tracking.import.line (One2many)
  |
  +-- tracking.import.line
       |-- import_log_id --> tracking.import.log
       |-- sale_order_id --> sale.order
       |-- carrier_id --> shipping.carrier

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

---

## Gearment-Specific Webhook Endpoint

```
POST /fulfillment/gearment/webhook
Headers:
  Content-Type: application/json
  X-Gearment-Signature: {hmac_signature}
Body: {
  "event": "tracking.updated",
  "data": {
    "reference_id": "SO12345",
    "order_id": "GEAR-789",
    "tracking_number": "9214490407314855743961",
    "carrier": "USPS",
    "status": "shipped"
  }
}
Response: {"status": "ok"} or {"status": "error", "message": "..."}
```

**Supported Events**:
- `order.completed` -- Partner finished production
- `order.cancelled` -- Partner cancelled the order
- `tracking.updated` -- Tracking number available / shipment status changed

**Validation**:
1. Verify Gearment-specific signature header
2. Map `reference_id` to sale.order.name
3. Map `event` type to appropriate handler
4. Create partner.sync.log record (type=callback)
5. Update order fields based on event type

---

## NEW (P0-18b1 2026-04-30): `gearment.api.log`

Per-call audit log for Gearment API interactions. Mirrors `etsy.api.log` (Spec 005 P0-17) — proven retention + ACL pattern.

| Field | Type | Required | Notes |
|---|---|---|---|
| `sale_order_id` | Many2one(`sale.order`, `ondelete='set null'`) | No | Null for catalog/system probes; set for order-specific operations |
| `endpoint` | Char | Yes | HTTP method + path, e.g. `POST /api/v3/orders` |
| `http_status` | Integer | No | Response code; null on connection failure |
| `request_started_at` | Datetime | Yes | Indexed for range queries |
| `duration_ms` | Integer | No | Wall-clock latency |
| `request_payload_summary` | Text | No | JSON body sent (Auth headers scrubbed; PII scrubbed: no buyer name, no order ref) |
| `response_summary` | Text | No | JSON response truncated to 4 KB |
| `error_message` | Text | No | Exception details on failure |
| `rate_limit_remaining` | Integer | No | From `X-RateLimit-Remaining` if Gearment provides one |
| `source` | Selection | Yes | `probe` / `draft` / `quote` / `confirm` / `callback` / `health_check` |

**Inherits**: none (deliberate — high write volume; mail.thread would balloon storage)

**Indexes** (in `init()` raw SQL, drift-template per memory `project_sql_constraints_drift`):
- `(sale_order_id, request_started_at DESC)` — recent activity per order
- `(source, request_started_at DESC)` — deferred to P0-13 perf slice
- `(http_status)` — deferred

**Retention**:
- Cron `_cron_cleanup_old_logs` daily; deletes rows where `request_started_at < now() - <retention>` days
- ICP `multichannel_hub_fulfillment.api_log_retention_days` (default 30)

**Security**:
- `group_system` full R/W/C/U
- `group_sale_manager` R only
- No record rules in P0-18b1; per-shop rules deferred to P4-01

**Audit hygiene**:
- All `request_payload_summary` writes go through a `_scrub_pii(payload_dict) -> dict` helper that drops `buyer_name`, `address_line_1/2`, `email`, `phone`, `notes` (matches P0-17 `_audit_log` pattern in P0-16c)
- `Authorization` header MUST never appear in stored payload — assert in test

