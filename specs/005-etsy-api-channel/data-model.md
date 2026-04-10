# Data Model: Etsy API v3 Channel Integration

**Feature**: 005-etsy-api-channel | **Date**: 2026-04-10

## Entity Overview

| Entity | Type | Table | Description |
|--------|------|-------|-------------|
| etsy.shop | Extend existing | etsy_shop | Add API credentials, tokens, sync config |
| sale.order | Extend existing | sale_order | Add sync source, tracking push, last modified |
| sale.order.line | Extend existing | sale_order_line | Minor: no new fields needed |
| product.template | Extend existing | product_template | Add listing ID, state, sync metadata |
| res.config.settings | Extend existing | (transient) | Add Etsy API configuration fields |
| etsy.api.log | New model | etsy_api_log | API call audit trail |
| etsy.webhook.event | New model | etsy_webhook_event | Webhook event processing log |
| etsy.carrier.mapping | New model | etsy_carrier_mapping | Carrier name translation |

---

## Extended Models

### etsy.shop (extend)

New fields added to the existing `etsy.shop` model.

| Field | Type | Attributes | Description |
|-------|------|------------|-------------|
| etsy_numeric_shop_id | Char | index=True | Etsy's numeric shop identifier (resolved from API after auth) |
| etsy_api_key | Char | groups='base.group_system' | Application keystring (x-api-key header) |
| etsy_shared_secret | Char | groups='base.group_system' | Application shared secret (webhook HMAC) |
| etsy_access_token | Char | groups='base.group_system' | Current OAuth2 access token |
| etsy_refresh_token | Char | groups='base.group_system' | OAuth2 refresh token (90-day validity) |
| etsy_token_expiry | Datetime | | Access token expiration timestamp |
| etsy_refresh_token_expiry | Datetime | | Refresh token expiration (set 90 days from last refresh) |
| sync_mode | Selection | default='email_only' | Options: email_only, api_only, dual |
| last_receipt_sync | Datetime | | Timestamp of last successful receipt sync |
| last_listing_sync | Datetime | | Timestamp of last listing pull sync |
| api_connection_date | Datetime | | When API was first connected (forward-only sync start) |
| webhook_secret | Char | groups='base.group_system' | Webhook signing secret from Etsy portal |
| api_sync_interval | Integer | default=5 | Minutes between API sync cron runs |

**Constraints**:
- etsy_numeric_shop_id: UNIQUE (if set)

**Methods**:
- `action_start_etsy_oauth()`: Initiate PKCE OAuth2 flow
- `action_test_etsy_connection()`: Verify tokens, display shop info
- `action_register_webhooks()`: Guide admin to Etsy portal for webhook setup
- `_refresh_etsy_token()`: Refresh expired access token using refresh token
- `_get_etsy_client()`: Factory method returning configured EtsyApiClient instance

---

### sale.order (extend)

New fields added to the existing sale.order extension.

| Field | Type | Attributes | Description |
|-------|------|------------|-------------|
| etsy_sync_source | Selection | index=True | Options: email, api, webhook. How the order was ingested. |
| etsy_last_modified | Datetime | | Receipt update_timestamp from Etsy (for incremental sync) |
| etsy_tracking_push_status | Selection | default='none', index=True | Options: none, pending, pushed, failed |
| etsy_tracking_push_date | Datetime | | When tracking was last pushed to Etsy |
| etsy_tracking_push_error | Text | | Error message from last failed push attempt |
| etsy_receipt_status | Char | | Raw receipt status from Etsy API (paid, completed, etc.) |

**Methods**:
- `_cron_fetch_etsy_api_orders()`: Scheduled action -- sync orders via API for all API-enabled shops
- `_cron_push_tracking_to_etsy()`: Scheduled action -- push pending tracking numbers to Etsy
- `action_push_tracking_to_etsy()`: Manual button -- push tracking for a single order
- `action_retry_tracking_push()`: Manual button -- retry failed tracking push

**State Tracking for Tracking Push**:
```
none -> pending (tracking number added)
pending -> pushed (API call success)
pending -> failed (API call error)
failed -> pending (retry triggered)
pushed -> (terminal, no further transitions)
```

