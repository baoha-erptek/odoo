# Feature Specification: Etsy API v3 Channel Integration

**Feature Branch**: `005-etsy-api-channel`
**Created**: 2026-04-09
**Status**: **ACTIVE — Phase 0 (sandbox) + Phase 1 (production cutover)** per [ADR-008 API-first pivot](../006-master-plan/adrs/ADR-008-api-first-pivot.md) — owner sign-off 2026-04-13 (pivot)
**Input**: User description: "Etsy API v3 Channel Integration -- direct order sync, tracking push, listing management, webhooks, OAuth2 PKCE authentication, and rate limit handling. Replaces/supplements email-based order ingestion."

---

> **Active status (2026-04-13 pivot, supersedes earlier Phase 3 deferral)**
>
> Per [ADR-008](../006-master-plan/adrs/ADR-008-api-first-pivot.md), this spec is now the primary ingestion path for all new orders. Email parsing enters maintenance mode for legacy shops only.
>
> **Execution split**:
> - **Phase 0 (now, in parallel with Spec 002 cleanup)**: OAuth2 PKCE scaffolding, `EtsyApiClient`, shared rate limiter, `EtsyOrderSyncer` against owner's **personal developer token** (dev shop only), `etsy.api.log`, VCR-style test fixtures. No production shops touched. US1 + US2 + US5 + US8 scaffolding only.
> - **Phase 1 (after Etsy scopes approved, overlaps with Spec 003 dashboards)**: replace dev token with production OAuth flow, pilot shop runs `sync_audit_mode=True` for 1–2 weeks, BA reviews audit log, flip to `sync_mode='api_only'`. Repeat per shop. US3 (tracking push) wires into the Tracking Dashboard. Target: 3–5 shops cutover by end of Phase 1, remainder in Phase 2.
> - **Phase 2**: remaining 14–16 shops flipped to `api_only`; Gmail cron stops polling live shops; parser frozen.
>
> **Critical-path external dependency**: Etsy app scope review (3–8 weeks). Owner submits this week — see [guides/vi/etsy-app-review-guide.md](../006-master-plan/guides/vi/etsy-app-review-guide.md).
>
> **Structural changes per [ADR-002](../006-master-plan/adrs/ADR-002-drop-dual-sync-mode.md) and [ADR-005](../006-master-plan/adrs/ADR-005-carrier-unification.md)**:
> - `sync_mode` has exactly two values (`email_only`, `api_only`); `dual` is removed. Default for new `etsy.shop` records is `api_only`; existing 19 shops remain `email_only` until per-shop cutover.
> - A new `sync_audit_mode` Boolean drives the 1–2 week read-only audit period during each shop's cutover (API fetches + logs diffs, does not write to `sale.order`).
> - `etsy.carrier.mapping` is **deleted**. Carrier → Etsy enum mapping lives on `shipping.carrier.etsy_carrier_name` (ADR-005).
> - Webhook receiver (US4) downgraded from P1 to P2.
>
> Sections below are preserved for traceability. Any section not rewritten in a later revision is still authoritative for its scope, but `dual` references should be read as removed.

## Clarifications

### Session 2026-04-10

- Q: When a product is changed in both the system and on Etsy between sync cycles, which version wins? -> A: Etsy wins (last-write-wins from Etsy). Local edits push to Etsy only on demand; pull sync overwrites local data with Etsy state.
- Q: When an existing order is re-encountered during API sync with changes on Etsy, which fields should be updated? -> A: Status fields only -- update payment status, shipping status, and cancellation; preserve all operator-entered data (notes, assignments, design status).
- Q: When first connecting via API, should the system back-sync historical email-imported orders for enrichment? -> A: Forward-only -- only sync new orders from the API connection date. Historical enrichment deferred to a separate one-time task if needed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Etsy OAuth2 App Configuration (Priority: P1)

As an administrator, I need to register the Etsy API v3 application credentials in the system and complete the OAuth2 authorization flow with PKCE, so that the system can authenticate with Etsy on behalf of each shop.

