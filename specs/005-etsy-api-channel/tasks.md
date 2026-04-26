# Tasks: Etsy API v3 Channel Integration

**Feature Branch**: `005-etsy-api-channel` | **Date**: 2026-04-26
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Data Model**: [data-model.md](data-model.md) | **Research**: [research.md](research.md) | **Quickstart**: [quickstart.md](quickstart.md)

> **Execution split (per ADR-008 pivot)**:
> - **Phase 0 (sandbox, NOW)**: US1 + US2 + US5 + US8 scaffolding against the owner's personal developer token. Dev shop only. No production shops touched. Maps to Phases 1–6 below.
> - **Phase 1 (after Etsy scope approval)**: Production OAuth flow + per-shop `sync_audit_mode` validation → `api_only` cutover. US3 wires tracking push to the Tracking Dashboard. Maps to Phase 7 below.
> - **Phase 2 (rollout completion)**: Remaining shops cut over; webhooks (US4) and listings (US6) implemented. Maps to Phases 8–9 below.
>
> **Authoritative invariants (override data-model.md where it disagrees)**:
> - `sync_mode` has exactly two values: `email_only`, `api_only`. `dual` is removed (ADR-002).
> - `sync_audit_mode` is a separate Boolean used during the 1–2 week read-only validation phase.
> - `etsy.carrier.mapping` is **NOT** created. Carrier → Etsy enum lives on `shipping.carrier.etsy_carrier_name` (ADR-005). Tasks below skip the standalone mapping model.
> - US7 (Conversations / Messaging) is deferred until Etsy approves the conversations scope. No tasks in this file.

---

## Phase 1: Setup (project initialization)

- [ ] T001 Bump module version to `19.0.2.0.0` and add `requests` to dependencies in `custom_addons/etsy_integration/__manifest__.py`
- [ ] T002 Update module `description` and feature list in `custom_addons/etsy_integration/__manifest__.py` to reflect API v3 channel integration alongside legacy email parsing
- [ ] T003 [P] Add new model imports (`etsy_api_log`, `etsy_webhook_event`) to `custom_addons/etsy_integration/models/__init__.py`
- [ ] T004 [P] Add new service imports (`etsy_api_client`, `etsy_order_syncer`, `etsy_tracking_pusher`, `etsy_listing_syncer`) to `custom_addons/etsy_integration/services/__init__.py`
- [ ] T005 [P] Add new controller import (`webhook`) to `custom_addons/etsy_integration/controllers/__init__.py`
- [ ] T006 [P] Create VCR-style test fixtures directory `custom_addons/etsy_integration/tests/fixtures/etsy_api/` and add a sandbox fixture loader helper in `custom_addons/etsy_integration/tests/fixtures/__init__.py`
- [ ] T007 Register new data files (`ir_cron_data.xml` updates), view files, and security entries in the `data` and `depends` lists of `custom_addons/etsy_integration/__manifest__.py`

---

## Phase 2: Foundational (blocking prerequisites for ALL user stories)

**Purpose**: Models, ACLs, audit-trail infrastructure, and the empty `EtsyApiClient` shell that every story will build on. **Must complete before any user story phase begins.**

- [ ] T008 Create new model `etsy.api.log` (fields: `name` compute, `etsy_shop_id`, `endpoint`, `http_method`, `status_code`, `request_summary`, `response_summary`, `error_message`, `duration_ms`, `quota_remaining_second`, `quota_remaining_day`, `source` selection [`api`, `webhook`, `audit`]) in `custom_addons/etsy_integration/models/etsy_api_log.py`
- [ ] T009 [P] Create tree/form/search views and a top-level menu under "Etsy > API Logs" in `custom_addons/etsy_integration/views/etsy_api_log_views.xml`
- [ ] T010 [P] Add ACL rows for `etsy.api.log` (read-only for users, full for managers) in `custom_addons/etsy_integration/security/ir.model.access.csv`
- [ ] T011 [P] Add record rules restricting `etsy.api.log` to the user's allowed shops in `custom_addons/etsy_integration/security/etsy_security.xml`
- [ ] T012 Create skeleton `EtsyApiClient` class with constructor `(api_key, shared_secret, access_token, refresh_token, token_expiry, env=None)` and stub `_request()`, `_log_call()`, `authenticate()`, `refresh_access_token()`, `test_connection()` methods in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T013 [P] Add unit-test scaffold `EtsyApiClientTestCase` (pytest) hitting recorded fixtures from `tests/fixtures/etsy_api/` in `custom_addons/etsy_integration/tests/test_etsy_api_client.py`
- [ ] T014 [P] Extend `etsy.shop` with API credential fields (`etsy_numeric_shop_id`, `etsy_api_key`, `etsy_shared_secret`, `etsy_access_token`, `etsy_refresh_token`, `etsy_token_expiry`, `etsy_refresh_token_expiry`, `webhook_secret`, `api_connection_date`, `api_sync_interval`, `last_receipt_sync`, `last_listing_sync`) — all credential fields gated by `groups='base.group_system'` — in `custom_addons/etsy_integration/models/etsy_shop.py`
- [ ] T015 [P] Add `etsy_sync_source` (Selection: `email`, `api`, `webhook`) and `etsy_last_modified` (Datetime, indexed) to `sale.order` in `custom_addons/etsy_integration/models/sale_order.py`

