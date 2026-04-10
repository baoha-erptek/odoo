# Research: Etsy API v3 Channel Integration

**Feature**: 005-etsy-api-channel | **Date**: 2026-04-10

## R1: Etsy OAuth2 with PKCE

**Decision**: Implement OAuth2 Authorization Code Grant with PKCE (SHA-256) per Etsy's mandatory requirement.

**Rationale**: Etsy v3 API requires PKCE for all OAuth2 flows. No alternative authentication method is available for accessing private shop data.

**Key Details**:
- Authorization URL: `https://www.etsy.com/oauth/connect`
- Token URL: `https://api.etsy.com/v3/public/oauth/token`
- Grant type: `authorization_code` (initial) + `refresh_token` (renewal)
- PKCE: Generate 43-128 char `code_verifier`, compute `code_challenge = base64url(sha256(code_verifier))`, send `code_challenge_method=S256`
- Access token: expires 3600 seconds (1 hour)
- Refresh token: valid 90 days, single-use (new refresh token issued on each use)
- Required scopes: `transactions_r transactions_w listings_r listings_w shops_r email_r`
- All API requests require `x-api-key` header with the application's keystring

**Alternatives Considered**:
- API key only: Insufficient for private shop data (read-only public access)
- OAuth2 without PKCE: Not supported by Etsy v3

**Implementation Pattern**: Reuse existing `controllers/oauth.py` state-nonce CSRF pattern. Store `code_verifier` in `ir.config_parameter` (same as current `oauth_state` pattern). New callback route: `/etsy/api/oauth/callback`.

---

## R2: Receipt/Order Sync Strategy

**Decision**: Incremental sync via `GET /v3/application/shops/{shop_id}/receipts` with `min_last_modified` parameter. Forward-only from connection date.

**Rationale**: Incremental sync minimizes API calls (respects rate limits) while ensuring no orders are missed. Forward-only avoids conflicting with 17,659+ historical email-imported orders.

**Key Details**:
- Endpoint: `GET /v3/application/shops/{shop_id}/receipts`
- Auth scope: `transactions_r`
- Pagination: `offset` + `limit` (max 100 per page)
- Filter: `was_paid=true`, `min_last_modified={unix_timestamp}`
- Receipt fields map directly to existing sale.order fields (see data-model.md)
- Each receipt contains `transactions[]` array (one per order line item)
- Buyer email available via API (not available in email notifications)
- Product matching: by `listing_id` (new field) with fallback to name match

**Receipt-to-Order Field Mapping**:

| Etsy Receipt Field | Odoo Field | Notes |
|---|---|---|
| receipt_id | sale.order.etsy_order_id | Primary dedup key |
| buyer_email | res.partner.email | New data source |
| name (shipping) | res.partner.name | Shipping recipient |
| formatted_address | res.partner address fields | Parsed from sub-fields |
| transactions[].transaction_id | sale.order.line.etsy_transaction_id | Line dedup |
| transactions[].title | product.product.name | Product name |
| transactions[].listing_id | product.product.etsy_listing_id | New: reliable match |
| transactions[].price.amount/divisor | sale.order.line.price_unit | Computed: amount/divisor |
| transactions[].quantity | sale.order.line.product_uom_qty | |
| transactions[].variations[] | sale.order.line.etsy_color/size/option | Variant text |
| grandtotal.amount/divisor | sale.order.etsy_subtotal | |
| total_shipping_cost.amount/divisor | sale.order.etsy_shipping_cost | |
| discount_amt.amount/divisor | (discount handling) | |
| message_from_buyer | sale.order.etsy_note_from_buyer | |
| is_gift + gift_message | sale.order.etsy_gift_message | |
| create_timestamp | sale.order.date_order | Unix -> Datetime |
| update_timestamp | sale.order.etsy_last_modified | For incremental sync |
| status | (order status mapping) | paid/completed/etc. |
| currency_code | sale.order.currency_id | ISO 4217 lookup |

**Alternatives Considered**:
- Full sync (fetch all receipts every cycle): Excessive API calls, hits rate limits
- Back-sync historical orders: Risk of conflicts with operator-annotated data, rate limit issues

---

## R3: Tracking Push to Etsy