**Why this priority**: Without authentication, no API calls can be made. This is the foundational prerequisite for every other user story.

**Independent Test**: Enter the Etsy API key in Settings. Click "Authorize Etsy". Complete the OAuth2 consent flow in the browser. Verify the system stores valid tokens. Wait for token expiry and verify the system auto-refreshes.

**Acceptance Scenarios**:

1. **Given** valid Etsy API credentials entered in Settings, **When** the administrator clicks "Authorize Etsy", **Then** the system redirects to Etsy's consent page with correct PKCE parameters and, on success, stores the access token, refresh token, and expiry timestamp per shop.
2. **Given** a stored access token that has expired (older than 1 hour), **When** any API call is attempted, **Then** the system automatically refreshes the token using the refresh token before proceeding.
3. **Given** a refresh token that has expired (older than 90 days) or been revoked, **When** the system attempts to refresh, **Then** it logs the error, flags the shop in `etsy.sync.health`, and surfaces an admin notification to re-authorize. It does **not** fall back to email (violates single-writer invariant per [ADR-002](../006-master-plan/adrs/ADR-002-drop-dual-sync-mode.md) / [ADR-008](../006-master-plan/adrs/ADR-008-api-first-pivot.md)). Orders placed during the outage are fetched on recovery via incremental sync.
4. **Given** multiple Etsy shops configured in the system, **When** the administrator authorizes each shop, **Then** each shop maintains its own independent set of OAuth2 tokens.
5. **Given** the Settings page, **When** the administrator clicks "Test Connection", **Then** the system verifies the current tokens and displays the connected Etsy user name and shop name.

---

### User Story 2 - Direct Order/Receipt Sync from Etsy API (Priority: P1)

As a shop operator, I want orders to be fetched directly from the Etsy API as structured data, so that order ingestion is reliable and not dependent on email template format stability.

**Why this priority**: This is the core value proposition. Direct API sync eliminates the regex-based email parsing fragility that is the primary risk in the current system (43 regex patterns that break when Etsy changes email templates).

**Independent Test**: Configure a shop with valid tokens. Trigger the API sync. Verify sale orders are created with correct customer, products, line items, prices, shipping costs, and buyer notes matching the Etsy Seller Portal.

**Acceptance Scenarios**:

1. **Given** a configured shop with valid tokens, **When** the order sync runs, **Then** the system fetches new and updated receipts from Etsy using incremental sync (only receipts modified since the last sync) and creates corresponding sale orders. Only orders from the API connection date forward are synced; historical email-imported orders are not back-synced.
2. **Given** an Etsy receipt with multiple items, **When** processed, **Then** a single sale order is created with one line per item, each with correct transaction ID, product name, price, quantity, and variation details (size, color, etc.).
3. **Given** a receipt that already exists in the system (matched by Etsy order ID), **When** encountered during sync, **Then** the existing order is NOT duplicated. Only status fields are updated (payment status, shipping status, cancellation); operator-entered data (notes, assignments, design status) is preserved.
4. **Given** receipt data includes the buyer's email address (available via API but not in email notifications), **When** the order is created, **Then** the customer record stores the email, improving deduplication accuracy over email-parsed orders.
5. **Given** a product from the receipt, **When** the order line is created, **Then** the system matches existing products by Etsy listing ID (more reliable than name matching), falling back to name match for compatibility with legacy email-parsed products.
6. **Given** a shop running `sync_audit_mode=True` during cutover, **When** the API sync runs, **Then** receipt data is fetched and compared against email-parsed records; diffs are written to `etsy.api.log` (source=`audit`) and **no writes** are made to `sale.order`. (Replaces the earlier "dual mode" scenario, removed per [ADR-002](../006-master-plan/adrs/ADR-002-drop-dual-sync-mode.md).)
7. **Given** the API returns an error (authentication failure, rate limit, server error), **When** the sync fails, **Then** the error is logged and the sync retries on the next scheduled cycle.

---

### User Story 3 - Push Tracking Numbers to Etsy (Priority: P1)