---

## Phase 3: User Story 1 — Etsy OAuth2 App Configuration (P1, sandbox)

**Story Goal**: Administrator can register Etsy API credentials and complete the OAuth2 PKCE authorization flow per shop; tokens auto-refresh transparently.

**Independent Test (per spec)**: Enter Etsy API key in Settings → Click "Authorize Etsy" → Complete OAuth consent in browser → Verify tokens stored → Wait for token expiry and verify auto-refresh.

- [ ] T016 [US1] Add `res.config.settings` fields `etsy_api_key`, `etsy_api_shared_secret`, `etsy_api_sync_interval`, `etsy_api_log_level`, `etsy_api_log_retention_days` mapped to `ir.config_parameter` keys in `custom_addons/etsy_integration/models/res_config_settings.py`
- [ ] T017 [US1] Add settings UI section "Etsy API Configuration" with the new fields and "Authorize" / "Test Connection" buttons to `custom_addons/etsy_integration/views/res_config_settings_views.xml`
- [ ] T018 [US1] Implement PKCE helper `generate_pkce_pair()` (43-128 char verifier, SHA-256 challenge) and `build_authorize_url(shop, redirect_uri, scopes)` in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T019 [US1] Implement `action_start_etsy_oauth()` on `etsy.shop` that stores `code_verifier` + `state` in `ir.config_parameter` and returns a redirect to Etsy's `/oauth/connect` URL in `custom_addons/etsy_integration/models/etsy_shop.py`
- [ ] T020 [US1] Add OAuth callback route `/etsy/api/oauth/callback` that validates the `state` nonce, exchanges the `code` + `code_verifier` for tokens, persists tokens onto `etsy.shop`, and resolves `etsy_numeric_shop_id` via `GET /v3/application/users/me` in `custom_addons/etsy_integration/controllers/oauth.py`
- [ ] T021 [US1] Implement `EtsyApiClient.refresh_access_token()` (single-use refresh, updates `etsy_token_expiry` and rolls `etsy_refresh_token_expiry` 90 days forward) and a transparent 401-then-refresh-then-retry path inside `_request()` in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T022 [US1] Add `_refresh_etsy_token()` and `_get_etsy_client()` factory methods on `etsy.shop` so callers receive an `EtsyApiClient` pre-loaded with the latest tokens in `custom_addons/etsy_integration/models/etsy_shop.py`
- [ ] T023 [US1] Implement `action_test_etsy_connection()` on `etsy.shop` that calls `EtsyApiClient.test_connection()` and surfaces the connected user/shop name via `display_notification` in `custom_addons/etsy_integration/models/etsy_shop.py`
- [ ] T024 [US1] Add a 7-day-before-refresh-expiry warning that flips `multichannel.sync.health` (entry `etsy_api_sync`) into a warning state in `custom_addons/etsy_integration/models/etsy_shop.py`
- [ ] T025 [P] [US1] Add integration test `test_oauth_pkce_flow` exercising authorize URL generation, callback exchange (mocked HTTP), and refresh-on-expiry in `custom_addons/etsy_integration/tests/test_etsy_oauth.py`
- [ ] T026 [P] [US1] Add integration test `test_token_refresh_failure_flags_health` verifying that an expired/revoked refresh token logs an error, sets the shop unhealthy, and does NOT fall back to email in `custom_addons/etsy_integration/tests/test_etsy_oauth.py`

**Story 1 Checkpoint**: Tokens persisted per shop. Auto-refresh works. Test Connection displays shop name. Refresh failure surfaces in `multichannel.sync.health`. **No production shops touched** — sandbox dev token only.

---

## Phase 4: User Story 5 — Rate Limiting and API Resilience (P1, sandbox)

**Story Goal**: Every API operation respects Etsy's QPS/QPD limits and recovers from transient failures via exponential backoff.