**Decision**: Batch push via dedicated cron using `POST /v3/application/shops/{shop_id}/receipts/{receipt_id}/tracking`.

**Rationale**: Decoupled cron allows batch processing with rate limit respect. Push status tracking enables retry on failure.

**Key Details**:
- Endpoint: `POST /v3/application/shops/{shop_id}/receipts/{receipt_id}/tracking`
- Auth scope: `transactions_r transactions_w`
- Required fields: `tracking_code` (string), `carrier_name` (string)
- Etsy supports 400+ carrier names (must match exactly)
- Push triggers Etsy to send buyer notification email and finalize transaction totals
- Carrier name mapping needed: system carrier names may differ from Etsy carrier names

**Carrier Mapping Examples**:

| System Name | Etsy carrier_name |
|-------------|-------------------|
| USPS | usps |
| FedEx | fedex |
| UPS | ups |
| DHL | dhl |
| UniUni | other |
| YunExpress | other |

**Alternatives Considered**:
- Real-time push on tracking field write: Risky (write could fail, no rate limit control)
- Manual push only: Misses batch efficiency after logistics Excel imports

---

## R4: Webhook Implementation

**Decision**: HTTP controller at `/etsy/webhook/callback` with HMAC-SHA256 signature verification. Webhooks supplement (not replace) cron-based sync.

**Rationale**: Webhooks provide near-real-time order notifications (<60s) while cron sync acts as a safety net for missed deliveries. Etsy's retry mechanism (exponential backoff up to 10h) provides resilience.

**Key Details**:
- Events: `order.paid`, `order.shipped`, `order.canceled`, `order.delivered`
- Payload: `{"event_type": "...", "resource_url": "...", "shop_id": "..."}`
- Payload does NOT contain full order data -- follow-up API call needed
- Signature verification:
  1. Concatenate: `{webhook-id}.{webhook-timestamp}.{raw_body}`
  2. Base64-decode the webhook secret (remove `whsec_` prefix)
  3. HMAC-SHA256 of concatenated string with decoded secret
  4. Base64-encode result, compare with `webhook-signature` header
- Registration: via Etsy Developer Portal webhook management (not API endpoint)
- Retry schedule: immediate, 5s, 5m, 30m, 2h, 5h, 10h, 10h

**Controller Pattern**:
- Route: `@http.route('/etsy/webhook/callback', type='json', auth='none', csrf=False, methods=['POST'])`
- `auth='none'` because webhooks cannot authenticate as Odoo users
- `type='json'` for automatic JSON body parsing
- Signature verified before any processing

**Alternatives Considered**:
- Polling only (no webhooks): Works but 5-10 minute latency
- Webhooks only (no cron sync): Too risky -- missed webhooks would mean lost orders

---

## R5: Rate Limiting Strategy

**Decision**: In-memory token bucket rate limiter in EtsyApiClient. Read response headers to track remaining quota.

**Rationale**: Token bucket is simple, effective, and requires no external dependencies. Response header monitoring provides early warning for daily quota depletion.

**Key Details**:
- Etsy rate limits: QPS (queries per second) + QPD (queries per day)
- QPS checked first, then QPD. Exceeding either returns HTTP 429.
- Response headers:
  - `x-limit-per-second`: Total QPS allocation
  - `x-remaining-this-second`: Remaining in current second
  - `x-limit-per-day`: Total QPD allocation
  - `x-remaining-today`: Remaining in 24h window
- QPD uses sliding window algorithm (rolling 24h, not midnight reset)
- HTTP 429 response includes `retry-after` header (seconds to wait)
- Default safe limit: 8 req/sec (80% of typical 10 QPS allocation, leaving headroom)

**Retry Strategy**:
- Transient errors (500, 502, 503, timeout): Retry up to 3 times with exponential backoff (2s, 8s, 32s)
- Rate limit (429): Wait `retry-after` seconds, then retry once
- Permanent errors (400, 401, 403, 404): No retry, log and raise

**Alternatives Considered**:
- External rate limiter (Redis): Overkill for single-process Odoo worker
- Fixed delay between requests: Wastes time when under limit
- No rate limiting: Risk of account suspension

---

## R6: Listing Sync Strategy