As a fulfillment coordinator, I need tracking numbers entered in the system to be automatically pushed to Etsy, so that customers see tracking information in their Etsy purchase history without manual updates on the Etsy portal.

**Why this priority**: Tracking push is the most requested capability that email parsing cannot provide. It directly saves operator time currently spent manually entering tracking on the Etsy Seller Portal for every order.

**Independent Test**: Enter a tracking number on an Etsy sale order. Verify the tracking appears on the corresponding order in Etsy Seller Portal within one sync cycle.

**Acceptance Scenarios**:

1. **Given** an Etsy sale order with a newly added tracking number and carrier, **When** the tracking push runs (automated or manual), **Then** the system sends the tracking code and carrier name to Etsy and the order shows tracking on the Etsy portal.
2. **Given** a successful tracking push, **When** completed, **Then** the push status is recorded as "pushed" with a timestamp on the order.
3. **Given** the push fails (e.g., invalid carrier name), **When** the error occurs, **Then** the status is recorded as "failed" with the error message, and the operator can retry after correcting the issue.
4. **Given** a batch of orders with new tracking numbers (e.g., after a logistics partner Excel import), **When** the tracking push runs, **Then** all pending pushes are processed sequentially, respecting rate limits.
5. **Given** the carrier name in the system does not match an Etsy-supported carrier name, **When** preparing the push, **Then** the system uses a configurable carrier name mapping or flags the order for manual carrier name selection.

---

### User Story 4 - Webhook Receiver for Real-Time Etsy Events (Priority: P2)

As a system administrator, I want the system to receive real-time notifications from Etsy when orders are placed, paid, shipped, or cancelled, so that order data appears within seconds instead of waiting for the next scheduled sync.

**Why this priority**: Webhooks reduce order ingestion latency from minutes (cron-based polling) to near-real-time. Combined with periodic API sync as a safety net, this provides the most reliable and timely order pipeline.

**Independent Test**: Register a webhook for order events. Place a test order on Etsy. Verify the order appears in the system within 60 seconds.

**Acceptance Scenarios**:

1. **Given** a configured shop with valid tokens, **When** the administrator clicks "Register Webhooks", **Then** the system registers subscriptions for key order events (paid, shipped, cancelled, delivered) at the system's callback endpoint.
2. **Given** a registered webhook, **When** Etsy sends an order event, **Then** the system verifies the cryptographic signature, fetches the full receipt data via the API, and creates or updates the sale order.
3. **Given** a webhook with an invalid signature, **When** received, **Then** the system rejects it and logs the invalid attempt for security monitoring.
4. **Given** the webhook processing fails (e.g., database error), **When** the failure occurs, **Then** Etsy's retry mechanism (exponential backoff) redelivers the event, and the system handles retries without creating duplicates.
5. **Given** webhooks are the primary order intake, **When** a webhook delivery fails beyond Etsy's retry window, **Then** the periodic API sync (US2) acts as a safety net and picks up the missed order.

---

### User Story 5 - Rate Limiting and API Resilience (Priority: P1)

As a system administrator, I need the Etsy API integration to respect rate limits and handle failures gracefully, so that the system is not blocked by Etsy and recovers automatically from transient errors.

**Why this priority**: Without proper rate limiting, Etsy returns errors and may throttle or block the application. This is a cross-cutting concern that affects every API operation. The user specifically noted the ~10 requests/second limit.

**Independent Test**: Trigger a batch operation that would exceed 10 requests/second. Verify the system automatically throttles to stay within limits. Simulate an API timeout and verify retry behavior.

**Acceptance Scenarios**:

1. **Given** the system is making API calls, **When** the request rate approaches the per-second limit, **Then** the system inserts appropriate delays to stay within the limit.
2. **Given** the API responds with a "too many requests" error including a retry-after value, **When** received, **Then** the system waits for the specified duration before retrying.
3. **Given** an API call fails with a transient error (server error, timeout), **When** the failure occurs, **Then** the system retries up to 3 times with exponential backoff.
4. **Given** an API call fails with a permanent error (bad request, forbidden, not found), **When** the failure occurs, **Then** the system does NOT retry and logs the error for investigation.
5. **Given** the daily quota is approaching depletion, **When** detected from API response headers, **Then** the system logs a warning and reduces sync frequency to conserve quota.
6. **Given** all API operations, **When** each completes, **Then** the request and response details are logged for debugging and audit purposes, with configurable verbosity.