---

### product.template (extend)

New fields added to the existing product.template extension.

| Field | Type | Attributes | Description |
|-------|------|------------|-------------|
| etsy_listing_id | Char | index=True, copy=False | Etsy listing identifier for reliable matching |
| etsy_listing_state | Selection | | Options: draft, active, inactive, sold_out, expired |
| etsy_listing_last_sync | Datetime | | When listing data was last synced from Etsy |
| etsy_taxonomy_id | Integer | | Etsy taxonomy category (required for listing push) |
| etsy_who_made | Selection | | Options: i_did, someone_else, collective |
| etsy_when_made | Selection | | Options: made_to_order, 2020_2025, before_2020, etc. |
| is_etsy_listing | Boolean | compute, store=True | Computed: bool(etsy_listing_id) |

**Constraints**:
- etsy_listing_id: UNIQUE per shop (composite with etsy_shop_id if needed)

**Methods**:
- `action_push_to_etsy()`: Manual button -- push product data to Etsy as listing
- `action_pull_from_etsy()`: Manual button -- refresh product data from Etsy listing
- `action_upload_image_to_etsy()`: Manual button -- upload product image to Etsy

---

### res.config.settings (extend)

New fields for Etsy API configuration (transient model, mapped to ir.config_parameter).

| Field | Type | Config Parameter Key | Description |
|-------|------|---------------------|-------------|
| etsy_api_key | Char | etsy_integration.etsy_api_key | Application keystring |
| etsy_api_shared_secret | Char | etsy_integration.etsy_api_shared_secret | Shared secret |
| etsy_api_sync_interval | Integer | etsy_integration.etsy_api_sync_interval | Minutes between syncs (default: 5) |
| etsy_api_log_level | Selection | etsy_integration.etsy_api_log_level | Options: errors_only, all, verbose |
| etsy_api_log_retention_days | Integer | etsy_integration.etsy_api_log_retention_days | Days to retain logs (default: 30) |

**Methods**:
- `action_start_etsy_api_oauth()`: Build PKCE authorization URL and redirect
- `action_test_etsy_api_connection()`: Verify API credentials

---

## New Models

### etsy.api.log

Audit trail for every Etsy API call. Auto-vacuumed after retention period.

| Field | Type | Attributes | Description |
|-------|------|------------|-------------|
| name | Char | compute | Display: "{method} {endpoint} -> {status_code}" |
| etsy_shop_id | Many2one | required=True, ondelete='cascade' | Related shop |
| endpoint | Char | required=True, index=True | API endpoint path |
| http_method | Selection | required=True | Options: GET, POST, PATCH, PUT, DELETE |
| status_code | Integer | index=True | HTTP response status code |
| request_summary | Text | | Truncated request body (first 1000 chars) |
| response_summary | Text | | Truncated response body (first 1000 chars) |
| error_message | Text | | Error details if status >= 400 |
| duration_ms | Integer | | Request duration in milliseconds |
| quota_remaining_second | Integer | | x-remaining-this-second header value |
| quota_remaining_day | Integer | | x-remaining-today header value |
| create_date | Datetime | | Auto-set by Odoo |

**Constraints**: None beyond standard Odoo.

**Cleanup**: `_cron_cleanup_api_logs()` deletes records older than `etsy_api_log_retention_days`.

**Security**: Read-only for sales users, full access for managers.

---

### etsy.webhook.event

Record of each received webhook event with processing status.

| Field | Type | Attributes | Description |
|-------|------|------------|-------------|
| name | Char | compute | Display: "{event_type} - {etsy_receipt_id}" |
| event_type | Char | required=True, index=True | e.g., order.paid, order.shipped |
| etsy_shop_id | Many2one | ondelete='cascade' | Related shop (from payload shop_id) |
| etsy_receipt_id | Char | index=True | Receipt ID from resource_url |
| resource_url | Char | | Full resource URL from payload |
| raw_payload | Text | | Raw JSON payload |
| signature_valid | Boolean | default=False | HMAC signature verification result |
| processing_status | Selection | default='pending', index=True | Options: pending, processed, failed, rejected |
| error_message | Text | | Processing error details |
| sale_order_id | Many2one | ondelete='set null' | Created/updated sale order |
| create_date | Datetime | | Auto-set by Odoo |