**Independent Test (per spec)**: Trigger a batch operation that would exceed 10 req/sec → verify auto-throttling. Simulate API timeout → verify retries.

- [ ] T027 [US5] Implement an in-memory token-bucket rate limiter (`_qps_bucket` capacity=8, refill=8/sec, configurable) in `EtsyApiClient._request()` in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T028 [US5] Parse `x-limit-per-second`, `x-remaining-this-second`, `x-limit-per-day`, `x-remaining-today` response headers and persist last observed values into `etsy.api.log` rows in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T029 [US5] Implement HTTP 429 handling: read `retry-after` header, sleep, retry once in `EtsyApiClient._request()` in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T030 [US5] Implement exponential backoff for transient errors (500/502/503/timeout): up to 3 retries at 2s/8s/32s; permanent errors (400/401/403/404) raise immediately without retry in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T031 [US5] Implement `_log_call()` writing every request/response (with truncated bodies, duration_ms, quota headers) to `etsy.api.log` and respecting the `etsy_api_log_level` setting in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T032 [US5] Add a daily-quota warning hook: when `x-remaining-today` < 10% of `x-limit-per-day`, flip `multichannel.sync.health` into warning and log to `etsy.api.log` in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T033 [US5] Create scheduled action "Etsy: Cleanup API Logs" (daily) calling `_cron_cleanup_api_logs()` that deletes `etsy.api.log` rows older than `etsy_api_log_retention_days` (default 30) in `custom_addons/etsy_integration/data/ir_cron_data.xml`
- [ ] T034 [US5] Implement `_cron_cleanup_api_logs()` on `etsy.api.log` using batched `unlink` to avoid long transactions in `custom_addons/etsy_integration/models/etsy_api_log.py`
- [ ] T035 [P] [US5] Unit test `test_rate_limiter_throttles_above_qps` verifying token-bucket prevents >8 req/sec in `custom_addons/etsy_integration/tests/test_etsy_api_client.py`
- [ ] T036 [P] [US5] Unit test `test_429_retry_after_respected` and `test_transient_500_retries_3_times` and `test_permanent_404_no_retry` in `custom_addons/etsy_integration/tests/test_etsy_api_client.py`

**Story 5 Checkpoint**: Rate limiter caps QPS. 429s wait `retry-after`. Transient errors backed off; permanent errors raise. All calls logged. Cleanup cron prunes old logs.

---

## Phase 5: User Story 8 — Sync Mode Selection and One-Way Cutover (P1, sandbox)

**Story Goal**: Per-shop `sync_mode` with exactly two values plus a separate `sync_audit_mode` Boolean for the 1–2 week read-only validation period (ADR-002).

**Independent Test (per spec)**: Set `sync_audit_mode=True` on an `email_only` shop → verify API runs read-only and writes per-receipt diffs to `etsy.api.log` (source=`audit`) → verify zero `sale.order` writes. Flip to `sync_mode='api_only'` → verify email parsing stops and API becomes single writer.

- [ ] T037 [US8] Add `sync_mode` Selection field with options `[('email_only', 'Email Only'), ('api_only', 'API Only')]`, default `api_only` for new records, and `sync_audit_mode` Boolean default `False` to `etsy.shop` in `custom_addons/etsy_integration/models/etsy_shop.py`
- [ ] T038 [US8] Add a migration helper that ensures all 19 existing shops keep `sync_mode='email_only'` on upgrade (do NOT auto-flip live shops) in `custom_addons/etsy_integration/models/etsy_shop.py` (post-init hook in `__manifest__.py`)
- [ ] T039 [US8] Add UI field group "Sync Mode" on the shop form with the two-value selector and the `sync_audit_mode` toggle, plus a help tooltip explaining the audit period in `custom_addons/etsy_integration/views/etsy_shop_views.xml`
- [ ] T040 [US8] Implement an `admin_override` confirmation wizard that gates flips from `api_only` back to `email_only` (button on shop form opens wizard requiring typed confirmation) in `custom_addons/etsy_integration/wizards/etsy_sync_mode_revert_wizard.py` and matching view
- [ ] T041 [US8] Update the existing email-fetch cron (legacy parser entrypoint) to skip orders where the shop is `api_only` AND outside the 30-day shadow window post-cutover, but still mark emails as processed in `custom_addons/etsy_integration/models/sale_order.py`
- [ ] T042 [US8] Add `_record_audit_diff(receipt, existing_order)` helper that writes `source='audit'` rows to `etsy.api.log` comparing critical fields (`amount_total`, line items, shipping address) when `sync_audit_mode=True` in `custom_addons/etsy_integration/services/etsy_order_syncer.py`
- [ ] T043 [P] [US8] Integration test `test_sync_mode_only_two_values` (asserts no `dual` option in selection) in `custom_addons/etsy_integration/tests/test_sync_mode.py`
- [ ] T044 [P] [US8] Integration test `test_audit_mode_writes_diffs_no_orders` (sync_audit_mode=True writes audit log rows but creates zero `sale.order`) in `custom_addons/etsy_integration/tests/test_sync_mode.py`
- [ ] T045 [P] [US8] Integration test `test_revert_to_email_requires_admin_override` in `custom_addons/etsy_integration/tests/test_sync_mode.py`