---

### User Story 6 - Bidirectional Listing/Product Management (Priority: P2)

As a shop owner, I need to manage Etsy product listings from within the system, including creating new listings, updating prices/inventory, and uploading images, so that I do not need to switch to the Etsy Seller Portal for product management.

**Why this priority**: Listing management adds significant operational value but is not blocking order processing. The business can continue managing listings directly on Etsy while the P1 features stabilize.

**Independent Test**: Create a new draft listing from the system with title, description, price, and image. Verify it appears as a draft on the Etsy Seller Portal. Update the price and verify it updates on Etsy.

**Acceptance Scenarios**:

1. **Given** a product marked as an Etsy product, **When** the operator triggers "Push to Etsy", **Then** the system creates a draft listing on Etsy with title, description, price, quantity, and required product attributes.
2. **Given** an existing Etsy listing linked to a product (via Etsy listing ID), **When** the operator updates the price or description and triggers "Push to Etsy", **Then** the change is pushed to Etsy on demand (not automatically, to avoid overwriting Etsy-side edits).
3. **Given** a product with a local image file, **When** the operator triggers image upload, **Then** the image is uploaded to the corresponding Etsy listing.
4. **Given** the "Pull from Etsy" action on a shop, **When** triggered, **Then** the system fetches all active listings from Etsy and creates or updates product records with listing ID, name, description, price, images, and listing state (draft/active/inactive/sold out/expired). Etsy data overwrites local product data during pull sync.
5. **Given** an Etsy listing whose state changes (e.g., sold out), **When** the periodic listing sync runs, **Then** the product's Etsy listing state in the system is updated accordingly.
6. **Given** an Etsy listing with variations (size, color), **When** synced, **Then** the variation details are stored and visible on the product form.
7. **Given** a product modified locally AND on Etsy between sync cycles, **When** the pull sync runs, **Then** Etsy data takes precedence (Etsy is source of truth for live marketplace data). Local-only changes must be explicitly pushed to Etsy to take effect.

---

### User Story 7 - Etsy Customer Messaging (Priority: P3 -- Deferred)

As a customer service representative, I need to see Etsy buyer conversations in the system and reply from within it, so I can manage customer communication without switching to the Etsy portal.

**Why this priority**: Etsy's Conversations API requires explicit app approval for the conversations scope, which is a business process dependency (not a technical one). This story is deferred until Etsy grants the required scope.

**Independent Test**: Deferred.

**Acceptance Scenarios**: Deferred -- will be defined when Etsy app approval for conversations scope is obtained.

---

### User Story 8 - Sync Mode Selection and One-Way Cutover (Priority: P1)

As an administrator, I need to choose the order ingestion method per shop (email-only or API-only) with a read-only audit period during cutover, so that I can migrate from email parsing to API sync one shop at a time with a validation gate and no race conditions.

**Why this priority**: The transition from email to API must be seamless but must NOT run both writers concurrently. Dual-writer mode was rejected per [ADR-002](../006-master-plan/adrs/ADR-002-drop-dual-sync-mode.md) due to unmanageable race conditions and dedup-key mismatches. Cutover is per-shop, one-way, with an audit phase.

**Independent Test**: Set `sync_audit_mode=True` on a shop that is still `email_only`. Verify the API runs read-only and logs per-receipt field diffs to `etsy.api.log` (source=`audit`). Verify no `sale.order` writes occur. Flip to `sync_mode=api_only` and verify email parsing stops for that shop while API sync becomes the single writer.

**Acceptance Scenarios**:

1. **Given** the shop configuration, **When** the administrator sets the sync mode, **Then** the options are exactly two: "Email Only" (legacy) and "API Only" (new). Default for newly-created shops is "API Only"; existing shops remain "Email Only" until cutover.
2. **Given** a shop with `sync_audit_mode=True` (regardless of `sync_mode`), **When** the API client runs, **Then** it fetches receipts and writes comparison diffs to `etsy.api.log` (source=`audit`) — no `sale.order` writes.
3. **Given** `sync_mode='api_only'`, **When** the email fetch runs, **Then** emails from that shop are still fetched and marked processed (prevent backlog) for 30 days post-cutover as a shadow-logging safety net, after which the shop is removed from the Gmail filter entirely.
4. **Given** `sync_mode='api_only'` and the OAuth token becomes invalid, **When** the API sync fails, **Then** the system logs the error, surfaces an admin notification to re-authorize, and flags the shop in `etsy.sync.health`. It does **not** fall back to email (that would re-introduce a second writer).
5. **Given** `sync_mode='api_only'`, **When** an admin attempts to flip back to `email_only`, **Then** the UI requires an explicit "admin override" confirmation (the switch is conceptually one-way).

---

### Edge Cases

- What happens when the Etsy API returns a receipt with a currency other than EUR? The system respects the receipt's currency and sets the order currency accordingly (consistent with multi-currency handling in Spec 002).
- What happens when the Etsy API is down for an extended period (>24 hours)? In `api_only` mode, orders are queued on Etsy's side and fetched on recovery via incremental sync (Etsy preserves order data; `etsy_last_modified` ensures no rows are missed). `etsy.sync.health` raises a warning after 1h of failed syncs and an error after 24h. No email fallback (would violate single-writer invariant per [ADR-002](../006-master-plan/adrs/ADR-002-drop-dual-sync-mode.md)).
- What happens when the webhook endpoint is not reachable from Etsy (e.g., local development, firewall)? The periodic cron sync (US2) acts as the primary source; webhooks are a latency optimization, not a requirement.
- What happens when the shop's Etsy account changes (e.g., shop transferred to new owner)? The OAuth tokens become invalid; the administrator must re-authorize and the system detects the token failure.
- What happens when a listing push fails due to missing required product attributes? The system validates required fields before the API call and presents a clear error listing which fields are missing.
- What happens when the PKCE authorization code is lost between the redirect and the callback? The code verifier is stored server-side and retrieved during the callback using a state parameter.
- What happens to historical orders imported via email when API sync is first enabled? They remain as-is. The API sync starts from the connection date forward. Historical enrichment (adding buyer email, listing IDs to old orders) is a separate one-time task, not part of ongoing sync.
- What happens when a listing conflict occurs (changed in both the system and on Etsy)? Etsy data wins on pull sync. Local edits must be explicitly pushed to override Etsy state.

## Requirements *(mandatory)*

### Functional Requirements

#### OAuth2 and Authentication

- **FR-001**: System MUST implement Etsy OAuth2 with PKCE (Proof Key for Code Exchange with SHA-256 challenge method)
- **FR-002**: System MUST store access token, refresh token, and token expiry per shop
- **FR-003**: System MUST auto-refresh expired access tokens transparently before API calls
- **FR-004**: System MUST alert the administrator when the refresh token expiry approaches (7 days before the 90-day limit)
- **FR-005**: System MUST provide a "Test Connection" action that verifies API credentials and displays the connected Etsy user and shop name
- **FR-006**: System MUST store the Etsy numeric shop ID on the shop record after initial authorization (resolved from the API user profile)

#### Order Sync

- **FR-007**: System MUST sync orders via Etsy's receipt listing endpoint using incremental sync (only receipts modified since last sync timestamp). Initial sync starts from the API connection date (forward-only; no historical back-sync)
- **FR-008**: System MUST create sale orders with all receipt fields mapped, including buyer email, item details, prices, shipping costs, buyer notes, and gift messages
- **FR-009**: System MUST deduplicate orders by Etsy order ID (consistent with existing unique constraint). On re-sync, only update status fields (payment, shipping, cancellation); preserve operator-entered data
- **FR-010**: System MUST handle pagination for receipt listing (Etsy uses offset + limit, max 100 per page)
- **FR-011**: System MUST record the sync source on each order (email, API, or webhook) for diagnostics
- **FR-012**: System MUST support a configurable sync interval (default: 5 minutes, separate from the email polling cron)
- **FR-013**: System MUST support a sync mode per shop: exactly two values — `email_only` or `api_only`. Default for new `etsy.shop` records is `api_only`. The switch is one-way (admin override required to revert). A separate `sync_audit_mode` Boolean enables a 1–2 week read-only audit phase during which the API client runs, logs comparison diffs, and does NOT write to `sale.order` ([ADR-002](../006-master-plan/adrs/ADR-002-drop-dual-sync-mode.md)).