**Decision**: Pull-dominant with explicit push. Etsy is source of truth for marketplace data. Local edits require manual "Push to Etsy" action.

**Rationale**: Etsy is the live marketplace; operators making Etsy-side edits react to market conditions. Auto-pushing local changes could cause pricing errors visible to buyers.

**Key Details**:
- Pull sync: `GET /v3/application/shops/{shop_id}/listings/active` for all active listings
- Push (on demand): `PATCH /v3/application/shops/{shop_id}/listings/{listing_id}`
- Create draft: `POST /v3/application/shops/{shop_id}/listings` (requires taxonomy_id, who_made, when_made, is_supply)
- Image upload: `POST /v3/application/shops/{shop_id}/listings/{listing_id}/images` (binary multipart)
- Listing states: draft, active, inactive, sold_out, expired
- Auth scopes: `listings_r`, `listings_w`

**Listing Field Mapping**:

| Etsy Listing Field | Odoo Field | Notes |
|---|---|---|
| listing_id | product.template.etsy_listing_id | Primary match key |
| title | product.template.name | |
| description | product.template.description_sale | |
| price.amount/divisor | product.template.list_price | |
| quantity | product.product.qty_available | Approximation |
| state | product.template.etsy_listing_state | Selection field |
| taxonomy_id | product.template.etsy_taxonomy_id | Required for push |
| who_made | product.template.etsy_who_made | Required for push |
| when_made | product.template.etsy_when_made | Required for push |
| images[0].url_570xN | product.template.image_1920 | Primary image |

**Alternatives Considered**:
- Bidirectional auto-sync: Risk of data ping-pong and marketplace corruption
- Push-only: Operators often edit on Etsy directly; pull ensures Odoo stays current

---

## R7: Sync Mode Transition

**Decision**: Per-shop `sync_mode` selection field with three states: `email_only`, `api_only`, `dual`. Default for existing shops: `email_only` (no disruption). New shops: `dual`.

**Rationale**: Gradual transition prevents data loss. Dual mode proves API reliability before cutting over. Automatic fallback from API to email on token failure provides safety net.

**Key Details**:
- `email_only`: Current behavior, email cron processes this shop's emails
- `api_only`: API cron syncs orders, email cron marks emails as processed but does not create orders
- `dual`: Both crons active, dedup by etsy_order_id prevents duplicates
- Fallback: If API auth fails in `api_only` mode, auto-switch to `dual` and notify admin
- Migration path: email_only -> dual (validate) -> api_only (once confident)

**Alternatives Considered**:
- Global switch (all shops same mode): Too risky for multi-shop operations
- Automatic mode detection: Complexity without clear benefit

---

## R8: EtsyApiClient Architecture

**Decision**: Standalone Python class following the GmailClient pattern. No ORM dependency. Handles auth, rate limiting, retries, and logging internally.

**Rationale**: Keeps the service testable without Odoo infrastructure. Consistent with existing architecture (8.5/10 separation of concerns rating from investigation report).

**Key Interface**:
```
EtsyApiClient(api_key, shared_secret, access_token, refresh_token, token_expiry)
  .authenticate() -> bool
  .refresh_access_token() -> bool
  .test_connection() -> tuple[bool, str]
  .get_shop_receipts(shop_id, min_last_modified, limit, offset) -> dict
  .get_receipt(shop_id, receipt_id) -> dict
  .create_receipt_shipment(shop_id, receipt_id, tracking_code, carrier_name) -> dict
  .get_shop_listings(shop_id, state, limit, offset) -> dict
  .create_draft_listing(shop_id, listing_data) -> dict
  .update_listing(shop_id, listing_id, listing_data) -> dict
  .upload_listing_image(shop_id, listing_id, image_data) -> dict
  ._request(method, endpoint, **kwargs) -> dict  # Central request handler
```

**Internal Concerns**:
- `_request()` handles: Bearer token header, x-api-key header, rate limiting (token bucket), retry with backoff, response header parsing (quota tracking), error classification (transient vs permanent), request/response logging
- Token refresh is transparent: if 401 received, attempt refresh once, then retry original request

**Alternatives Considered**:
- Etsy Python SDK: None officially supported; third-party SDKs are unmaintained
- requests.Session with auth hooks: Less control over retry/rate limit behavior
