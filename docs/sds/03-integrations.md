# System Design Spec — 03. External Integrations

**Title:** Multichannel Hub Integrations Reference  
**Date:** 2026-07-03  
**Status:** Draft for Owner Review  
**Version:** 1.0  
**Source of Truth:** This document is the canonical external-surface reference for the multichannel hub. All routes, crons, env vars, and API bindings live here. Code paths are verified against `/home/odoo/odoo_dev/other_projects/odoo19_esty/custom_addons/` HEAD.

---

## Table of Contents

1. [Etsy v3 API](#1-etsy-v3-api)
2. [Gearment v3 API](#2-gearment-v3-api)
3. [Gmail Ingestion](#3-gmail-ingestion)
4. [Google Drive Integration](#4-google-drive-integration)
5. [GKE Logistics](#5-gke-logistics)
6. [HTTP Controllers Inventory](#6-http-controllers-inventory)
7. [Cron Jobs Inventory](#7-cron-jobs-inventory)
8. [Environment Variables & System Parameters](#8-environment-variables--system-parameters)

---

## 1. Etsy v3 API

### 1.1 Authentication

**Method:** OAuth 2.0 PKCE (Proof Key for Code Exchange)

**Credential Storage:**
- Client ID, Client Secret, Redirect URIs: `/opt/odoo/secrets/credentials.json`
- Access Token, Refresh Token: Encrypted (Fernet cipher) on `etsy.shop` record via `_set_access_token()` / `_set_refresh_token()` helpers
- Token file schema: JSON with `client_id`, `client_secret`, `redirect_uris` dict (base URL → full callback URL mapping)

**Scope Grant (E1 Approval — 2026-05-12):**

| Scope | Permission | Status | Notes |
|-------|-----------|--------|-------|
| `transactions_r` | Read orders, receipts | GRANTED | Core ingest |
| `transactions_w` | Update order state | GRANTED | Tracking push, fulfillment marking |
| `listings_r` | Read shop listings | GRANTED | Catalog sync (P-LIST-* slices) |
| `listings_w` | Create/update/delete listings | GRANTED | Outbound publish (P-PUB-* slices) |
| `shops_r` | Read shop profile, shipping profiles | GRANTED | Master data cache |
| `shops_w` | Update shipping profiles | GRANTED | CreateShopShippingProfile API (ESTY-201) |
| `email_r` | Read shop email address | GRANTED | Shop contact info verification |
| `conversations_r` | Read buyer messages | **REJECTED** | E1 excluded; P1-MSG-* blocked |

**Required Scopes Set (Hard-Coded Validation):**

```
{'transactions_r', 'transactions_w', 'listings_r', 'listings_w', 'shops_r', 'shops_w', 'email_r'}
```

**Forbidden Scopes (Reject on Callback):**

```
{'conversations_r'}
```

If Etsy returns a forbidden scope, the OAuth callback fails with 400 bad request.

**Re-Authorization Timeline:**
- Original pilot shop (JaHandmadeArt, shop_id=60752333): Authorized before 2026-05-12; lacks `shops_w`
- Post-2026-05-12 shops: All have `shops_w` included
- **Action Required:** Shops needing `shops_w` must re-authorize after 2026-06-13 cutover

### 1.2 API Endpoints Used

**Module:** `etsy_integration`  
**Entrypoint:** `custom_addons/etsy_integration/services/etsy_api_client.py`

| Endpoint | Method | Purpose | Spec Slice | Status |
|----------|--------|---------|-----------|--------|
| `GET /oauth/authorize` | — | OAuth PKCE flow redirect | 005-A | Shipped |
| `GET /oauth/access_tokens` | — | Token exchange | 005-A | Shipped |
| `GET /v3/application/shops/{shop_id}/receipts` | GET | Fetch orders (API ingest) | 005-B | Shipped |
| `GET /v3/application/shops/{shop_id}/receipts/{receipt_id}` | GET | Fetch single order detail | 005-B | Shipped |
| `POST /v3/application/shops/{shop_id}/receipts/{receipt_id}/tracking` | POST | Push tracking + carrier | 003-A | Shipped |
| `GET /v3/application/shops/{shop_id}/listings` | GET | List all shop listings | 008-* | Shipped |
| `GET /v3/application/shops/{shop_id}/listings/{listing_id}` | GET | Listing details + inventory | 008-* | Shipped |
| `GET /v3/application/shops/{shop_id}/listings/{listing_id}/inventory` | GET | Inventory tier breakdown | 008-* | Shipped |
| `PATCH /v3/application/shops/{shop_id}/listings/{listing_id}/inventory` | PATCH | Update inventory quantity | 009-010-* | Planned (Phase 3) |
| `POST /v3/application/shops/{shop_id}/listings` | POST | Create listing (draft) | 011-* | Planned (Phase 3) |
| `PUT /v3/application/shops/{shop_id}/listings/{listing_id}` | PUT | Update listing | 011-* | Planned (Phase 3) |
| `POST /v3/application/shops/{shop_id}/listings/{listing_id}/images` | POST | Upload listing image | 011-* | Planned (Phase 3) |
| `GET /v3/application/shops/{shop_id}/shipping-profiles` | GET | Fetch shipping profiles | 003-B (ESTY-201) | Shipped |
| `POST /v3/application/shops/{shop_id}/shipping-profiles` | POST | Create shipping profile | 003-B (ESTY-201) | Shipped |
| `GET /v3/application/etsy-taxonomy` | GET | Category taxonomy cache | 008-* | Shipped |

### 1.3 Rate Limiting

**Limit:** Unknown (not documented in Etsy v3 OAS; inferred from v2 docs: ~300 req/min per shop)

**Backoff Strategy:** 
- Retry on `429 Too Many Requests` or `503 Service Unavailable` with exponential backoff (2s → 4s → 8s)
- Max 3 retries per request
- Implemented in `etsy_api_client.py` `_retry_request()`

**Cron Timing (Spacing to Avoid Storms):**
- Receipts sync: 5-minute interval
- Listing sync: 5-minute interval
- Tracking push: 5-minute interval
- Email fetch (fallback): 10-minute interval

### 1.4 Error Handling

**Audit Log:** Every request (success or failure) logged to `etsy.api.log` model

| Attribute | Type | Notes |
|-----------|------|-------|
| `endpoint` | Char | API path (e.g., `GET /v3/application/shops/{id}/receipts`) |
| `http_status` | Integer | HTTP response code (200, 401, 403, 429, 500, 503, etc.) |
| `source` | Selection | `cron_sync`, `manual`, etc. |
| `direction` | Selection | `inbound`, `outbound` |
| `request_headers` | JSON | Scrubbed headers (auth/x-api-key redacted) |
| `request_body` | Text | First 4096 chars of request JSON |
| `response_body` | Text | First 4096 chars of response JSON |
| `http_duration_ms` | Integer | Round-trip time |
| `api_error_code` | Char | Etsy-specific error code (e.g., `"1010"` for rate limit) |
| `shop_id` | Integer | Etsy numeric shop ID (FK to etsy.shop) |

**Common Error Codes:**
- `401 Unauthorized` → Token expired or revoked; trigger re-authorization flow
- `403 Forbidden` → Shop lacks scope; re-authorize required
- `429 Too Many Requests` → Rate limit; backoff and retry
- `503 Service Unavailable` → Etsy maintenance; backoff and retry

### 1.5 Sandbox vs. Production

**Configuration:**

| Environment | Base URL | API Key Location | Shop ID | Active |
|-------------|----------|-----------------|---------|--------|
| **Development** | `https://openapi.etsy.com/v3/application` | `secrets/credentials.json` (dev OAuth app) | Test shop (if any) | During development only |
| **Staging** | `https://openapi.etsy.com/v3/application` (prod API, **NOT** sandbox) | `secrets/credentials.json` (staging OAuth app) | JaHandmadeArt (60752333) | Active; pilot cutover |
| **Production** | `https://openapi.etsy.com/v3/application` | `secrets/credentials.json` (prod OAuth app) | All 19 shops | Future (post-Phase 1 E2E) |

**Important:** Etsy does NOT have a sandbox API. All testing against the real API on a real dev shop. Master data (categories, attributes) must be cached to avoid test pollution.

---

## 2. Gearment v3 API

### 2.1 Authentication

**Credentials:**
- API Key: `GEARMENT_API_KEY` (env var, used as HTTP header `x-api-key`)
- API Secret: `GEARMENT_API_SECRET` (env var, used for HMAC signing)
- Base URL: `GEARMENT_API_BASE_URL` (env var, default `https://api.gearment.com`)

**Header Format:**

```
X-Gearment-Client-Key: {GEARMENT_API_KEY}
X-Gearment-Client-Secret: {GEARMENT_API_SECRET}
```

**Secret Usage (Webhook Verification):**

Secrets are used to HMAC-SHA256-sign inbound webhook payloads. See § 2.4 below.

### 2.2 API Endpoints Used

**Module:** `multichannel_hub_fulfillment`  
**Entrypoint:** `custom_addons/multichannel_hub_fulfillment/services/gearment_api_client.py`

| Endpoint | Method | Purpose | Spec Slice | Status |
|----------|--------|---------|-----------|--------|
| `POST /api/v3/orders/draft` | POST | Push SO to Gearment (create quote) | P4-01-B | Shipped |
| `PUT /api/v3/orders/{order_id}/confirm` | PUT | Confirm quote → fulfillment start | P4-01-B | Shipped |
| `POST /api/v3/orders/{order_id}/cancel` | POST | Cancel quote/order | P4-01-C | Shipped |
| `GET /api/v3/orders/{order_id}` | GET | Fetch order status | P4-01-D | Shipped |

**Payload Contract (POST /api/v3/orders/draft):**

```json
{
  "reference": "SO-12345",
  "shipping_address": { ... },
  "line_items": [
    {
      "variant_id": "prod-456",
      "quantity": 2,
      "printing_options": [
        {
          "name": "Color",
          "value": "Red"
        }
      ]
    }
  ],
  "currency": "USD",
  "total_price": 99.99
}
```

### 2.3 Rate Limiting

**Limit:** 100 requests per 10 seconds (hard cap)

**Backoff Strategy:**
- If 429 → wait 10s, retry once
- If still 429 → fail; log and alert operator
- Batch requests (multiple orders) in a single 10s window only if < 100 reqs

**Cron Scheduling (Controlled via Wizard):**
- No automatic cron; quotes are user-triggered via form action button or bulk action
- Manual quote wizard captures order lines and calls Gearment inline (blocking HTTP)

### 2.4 Webhook: HMAC-SHA256 Verification + Replay Defense

**Inbound URL:** `POST /gearment/webhook` (public endpoint, no auth required)

**Signature Scheme:**

```
signing_string = url_path + nonce + timestamp + base64url(body)
X-Connect-Signature = base64url(HMAC-SHA256(GEARMENT_API_SECRET, signing_string))
```

**Required Headers (Validation Order):**

| Header | Example | Validation |
|--------|---------|-----------|
| `X-Connect-Signature` | `mUXXmLe4...` | HMAC-SHA256 digest (urlsafe base64) |
| `X-Connect-Timestamp` | `1777735761` | Unix epoch seconds; must be within ±5min of server time |
| `X-Connect-Nonce` | `abc-123-def` | Unique per request; deduplicated within 10-min window |
| `X-Connect-Client-Key` | `gearment_key_123` | Must match `GEARMENT_API_KEY` env var |

**Verification Flow (Controller):**

1. Read raw request body (bytes)
2. Extract headers; validate all 4 required headers present
3. Extract `X-Connect-Timestamp`, validate within window (±5 min)
4. Query `gearment.api.log` for prior nonce within 10-min window; if found → reject (401 nonce_replay)
5. Compute expected signature: `base64url(HMAC-SHA256(GEARMENT_API_SECRET, signing_string))`
6. Compare with `X-Connect-Signature` via `hmac.compare_digest()` (constant-time)
7. On success → 200 `{"status":"ok"}`, audit row with `signature_verified=True`
8. On failure → 401 `{"error":"unauthorized"}`, audit row with `signature_verified=False` + `verify_failure_reason`

**Replay Protection (P0-18b2c):**

- Dedup window: 10 minutes (600 seconds)
- Nonce search: Query `gearment.api.log` for `(nonce_value, request_timestamp >= cutoff)`
- DB-level backup: Partial unique index on `(nonce_value, request_timestamp)` with condition `signature_verified=True`
- If concurrent request inserts same (nonce, ts) pair → `psycopg2.IntegrityError` caught, return 401 nonce_replay_db

**Body Truncation (Security):**

- On signature verification success → store full body (up to 4096 chars)
- On verification failure → truncate body to 256 chars (defense against logging hostile payloads)

### 2.5 Webhook Topics Handled

**Topic Key:** `body['type']` (fallback: `body['event']` or `body['topic']`)

| Topic | Handler | Purpose | Status |
|-------|---------|---------|--------|
| `quote.created` | `GearmentWebhookDispatcher.on_quote_created()` | Quote ready for review | Shipped |
| `order.confirmed` | `GearmentWebhookDispatcher.on_order_confirmed()` | Fulfillment started | Shipped |
| `order.tracking_updated` | `GearmentWebhookDispatcher.on_tracking_updated()` | Tracking info available | Shipped |
| `order.shipped` | `GearmentWebhookDispatcher.on_order_shipped()` | Order fulfilled | Shipped |
| `order.cancelled` | `GearmentWebhookDispatcher.on_order_cancelled()` | Order cancelled | Shipped |

**Dispatcher Location:** `custom_addons/multichannel_hub_fulfillment/services/gearment_webhook_dispatcher.py`

### 2.6 Error Handling

**Audit Log:** Every webhook (verified or not) logged to `gearment.api.log`

| Attribute | Notes |
|-----------|-------|
| `endpoint` | `POST /gearment/webhook` |
| `http_status` | 200 (success), 401 (sig fail), 503 (db error, still returns 200) |
| `source` | `inbound_webhook` |
| `direction` | `inbound` |
| `signature_verified` | Boolean; True only if HMAC + replay checks pass |
| `verify_failure_reason` | Reason if verified=False (e.g., `signature_mismatch`, `timestamp_outside_window`, `nonce_replay`) |
| `nonce_value` | From `X-Connect-Nonce` header |
| `request_timestamp` | From `X-Connect-Timestamp` header (stored as int for queries) |
| `business_handled` | Boolean; True if dispatcher routed to a handler |
| `business_summary` | String; outcome (e.g., `'order_not_found'`, `'state_transition_ok'`) |
| `sale_order_id` | FK to `sale.order` if webhook matched a known order |

---

## 3. Gmail Ingestion

### 3.1 Purpose

**Fallback Email Parser:** Reads Etsy order confirmation emails from a Gmail mailbox; parses order data using regex patterns; creates `sale.order` records and `design.file` rows.

**Primary Ingest Method:** API sync (Etsy v3 receipts endpoint, § 1.2)  
**Fallback Role:** When API ingest is unavailable or rate-limited, Gmail cron reads emails (per ADR-008a)

### 3.2 Gmail API Credentials

**Type:** OAuth 2.0 (user-delegated, not service account)

**Configuration Parameters (ir.config_parameter):**

| Key | Type | Purpose | Default |
|-----|------|---------|---------|
| `etsy_integration.gmail_client_id` | Char | OAuth app client ID (GCP project) | — |
| `etsy_integration.gmail_client_secret` | Char | OAuth app client secret | — |
| `etsy_integration.gmail_label` | Char | Gmail label to poll (e.g., `"INBOX"`, `"[Gmail]/All Mail"`) | `"[Gmail]/All Mail"` |
| `etsy_integration.gmail_refresh_token` | Char | Refresh token (persisted after first auth) | — |

**Scopes Required:**

```
https://www.googleapis.com/auth/gmail.modify
```

Allows: Read labels, list messages, read message content, modify labels (mark processed).

### 3.3 Email Polling

**Cron Schedule:**
- Job ID: `ir_cron_fetch_etsy_emails` (record: `etsy_integration.ir_cron_fetch_etsy_emails`)
- Interval: 10 minutes
- Method: `sale.order._cron_fetch_etsy_emails()`
- User: `base.user_root` (system access)

**Flow:**

1. Build Gmail API client using stored refresh token
2. List unread messages in `gmail_label` (e.g., `INBOX`)
3. For each message:
   - Fetch full message body
   - Parse email subject + body via regex patterns (see § 3.4)
   - Extract order ID, buyer, items, totals
   - Create or update `sale.order` + `sale.order.line`
   - Create `design.file` rows for each design attachment (base64 in email)
4. Mark email as read (remove `UNREAD` label)
5. Log summary (# processed, # errors) to `_logger`

### 3.4 Email Parser Patterns

**Service:** `custom_addons/etsy_integration/services/email_parser.py` (ORM-free, pure Python)

**Input Contract:** Raw email HTML/plain text  
**Output Contract:** Structured dict with fields:

```python
{
    'order_id': str,
    'buyer_name': str,
    'buyer_email': str,
    'order_date': datetime,
    'items': [
        {
            'sku': str,
            'quantity': int,
            'price': decimal,
            'design_attachment_base64': str | None,
        }
    ],
    'total': decimal,
    'shipping_address': str,
}
```

**Key Patterns (Regex):**

- Order ID: Etsy pref `Order #(\d{10})` (Etsy uses 10-digit numeric IDs in order emails)
- Buyer: Extract from `From:` header + email body salutation
- Items: Parse table rows in HTML email (product name, SKU, qty, price)
- Designs: Extract attachment filename/encoding from email headers

### 3.5 Error Handling

**Failures:**
- Malformed email (unparseable) → log warning, skip, mark read (prevent re-processing)
- Duplicate order detected → log info, skip duplicate lines, no error
- Design attachment too large (> 10 MB) → log warning, skip attachment, create order without design file
- No matching items found → log error, do not create order (safety guard)

---

## 4. Google Drive Integration

### 4.1 Purpose

- **Design File Upload:** Promote approved design files from Odoo storage to GDrive (ADR-006)
- **Master Data Cache:** Poll GDrive folders for partner/logistics files (Excel, reference sheets)
- **Primary Storage:** Design files in GDrive; links stored in `design.file.gdrive_preview_url`

### 4.2 Service Account Authentication

**Credentials Type:** Google Service Account (JSON key file)

**Env Var:** `GDRIVE_SERVICE_ACCOUNT_JSON`  
**Default Path:** `/app/secrets/gdrive-service-account.json`

**Scopes:**

```
https://www.googleapis.com/auth/drive
```

Allows: Read/write all files on the service account's Shared Drive.

**JSON Schema (from Google Cloud Console):**

```json
{
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "...",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "..."
}
```

### 4.3 Design File Upload Cron

**Cron Schedule:**
- Job ID: `cron_design_file_gdrive_sync` (in `multichannel_hub_core/data/ir_cron_data.xml`)
- Interval: 5 minutes
- Method: `design.file._cron_sync_approved_to_gdrive()`
- User: `base.user_root`

**Killswitch:**
- ICP key: `multichannel_hub.design_gdrive_auto_sync_enabled` (default: `True`)
- ICP key: `multichannel_hub.design_file_default_gdrive_folder_id` (no-op if unset)

**Flow:**

1. Query for approved `design.file` records with `storage_mode='small'` (binary upload needed)
2. For each file:
   - Check if already uploaded (via marker in `design.file.gdrive_file_id`)
   - If not uploaded:
     - Call `GdriveUploader.upload_file(blob, name, folder_id)`
     - Store returned `gdrive_file_id` on record
     - Store returned `gdrive_preview_url` on record
     - Update storage mode to `'gdrive'` (logical transition; data now lives on Drive)
3. Log count of uploaded files

### 4.4 Shop Folder Management

**Method:** `GdriveUploader.ensure_shop_folder(shop)`

- Queries GDrive for existing folder named after `etsy.shop.name`
- If found → return cached `shop.x_gdrive_design_folder_id`
- If not found → create folder, cache folder ID on shop
- Escapes folder name for Drive query safety (single quotes, backslashes)

**Shared Drive Compatibility:**

All Drive API calls include:
```
supportsAllDrives=True
includeItemsFromAllDrives=True
```

Allows access to items on a Shared Drive (not just personal My Drive).

### 4.5 Error Handling

**Failures:**
- Credential file missing → log warning, raise `FileNotFoundError`
- Authentication failure (invalid key, revoked access) → log warning, return error dict with `error` field
- Upload timeout or network error → log warning, retry up to 3 times, then return error dict
- Folder creation race condition (concurrent requests) → ignore; use the found folder

**Soft Failures (Logged, No Alert):**
- Design file larger than 50 MB → log warning, skip upload
- GDrive quota exceeded → log error, defer to next cron run

---

## 5. GKE Logistics

### 5.1 Purpose

Track shipments from Vietnam logistics partner (GKE). Import tracking data (Excel format) into Odoo.

### 5.2 Data Import Format

**Source:** Excel file (.xlsx), manually placed in a monitored folder or GDrive

**Columns (Required):**

| Column | Type | Notes |
|--------|------|-------|
| Order Reference | Char | SO name (e.g., `SO-12345`) or Etsy order ID |
| Carrier | Char | `USPS`, `UniUni`, `YunExpress`, or other (auto-detect) |
| Tracking Number | Char | Carrier-specific tracking ID |
| Status | Char | `pending`, `in_transit`, `delivered`, `returned`, `failed` |
| Estimated Delivery | Date | Expected arrival date |
| Current Location | Char | Free text; parsed for city/country |

### 5.3 Carrier Detection

**Method:** `custom_addons/multichannel_hub_fulfillment/services/carrier_detector.py`

**Mapping (Heuristic):**

| Tracking Number Pattern | Carrier | Notes |
|------------------------|---------|-------|
| 13 digits, all numeric | `USPS` | USPS Tracking barcode format |
| Starts `1Z` + 16 chars | `UPS` | UPS tracking number |
| Starts `9` + 21 digits | `DHL` | DHL international format |
| `tracking.yunexpress.com` URL | `YunExpress` | URL-based routing |
| `tracking.4px.com` | `4PX` | China logistics partner |
| Fallback (unmatched) | `OTHER` | Manual review required |

**Usage:** Model method `stock.picking._detect_carrier_from_tracking(tracking_number)`

### 5.4 Import Cron

**Cron Schedule:**
- Job ID: Not yet cron-driven (manual wizard in Phase 2)
- Method: `stock.picking._cron_import_gke_tracking()` (planned for future)

**Flow (Manual Wizard — Current):**

1. Operator uploads Excel via wizard
2. Wizard parses file; auto-detects carriers
3. For each row:
   - Find `sale.order` by reference number
   - Create or update `stock.picking` with carrier + tracking number
   - Sync tracking to Etsy API (see § 1.2 POST `/receipts/{id}/tracking`)
4. Display summary (# created, # updated, # errors)

---

## 6. HTTP Controllers Inventory

**Module Structure:** Controllers live in `custom_addons/{module}/controllers/{endpoint}.py`

### 6.1 OAuth Controllers (etsy_integration)

#### 6.1.1 `/etsy/api/oauth/authorize`

**File:** `custom_addons/etsy_integration/controllers/etsy_oauth.py`

| Property | Value |
|----------|-------|
| **Route** | `/etsy/api/oauth/authorize` |
| **Methods** | `GET` |
| **Auth** | `user` (login required) |
| **CSRF Protection** | Default (enabled) |
| **Purpose** | Initiate PKCE flow; redirect to Etsy authorize endpoint |
| **Parameters** | `shop_id` (required, query string) |
| **Query Params** | `code_challenge`, `state` (generated), `client_id`, `response_type=code` |
| **Response** | 302 redirect to `https://www.etsy.com/oauth/authorize?...` |
| **Side Effects** | Stores PKCE verifier in `ir.config_parameter` under `etsy.oauth.pending.{state}` |

**Error Handling:**
- Missing `shop_id` → 400 `{"error": "Missing shop_id"}`
- Shop not found → 404 `{"error": "Shop not found"}`
- Credentials file missing → 500 `{"error": "OAuth not configured"}`

#### 6.1.2 `/etsy/api/oauth/callback`

**File:** `custom_addons/etsy_integration/controllers/etsy_oauth.py`

| Property | Value |
|----------|-------|
| **Route** | `/etsy/api/oauth/callback` |
| **Methods** | `GET` |
| **Auth** | `public` (no login required; state validates sender) |
| **CSRF Protection** | Disabled (OAuth callback pattern) |
| **Purpose** | Handle Etsy redirect after user authorization |
| **Parameters** | `code`, `state`, `error` (query string) |
| **Flow** | 1. Validate state → retrieve verifier; 2. Exchange code + verifier → tokens; 3. Scope assertion; 4. Encrypt + store on shop |
| **Response** | 200 with JSON or HTML status; on success: `{"status": "authorized"}`; on error: 400/401 with error message |
| **Side Effects** | Creates/updates `etsy.shop` record; stores encrypted tokens; deletes `ir.config_parameter` verifier row |

**Scope Assertion (Failure Conditions):**
- Missing any required scope → 401 `{"error": "Missing required scope: X"}`
- `conversations_r` present (forbidden) → 401 `{"error": "conversations_r not allowed"}`
- Token refresh or storage fails → 500 `{"error": "Token storage failed"}`

#### 6.1.3 `/etsy/oauth/callback` (Legacy)

**File:** `custom_addons/etsy_integration/controllers/oauth.py` (DEPRECATED, kept for backward compatibility)

| Property | Value |
|----------|-------|
| **Route** | `/etsy/oauth/callback` |
| **Status** | Deprecated; use `/etsy/api/oauth/callback` instead |
| **Note** | May be removed in future release |

### 6.2 Webhook Controller (multichannel_hub_fulfillment)

#### 6.2.1 `/gearment/webhook`

**File:** `custom_addons/multichannel_hub_fulfillment/controllers/gearment_webhook.py`

| Property | Value |
|----------|-------|
| **Route** | `/gearment/webhook` |
| **Methods** | `POST` |
| **Auth** | `public` (HMAC signature validates sender) |
| **CSRF Protection** | Disabled (webhook pattern) |
| **Content-Type** | `application/json` |
| **Purpose** | Receive + verify + dispatch Gearment webhook notifications |
| **Body Size Limit** | 1 MB (pre-checked via `Content-Length` header) |
| **Response on Success (200)** | `{"status": "ok"}` |
| **Response on Failure (401)** | `{"error": "unauthorized"}` (truncated body if verify fails) |
| **Side Effects** | Audit log written to `gearment.api.log`; if verified + handler exists: update `sale.order` state or create records |

**Request Headers (Required):**

```
X-Connect-Signature: <HMAC-SHA256>
X-Connect-Timestamp: <Unix seconds>
X-Connect-Nonce: <UUID or random>
X-Connect-Client-Key: <GEARMENT_API_KEY>
```

**Verification Errors (401 response):**
- `missing_signature_header`, `missing_timestamp_header`, `missing_nonce_header`, `missing_client_key_header`
- `client_key_mismatch` (doesn't match env var)
- `timestamp_invalid` (not a valid integer)
- `timestamp_outside_window` (too old or too far in future)
- `nonce_replay` (duplicate within 10-min window)
- `signature_mismatch` (HMAC doesn't verify)

**Body Truncation:**
- Verified payload: stored full (up to 4096 chars)
- Unverified payload: truncated to 256 chars (security)

---

## 7. Cron Jobs Inventory

**Framework:** All crons use Odoo's `ir.cron` model; jobs are Python code snippets, not external processes.

### 7.1 Etsy Integration Crons

**File:** `custom_addons/etsy_integration/data/ir_cron_data.xml`

#### 7.1.1 Email Fetching (Fallback)

| Field | Value |
|-------|-------|
| **ID** | `ir_cron_fetch_etsy_emails` |
| **Name** | `Etsy: Fetch Order Emails` |
| **Model** | `sale.order` |
| **Method** | `_cron_fetch_etsy_emails()` |
| **Interval** | 10 minutes |
| **Active** | False (optional; email is fallback only; API takes priority) |
| **Purpose** | Poll Gmail for order confirmation emails; parse + create orders |

#### 7.1.2 API Receipts Sync

| Field | Value |
|-------|-------|
| **ID** | `cron_etsy_order_sync` |
| **Name** | `Etsy: API Receipts Sync` |
| **Model** | `etsy.shop` |
| **Method** | `_cron_sync_orders()` |
| **Interval** | 5 minutes |
| **Active** | True |
| **Purpose** | Fetch new orders from Etsy API; create sale.order records |
| **User** | `base.user_root` |

#### 7.1.3 Listing Sync

| Field | Value |
|-------|-------|
| **ID** | `cron_etsy_listing_sync` |
| **Name** | `Etsy: Listing Metadata Sync` |
| **Model** | `etsy.listing` |
| **Method** | `_cron_sync_listings()` |
| **Interval** | 5 minutes |
| **Active** | True |
| **Purpose** | Fetch listing metadata from Etsy; update inventory cache |
| **Note** | Part of Spec 008 (listing inventory tracking) |

#### 7.1.4 Listing Variant Inventory Sync

| Field | Value |
|-------|-------|
| **ID** | `cron_etsy_listing_variant_sync` |
| **Name** | `Etsy: Listing Variant Inventory Sync` |
| **Model** | `etsy.listing_product` |
| **Method** | `_cron_sync_variants()` |
| **Interval** | 5 minutes |
| **Active** | True |
| **Purpose** | Sync variant-level inventory (per-size, per-color, etc.) |

#### 7.1.5 Tracking Push

| Field | Value |
|-------|-------|
| **ID** | `ir_cron_etsy_tracking_push` |
| **Name** | `Etsy: Push Tracking to Etsy` |
| **Model** | `sale.order` |
| **Method** | `_cron_push_tracking()` |
| **Interval** | 5 minutes |
| **Active** | True |
| **Purpose** | Push fulfillment + tracking data back to Etsy (when order shipped) |
| **User** | `base.user_root` |

#### 7.1.6 API Log Retention Sweep

| Field | Value |
|-------|-------|
| **ID** | `cron_etsy_api_log_cleanup` |
| **Name** | `Etsy: API Log Retention Sweep` |
| **Model** | `etsy.api.log` |
| **Method** | `_cron_cleanup_old_logs()` |
| **Interval** | 1 day |
| **Active** | True |
| **Purpose** | Delete audit logs older than 30 days (configurable) |
| **User** | `base.user_root` |

#### 7.1.7 Image Download

| Field | Value |
|-------|-------|
| **ID** | `ir_cron_download_pending_etsy_images` |
| **Name** | `Etsy: Download Pending Product Images` |
| **Model** | `product.template` |
| **Method** | `_cron_download_etsy_images()` |
| **Interval** | 30 minutes |
| **Active** | True |
| **Purpose** | Download product images from Etsy listings; attach to product records |
| **User** | `base.user_root` |

#### 7.1.8 Message Dedupe Retention

| Field | Value |
|-------|-------|
| **ID** | `cron_etsy_message_dedupe_retention` |
| **Name** | `Etsy: Message Dedupe Retention Sweep` |
| **Model** | `etsy.message.dedupe` |
| **Method** | `_cron_dedupe_retention()` |
| **Interval** | 1 day |
| **Active** | True |
| **Purpose** | Purge old message dedup markers (older than 7 days) to free DB space |

#### 7.1.9 Taxonomy Sync

| Field | Value |
|-------|-------|
| **ID** | `cron_etsy_taxonomy_sync` |
| **Name** | `Etsy: Taxonomy Cache Sync (P-LIST-CATEGORY)` |
| **Model** | `etsy.shop` |
| **Method** | `_cron_sync_taxonomy()` |
| **Interval** | 7 days |
| **Active** | True |
| **Purpose** | Refresh Etsy category taxonomy (used for listing creation) |
| **Note** | Runs weekly to keep category IDs current |

#### 7.1.10 Shipping Profile Sync

| Field | Value |
|-------|-------|
| **ID** | `cron_etsy_shipping_profile_sync` |
| **Name** | `Etsy: Shipping Profile Cache Sync (P-LIST-SHIPPING)` |
| **Model** | `etsy.shop` |
| **Method** | `_cron_sync_shipping_profiles()` |
| **Interval** | 1 day |
| **Active** | True |
| **Purpose** | Refresh cached shipping profiles (used for listing creation) |

### 7.2 Multichannel Hub Core Crons

**File:** `custom_addons/multichannel_hub_core/data/ir_cron_data.xml`

#### 7.2.1 Overdue Approval Recompute

| Field | Value |
|-------|-------|
| **ID** | `cron_recompute_overdue_approval` |
| **Name** | `Multichannel Hub: recompute is_overdue_approval` |
| **Model** | `sale.order` |
| **Method** | `_cron_recompute_overdue_approval()` |
| **Interval** | 1 day |
| **Active** | True |
| **Purpose** | Recalculate `is_overdue_approval` flag (design approval deadline check) daily |
| **User** | `base.user_root` |
| **Note** | Ensures dashboard marker updates even if no DB writes triggered `@api.depends` |

#### 7.2.2 Duplicate Buyer Recompute

| Field | Value |
|-------|-------|
| **ID** | `cron_recompute_duplicate_buyer` |
| **Name** | `Multichannel Hub: recompute is_duplicate_buyer` |
| **Model** | `sale.order` |
| **Method** | `_cron_recompute_duplicate_buyer()` |
| **Interval** | 1 day |
| **Active** | True |
| **Purpose** | Recalculate `is_duplicate_buyer` flag (retroactively flag older orders from repeat buyers) |
| **User** | `base.user_root` |

#### 7.2.3 Design File GDrive Sync

| Field | Value |
|-------|-------|
| **ID** | `cron_design_file_gdrive_sync` |
| **Name** | `Multichannel Hub: sync approved design files to GDrive` |
| **Model** | `design.file` |
| **Method** | `_cron_sync_approved_to_gdrive()` |
| **Interval** | 5 minutes |
| **Active** | True |
| **Purpose** | Promote approved `design.file` rows (storage_mode='small') to GDrive; update storage mode to 'gdrive' |
| **User** | `base.user_root` |
| **Killswitch** | ICP `multichannel_hub.design_gdrive_auto_sync_enabled` (default True) |
| **No-Op Condition** | ICP `multichannel_hub.design_file_default_gdrive_folder_id` is not set |

### 7.3 Gearment Crons

**File:** `custom_addons/multichannel_hub_fulfillment/data/ir_cron_gearment_api_log_retention.xml`

#### 7.3.1 API Log Retention Sweep

| Field | Value |
|-------|-------|
| **ID** | `ir_cron_gearment_api_log_cleanup` |
| **Name** | `Gearment API Log: cleanup old rows` |
| **Model** | `gearment.api.log` |
| **Method** | `_cron_cleanup_old_logs()` |
| **Interval** | 1 day |
| **Active** | True |
| **Purpose** | Delete webhook audit logs older than 30 days |
| **User** | (not explicitly set in XML; default applies) |

### 7.4 Orphaned Crons (No ir.cron Record)

**Dead Code Candidate:**

| Method | Location | Status | Note |
|--------|----------|--------|------|
| `image_downloader.cron_download_pending_images()` | `multichannel_hub_core/models/image_downloader.py` | No cron record | Method defined but not wired to `ir.cron`; orphaned (migration in progress?) |

---

## 8. Environment Variables & System Parameters

### 8.1 Environment Variables (Read at Runtime)

**Source:** `.env` file or container environment  
**Access Pattern:** `os.environ.get('VAR_NAME', 'default')`

#### 8.1.1 Gearment Integration

| Variable | Type | Purpose | Required? | Default |
|----------|------|---------|-----------|---------|
| `GEARMENT_API_KEY` | String | Client key for Gearment API requests (header `x-api-key`) | Yes | — |
| `GEARMENT_API_SECRET` | String | Secret for HMAC-SHA256 webhook signature verification | Yes | — |
| `GEARMENT_API_BASE_URL` | String | Base URL for Gearment API | No | `https://api.gearment.com` |

#### 8.1.2 Google Drive Integration

| Variable | Type | Purpose | Required? | Default |
|----------|------|---------|-----------|---------|
| `GDRIVE_SERVICE_ACCOUNT_JSON` | String (Path) | File path to GDrive service account JSON key | No | `/app/secrets/gdrive-service-account.json` |

#### 8.1.3 Testing / Feature Flags

| Variable | Type | Purpose | Required? | Notes |
|----------|------|---------|-----------|-------|
| `MULTICHANNEL_HUB_FULFILLMENT_LIVE_API` | Bool (`'1'` or `'0'`) | Skip mocked Gearment API in tests; call real API | No | Default: `'0'` (use mocks); set to `'1'` for live E2E testing |

### 8.2 System Parameters (ir.config_parameter)

**Scope:** Odoo database; stored in `ir.config_parameter` model  
**Access Pattern:** `self.env['ir.config_parameter'].sudo().get_param('key', default='...')`

#### 8.2.1 Etsy Integration

| Key | Type | Purpose | Default | Scope |
|-----|------|---------|---------|-------|
| `etsy.oauth.credentials_path` | Char | File path to OAuth app credentials JSON | `/opt/odoo/secrets/credentials.json` | All shops |
| `etsy_integration.gmail_client_id` | Char | Gmail OAuth app client ID | — | Gmail auth (fallback email ingest) |
| `etsy_integration.gmail_client_secret` | Char | Gmail OAuth app client secret | — | Gmail auth |
| `etsy_integration.gmail_label` | Char | Gmail label to poll (e.g., `"[Gmail]/All Mail"`) | `"[Gmail]/All Mail"` | Email cron |
| `etsy_integration.gmail_refresh_token` | Char | Gmail refresh token (persisted after OAuth) | — | Email cron (fallback) |
| `etsy_integration.etsy_api_version` | Char | Etsy API version | `v3` | API client |
| `etsy_integration.etsy_api_base_url` | Char | Base URL for Etsy API | `https://openapi.etsy.com/v3/application` | API client |
| `etsy_integration.etsy_log_retention_days` | Integer | Days to keep API audit logs | `30` | Log cleanup cron |
| `design.auto_create_on_confirm` | Char (`'True'` or `'False'`) | Auto-create design order when SO confirmed | `'True'` | Design module |

#### 8.2.2 Multichannel Hub Core

| Key | Type | Purpose | Default | Scope |
|-----|------|---------|---------|-------|
| `multichannel_hub.default_pipeline_code` | Char | Default pipeline (when SO has no explicit pipeline) | `order_pipeline_vn_internal_production` | Order state machine |
| `multichannel_hub.design_gdrive_auto_sync_enabled` | Char (`'True'` or `'False'`) | Enable auto-sync of approved design files to GDrive | `'True'` | Design file GDrive cron |
| `multichannel_hub.design_file_default_gdrive_folder_id` | Char | GDrive folder ID for design file uploads | — | Design file GDrive cron (no-op if unset) |
| `multichannel_hub.large_file_threshold_bytes` | Integer | Max size (bytes) for binary file storage before rejection | `10485760` (10 MB) | Design file upload |
| `web.base.url` | Char | Odoo server base URL (used by OAuth callbacks to resolve redirect URI) | — | OAuth controller (redirect URI picking) |

#### 8.2.3 Product Catalog / Inventory

| Key | Type | Purpose | Default | Scope |
|-----|------|---------|---------|-------|
| `multichannel_hub.product_catalog_gdrive_folder_id` | Char | GDrive folder ID for product Excel imports | — | Catalog import wizard |
| `multichannel_hub.product_catalog_source_file_name` | Char | Filename of product master Excel (e.g., `"Product_Catalog_Master.xlsx"`) | `"Product_Catalog_Master.xlsx"` | Catalog import cron |

---

## Document Metadata

| Field | Value |
|-------|-------|
| **Last Updated** | 2026-07-03 |
| **Verified Against** | Git HEAD of `feature/006-master-plan-coding` (all 4 modules merged to main 2026-07-03) |
| **Scope** | External-surface reference; routes, crons, env vars, API bindings |
| **Related Docs** | `01-architecture.md` (data model), `02-flows.md` (business processes), `04-security.md` (ACLs) |
| **Approval** | Draft for Owner Review |
| **Status** | Complete; all 8 sections populated with code-verified details |

---

## Appendix A. Quick Reference — All Routes

```
GET  /etsy/api/oauth/authorize     → Initiate PKCE flow
GET  /etsy/api/oauth/callback      → OAuth callback (token exchange)
GET  /etsy/oauth/callback          → Legacy (deprecated)
POST /gearment/webhook             → Gearment webhook (HMAC-verified)
```

---

## Appendix B. Quick Reference — All Crons

```
Etsy:
  ir_cron_fetch_etsy_emails                (10 min, fallback email ingest)
  cron_etsy_order_sync                     (5 min, API receipts)
  cron_etsy_listing_sync                   (5 min, listing metadata)
  cron_etsy_listing_variant_sync           (5 min, variant inventory)
  ir_cron_etsy_tracking_push               (5 min, push tracking)
  cron_etsy_api_log_cleanup                (1 day, retention sweep)
  ir_cron_download_pending_etsy_images     (30 min, image download)
  cron_etsy_message_dedupe_retention       (1 day, dedupe cleanup)
  cron_etsy_taxonomy_sync                  (7 days, category cache)
  cron_etsy_shipping_profile_sync          (1 day, shipping cache)

Multichannel Hub Core:
  cron_recompute_overdue_approval          (1 day, flag recompute)
  cron_recompute_duplicate_buyer           (1 day, flag recompute)
  cron_design_file_gdrive_sync             (5 min, GDrive upload)

Gearment:
  ir_cron_gearment_api_log_cleanup         (1 day, retention sweep)
```

---

## Appendix C. Quick Reference — All Env Vars

```
GEARMENT_API_KEY                           (required, webhook signing)
GEARMENT_API_SECRET                        (required, webhook signing)
GEARMENT_API_BASE_URL                      (optional, default: https://api.gearment.com)
GDRIVE_SERVICE_ACCOUNT_JSON                (optional, default: /app/secrets/gdrive-service-account.json)
MULTICHANNEL_HUB_FULFILLMENT_LIVE_API      (optional, testing flag)
```

---

## Appendix D. Quick Reference — Key System Parameters

```
etsy.oauth.credentials_path                (OAuth credentials file path)
etsy_integration.gmail_client_id           (Gmail OAuth)
etsy_integration.gmail_client_secret       (Gmail OAuth)
etsy_integration.gmail_label               (Gmail label to poll)
etsy_integration.gmail_refresh_token       (Gmail token, auto-set)
design.auto_create_on_confirm              (auto-create design order)
multichannel_hub.design_gdrive_auto_sync_enabled   (GDrive sync killswitch)
multichannel_hub.design_file_default_gdrive_folder_id  (GDrive folder)
multichannel_hub.default_pipeline_code    (default order pipeline)
web.base.url                               (OAuth redirect URI resolution)
```