#### Tracking Push

- **FR-014**: System MUST push tracking numbers to Etsy using the receipt tracking endpoint with tracking code and carrier name
- **FR-015**: System MUST read the Etsy carrier name from `shipping.carrier.etsy_carrier_name` (ADR-005). The standalone `etsy.carrier.mapping` model is removed. Orders whose carrier has no matching Etsy enum push with `other` and log a warning to `etsy.api.log`.
- **FR-016**: System MUST track push status per order (none, pending, pushed, failed) with timestamps and error messages
- **FR-017**: System MUST process tracking pushes in batch via a scheduled job, respecting rate limits

#### Webhooks

- **FR-018**: System MUST provide a webhook callback endpoint accessible from the internet
- **FR-019**: System MUST verify HMAC-SHA256 signatures on incoming webhooks using the application shared secret
- **FR-020**: System MUST handle webhook events: order paid, order shipped, order cancelled, order delivered
- **FR-021**: System MUST support registering and deregistering webhook subscriptions via the Etsy API
- **FR-022**: Webhook processing MUST be idempotent (safe to process the same event multiple times without side effects)

#### Rate Limiting

- **FR-023**: System MUST enforce a per-second request limit (configurable, default ~10 requests/second as per Etsy documentation)
- **FR-024**: System MUST respect "too many requests" responses and wait for the retry-after duration before retrying
- **FR-025**: System MUST implement exponential backoff for transient errors (up to 3 retries)
- **FR-026**: System MUST NOT retry permanent errors (bad request, forbidden, not found)
- **FR-027**: System MUST monitor and log daily quota consumption from API response headers

#### Listing Management

- **FR-028**: System MUST link products to Etsy listings via a unique Etsy listing ID field
- **FR-029**: System MUST support creating draft listings on Etsy from product records
- **FR-030**: System MUST support updating listing price, title, description, and quantity from the system via on-demand push (not automatic). Etsy is source of truth during pull sync; local edits require explicit push to take effect
- **FR-031**: System MUST support uploading product images to Etsy listings
- **FR-032**: System MUST support pulling all active listings from Etsy into product records
- **FR-033**: System MUST track Etsy listing state (draft, active, inactive, sold out, expired) on the product

#### API Logging

- **FR-034**: System MUST log all API calls with endpoint, method, status code, response time, and error messages
- **FR-035**: System MUST support configurable log retention (default: 30 days with automatic cleanup of older records)

### Key Entities