**Story 8 Checkpoint**: Two-value selection enforced. Audit mode logs diffs without writing orders. Admin override gates the one-way flip back.

---

## Phase 6: User Story 2 — Direct Order/Receipt Sync (P1, sandbox MVP)

**Story Goal**: Orders fetched directly from the Etsy API via incremental sync; existing orders update status fields only.

**Independent Test (per spec)**: Configure shop with valid tokens → trigger API sync → verify sale orders created with correct customer, products, line items, prices, shipping costs, buyer notes matching the Etsy Seller Portal.

- [ ] T046 [US2] Implement `EtsyApiClient.get_shop_receipts(shop_id, min_last_modified, limit, offset)` and `EtsyApiClient.get_receipt(shop_id, receipt_id)` in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T047 [US2] Create `EtsyOrderSyncer` class (constructor `(env)`, key method `sync_shop_orders(shop)`) that paginates receipts (offset+limit, max 100/page) using `was_paid=true` and `min_last_modified=int(shop.last_receipt_sync.timestamp())` in `custom_addons/etsy_integration/services/etsy_order_syncer.py`
- [ ] T048 [US2] Implement receipt-to-OrderCreator-payload transformer using the field mapping in `research.md` R2 (currency conversion via `amount/divisor`, variations, transaction_id, buyer email) in `custom_addons/etsy_integration/services/etsy_order_syncer.py`
- [ ] T049 [US2] Extend `OrderCreator` with `process_api_result(payload, source='api')` that reuses partner/product matching and writes `etsy_sync_source='api'` and `etsy_last_modified` on the created `sale.order` in `custom_addons/etsy_integration/services/order_creator.py`
- [ ] T050 [US2] Implement status-only update path: when an order with the same `etsy_order_id` already exists, only update `etsy_receipt_status`, payment status, shipping status, cancellation; preserve operator-entered notes, assignments, design status in `custom_addons/etsy_integration/services/etsy_order_syncer.py`
- [ ] T051 [US2] Add `etsy_listing_id` (Char, indexed, copy=False) to `product.product` and update the matching logic in `OrderCreator` to prefer `etsy_listing_id` match before falling back to name match in `custom_addons/etsy_integration/models/product_product.py` and `custom_addons/etsy_integration/services/order_creator.py`
- [ ] T052 [US2] Persist `buyer_email` from the receipt onto `res.partner.email` (creating partner if missing) and update dedup logic to prefer email match over name match in `custom_addons/etsy_integration/services/order_creator.py`
- [ ] T053 [US2] Implement `_cron_fetch_etsy_api_orders()` on `sale.order` iterating `etsy.shop` records where `sync_mode='api_only'` OR `sync_audit_mode=True`, calling `EtsyOrderSyncer.sync_shop_orders(shop)`, and updating `last_receipt_sync` on success in `custom_addons/etsy_integration/models/sale_order.py`
- [ ] T054 [US2] Register cron "Etsy: API Order Sync" (interval 5 minutes, configurable per `api_sync_interval`) in `custom_addons/etsy_integration/data/ir_cron_data.xml`
- [ ] T055 [US2] Wire `_cron_fetch_etsy_api_orders` to update `multichannel.sync.health` row `etsy_api_sync` (last run, row count, error count) per ADR-003 in `custom_addons/etsy_integration/models/sale_order.py`
- [ ] T056 [US2] Implement forward-only guard: skip receipts where `create_timestamp < shop.api_connection_date.timestamp()` to avoid back-syncing historical email-imported orders in `custom_addons/etsy_integration/services/etsy_order_syncer.py`
- [ ] T057 [US2] Honor receipt currency: set `sale.order.currency_id` from `currency_code` (ISO 4217 lookup); fall back to the shop's default currency if unknown in `custom_addons/etsy_integration/services/etsy_order_syncer.py`
- [ ] T058 [P] [US2] Integration test `test_api_sync_creates_order_from_fixture` using a recorded Etsy receipt JSON in `tests/fixtures/etsy_api/receipt_basic.json` in `custom_addons/etsy_integration/tests/test_etsy_order_syncer.py`
- [ ] T059 [P] [US2] Integration test `test_api_sync_status_only_update_preserves_notes` in `custom_addons/etsy_integration/tests/test_etsy_order_syncer.py`
- [ ] T060 [P] [US2] Integration test `test_forward_only_skips_pre_connection_receipts` in `custom_addons/etsy_integration/tests/test_etsy_order_syncer.py`
- [ ] T061 [P] [US2] Integration test `test_api_sync_pagination_handles_300_receipts` (asserts no more than 4 paginated calls for 300 receipts) in `custom_addons/etsy_integration/tests/test_etsy_order_syncer.py`
- [ ] T062 [P] [US2] Integration test `test_api_sync_writes_buyer_email_and_listing_id` verifying enrichment over email-parsed orders in `custom_addons/etsy_integration/tests/test_etsy_order_syncer.py`