**Constraints**: None.

**Idempotency**: Before processing, check if an event with same `event_type` + `etsy_receipt_id` was already processed successfully. If so, skip.

**Security**: Read-only for all users.

---

### etsy.carrier.mapping

Configurable mapping between system carrier names and Etsy-recognized carrier names.

| Field | Type | Attributes | Description |
|-------|------|------------|-------------|
| name | Char | required=True | Display name |
| system_carrier_name | Char | required=True, index=True | Carrier name as used in the system |
| etsy_carrier_name | Char | required=True | Carrier name as recognized by Etsy |
| active | Boolean | default=True | Active toggle |

**Constraints**:
- SQL: UNIQUE(system_carrier_name) -- one mapping per system carrier

**Seed Data** (etsy_carrier_mapping_data.xml):
- USPS -> usps
- FedEx -> fedex
- UPS -> ups
- DHL -> dhl
- DHL Express -> dhl
- UniUni -> other
- YunExpress -> other
- Amazon Logistics -> amazon-shipping-us

**Security**: Full CRUD for managers, read-only for users.

---

## Service Layer (Non-ORM)

### EtsyApiClient

Pure Python HTTP client. No Odoo ORM dependency.

**Constructor**: `(api_key, shared_secret, access_token, refresh_token, token_expiry)`

**Internal State**:
- `_access_token`: Current access token
- `_token_expiry`: Expiry datetime
- `_qps_bucket`: Token bucket for rate limiting (capacity=8, refill=8/sec)
- `_last_quota_day`: Last observed x-remaining-today value

**Contracts**: See research.md R8 for full interface.

### EtsyOrderSyncer

Bridge between EtsyApiClient JSON responses and OrderCreator.

**Constructor**: `(env)` -- requires Odoo environment for ORM access.

**Key Method**: `sync_shop_orders(shop)` -- fetches receipts for a shop, transforms to OrderCreator-compatible format, creates/updates orders.

### EtsyTrackingPusher

Batch tracking push service.

**Constructor**: `(env)` -- requires Odoo environment.

**Key Method**: `push_pending_tracking(shop)` -- finds orders with `etsy_tracking_push_status='pending'`, pushes tracking to Etsy, updates status.

### EtsyListingSyncer

Listing pull/push service.

**Constructor**: `(env)` -- requires Odoo environment.

**Key Methods**:
- `pull_listings(shop)` -- fetch active listings, create/update products
- `push_listing(shop, product)` -- push single product to Etsy
- `upload_image(shop, product)` -- upload product image to Etsy

---

## Scheduled Actions (Cron Jobs)

| Name | Model | Method | Interval | Description |
|------|-------|--------|----------|-------------|
| Etsy: API Order Sync | sale.order | _cron_fetch_etsy_api_orders | 5 min | Sync receipts for all api_only/dual shops |
| Etsy: Push Tracking | sale.order | _cron_push_tracking_to_etsy | 5 min | Push pending tracking for all API-enabled shops |
| Etsy: Listing Sync | product.template | _cron_sync_etsy_listings | 60 min | Pull listing updates for all API-enabled shops |
| Etsy: Cleanup API Logs | etsy.api.log | _cron_cleanup_api_logs | 1 day | Delete logs older than retention period |

---

## Entity Relationship Diagram (text)

```
etsy.shop (extended)
  |-- 1:N --> sale.order (via etsy_shop_id)
  |-- 1:N --> etsy.api.log (via etsy_shop_id)
  |-- 1:N --> etsy.webhook.event (via etsy_shop_id)

sale.order (extended)
  |-- 1:N --> sale.order.line (standard)
  |-- N:1 --> etsy.shop
  |-- 0:1 <-- etsy.webhook.event (via sale_order_id)

product.template (extended)
  |-- etsy_listing_id links to Etsy Listing (external)

etsy.carrier.mapping (standalone)
  |-- Used by EtsyTrackingPusher to translate carrier names
```