- **Etsy Shop** (extended): API credentials, OAuth2 tokens, `sync_mode` (`email_only` | `api_only`, default `api_only`), `sync_audit_mode` (Boolean), and sync timestamps. Related to sale orders and products.
- **Sale Order** (extended): Tracking push status, sync source indicator, and last-modified timestamp from Etsy for incremental sync.
- **Product** (extended): Etsy listing ID for reliable product matching; listing state tracking.
- **API Call Log** (`etsy.api.log`): Audit trail for every Etsy API request/response (including `source='audit'` rows produced during `sync_audit_mode`).
- **Webhook Event** (`etsy.webhook.event`, P2): Received webhook records with signature verification status and processing outcome.
- **Sync Health** (`multichannel.sync.health`, formerly `etsy.sync.health` — see Spec 002 R8 / ADR-003): Single row per integration (`etsy_api_sync`, `etsy_tracking_push`) tracking last run, row count, error count.
- ~~Carrier Name Mapping~~ — **removed** per [ADR-005](../006-master-plan/adrs/ADR-005-carrier-unification.md). Etsy enum mapping moved to `shipping.carrier.etsy_carrier_name`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: API-synced orders contain all fields present in email-parsed orders, plus additional data (buyer email, listing ID) that email parsing cannot provide
- **SC-002**: During a shop's `sync_audit_mode` phase (1–2 weeks), ≥99.5% field match between email-parsed and API-fetched data on critical fields (`amount_total`, line items, shipping address). Diffs logged to `etsy.api.log` (source=`audit`) and reviewed by BA before flipping to `api_only`.
- **SC-003**: Tracking numbers pushed to Etsy within 5 minutes of being entered in the system (within a single sync cycle)
- **SC-004**: Webhook-delivered orders appear in the system within 60 seconds of the Etsy event
- **SC-005**: The system processes 500+ orders per sync cycle without exceeding rate limits or timing out
- **SC-006**: Token refresh operates transparently with zero manual intervention during the 90-day refresh token validity period
- **SC-007**: When the Etsy API is unavailable for 24+ hours, `etsy.sync.health` raises an error tile (warning at 1h, error at 24h); orders placed during the outage are retained on Etsy's side and fetched on recovery via incremental sync (`etsy_last_modified` checkpoint). No email fallback per [ADR-008](../006-master-plan/adrs/ADR-008-api-first-pivot.md).
- **SC-008**: All API calls are logged and queryable for troubleshooting, with logs auto-cleaned after the retention period
- **SC-009**: Operators save at least 2 hours per day by eliminating manual tracking entry on the Etsy Seller Portal

## Assumptions

- The Etsy developer account and API key have been registered at Etsy's developer portal before implementation begins
- The Etsy app has been granted the required scopes: transactions (read/write), listings (read/write), shops (read), email (read). **Scope review submission is a Phase 0 task** (master plan §7). Implementation of this spec starts only after approval (typical 3–8 weeks).
- The Conversations API scope is NOT available (requires separate Etsy approval); customer messaging (US7) is deferred
- Spec 003 (sales channel field on sale orders) is implemented before or concurrently, so API-synced orders can be tagged as "etsy" channel
- Spec 004 (tracking number fields and carrier model) provides the tracking data that this spec pushes to Etsy
- The server is accessible from the internet (or via a tunnel/proxy) for webhook delivery; if not, webhooks are optional and cron-based sync is sufficient
- The existing order creation service can be extended to accept API-sourced data alongside email-parsed data
- Etsy API v3 will remain stable during implementation; breaking changes are announced in advance
- The standard HTTP client library already used for Gmail API calls is sufficient for Etsy API calls

## Out of Scope

- **Amazon SP-API connector** -- separate future spec
- **WooCommerce/Website connector** -- separate future spec
- **Etsy Conversations API** (messaging) -- deferred until Etsy app approval for conversations scope
- **Etsy Financial API** (payment ledger, disbursements) -- not needed for current operations
- **Etsy Shipping Labels API** -- labels are managed via logistics partners (Spec 004)
- **Full product variant management** (product attributes/variants in the system) -- stores variation data as text fields consistently with existing approach
- **Multi-channel inventory sync / overselling prevention** -- future spec
- **Automated proactive token rotation** beyond refresh-on-expiry

## Dependencies

| This Spec Needs | From | Why |
|-----------------|------|-----|
| Sales channel field on sale orders | Spec 003 | API-synced orders need channel tagging |
| Channel order reference field | Spec 003 | Store Etsy receipt ID generically |
| Tracking number fields on sale orders | Spec 004 | Tracking push reads from these fields |
| Carrier model | Spec 004 | Carrier name mapping builds on this |

| Other Specs Need From This | What |
|----------------------------|------|
| Spec 004 (partner tracking push) | The tracking pusher service can be called after partner callbacks write tracking |
| Spec 004 (CRM messaging) | The API client provides authenticated access; conversations endpoint added when scope is granted |
| Future channel connectors | The API client pattern and logging model serve as architectural templates |