**Story 2 Checkpoint** (Phase 0 sandbox MVP exit): API sync creates orders end-to-end against the dev shop. Status-only updates preserve operator data. Forward-only guard active. `multichannel.sync.health` updates after each run. **This is the MVP — owner sign-off here gates Phase 1 production cutover.**

---

## Phase 7: User Story 3 — Push Tracking Numbers to Etsy (P1, Phase 1 production cutover)

**Story Goal**: Tracking numbers entered in Odoo automatically pushed to Etsy within one sync cycle; carrier name resolved from `shipping.carrier.etsy_carrier_name` (ADR-005).

**Independent Test (per spec)**: Enter tracking on an Etsy sale order → verify tracking visible on Etsy Seller Portal within one sync cycle.

> **Dependency**: Requires `shipping.carrier` (Spec 004) seeded with `etsy_carrier_name` enum values. Verify the field exists before starting this phase.

- [ ] T063 [US3] Add tracking-push fields to `sale.order`: `etsy_tracking_push_status` (Selection: none/pending/pushed/failed, default `none`, indexed), `etsy_tracking_push_date` (Datetime), `etsy_tracking_push_error` (Text) in `custom_addons/etsy_integration/models/sale_order.py`
- [ ] T064 [US3] Add an `@api.onchange('carrier_tracking_ref')` (or write hook) on `sale.order` that flips `etsy_tracking_push_status` from `none`→`pending` when a tracking number is set on an Etsy order in `custom_addons/etsy_integration/models/sale_order.py`
- [ ] T065 [US3] Implement `EtsyApiClient.create_receipt_shipment(shop_id, receipt_id, tracking_code, carrier_name, send_bcc=False)` calling `POST /v3/application/shops/{shop_id}/receipts/{receipt_id}/tracking` in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T066 [US3] Create `EtsyTrackingPusher` class (constructor `(env)`, key method `push_pending_tracking(shop)`) that searches `sale.order` rows with `etsy_tracking_push_status='pending'` for the shop and calls the API per row in `custom_addons/etsy_integration/services/etsy_tracking_pusher.py`
- [ ] T067 [US3] Resolve Etsy carrier name from `order.carrier_id.etsy_carrier_name` (Spec 004 / ADR-005); if blank, push with `other` and log a warning row to `etsy.api.log` in `custom_addons/etsy_integration/services/etsy_tracking_pusher.py`
- [ ] T068 [US3] Update tracking-push status on success (`pushed` + timestamp) and failure (`failed` + error message); leave `pushed` as terminal in `custom_addons/etsy_integration/services/etsy_tracking_pusher.py`
- [ ] T069 [US3] Implement `_cron_push_tracking_to_etsy()` on `sale.order` iterating API-enabled shops and calling `EtsyTrackingPusher.push_pending_tracking(shop)` in `custom_addons/etsy_integration/models/sale_order.py`
- [ ] T070 [US3] Register cron "Etsy: Push Tracking" (interval 5 minutes) in `custom_addons/etsy_integration/data/ir_cron_data.xml`
- [ ] T071 [US3] Add manual "Push Tracking to Etsy" and "Retry Tracking Push" buttons (and their `action_*` methods) to the Etsy sale-order form in `custom_addons/etsy_integration/views/sale_order_views.xml` and `custom_addons/etsy_integration/models/sale_order.py`
- [ ] T072 [US3] Wire `_cron_push_tracking_to_etsy` to update `multichannel.sync.health` row `etsy_tracking_push` per ADR-003 in `custom_addons/etsy_integration/models/sale_order.py`
- [ ] T073 [P] [US3] Integration test `test_tracking_push_success_sets_pushed_status` in `custom_addons/etsy_integration/tests/test_etsy_tracking_pusher.py`
- [ ] T074 [P] [US3] Integration test `test_tracking_push_unknown_carrier_uses_other_and_warns` in `custom_addons/etsy_integration/tests/test_etsy_tracking_pusher.py`
- [ ] T075 [P] [US3] Integration test `test_tracking_push_failure_records_error_and_allows_retry` in `custom_addons/etsy_integration/tests/test_etsy_tracking_pusher.py`
- [ ] T076 [P] [US3] Integration test `test_tracking_push_batch_respects_rate_limit` (asserts no more than 8 calls/sec across 50 orders) in `custom_addons/etsy_integration/tests/test_etsy_tracking_pusher.py`

