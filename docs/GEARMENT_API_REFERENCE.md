# Gearment v3 API Reference

**Last Updated**: 2026-05-10  
**API Version**: v3  
**Canonical URL**: https://developers.gearment.com/api  
**Implementation Status**: P4-01 (Gearment adapter + state machine + quote workflow)

---

## Table of Contents

1. [Quickstart](#quickstart)
2. [Authentication](#authentication)
3. [Order Push Payload Reference](#order-push-payload-reference)
4. [Printing Options Deep Dive](#printing-options-deep-dive)
5. [Webhook Reference](#webhook-reference)
6. [Error Response Format](#error-response-format)
7. [Rate Limits and Idempotency](#rate-limits-and-idempotency)
8. [Order Status State Machine](#order-status-state-machine)
9. [SKU Registration and Catalog](#sku-registration-and-catalog)
10. [Sandbox vs Production](#sandbox-vs-production)
11. [Open Questions for Gearment Support](#open-questions-for-gearment-support)

---

## Quickstart

### Environment Variables

The Gearment adapter reads three required environment variables (set in `.env`):

```bash
GEARMENT_API_BASE_URL=https://api.gearmentinc.com/integration-handler    # Sandbox
GEARMENT_API_BASE_URL=https://apiv2.gearment.com/integration-handler      # Production
GEARMENT_API_KEY=<your-api-key>
GEARMENT_API_SECRET=<your-api-secret>
GEARMENT_WEBHOOK_HMAC_SECRET=<your-webhook-secret>  # For inbound webhook validation
```

### Base URLs

| Environment | Base URL | Use Case |
|---|---|---|
| **Sandbox** | `https://api.gearmentinc.com/integration-handler` | Development + testing (E2 Gearment sandbox credentials) |
| **Production** | `https://apiv2.gearment.com/integration-handler` | Live fulfillment orders |

*Source*: [https://developers.gearment.com/api/section/overview](https://developers.gearment.com/api/section/overview); confirmed in `custom_addons/multichannel_hub_fulfillment/services/gearment_api_client.py:82`

### Quick Call Example

```python
from requests import post

headers = {
    'X-Gearment-Client-Key': 'YOUR_API_KEY',
    'X-Gearment-Client-Secret': 'YOUR_API_SECRET',
    'Accept': 'application/json',
}

url = 'https://api.gearmentinc.com/integration-handler/api/v3/orders/draft'
payload = {
    'data': {
        'reference_id': 'SO-2026-00001',
        'store_id': 'etsy-shop-123',
        'addresses': [{ /* address */ }],
        'line_items': [{ /* line */ }],
    }
}

response = post(url, json=payload, headers=headers, timeout=30)
response.raise_for_status()
```

---

## Authentication

### HTTP Headers (Required on Every Request)

All requests to Gearment API v3 must include:

```
X-Gearment-Client-Key: <api_key>
X-Gearment-Client-Secret: <api_secret>
Accept: application/json
```

### Credential Retrieval

1. Log in to Gearment Dashboard
2. Navigate to **Team Settings** > **Developer Settings**
3. Generate or copy existing API Key (`X-Gearment-Client-Key`)
4. Generate or copy existing API Secret (`X-Gearment-Client-Secret`)
5. For webhook signature verification (inbound callbacks), obtain the **HMAC Secret** from the same location or ask Gearment support

*Source*: [https://developers.gearment.com/api/section/overview](https://developers.gearment.com/api/section/overview); credentials stored in `.env` per `CLAUDE.md` reference

### Credential Missing Behavior

If any required env var is missing at adapter initialization, `GearmentApiClient.__init__()` raises:
```
ValueError: GearmentApiClient missing required env vars: GEARMENT_API_KEY, ...
```

*Source*: `custom_addons/multichannel_hub_fulfillment/services/gearment_api_client.py:75-79`

---

## Order Push Payload Reference

### Endpoint

```
POST /api/v3/orders/draft
```

### Request Body Structure

The wire format is a single-object envelope with a `data` key (NOT an array):

```json
{
  "data": {
    "reference_id": "SO-2026-00001",
    "store_id": "etsy-shop-123",
    "addresses": [
      {
        "first_name": "Alice",
        "last_name": "Buyer",
        "street_1": "123 Main St",
        "street_2": "Apt 4B",
        "city": "Boston",
        "state": "MA",
        "zip_code": "02108",
        "country_code": "US",
        "phone": "617-555-0100",
        "email": "alice@example.com"
      }
    ],
    "line_items": [
      {
        "legacy_id": 1001,
        "quantity": 1,
        "sku": "DEMO-T-RED-M",
        "printing_options": [
          {
            "location_code": "front",
            "url": "https://drive.google.com/uc?id=ABC123&export=download"
          },
          {
            "location_code": "back",
            "url": "https://drive.google.com/uc?id=XYZ789&export=download"
          }
        ],
        "personalisation": "John's Tshirt",
        "custom_attributes": {}
      }
    ],
    "shipping_method": "standard",
    "notes": "Gift message: Happy Birthday!",
    "custom_attributes": {}
  }
}
```

### Field Reference

| Field | Type | Required | Description | Example |
|---|---|---|---|---|
| `reference_id` | string | YES | Your internal order ID (used for idempotency) | `SO-2026-00001` |
| `store_id` | string | YES | Your store/shop identifier | `etsy-shop-123` or `12345` |
| `addresses` | array | YES | Array with exactly one shipping address | `[{...}]` |
| `addresses[].first_name` | string | YES | Recipient first name (empty parts default to `'-'` in our adapter) | `Alice` |
| `addresses[].last_name` | string | YES | Recipient last name | `Buyer` |
| `addresses[].street_1` | string | YES | Primary street address | `123 Main St` |
| `addresses[].street_2` | string | NO | Secondary address line (apt, suite, etc.) | `Apt 4B` |
| `addresses[].city` | string | YES | City name | `Boston` |
| `addresses[].state` | string | YES | State or province code or name | `MA` or `Massachusetts` |
| `addresses[].zip_code` | string | YES | Postal code | `02108` |
| `addresses[].country_code` | string | YES | ISO 3166-1 alpha-2 country code | `US` |
| `addresses[].phone` | string | NO | Phone number (no specific format enforced) | `617-555-0100` |
| `addresses[].email` | string | NO | Email address | `alice@example.com` |
| `line_items` | array | YES | One or more product lines | `[{...}]` |
| `line_items[].legacy_id` | integer | YES | Gearment catalog product ID (can be 0 on fallback) | `1001` |
| `line_items[].quantity` | integer | YES | Quantity of this line item | `1`, `5` |
| `line_items[].sku` | string | NO | Merchant SKU (for order reconciliation, not validation) | `DEMO-T-RED-M` |
| `line_items[].printing_options` | array | YES | **At least one** required; see [Printing Options Deep Dive](#printing-options-deep-dive) | `[{...}]` |
| `line_items[].personalisation` | string | NO | Custom personalization text | `John's Tshirt` |
| `line_items[].custom_attributes` | object | NO | Reserved for future use | `{}` |
| `shipping_method` | string | NO | Carrier name or method; defaults to `'standard'` in our adapter | `standard`, `express`, `fedex` |
| `notes` | string | NO | Order notes (HTML-escaped before wire transmission to prevent script injection) | `Gift message: Happy Birthday!` |
| `custom_attributes` | object | NO | Reserved for future use | `{}` |

### Implemented in Our Adapter

*Source*: `custom_addons/multichannel_hub_fulfillment/services/gearment_payload_builder.py:28-123` (P4-01-B payload regen)

Our `build_payload(order, design_files)` function constructs the above shape automatically from a `sale.order` recordset:

- `reference_id` ← `sale.order.channel_order_ref` or `sale.order.name`
- `store_id` ← `sale.order.etsy_shop_id.etsy_shop_id` or `display_name`
- `addresses[0]` ← `sale.order.partner_shipping_id` or `partner_id` (split name into first/last)
- `line_items[]` ← `sale.order.order_line` (filtered to non-empty `x_gearment_sku`)
- `shipping_method` ← `sale.order.fulfillment_id.shipping_carrier_id.gearment_carrier_name` (default: `'standard'`)
- `notes` ← `sale.order.note` (HTML-escaped)

**Lines without a Gearment SKU are silently skipped.** If a line has no `printing_options`, the entire line is skipped (operator sees missing-design gap on dashboard).

---

## Printing Options Deep Dive

### The Problem: Opaque Validation (Defect-2026-05-10-05, HIGH)

After the P4-01-FIX-PAYLOAD-SCHEMA fix landed (schema structure corrected), the live Gearment API at `https://apiv2.gearment.com/integration-handler/api/v3/orders/draft` still rejects orders with:

```
400 Bad Request
data.line_items[0]: A line item must include at least one printing option 
with location_code front, pocket, back or whole [has_front_back_or_whole_printing_option]
```

The error message says the validator accepts exactly `front`, `pocket`, `back`, `whole` — yet all our probes against those values are rejected identically.

*Source*: `docs/E2E_DEFECTS_2026-05-10.md` §Defect-2026-05-10-05; E2E run 2026-05-10 10:18–10:19 UTC captured 12 rejection variants

### Attempted Key Variants

| Outer Key (array field name) | Probed | Result |
|---|---|---|
| `printing_options` | YES | Does not trigger "value must contain at least 1 item(s)"; all requests sent with this key |
| `print_locations` | YES | Rejected (probably "unknown field") |
| `placements` | YES | Rejected |
| `prints` | YES | Rejected |
| `options` | YES | Rejected |

### Attempted Inner location_code Key Variants

| Inner Key (location code name) | Probed | Result |
|---|---|---|
| `location_code` | YES | Rejected with the validation error above |
| `locationCode` (lowerCamelCase) | YES | Rejected identically |
| `code` | YES | Rejected |
| `location` | YES | Rejected |
| `position` | YES | Rejected |

### Attempted location_code Value Variants

All 8 variants below produced the **exact same error message**:

| location_code Value | Probed | Result |
|---|---|---|
| `"front"` | YES | Rejected: `has_front_back_or_whole_printing_option` |
| `"FRONT"` (uppercase) | YES | Rejected identically |
| `1` (integer enum 1) | YES | Rejected identically |
| `0` (integer enum 0) | YES | Rejected identically |
| `"PRINTING_LOCATION_FRONT"` | YES | Rejected identically |
| `"PRINT_LOCATION_FRONT"` | YES | Rejected identically |
| `"LOCATION_FRONT"` | YES | Rejected identically |
| `"PRINT_LOCATION_TYPE_FRONT"` | YES | Rejected identically |

### Attempted URL Key Variants

| URL Field Name | Probed | Result |
|---|---|---|
| `url` | YES | Rejected identically |
| `image_url` | YES | Rejected identically |
| `design_url` | YES | Rejected identically |
| `file_url` | YES | Rejected identically |
| `image` | YES | Rejected identically |
| `imageUrl` (lowerCamelCase) | YES | Rejected identically |
| `designUrl` | YES | Rejected identically |
| `printUrl` | YES | Rejected identically |

### Current Hypothesis

Three plausible root causes (ordered by likelihood):

1. **Proto3 Field Naming Convention Mismatch** ← MOST LIKELY  
   The public docs use examples like `PRINT_LOCATION_CODE_WHOLE`, but the actual proto3 wire format may use a different JSON key name (e.g., `print_location_code` with a specific enum type). The docs page is reportedly a stub; truth is in the OpenAPI YAML under `tags[]`.

2. **Missing Required Sibling Field**  
   There may be a second required field on the `printing_option` object (e.g., `image` as a MessageType wrapper for the URL) that our payloads are missing. When the deseri alizer encounters an empty or wrong field, it silently defaults the entire `printing_option` object, which then has `location_code=""` and fails validation.

3. **Array Deserialization Failure**  
   The `printing_options` array may not deserialize at all due to a proto3 mismatch, causing each element to be silently dropped. The line_item then has zero printing options, triggering the validator.

4. **Demo SKU Not Registered** ← LEAST LIKELY (but still possible)  
   SKU `DEMO-T-*` may not be registered in the Gearment catalog on the production API. If the validator does a catalog lookup and finds no SKU, it may reject the entire line regardless of the `location_code` value. However, this would produce a different error message (e.g., "SKU not found").

### Current Implementation in Our Adapter

*Source*: `custom_addons/multichannel_hub_fulfillment/services/gearment_payload_builder.py:77-94`

```python
_PRINT_LOCATIONS_DEFAULT = ('front', 'back')

printing_options = tuple(
    {
        'location_code': code,
        'url': df.file_url or df.gdrive_preview_url,
    }
    for code, df in zip(_PRINT_LOCATIONS_DEFAULT, line_designs)
    if (df.file_url or df.gdrive_preview_url)
)
```

- First design file → `location_code='front'`
- Second design file → `location_code='back'`
- Per-design override field deferred (no `design.file.x_gearment_location_code` yet)
- URL preference: `file_url` (external CDN) → `gdrive_preview_url`

### Docs Source — RESOLVED 2026-07-05 (doc crawl)

The docs were crawled into `docs/vendor/gearment/` (raw HTML in `_raw/`, git-ignored).
The renderer is a JS SPA (Stoplight Elements) but **server-renders the example
payloads**, which are authoritative. Findings:

- The `location_code` example value is **`PRINT_LOCATION_CODE_WHOLE`** — the enum uses the
  proto3 `PRINT_LOCATION_CODE_*` prefix. This is the house style across every enum in the
  same doc (`VENDOR_ORDER_STATUS_*`, `VENDOR_CREATED_METHOD_*`,
  `VENDOR_ORDER_DRAFT_STATUS_*`, …), so the pattern is not a guess.
- **Root cause of Defect-2026-05-10-05:** our probes tried `front`, `FRONT`,
  `PRINT_LOCATION_FRONT`, `LOCATION_FRONT`, `PRINT_LOCATION_TYPE_FRONT` — but **never
  `PRINT_LOCATION_CODE_FRONT`**. The validator's "must be front/pocket/back/whole" message
  quotes the *human* names; the wire value is the prefixed enum.
- **Correct draft value set** (WHOLE literal-confirmed; FRONT/BACK/POCKET inferred from the
  400 error's own allowed-list + the proven prefix pattern — confirm with one live probe):
  `PRINT_LOCATION_CODE_FRONT`, `PRINT_LOCATION_CODE_POCKET`, `PRINT_LOCATION_CODE_BACK`,
  `PRINT_LOCATION_CODE_WHOLE`.
- **Draft ≠ Quote.** Draft (`/orders/draft`) uses
  `printing_options:[{location_code:"PRINT_LOCATION_CODE_*", url}]`; Quote
  (`/orders/{ref}/price`) uses `print_locations:["front"]` (lowercase strings). Our builder
  must not send the draft enum to the quote endpoint or vice versa.
- **`variant_id`, not SKU.** Draft line items key on `variant_id` (e.g. `GM0002003147`) +
  `product_id` (e.g. `G5000`), looked up via `/api/v3/catalog/variants/stock`. Synthetic
  `DEMO-T-*` SKUs fail catalog lookup (this is the separate Defect-2026-05-10-02).

**Required fix** (separate slice, RED test first — do NOT hand-edit without a failing
test): in `services/gearment_payload_builder.py`, change `_PRINT_LOCATIONS_DEFAULT` from
`('front','back')` to the prefixed enum values, and source `variant_id` from the Gearment
catalog rather than the Odoo SKU.

Full evidence: `docs/vendor/gearment/api_api.order.v1.vendororderapi.md`
(draft example ≈ lines 581–594).

---

## Webhook Reference

### Webhook Basics

Gearment sends webhooks as HTTPS POST requests to your configured callback URL when order status changes. Each webhook includes:

- **Event Type** in the body `type` field (or `topic` in older payloads)
- **Signature** in the `X-Connect-Signature` header (HMAC-SHA256)
- **Nonce** in the `X-Connect-Nonce` header (replay protection)
- **Timestamp** in the `X-Connect-Timestamp` header (for signature validation window)

*Source*: [https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi](https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi); auto-memory `reference_gearment_webhook_signature.md` confirms HMAC scheme

### HMAC Signature Validation

**Scheme**: `HMAC-SHA256(GEARMENT_WEBHOOK_HMAC_SECRET, url_path + nonce + timestamp + base64url(body))`

Example calculation:

```python
import hashlib
import hmac
import base64

def verify_gearment_webhook(headers: dict, body: bytes, secret: str) -> bool:
    """Validate Gearment webhook signature per P0-18b2b."""
    
    signature_header = headers.get('X-Connect-Signature')
    nonce = headers.get('X-Connect-Nonce', '')
    timestamp = headers.get('X-Connect-Timestamp', '')
    request_path = '/api/v3/webhooks/callback'  # Your callback path
    
    if not signature_header or not nonce or not timestamp:
        return False
    
    # Concatenate: path + nonce + timestamp + base64url(body)
    body_b64 = base64.urlsafe_b64encode(body).decode('utf-8').rstrip('=')
    message = f"{request_path}{nonce}{timestamp}{body_b64}"
    
    # Compute HMAC-SHA256
    computed = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Constant-time comparison
    return hmac.compare_digest(computed, signature_header)
```

**Important**: 
- The signature is computed over `url_path` (not the full URL), so you must use your callback path exactly as configured in Gearment Dashboard
- Nonce + timestamp prevent replay attacks; always validate them
- There is NO separate `GEARMENT_WEBHOOK_HMAC_SECRET` env var — use the same secret from your Gearment Dashboard API settings

*Source*: auto-memory `reference_gearment_webhook_signature.md`; implementation in `custom_addons/multichannel_hub_fulfillment/controllers/webhook_controller.py` (P0-18b2b)

### Supported Webhook Events

Events are identified by the `type` field in the JSON body:

| Event Type | Trigger | Body Shape | Example |
|---|---|---|---|
| `order_created` | Order draft created or pushed from external system | Depends on version | *[Under discovery — no payload captured yet]* |
| `order_processing` | Order accepted + moved to production queue | `{order: {...}, ...}` | *[Under discovery]* |
| `order_shipped` | Order fulfilled + tracking assigned | `{order: {...}, tracking: {...}}` | See V3 Sample below |
| `order_canceled` | Order cancelled (note single-L spelling per dashboard observation) | `{order: {...}}` | *[Under discovery]* |
| `tracking_updated` | Tracking info changed (e.g., status from "in transit" to "delivered") | `{order: {...}, tracking: {...}}` | *[Under discovery]* |

### V3 Sample Payload (Captured 2026-05-02 Dashboard Simulator)

```json
{
  "order": {
    "gearment_id": "GEAR-2026-00001",
    "gearment_name": "ORD-2026-00001",
    "reference": "SO-2026-00001",
    "status": "shipped",
    "vendor_id": "etsy-shop-123"
  },
  "tracking": {
    "company": "USPS",
    "number": "9400111899223456789012",
    "url": "https://tools.usps.com/go/TrackConfirmAction.action?tLabels=9400111899223456789012"
  }
}
```

**Field Mapping**:
- `order.reference` ← Our `sale.order.name` or `channel_order_ref` (matches the `reference_id` we sent)
- `order.status` ← Gearment fulfillment state (values observed: `shipped`, possibly `completed`, `processing`, `cancelled`)
- `order.gearment_id` ← Gearment's internal order ID (store for audit; not used in our routing)
- `tracking.company` ← Carrier name (auto-detect to match our `shipping_carrier_id`)
- `tracking.number` ← Tracking number (write to `sale.order.tracking_number`)
- `tracking.url` ← Deep link to carrier tracking page (may skip our `tracking_url_template` for Gearment orders)

### Webhook Event Schema Discovery Gaps

The following are **NOT YET CONFIRMED** and need Gearment support confirmation:

1. Full event type enum (are there more than 5 event types?)
2. Payload structure for `order_created`, `order_processing`, `order_canceled` (only `order_shipped` captured)
3. Timestamp field name (is it in the webhook body, or only in the `X-Connect-Timestamp` header?)
4. Whether `order.status` values map directly to our `x_gearment_status` Selection (pending / accepted / in_production / shipped / failed)
5. Retry and timeout semantics (how long does Gearment wait for a 200 OK? how many retries?)

---

## Error Response Format

### HTTP Status Codes Observed

| Status | Meaning | Example | Retry? |
|---|---|---|---|
| `200` | Success | Order draft created | NO |
| `400` | Bad Request | Malformed payload, missing required field, or validation failure | NO (fix payload) |
| `401` / `403` | Authentication Failure | Invalid or expired API key/secret | NO (fix credentials) |
| `429` | Rate Limit Exceeded | 100 req/10 sec limit breached | YES (with backoff) |
| `503` / `504` | Service Unavailable | Gearment server or Cloudflare WAF throttling | YES (longer backoff) |

*Source*: `custom_addons/multichannel_hub_fulfillment/services/gearment_api_client.py:32-39` (constants + backoff strategy)

### 400 Bad Request Structure

Gearment's 400 errors carry a `data.field_name: validation rule [error_code]` structure:

```json
{
  "error": "Bad Request",
  "details": {
    "data": {
      "line_items[0]": "A line item must include at least one printing option with location_code front, pocket, back or whole [has_front_back_or_whole_printing_option]"
    }
  }
}
```

Or simpler:

```
400 Client Error: Bad Request for url: https://apiv2.gearment.com/integration-handler/api/v3/orders/draft
```

Our adapter captures the error text in `gearment.api.log.error_message` **but does not yet populate `http_status` on the failure path** — this is Defect-2026-05-10-03 (MEDIUM).

*Source*: `docs/E2E_DEFECTS_2026-05-10.md` §Defect-2026-05-10-03

### Error Logging

Every request (success or failure) is logged to `gearment.api.log`:

| Field | Populated When | Notes |
|---|---|---|
| `http_status` | Success only (BUG: should be set on all requests) | Integer: 200, 400, 429, 503, etc. |
| `error_message` | Failure only | Exception text or response body snippet |
| `request_payload_summary` | Always | JSON (PII-scrubbed: 9 keys removed) |
| `response_summary` | Success only | JSON (truncated to ~4 KB) |
| `sale_order_id` | Success only (BUG: should be set on all requests) | NULL on failure; operator cannot trace which order failed without grep-walking chatter |
| `direction` | Always | 'outbound' for our requests; 'inbound' for webhook callbacks |
| `endpoint` | Always | HTTP method + path, e.g. "POST /api/v3/orders/draft" |

*Source*: `custom_addons/multichannel_hub_fulfillment/models/gearment_api_log.py:14-103`

### PII Scrubbing Before Log Write

The following 9 keys are recursively removed from all payloads before audit logging:

```python
_PII_KEYS = frozenset({
    'first_name', 'last_name', 'buyer_name',
    'address_line_1', 'address_line_2', 'street_1', 'street_2',
    'email', 'phone', 'notes', 'address', 'addresses'
})
```

Plus a deep-scrub helper that removes these keys from nested dicts and lists. Result: chatter and logs show payload structure but not customer PII.

*Source*: `custom_addons/multichannel_hub_fulfillment/services/gearment_adapter.py:67-78`

---

## Rate Limits and Idempotency

### Rate Limit Policy

**Gearment enforces**: 100 requests per 10 seconds. Exceeding this returns HTTP 429 with a `Retry-After` header.

Our client implements:

1. **Advisory Token Bucket** (pre-flight limit check, logs warning if breached but sends anyway)
2. **Exponential Backoff** on 429:  
   - Delays: (1, 2, 4) seconds for normal errors  
   - Delays: (5, 15, 45) seconds for 503/504 service unavailable (P4-01-B S4 surprise)
   - Max retries: 3
3. **Retry-After Header** honor: If Gearment sends `Retry-After`, we wait that duration (capped at 60 seconds) before retrying

*Source*: `custom_addons/multichannel_hub_fulfillment/services/gearment_api_client.py:30-37, 94-150`

### Idempotency Belt-and-Braces

To prevent duplicate order submissions:

**HTTP Header**:
```
Idempotency-Key: <sha256-hex-of-reference_id>
```

**Request Body**:
```json
{"data": {
    "reference_id": "SO-2026-00001",
    ...
}}
```

Both are set by our adapter. Gearment honors whichever (typically the header) to deduplicate. Idempotency window is **not documented** — assume 24 hours as industry standard.

*Source*: `custom_addons/multichannel_hub_fulfillment/services/gearment_adapter.py:31-39` (idempotency_key generation); `gearment_payload.py:95-97` (property)

---

## Order Status State Machine

### Gearment Side (Webhook-Driven)

The `sale.order.x_gearment_status` Selection field tracks Gearment's fulfillment state:

```python
x_gearment_status = fields.Selection([
    ('pending', 'Pending'),           # Pushed, not yet accepted
    ('accepted', 'Accepted'),         # In Gearment queue
    ('in_production', 'In Production'),
    ('shipped', 'Shipped'),
    ('failed', 'Failed'),
], string='Gearment Status', readonly=True, tracking=True)
```

Values are updated by webhook callbacks (P0-18b2). Gearment-side state is **distinct** from our local outbound push lifecycle.

*Source*: `custom_addons/multichannel_hub_fulfillment/models/sale_order.py:57-68`

### Our Side (Operator-Driven Push Lifecycle)

The `sale.order.x_gearment_outbound_state` Selection tracks the local push process:

```python
x_gearment_outbound_state = fields.Selection([
    ('draft', 'Draft'),
    ('quoted', 'Quoted'),
    ('operator_review', 'Operator Review'),
    ('confirmed', 'Confirmed'),
    ('cancelled', 'Cancelled'),
], string='Gearment Outbound State', default='draft', tracking=True)
```

**Flow**:

1. **draft** ← Order created (initial state)
2. **quoted** ← Operator calls `action_get_gearment_quote()` (fetches price from `/orders/{ref}/price`)
3. **operator_review** ← Quote expires or operator manually moves to review state
4. **confirmed** ← Operator clicks "Confirm" (calls `/orders/draft/labeled` which finalizes the order)
5. **cancelled** ← Operator explicitly cancels (no auto-cancel per E3 invariant)

*Source*: `custom_addons/multichannel_hub_fulfillment/models/sale_order.py:71-86` (P4-01-C); `specs/004-fulfillment-routing/findings.md` (decision E1.b)

### Mapping to 17-VN Pipeline Stages

The canonical 17 Vietnamese pipeline stages (per ADR-010 Amendment) are the **source of truth** for overall order state. Gearment-side state is informational only:

| VN Stage | Gearment Status | Notes |
|---|---|---|
| `TS01-received` | `pending` | Email parsed → Odoo order created |
| `TS02-design-in-progress` | `pending` | Designer working on proof |
| `TS03-design-approved` | `pending` | Design approved by customer |
| `TS04-production-scheduled` | `accepted` | Order pushed to Gearment |
| `TS05-production-in-progress` | `in_production` | Gearment printing the order |
| `TS06-production-complete` | `shipped` | Order printed + packed |
| `TS07-label-generated` | `shipped` | Shipping label assigned |
| `TS08-ready-for-shipment` | `shipped` | In warehouse queue |
| ... (9–17 are tracking + delivery states) | `shipped` | Carrier updates via GKE import |

*Source*: `specs/004-fulfillment-routing/findings.md` (R1); auto-memory `project_hybrid_dropship_mto_amendment.md`

---

## SKU Registration and Catalog

### Do We Need Pre-Registered SKUs?

**UNKNOWN — needs vendor confirmation.**

Our implementation uses `sale.order.line.product_id.product_tmpl_id.x_gearment_sku` which can be:

- A numeric Gearment catalog product ID (e.g., `1001`)
- A merchant SKU code (e.g., `DEMO-T-RED-M`)

The adapter coerces both into `line_items[].legacy_id` (integer) + `line_items[].sku` (string). If the SKU is not registered in Gearment's catalog, the validator rejects the order — but we haven't tested this hypothesis against live Gearment yet (demo SKUs `DEMO-T-*` are not registered, and that may be why we get 400 errors; see Defect-2026-05-10-02).

*Source*: `gearment_payload_builder.py:126-137` (`_safe_int` function); Defect-2026-05-10-02 hypothesis (d)

### Catalog Query API

Gearment provides a **Catalog API** at `GET /api/v3/catalog/products` (presumably), but we haven't implemented it yet. To query available SKUs:

1. Log in to Gearment Dashboard
2. Navigate to **Products** or **Catalog**
3. Search or browse available variants + their IDs
4. Export or screenshot the mapping for use in our `product.product.x_gearment_sku` seeding

Alternatively, ask Gearment support for an export of all available product IDs / SKUs.

*Source*: [https://developers.gearment.com/api](https://developers.gearment.com/api); Catalog API mentioned but not yet integrated; `specs/004-fulfillment-routing/research.md` §R3

### Variant ID vs Legacy ID vs SKU

The Gearment schema distinguishes:

- `variant_id`: Gearment's internal variant identifier (NOT used in our current payload; reserved for future flexibility)
- `legacy_id`: Integer product ID (our `x_gearment_sku` coerced to int)
- `sku`: Merchant's SKU string (our `x_gearment_sku` as-is)

We populate both `legacy_id` and `sku` for maximum compatibility. If your SKU is non-numeric, `legacy_id` falls back to `0` (which Gearment rejects).

*Source*: `gearment_payload.py:56-74` (GearmentLineItem dataclass); `gearment_payload_builder.py:73`

---

## Sandbox vs Production

### Environment Switching

| Setting | Sandbox | Production |
|---|---|---|
| **Env Var**: `GEARMENT_API_BASE_URL` | `https://api.gearmentinc.com/integration-handler` | `https://apiv2.gearment.com/integration-handler` |
| **Env Var**: `GEARMENT_API_KEY` | Sandbox key from dashboard | Production key from dashboard |
| **Env Var**: `GEARMENT_API_SECRET` | Sandbox secret | Production secret |
| **Database**: `demo_esty` | Safe for E2E testing | **NEVER use production orders** |
| **Database**: `prod_esty` (future) | N/A | Production orders only |
| **Order IDs** | Synthetic (e.g., `DEMO-T-*`, ordertest2) | Real Etsy orders |
| **Shipping** | Dummy (testing only) | Real fulfillment to customers |

### Configuration in Docker Compose

In `.env` file:

```bash
# Sandbox (development)
GEARMENT_API_BASE_URL=https://api.gearmentinc.com/integration-handler
GEARMENT_API_KEY=sandbox_key_from_dashboard
GEARMENT_API_SECRET=sandbox_secret_from_dashboard

# Production (after go-live approval)
# GEARMENT_API_BASE_URL=https://apiv2.gearment.com/integration-handler
# GEARMENT_API_KEY=prod_key_from_dashboard
# GEARMENT_API_SECRET=prod_secret_from_dashboard
```

*Source*: `CLAUDE.md` (project instructions); `docker-compose.yml` + `.env` per staging deployment 2026-05-01

---

## Open Questions for Gearment Support

> **UPDATE 2026-07-05 — doc crawl (`docs/vendor/gearment/`) answered most of Category 1 &
> 2 without vendor contact.** Status per question below. Remaining opens are Category 3
> (webhook payload completeness) and a live-probe confirmation of the non-WHOLE enum
> values. Vendor escalation only still needed if the live probe below fails.

### Category 1: Printing Options Validation (BLOCKING Defect-2026-05-10-05)

1. **Q1.1**: The error message says "location_code must be one of: front, pocket, back, whole" — but our probes with `location_code: "front"` (lowercase string) are rejected with the exact same error. Are there variant field names or enum encoding requirements NOT documented in the public API docs?

   - What is the exact JSON field name in the v3 OpenAPI schema for printing location?
   - What are the valid enum values and their JSON encoding (string, integer enum, CONSTANT_CASE)?
   - Does the field have a different name in the proto3 source?

   > **ANSWERED 2026-07-05 (doc crawl):** Field name is `location_code`, string value, and
   > the encoding is the proto3 enum `PRINT_LOCATION_CODE_*` — the docs example is
   > `PRINT_LOCATION_CODE_WHOLE`. Our probes used the bare/human names; that is the bug.
   > `PRINT_LOCATION_CODE_WHOLE` is literal-confirmed; `FRONT`/`POCKET`/`BACK` are inferred
   > from the 400 allowed-list + the prefix pattern → **one live probe closes this**.

2. **Q1.2**: We have tested 8 location_code variants and 8 URL key variants with no success. Is there a required **sibling field** on the `printing_option` object that we are missing (e.g., `image` as a MessageType, `dimension`, `color_mode`)?

   - What are ALL required fields on `printing_options[i]`?
   - Is there a sample v3 payload generated by your own dashboard that we can compare against?

   > **ANSWERED 2026-07-05 (doc crawl):** No hidden sibling field. The documented
   > `printing_option` object is exactly `{location_code, url}` (see
   > `docs/vendor/gearment/api_api.order.v1.vendororderapi.md`). The rejection was the wrong
   > `location_code` value, not a missing field.

3. **Q1.3**: Can you provide a sample order payload captured from your **dashboard** (not our synthetic orders)?

   > **ANSWERED 2026-07-05:** Docs ship a full draft example (line_items → variant_id,
   > quantity, printing_options[{location_code, url}], barcode_url). Captured in the corpus.
   > Only "multi-design front+back" combos remain to be confirmed via live probe.

### Category 2: Demo Data and Catalog (BLOCKING Defect-2026-05-10-02)

4. **Q2.1**: Our demo SKUs (`DEMO-T-*`) are being rejected by your API. Are these pre-registered in your **sandbox** catalog?

   > **PARTIALLY ANSWERED 2026-07-05 (doc crawl):** Draft line items key on **`variant_id`**
   > (e.g. `GM0002003147`) + `product_id` (e.g. `G5000`), resolved via
   > `GET /api/v3/catalog/variants/stock?filter.product_ids=...&filter.variant_ids=...`.
   > Free-text `DEMO-T-*` SKUs are not catalog variants → rejected. Still open: obtain a
   > real sandbox/dev `variant_id` to test with (owner can pull from the catalog endpoint).

5. **Q2.2**: When an order is rejected with HTTP 400, is the root cause always in the payload, or could it be a catalog lookup failure?

   > **STILL OPEN:** error body is opaque; the two failure modes (bad enum vs. unknown
   > variant) were indistinguishable. Now separable by fixing the enum first, then testing a
   > known-good `variant_id`.

### Category 3: Webhook and Delivery Mechanics

6. **Q3.1**: Our webhook payload samples are incomplete. Can you provide sample bodies for all supported event types?

   - What are the full payloads for `order_created`, `order_processing`, `order_canceled`?
   - What is the timestamp field name and Unix epoch vs RFC3339 format?
   - Are there any other event types beyond the 5 we've observed?

7. **Q3.2**: Webhook delivery and retry semantics:

   - How long do you wait for a 200 OK response before timing out?
   - How many times do you retry a failed webhook delivery?
   - What is the maximum age of a webhook (can we ignore webhooks older than 1 hour)?

### Category 4: API Completeness

8. **Q4.1**: The Gearment API v3 documentation site is reportedly a stub. Where is the **canonical OpenAPI YAML**?

   > **ANSWERED 2026-07-05:** No standalone OpenAPI/Swagger file is served —
   > `/openapi.json`, `/openapi.yaml`, `/swagger.json` all 404 on both
   > `developers.gearment.com` and `apiv2.gearment.com`. The docs SPA at
   > `developers.gearment.com/api/*` is **not** a stub; it server-renders the full request
   > schemas + examples (Stoplight Elements). Corpus in `docs/vendor/gearment/`. A published
   > Postman collection also exists at `https://api.gearment.com/` (documenter.pstmn.io).

   - Can you provide the OpenAPI / Swagger YAML file (or link) that is the source of truth?
   - Specifically, we need the proto3 message definitions for `GearmentOrderPayload`, `PrintingOption`, and `LineItem`.

9. **Q4.2**: We haven't implemented `GET /api/v3/catalog/products` yet. Is this endpoint stable and documented?

   - Can we query all available products / SKUs via API, or only via dashboard?
   - What is the response schema for product queries?

### Category 5: Production Readiness

10. **Q5.1**: Before we cut over to production, what is your recommended validation checklist?

    - Should we do a smoke test with a real product SKU (not DEMO) on sandbox first?
    - Are there any quotas or limits per shop_id we should be aware of?
    - What is the SLA for order fulfillment (how long from push to "shipped" status)?

---

## Summary: Implementation Readiness

| Component | Status | Notes |
|---|---|---|
| **Authentication (HTTP headers)** | READY | Tested; env vars in `.env` |
| **Order push (`POST /api/v3/orders/draft`)** | WORKING (schema correct) | But 400 errors due to unknown printing_options validation (Q1.1–1.3) |
| **Quote fetch (`GET /api/v3/orders/{ref}/price`)** | READY (P4-01-C) | Tested; Money proto decoding working |
| **Order confirm (`POST /api/v3/orders/draft/labeled`)** | READY (P4-01-C) | Tested; idempotency working |
| **Webhook parsing (inbound)** | READY (P0-18b2b) | HMAC verification + nonce replay-protection; event dispatch incomplete (need full payload samples) |
| **Webhook events (`order_shipped`, etc.)** | PARTIAL | One sample captured; others under discovery (Q3.1) |
| **SKU registration** | BLOCKED | Demo SKUs not registered; don't know if pre-registration required (Q2.1) |
| **Catalog query API** | NOT STARTED | No implementation yet (Q4.2) |
| **Production cut-over** | BLOCKED | Cannot certify until printing_options validation is resolved |

**E2E Status**: P4-01-D DONE (code + state machine + UI), but **P4-01-FIX-PRINTING-OPTIONS** + **P4-01-FIX-LOG-LINKAGE** + **P2-FIX-ARCHIVE-FOLDER** defects are active (see `docs/E2E_DEFECTS_2026-05-10.md`).

---

## References

**Gearment Documentation**:
- Overview: https://developers.gearment.com/api/section/overview
- Order API: https://developers.gearment.com/api/api.order.v1.vendororderapi
- Webhook API: https://developers.gearment.com/api/api.webhook.v1.vendorwebhookapi
- Main: https://developers.gearment.com/api

**Our Implementation**:
- Adapter: `custom_addons/multichannel_hub_fulfillment/services/gearment_adapter.py`
- Payload Builder: `custom_addons/multichannel_hub_fulfillment/services/gearment_payload_builder.py`
- Payload Schema: `custom_addons/multichannel_hub_fulfillment/services/gearment_payload.py`
- API Client: `custom_addons/multichannel_hub_fulfillment/services/gearment_api_client.py`
- Audit Log Model: `custom_addons/multichannel_hub_fulfillment/models/gearment_api_log.py`
- Order Model Extension: `custom_addons/multichannel_hub_fulfillment/models/sale_order.py`

**Specs & Planning**:
- Master Plan: `specs/006-master-plan/MASTER_PLAN.md`
- Tracker: `.claude/plans/006-master-plan-tracking.md`
- Fulfillment Research: `specs/004-fulfillment-routing/research.md`
- Fulfillment Findings: `specs/004-fulfillment-routing/findings.md`
- E2E Defects: `docs/E2E_DEFECTS_2026-05-10.md`

**Commits**:
- P4-01-B (schema regen): `ac7915b3710`
- P4-01-D (UI + state machine): `8410d3274a7`
- P4-01-FIX-LOG-LINKAGE: `099f48c1e3d`
- P4-01-FIX-PAYLOAD-SCHEMA: `ac7915b3710`

---

**Document Status**: DRAFT (2026-05-10)  
**Next Action**: Close open questions 1.1–5.1 via Gearment support email; update this document with confirmed values.