**Story 3 Checkpoint**: Tracking pushes within one cron cycle. SC-003 (≤5 min from entry) verified. SC-009 (2h/day operator savings) measurable.

---

## Phase 8: User Story 4 — Webhook Receiver (P2)

**Story Goal**: Real-time order events (`order.paid`, `order.shipped`, `order.canceled`, `order.delivered`) processed within 60 seconds.

**Independent Test (per spec)**: Register webhook → place test order on Etsy → verify order appears within 60 seconds.

> **Note**: Webhooks are a latency optimization, not a requirement. The cron sync (US2) is the safety net. P2 priority — implement after Phase 7 ships.

- [ ] T077 [US4] Create new model `etsy.webhook.event` (fields per data-model.md §New Models: `name`, `event_type`, `etsy_shop_id`, `etsy_receipt_id`, `resource_url`, `raw_payload`, `signature_valid`, `processing_status`, `error_message`, `sale_order_id`) in `custom_addons/etsy_integration/models/etsy_webhook_event.py`
- [ ] T078 [P] [US4] Add ACL rows (read-only for all users) for `etsy.webhook.event` in `custom_addons/etsy_integration/security/ir.model.access.csv`
- [ ] T079 [P] [US4] Create tree/form/search views and a menu under "Etsy > Webhook Events" in `custom_addons/etsy_integration/views/etsy_webhook_event_views.xml`
- [ ] T080 [US4] Implement signature verifier `verify_etsy_webhook(headers, raw_body, secret)` performing HMAC-SHA256 over `{webhook-id}.{webhook-timestamp}.{raw_body}` (base64-decoding the `whsec_` secret first) in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T081 [US4] Implement webhook controller route `@http.route('/etsy/webhook/callback', type='json', auth='none', csrf=False, methods=['POST'])` that verifies signature, persists an `etsy.webhook.event` row, and dispatches per event_type in `custom_addons/etsy_integration/controllers/webhook.py`
- [ ] T082 [US4] On valid event, fetch the full receipt via `EtsyApiClient.get_receipt(shop_id, receipt_id)` and call `EtsyOrderSyncer.process_single_receipt(shop, receipt_json, source='webhook')` (extract this method from `sync_shop_orders` in T047) in `custom_addons/etsy_integration/services/etsy_order_syncer.py`
- [ ] T083 [US4] Implement webhook idempotency: before processing, check for an existing successfully-processed `etsy.webhook.event` with the same `event_type` + `etsy_receipt_id`; if found, return early in `custom_addons/etsy_integration/controllers/webhook.py`
- [ ] T084 [US4] Reject and log invalid-signature attempts (sets `signature_valid=False`, `processing_status='rejected'`) in `custom_addons/etsy_integration/controllers/webhook.py`
- [ ] T085 [US4] Add `action_register_webhooks()` on `etsy.shop` (instructions/copy-button to Etsy portal — Etsy registration is portal-only, not API) in `custom_addons/etsy_integration/models/etsy_shop.py`
- [ ] T086 [P] [US4] Integration test `test_webhook_valid_signature_creates_order` in `custom_addons/etsy_integration/tests/test_etsy_webhook.py`
- [ ] T087 [P] [US4] Integration test `test_webhook_invalid_signature_rejected_and_logged` in `custom_addons/etsy_integration/tests/test_etsy_webhook.py`
- [ ] T088 [P] [US4] Integration test `test_webhook_idempotent_replay_no_duplicate` in `custom_addons/etsy_integration/tests/test_etsy_webhook.py`
- [ ] T089 [P] [US4] Integration test `test_webhook_failure_then_cron_safety_net_picks_up_order` in `custom_addons/etsy_integration/tests/test_etsy_webhook.py`

**Story 4 Checkpoint**: SC-004 (<60s webhook-to-order latency) verified. Invalid signatures rejected. Replays idempotent. Cron safety net covers webhook failures.

---

## Phase 9: User Story 6 — Bidirectional Listing/Product Management (P2)

**Story Goal**: Pull listings from Etsy as the source of truth; push local product changes only on demand.

**Independent Test (per spec)**: Create a draft listing from Odoo → verify it appears as a draft on Etsy → update price → verify update on Etsy.

- [ ] T090 [US6] Add product fields `etsy_listing_state` (Selection: draft/active/inactive/sold_out/expired), `etsy_listing_last_sync` (Datetime), `etsy_taxonomy_id` (Integer), `etsy_who_made` (Selection), `etsy_when_made` (Selection), `is_etsy_listing` (Boolean compute store) to `product.template` in `custom_addons/etsy_integration/models/product_template.py` (new file) — keep `etsy_listing_id` on `product.product` per T051 with a related field on `product.template` if needed
- [ ] T091 [P] [US6] Add product form section "Etsy Listing" with the new fields, listing state badge, and "Push to Etsy" / "Pull from Etsy" / "Upload Image" buttons in `custom_addons/etsy_integration/views/product_views.xml`
- [ ] T092 [US6] Implement `EtsyApiClient.get_shop_listings(shop_id, state, limit, offset)`, `EtsyApiClient.create_draft_listing(shop_id, listing_data)`, `EtsyApiClient.update_listing(shop_id, listing_id, listing_data)`, `EtsyApiClient.upload_listing_image(shop_id, listing_id, image_data)` in `custom_addons/etsy_integration/services/etsy_api_client.py`
- [ ] T093 [US6] Create `EtsyListingSyncer` class (constructor `(env)`) with `pull_listings(shop)`, `push_listing(shop, product)`, `upload_image(shop, product)` per the field mapping in research.md R6 in `custom_addons/etsy_integration/services/etsy_listing_syncer.py`
- [ ] T094 [US6] Implement Etsy-wins pull semantics: `pull_listings` overwrites `name`, `description_sale`, `list_price`, `etsy_listing_state`, primary image; preserves Odoo-only fields in `custom_addons/etsy_integration/services/etsy_listing_syncer.py`
- [ ] T095 [US6] Implement validation gate on `push_listing`: ensure `etsy_taxonomy_id`, `etsy_who_made`, `etsy_when_made` are set; raise a `UserError` listing missing fields if not in `custom_addons/etsy_integration/services/etsy_listing_syncer.py`
- [ ] T096 [US6] Implement `action_push_to_etsy()`, `action_pull_from_etsy()`, `action_upload_image_to_etsy()` on `product.template` in `custom_addons/etsy_integration/models/product_template.py`
- [ ] T097 [US6] Implement `_cron_sync_etsy_listings()` (60-min interval) iterating API-enabled shops and calling `EtsyListingSyncer.pull_listings(shop)` in `custom_addons/etsy_integration/models/product_template.py` and register the cron in `custom_addons/etsy_integration/data/ir_cron_data.xml`
- [ ] T098 [US6] Persist Etsy variations as text fields on `sale.order.line` (`etsy_color`, `etsy_size`, `etsy_option`) in line with the existing approach (no full variant model) in `custom_addons/etsy_integration/models/sale_order_line.py`
- [ ] T099 [P] [US6] Integration test `test_pull_listings_overwrites_local_data` in `custom_addons/etsy_integration/tests/test_etsy_listing_syncer.py`
- [ ] T100 [P] [US6] Integration test `test_push_listing_validates_required_fields` in `custom_addons/etsy_integration/tests/test_etsy_listing_syncer.py`
- [ ] T101 [P] [US6] Integration test `test_image_upload_attaches_to_correct_listing` in `custom_addons/etsy_integration/tests/test_etsy_listing_syncer.py`

**Story 6 Checkpoint**: Listings pull on schedule. Local edits push only on demand. Image upload works. Listing-state transitions reflected in product records.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T102 [P] Add post-install hook (or migration) ensuring all 19 existing `etsy.shop` records keep `sync_mode='email_only'` and `sync_audit_mode=False` in `custom_addons/etsy_integration/migrations/19.0.2.0.0/post-migration.py`
- [ ] T103 [P] Update module README with the API channel sections (OAuth setup, sandbox vs prod, cutover playbook) in `custom_addons/etsy_integration/README.md`
- [ ] T104 [P] Ensure all new `_logger.info` calls in service layer are downgraded to `_logger.debug` per project hooks in `custom_addons/etsy_integration/services/etsy_api_client.py`, `etsy_order_syncer.py`, `etsy_tracking_pusher.py`, `etsy_listing_syncer.py`
- [ ] T105 [P] Run `ruff check --fix custom_addons/etsy_integration/` and resolve outstanding lints
- [ ] T106 [P] Verify ACLs/record rules for every new model via `security-reviewer` agent and patch any gaps in `custom_addons/etsy_integration/security/ir.model.access.csv` and `custom_addons/etsy_integration/security/etsy_security.xml`
- [ ] T107 [P] Verify combined unit + integration coverage ≥ 80% via `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init` and add tests for any uncovered branches
- [ ] T108 [P] Add `quickstart.md` cutover-playbook section documenting the per-shop sequence: enable `sync_audit_mode` → 1–2 weeks → BA review of audit log → flip `sync_mode='api_only'` → 30-day shadow window → remove from Gmail filter in `specs/005-etsy-api-channel/quickstart.md`
- [ ] T109 [P] Reconcile `data-model.md` with ADR-002 + ADR-005 (remove `dual` and `etsy.carrier.mapping` references; add `sync_audit_mode`) in `specs/005-etsy-api-channel/data-model.md`
- [ ] T110 Update `multichannel.sync.health` seed data to include `etsy_api_sync` and `etsy_tracking_push` rows (per ADR-003) in `custom_addons/etsy_integration/data/sync_health_data.xml` (or the equivalent file in `multichannel_hub_core` if that module owns the seed)

---

## Dependencies

```
Phase 1 (Setup)
   └─> Phase 2 (Foundational: API log model, EtsyApiClient skeleton, shop fields)
         ├─> Phase 3 (US1: OAuth2 PKCE)
         │     └─> Phase 4 (US5: Rate limiting + resilience)  ← needs auth headers + log model
         │           └─> Phase 5 (US8: sync_mode + audit)
         │                 └─> Phase 6 (US2: Order sync)         ← MVP exit, gates Phase 1 prod
         │                       └─> Phase 7 (US3: Tracking push) ← Phase 1 prod cutover
         │                             ├─> Phase 8 (US4: Webhooks, P2)
         │                             └─> Phase 9 (US6: Listings, P2)
         └─> Phase 10 (Polish, runs in parallel with later phases where possible)
```

**Critical path** (Phase 0 sandbox MVP): T001 → T012 → T014 → T020 → T021 → T027 → T037 → T046 → T047 → T053. Owner sign-off at the end of Phase 6 gates the move to Phase 7 (production cutover).

**Cross-story parallel opportunities**:
- T009/T010/T011 (foundational ACL + views) parallel.
- T025/T026 (US1 tests), T035/T036 (US5 tests), T043/T044/T045 (US8 tests), T058–T062 (US2 tests), T073–T076 (US3 tests), T086–T089 (US4 tests), T099–T101 (US6 tests) all parallel within their phases.
- All Phase 10 tasks (except T110, which depends on the seed-file owner) can run in parallel.

---

## Implementation Strategy

### MVP scope (Phase 0 sandbox)

**Phases 1 → 6 only** = 62 tasks (T001–T062). Delivers:
- OAuth2 PKCE flow against owner's personal developer token
- EtsyApiClient with rate limiting, retry, and full audit logging
- `sync_mode` + `sync_audit_mode` per ADR-002
- Direct API order sync to a single dev shop
- VCR-style fixture-driven test suite

**No production shops touched until Etsy approves scopes.** This is the gate for Phase 1 cutover.

### Phase 1 production cutover (post-scope-approval)

**Phase 7** (12 tasks, T063–T076) adds tracking push, then per-shop `sync_audit_mode` validation (1–2 weeks each) → flip to `sync_mode='api_only'` → 30-day Gmail shadow window. Target 3–5 shops by end of Phase 1.

### Phase 2 rollout

**Phases 8 + 9** (25 tasks, T077–T101) add webhooks (P2) and bidirectional listings (P2). Remaining 14–16 shops cut over in parallel.

### Polish (Phase 10)

**T102–T110** run in parallel with Phases 7–9 wherever they touch independent files.

---

## Validation

- **Total task count**: 110 (T001–T110).
- **Per-story counts**: US1 = 11, US2 = 17, US3 = 14, US4 = 13, US5 = 10, US6 = 12, US7 = 0 (deferred), US8 = 9. Setup = 7, Foundational = 8, Polish = 9.
- **Independent test criteria**: Defined under each story's "Independent Test" line, sourced verbatim from `spec.md`.
- **Format check**: All 110 tasks follow `- [ ] T### [P?] [US?] description with file path`. Setup, Foundational, and Polish tasks correctly omit the story label. User story tasks all carry their `[USx]` label.
- **MVP gate**: Phase 6 checkpoint (T062 complete + sandbox demo to owner) is the explicit sign-off gate before Phase 7 begins.
