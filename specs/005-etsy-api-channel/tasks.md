---
description: "Tasks for Spec 005 — Etsy API v3 Channel Integration with Email as Permanent Failover"
---

# Tasks: Etsy API v3 Channel Integration (with Email as Permanent Failover)

**Branch**: `005-etsy-api-channel` | **Date**: 2026-04-27 (Stage 4.4 regen, supersedes the 110-task version from commit `bfda694` — which was built around the now-superseded `sync_audit_mode` design)
**Modules**: `etsy_channel_api` (NEW) and `etsy_channel_email` (RENAMED from `etsy_integration`) per ADR-008a §5 + ADR-001 §11
**Input**: spec.md (2026-04-09 with 2026-04-13 ADR-002/008 amendments), plan.md (Stage 4.2 refresh), data-model.md (Stage 4.2 refresh), research.md (Stage 4.2 refresh), quickstart.md (Stage 4.2 refresh)
**Tests**: REQUIRED per project's two-phase testing rule (Phase 1 DB + Phase 2 ORM unit, 80%+ coverage). VCR cassettes for adapter tests recorded against owner's Etsy dev shop.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelisable (different files, no incomplete dependencies)
- **[Story]**: User Story label (US1–US8) for user-story-phase tasks; absent for Setup/Foundational/Polish phases

> **Major delta vs the 110-task `bfda694` version**:
> - **DROPPED**: tasks for `sync_audit_mode`, dual-write reconciliation, 30-day shadow logging, `etsy.carrier.mapping` model
> - **ADDED**: tasks for `EtsyChannelAdapter` protocol + `EtsyApiAdapter` + `EtsyEmailAdapter` + `EtsyOrderIngestor`, canonical `EtsyOrderPayload` dataclass, `etsy.shop.active_source` field, health-check cron + recovery-probe cron, `etsy.shop.source.change.log` model, `etsy.buyer.message` model (REQ-MSG-01), module-rename migration (`etsy_integration` → `etsy_channel_email`)
> - **MOVED**: shared adapter contract + ingestor live in `multichannel_hub_core` (Spec 003 prerequisite); the `etsy.carrier.mapping` model removal is part of the migration script

---

## Phase 1: Setup

- [ ] T001 Create new module skeleton at `custom_addons/etsy_channel_api/` — `__manifest__.py` (version `19.0.1.0.0`, depends `['multichannel_hub_core']`)
- [ ] T002 [P] Create `__init__.py` files in `etsy_channel_api/{models,services,controllers,views,data,security,i18n,tests,migrations}`
- [ ] T003 [P] Add `tests/fixtures/vcr_cassettes/.gitkeep` for VCR cassette directory
- [ ] T004 Create `etsy_channel_api/security/etsy_channel_api_security.xml` declaring groups `group_etsy_admin`, `group_etsy_api_log_reader`
- [ ] T005 [P] Create `etsy_channel_api/data/ir_config_parameter.xml` with `etsy.api.rate_limit_per_second=10`, `etsy.api.log.retention_days=30`, `etsy.health_check.failure_threshold=3`, `etsy.recovery_probe.success_threshold=6`, `etsy.health_check.email_silence_threshold_hours=24`

---

## Phase 2: Foundational (shared core + adapter contract)

These tasks land in `multichannel_hub_core` (delivered by Spec 003 — confirm prerequisite met). If `multichannel_hub_core` is not yet installed, T006-T010 fail — they are blocking dependencies.

- [X] T006 [P] Implement `etsy_integration/services/etsy_order_payload.py` with frozen dataclasses `EtsyAddressPayload`, `EtsyLineItemPayload`, `EtsyOrderPayload` per data-model.md §9 — **landed P0-16a 2026-04-28** on `feature/006-master-plan-coding`. Module-home moved from `multichannel_hub_core` per findings.md 2026-04-28. `line_items` is `tuple[..., ...]` (immutability hardening from security-reviewer HIGH).
- [X] T007 [P] Implement `etsy_integration/services/etsy_channel_adapter.py` with `EtsyChannelAdapter` Protocol (`fetch_new_orders`, `health_check`) and `HealthStatus` enum — **landed P0-16a 2026-04-28**. `@runtime_checkable` Protocol; module-home moved per findings entry above.
- [X] T008 Implement `etsy_integration/services/etsy_order_ingestor.py` — single ingestion service that selects adapter via `etsy_shop.sync_mode` (per ADR-002, not `active_source` per superseded spec), iterates `fetch_new_orders`, writes `sale.order` via existing `OrderCreator` service; idempotent via `etsy_order_id` UNIQUE — **landed P0-16b1 2026-04-28** (minimal slice; adapter-selection logic deferred to syncer P0-16c). Reuses `OrderCreator.process_etsy_payload` helper. Module-home: `etsy_integration` per findings 2026-04-28.
- [ ] T009 [P] Implement `multichannel_hub_core/utils/rate_limiter.py` — token-bucket limiter shared between API and email adapters per research.md R5
- [ ] T010 [P] Implement `multichannel_hub_core/controllers/webhook_base.py` — base controller for HMAC-verified webhook endpoints (used by US4 P2)
- [ ] T011 [P] Phase-2 unit tests `multichannel_hub_core/tests/test_etsy_order_payload.py`: `__post_init__` validation, frozen-immutability assertion, equality semantics
- [ ] T012 [P] Phase-2 unit tests `multichannel_hub_core/tests/test_rate_limiter.py`: token-bucket behaviour, retry-after handling

---

## Phase 3: US1 — Etsy OAuth2 PKCE authorization (P1)

- [ ] T013 [US1] Implement `etsy.shop` extension in `models/etsy_shop.py` — add API token fields, `active_source` (default 'email' for existing shops, 'api' post scope-grant), `auto_recovery`, `health_check_consecutive_failures`, `recovery_probe_consecutive_successes` per data-model.md §1
- [ ] T014 [US1] Add `etsy.shop` C-ESY-001 (token-required-when-active_source=api) and C-ESY-002 (manual-toggle-requires-system-group) constraints
- [ ] T015 [P] [US1] Implement `services/etsy_api_client.py` — OAuth2 PKCE flow, token refresh on 401, request signing, response parsing, integrates `multichannel_hub_core/utils/rate_limiter.py`
- [ ] T016 [US1] Implement `controllers/etsy_oauth_callback.py` — `/etsy/api/oauth/callback` route consuming state-nonce, swapping code for tokens, persisting to `etsy.shop`
- [ ] T017 [P] [US1] Add `views/etsy_shop_views.xml` — Settings → Etsy API Configuration form with "Authorize Etsy" button + "Test Connection" button + active_source toggle (system-group-only)
- [ ] T018 [P] [US1] Add token-expiry alert cron `cron_etsy_token_expiry_alert` — checks `etsy_refresh_token_expires_at` and raises a 7-day-warning activity per FR-004
- [ ] T019 [P] [US1] Phase-2 test `tests/test_oauth_flow.py` — PKCE code_verifier/challenge generation, refresh-token flow, expired-token auto-refresh, scope validation
- [ ] T020 [US1] Phase-1 DB test verifying `groups='base.group_system'` ACL on token columns (read fails for non-admin)

---

## Phase 4: US2 — Direct order/receipt sync via canonical payload (P1)

- [X] T021 [US2] Implement `services/etsy_api_adapter.py` — implements `EtsyChannelAdapter` Protocol; `fetch_new_orders(shop_id, since)` wraps `EtsyApiClient` paginated receipt fetch; transforms each receipt to `EtsyOrderPayload`; emits via generator — **landed P0-16b2 2026-04-28** (commit `ab48e8a8782`).
- [X] T022 [US2] Implement `services/etsy_order_syncer.py` — incremental sync orchestrator: reads `etsy_shop.etsy_last_receipt_sync_at`, calls `EtsyApiAdapter.fetch_new_orders`, passes to `EtsyOrderIngestor.ingest`, advances cursor — **landed P0-16c 2026-04-28** (commit `b70daf6b07a`). Per-payload cursor advancement; soft-warn on `sync_audit_mode + sync_mode='api_only'`; per-shop exception isolation in `etsy.shop._cron_sync_orders`.
- [X] T023 [P] [US2] Add cron `cron_etsy_order_sync` (default 5min interval) per FR-012 — **landed P0-16c 2026-04-28**. Cron filters `sync_mode='api_only'` shops (OQ5).
- [X] T024 [P] [US2] Implement `models/etsy_api_log.py` — `etsy.api.log` model per data-model.md §3 (audit trail with retention policy) — **landed P0-17 2026-04-28** (commit `481bd4250d7`). 11 fields; does NOT inherit mail.thread (high-volume); composite index `(shop_id, request_started_at DESC)` declared in init() raw SQL; `source` Selection adds `audit` (8 values total). New `group_etsy_api_log_reader` group; ACL: reader read-only, system full. P0-16c audit branch retrofit replaces `_logger.warning` with `etsy.api.log.sudo().create({...})` — PII scrubbed (receipt_id + amount + currency only).
- [X] T025 [P] [US2] Implement cron `cron_etsy_api_log_cleanup` per FR-035 (delete rows >retention_days) — **landed P0-17 2026-04-28**. Daily; raw SQL DELETE parameterized via psycopg2; threshold from `ir.config_parameter.etsy_integration.api_log_retention_days` with 30-day fallback; integer underflow guarded.
- [X] T026 [US2] Extend `sale.order` in `models/sale_order.py` — add `sync_source`, `etsy_last_modified`, `etsy_tracking_push_status`, `etsy_tracking_push_at`, `etsy_tracking_push_error` per data-model.md §6 — **P0-16c 2026-04-28** (`sync_source`/`etsy_last_modified`/`payment_status`) + **P1-12 2026-05-16** (`etsy_tracking_push_status` [none/pending/pushed/failed, default none], `etsy_tracking_push_at`, `etsy_tracking_push_error`).
- [ ] T027 [US2] Add composite index `(etsy_shop_id, etsy_last_modified DESC)` on `sale_order` per data-model.md §6 (Tech-architect recommendation) — deferred per active-prioritization (perf, post-prod-scale)
- [X] T028 [P] [US2] Implement `EtsyApiAdapter` mapping function `_receipt_to_payload(receipt_dict) -> EtsyOrderPayload`: maps Etsy fields to canonical schema (handles currency, line_items, shipping_address, buyer_message, listing_id) — **landed P0-16b2 2026-04-28**. Money divisor handling + variations list→dict flattening + payment_status from is_paid + provenance fields covered.
- [X] T029 [P] [US2] Implement `EtsyOrderIngestor` status-only-update logic for re-sync (FR-009): when `etsy_order_id` exists, update payment_status / shipping_status / cancellation only; preserve `mp_note`, `pic_user_id`, design state — **landed P0-16c 2026-04-28** (commit `b70daf6b07a`). Subset shipped: `payment_status` + `etsy_last_modified` updated; `shipping_status` + `cancellation` fields deferred to P0-17 (when full status taxonomy lands alongside `etsy.api.log`). Operator-field preservation (mp_note / pic_user_id) verified via test_existing_order_mp_note_preserved + test_existing_order_pic_user_id_preserved.
- [ ] T030 [P] [US2] Phase-2 test `tests/test_api_adapter.py` — record VCR cassette for representative receipts (different currencies, gift-message, multi-line); verify payload-mapping correctness
- [X] T031 [P] [US2] Phase-2 test `tests/test_order_syncer.py` — incremental sync with `since` cursor, dedup by etsy_order_id, status-only update preserving operator data, pagination handling — **landed P0-16c 2026-04-28** as `tests/test_etsy_order_syncer.py` (renamed). 11 tests across 6 classes covering all OQ1–OQ5 contracts. JSON fixtures replace VCR per owner decision 2026-04-28.
- [ ] T032 [US2] Phase-1 DB test verifying composite index `(etsy_shop_id, etsy_last_modified DESC)` exists post-install — paired with T027; deferred together
- [X] T033 [P] [US2] Add `etsy.api.log` views in `views/etsy_api_log_views.xml` (list + form for diagnostics) — **landed P0-17 2026-04-28**. List with `decoration-danger` on `http_status>=500`; read-only form (`create=false edit=false delete=false`); search with audit-only filter + group-by Shop/Source; menu under Etsy Integration gated to `group_etsy_api_log_reader,base.group_system`.

---

## Phase 5: US3 — Tracking push to Etsy (P1)

- [X] T034 [P] [US3] Implement `services/etsy_tracking_pusher.py` — reads `sale.order.fulfillment.tracking_number` + `shipping_carrier_id`; pushes via `POST /v3/application/shops/:shop_id/receipts/:receipt_id/tracking`; reads `shipping.carrier.etsy_carrier_name` (per ADR-005, FR-014/015) — **P1-12 2026-05-16**: `EtsyTrackingPusher(env).push(order)`; receipt_id == `order.etsy_order_id`, shop_id == `etsy.shop` record id (matches existing `etsy_api_adapter.py` convention); `EtsyApiClient.push_tracking` added; sets `fulfillment.etsy_ship_notified_at` on success.
- [X] T035 [P] [US3] Add cron `cron_etsy_tracking_push` (default 5min) — **P1-12 2026-05-16**: `ir_cron_etsy_tracking_push` → `sale.order._cron_push_tracking()`, fallback for the webhook (D-A) primary trigger.
- [X] T036 [P] [US3] Implement on-demand push action — button on `sale.order` form invoking `EtsyTrackingPusher.push(order)` synchronously — **P1-12 2026-05-16**: `action_push_tracking_to_etsy`, gated to `multichannel_hub_core.group_production_team` (view + method, FR-017 defense-in-depth per security review).
- [X] T037 [P] [US3] Handle unmapped carrier: when `etsy_carrier_name` is NULL, push with `other` and warn-log to `etsy.api.log` — **P1-12 2026-05-16**.
- [X] T038 [P] [US3] Phase-2 test `tests/test_tracking_pusher.py` — happy path, missing carrier mapping, retry on 5xx, push status field state machine — **P1-12 2026-05-16**: `tests/test_p1_12_db.py` (7) + `tests/test_p1_12_orm.py` (19), 26/26 green.
- [X] T039 [US3] Wire from Spec 003's Tracking Dashboard — when `sale.order.fulfillment.tracking_number` is written, schedule a queued job `EtsyTrackingPusher.enqueue(order)` (replaces cron-only delivery for low-latency push) — **P1-12 2026-05-16, decision D-A**: trigger is the Gearment `tracking_order_updated` webhook handler (`gearment_webhook_dispatcher._handle_tracking_order_updated`), NOT a sale.order write — owner directive 2026-05-10 D4 (Etsy tab is read-only mirror). Synchronous soft-fail (no queue model); permanent ValueError → `_logger.error`, transient → warning; 5-min cron retries.

---

## Phase 6: US5 — Rate limiting and API resilience (P1)

- [ ] T040 [US5] Verify `multichannel_hub_core/utils/rate_limiter.py` (T009) is wired into `EtsyApiClient` for ALL outgoing calls
- [ ] T041 [P] [US5] Implement `Retry-After` header handling in `EtsyApiClient` per FR-024
- [ ] T042 [P] [US5] Implement exponential-backoff retry (max 3) on 5xx + connection errors per FR-025
- [ ] T043 [P] [US5] Implement no-retry on 4xx (except 429 → handled by Retry-After) per FR-026
- [ ] T044 [P] [US5] Add daily quota tracking — parse `X-RateLimit-Limit-Daily` headers; warn at 80%, error at 95% per FR-027 + SC-007
- [ ] T045 [P] [US5] Phase-2 test `tests/test_rate_limiter.py` — verify ~10 req/s throttle, Retry-After honored, retry-on-5xx (3 attempts), no-retry-on-403
- [ ] T046 [P] [US5] Phase-2 test `tests/test_quota_tracking.py` — quota-warn at 80% threshold, quota-block at 95%

---

## Phase 7: US8 — Source switching (REQ-SRC-01..04, the new core ADR-008a v2)

- [ ] T047 [US8] Implement `models/etsy_shop_source_change_log.py` — `etsy.shop.source.change.log` per data-model.md §2 with append-only constraint (C-SCL-001) + auto-failover/recovery-probe-actor=null constraint (C-SCL-002)
- [ ] T048 [P] [US8] Add ACL for `etsy.shop.source.change.log`: read `group_audit_reader` + Manager; create via system; no update/delete except `base.group_system`
- [ ] T049 [US8] Implement `services/etsy_health_checker.py` — `EtsyHealthChecker.evaluate(shop)` per research.md R7: probes the shop's active source; on failure increments `health_check_consecutive_failures`; on success resets counter; when counter ≥ 3 → switch source, write `etsy.shop.source.change.log` row with `reason='auto-failover'`, raise HIGH alert
- [ ] T050 [US8] Implement source-specific probes: `_probe_api(shop)` calls `GET /v3/application/openapi-ping`; `_probe_email(shop)` queries Gmail label freshness ≥ N hours
- [ ] T051 [P] [US8] Add cron `cron_etsy_health_check` (default 5min interval) calling `EtsyHealthChecker.evaluate` for every shop
- [ ] T052 [US8] Implement `services/etsy_recovery_prober.py` — `EtsyRecoveryProber.evaluate(shop)`: ONLY for shops in failover; probes the original primary; on success increments `recovery_probe_consecutive_successes`; on failure resets counter; when counter ≥ 6 AND `auto_recovery=True` → switch back, write source-change row with `reason='recovery-probe'`
- [ ] T053 [P] [US8] Add cron `cron_etsy_recovery_probe` (default 1h interval) calling `EtsyRecoveryProber.evaluate` for every in-failover shop
- [ ] T054 [P] [US8] Implement migration script `migrations/19.0.1.0.0_post.py` to map legacy `sync_mode → active_source` per data-model.md §1, and bootstrap `etsy.shop.source.change.log` with `reason='bootstrap'` row per shop
- [ ] T055 [US8] Add `etsy.shop.active_source` manual-toggle UI: form view selection field gated by `groups='base.group_system'` per data-model.md §1 C-ESY-002
- [ ] T056 [P] [US8] Add `auto_recovery` checkbox in shop form view with help text "Sticky override — uncheck to prevent auto-switch-back from email to api"
- [ ] T057 [P] [US8] Implement `etsy.shop.source.change.log` views in `views/etsy_shop_source_change_log_views.xml` (list + filter by reason)
- [ ] T058 [US8] Modify `EtsyOrderIngestor.ingest` (T008) to dynamically select adapter from `shop.active_source` — `EtsyApiAdapter` if 'api', `EtsyEmailAdapter` if 'email'
- [ ] T059 [P] [US8] Phase-2 test `tests/test_health_check_failover.py` — 3-fail threshold triggers switch + audit log row + HIGH alert
- [ ] T060 [P] [US8] Phase-2 test `tests/test_recovery_probe.py` — 6-success threshold triggers switch back; `auto_recovery=False` blocks switch back
- [ ] T061 [P] [US8] Phase-2 test `tests/test_source_change_log.py` — append-only constraint, actor-null on auto-failover/recovery-probe, indexes `(shop_id, changed_at DESC)` and `(reason, changed_at DESC)`
- [ ] T062 [US8] Phase-1 DB test verifying source-change-log indexes exist + bootstrap row count matches shop count
- [ ] T063 [P] [US8] Add health dashboard tile compute methods in `multichannel.sync.health` (or extend existing model from Spec 002): `active_source_per_shop`, `auto_failover_count_7d`, `time_since_last_recovery_probe_success`, `parser_template_drift` per ADR-008a §6

---

## Phase 8: REQ-MSG-01 — Customer Message Hub (`buyer_message` ingestion, NEW v2.2)

- [ ] T064 [P] [REQ-MSG-01] Implement `models/etsy_buyer_message.py` — `etsy.buyer.message` model per data-model.md §4 with `(shop_id, etsy_receipt_id)` UNIQUE
- [ ] T065 [REQ-MSG-01] Implement `services/etsy_buyer_message_syncer.py` — extracts `buyer_message` field from each receipt during sync (T022); creates `etsy.buyer.message` row when non-empty; bundles with main sync (no extra HTTP call)
- [ ] T066 [P] [REQ-MSG-01] Modify `EtsyOrderIngestor` (T008) to also populate `etsy.buyer.message.sale_order_id` once the `sale.order` is created
- [ ] T067 [P] [REQ-MSG-01] Add ACL for `etsy.buyer.message`: read MP + BA + Owner per SRS v2.2; write `base.group_system` only (users mark-as-read)
- [ ] T068 [P] [REQ-MSG-01] Implement `views/etsy_buyer_message_views.xml` — Customer Message Hub list view + form view, mark-as-read button
- [ ] T069 [REQ-MSG-01] Add inline tab "Buyer Message" on `sale.order` form (visible when `etsy.buyer.message` row exists)
- [ ] T070 [P] [REQ-MSG-01] Add menu entry `Etsy → Customer Message Hub`
- [ ] T071 [P] [REQ-MSG-01] Phase-2 test `tests/test_buyer_message_syncer.py` — non-empty extraction, `(shop_id, receipt_id)` UNIQUE dedup, `is_read` write tracking, `sale_order_id` linkage

---

## Phase 9: US4 — Webhook receiver (P2)

- [ ] T072 [P] [US4] Implement `models/etsy_webhook_event.py` — `etsy.webhook.event` model per data-model.md §5 with `etsy_event_id` UNIQUE for idempotency
- [ ] T073 [US4] Implement `controllers/etsy_webhook.py` extending `multichannel_hub_core/controllers/webhook_base.py` (T010); HMAC-SHA256 verification using `etsy_shared_secret`; routes per event_type
- [ ] T074 [P] [US4] Implement webhook registration UI: "Register Webhooks" button on shop form invoking `EtsyApiClient.register_webhook(shop, event_types)` for `[order_paid, order_shipped, order_cancelled, order_delivered]`
- [ ] T075 [P] [US4] Implement webhook event processing — on `valid` signature: fetch full receipt via API, call `EtsyOrderIngestor.ingest_single`; on `invalid`/`missing` signature: log + reject 401
- [ ] T076 [P] [US4] Phase-2 test `tests/test_webhook_hmac.py` — HMAC verification (valid, invalid, missing), idempotency on replay (same `etsy_event_id`), tampered signature rejection
- [ ] T077 [P] [US4] Phase-2 test `tests/test_webhook_processing.py` — order-paid → order created; order-shipped → status updated; order-cancelled → cancellation propagated

---

## Phase 10: US6 — Bidirectional listing/product management (P2)

- [ ] T078 [P] [US6] Extend `product.template` in `models/product_template.py` — add `etsy_listing_id` (UNIQUE-when-non-null), `etsy_listing_state`, `etsy_listing_url` (computed), `etsy_last_listing_sync_at` per data-model.md §7
- [ ] T079 [P] [US6] Implement `services/etsy_listing_pusher.py` — push `product.template` → Etsy listing (create draft, update title/desc/price/qty, upload images) per FR-029/030/031
- [ ] T080 [P] [US6] Implement `services/etsy_listing_puller.py` — pull all active listings into `product.template`; Etsy data overwrites local on pull (FR-032)
- [ ] T081 [P] [US6] Add cron `cron_etsy_listing_state_sync` (default 1h) updating `etsy_listing_state` for products with `etsy_listing_id` non-null
- [ ] T082 [P] [US6] Add UI buttons on `product.template` form: "Push to Etsy", "Pull from Etsy", "Upload Image to Etsy"
- [ ] T083 [P] [US6] Phase-2 test `tests/test_listing_pusher.py` — draft creation, price update, image upload, missing-required-field validation
- [ ] T084 [P] [US6] Phase-2 test `tests/test_listing_puller.py` — pull all listings, overwrite local, state transitions

---

## Phase 11: Module rename — `etsy_integration` → `etsy_channel_email` (per ADR-008a §5)

These tasks land in the renamed `etsy_channel_email` module (was `etsy_integration`).

- [ ] T085 Rename `custom_addons/etsy_integration/` directory to `custom_addons/etsy_channel_email/` in git (single `git mv`)
- [ ] T086 Update `custom_addons/etsy_channel_email/__manifest__.py`: rename `name`, change `depends` to `['multichannel_hub_core']`, bump version to `19.0.1.0.1`
- [ ] T087 Implement `custom_addons/etsy_channel_email/migrations/19.0.1.0.1/pre-migrate.py` per research.md R10 — UPDATE `ir_module_module.name` from `etsy_integration` to `etsy_channel_email`; selectively move XML IDs in `ir_model_data` (carve-up by model owner)
- [ ] T088 [P] Implement `services/email_adapter.py` in `etsy_channel_email` — implements `EtsyChannelAdapter` Protocol; wraps existing `services/email_parser.py` to emit canonical `EtsyOrderPayload` records
- [ ] T089 [P] Phase-2 parity test `etsy_channel_email/tests/test_email_adapter.py` — for a representative receipt, the email adapter's canonical payload matches the API adapter's payload on required fields (using fixture from VCR cassette + corresponding email)
- [ ] T090 Verify `etsy_channel_email/data/ir_cron_data.xml` (Gmail polling cron) stays in place — STAYS OPERATIONAL FOREVER per ADR-008a §4
- [ ] T091 [P] Add module-rename smoke test on staging: install fresh, then run `pre-migrate.py`, verify `ir_module_module.name='etsy_channel_email'`, verify all sale.order data preserved

---

## Phase 11.5: P0-22 — Ingest parity (early arrival of T088 + T089)

Brought forward from Phase 11 because production cutover (P2-07) cannot ship until the API path writes the same `sale.order` / `sale.order.line` shape as the email path. Lands in `etsy_integration/` (pre-rename); migrates with the rest of the module under T085–T087. Plan: [`p0-22-plan.md`](./p0-22-plan.md).

- [X] T0-22-01 Read `EtsyOrderPayload` + `EtsyLineItemPayload`; add 4 optional `sale.order` fields (`shipping_service`, `processing_time`, `discount_code`, `subtotal`) + `name_override` on line item
- [X] T0-22-02 Read `email_parser.ParseResult`; verify it exposes `shipping_service` / `processing_time` / `discount_code` / `subtotal` / per-line `product_name`
- [X] T0-22-03 Write Phase 1 DB tests — 11 field existence + readonly=True on `payment_status` / `etsy_last_modified`
- [X] T0-22-04 Write Phase 2 ORM unit tests — per-adapter per-field mapping (4 email-side, 4 API-side)
- [X] T0-22-05 Write Phase 2 golden-fixture parity test — email + API → identical `sale.order` on 9 fields
- [X] T0-22-06 Author golden-email fixture (`tests/data/sample_p0_22_golden.txt`) covering all 9 fields
- [X] T0-22-07 Author golden-receipt JSON fixture (`tests/fixtures/etsy_v3/p0_22_golden_receipt.json`) with same `order_id`
- [X] T0-22-08 Implement `EtsyEmailAdapter._parse_result_to_payload` (`ParseResult` → `EtsyOrderPayload`, `source='email'`)
- [X] T0-22-09 Extend `EtsyApiAdapter` to populate new payload fields where receipt JSON has them
- [X] T0-22-10 Update `EtsyOrderIngestor` to write the 4 new payload fields onto `sale.order` + `name_override` onto `sale.order.line`
- [X] T0-22-11 Run `code-reviewer` + `security-reviewer` in parallel; block on CRITICAL/HIGH
- [X] T0-22-12 Run `odoo -u etsy_integration --stop-after-init`; verify 0 errors + all etsy_integration test tags pass
- [X] T0-22-13 Append `findings.md` §"P0-22" with implementation-choice rationale + any surprises
- [X] T0-22-14 Update tracker P0-22 row to `state=done`; T088 + T089 reference P0-22 commits

When T085–T087 (module rename) land, T0-22 code moves to `etsy_channel_email/` along with the rest of `etsy_integration/`. T088 + T089 close at that point because their work is already done.

---

## Phase 12: Polish & Cross-cutting

- [ ] T092 [P] Add `i18n/vi_VN.po` to both `etsy_channel_api` and `etsy_channel_email` with 100% string coverage; CI gate per Spec 003's `test_i18n_coverage` pattern
- [ ] T093 [P] Add doc string headers to all new models referencing the relevant ADR + REQ ID
- [ ] T094 [P] Update `CLAUDE.md` (project root) with `etsy_channel_api` + `etsy_channel_email` sections + module entry-points
- [ ] T095 [P] Run `ruff check custom_addons/etsy_channel_api/ custom_addons/etsy_channel_email/` and fix any violations
- [ ] T096 Run module install on staging: `docker exec namco_odoo19 odoo -d namco_odoo19 -i etsy_channel_email -u etsy_channel_email --stop-after-init` then `-i etsy_channel_api`. Verify clean install (no warnings/errors).
- [ ] T097 Run full test suite on both modules; target ≥80% coverage on each
- [ ] T098 Run quickstart.md walkthrough end-to-end on staging — all 9 sections green
- [ ] T099 [P] Update `specs/006-master-plan/SRS_Multichannel_Hub_EN.md` if the canonical-payload schema diverges from the documented contract during implementation
- [ ] T100 Document operational runbook: source-failover incident response (who/when/what action), GDrive auth-failure escalation, Etsy scope-revocation recovery

---

## Dependencies (story completion order)

```
Setup (T001–T005) → Foundational (T006–T012) [requires multichannel_hub_core from Spec 003]
  ↓
US1 (T013–T020) → US2 (T021–T033)
  ↓
                  ┌→ US3 (T034–T039)
                  ├→ US5 (T040–T046) — cross-cutting throughout
                  ├→ US8 (T047–T063) — REQ-SRC-01..04 ★ THE NEW CORE
                  ├→ REQ-MSG-01 (T064–T071)
                  └→ US4 (T072–T077) [P2]
                       ↓
                  US6 (T078–T084) [P2]
                       ↓
                  Module rename (T085–T091) [run before Phase 12 polish]
                       ↓
                  Polish (T092–T100)
```

**Phase 0 (sandbox) MVP** = Setup + Foundational + US1 + US2 + US5 + US8 (against dev token only). This is what the Master Plan §4 calls "Phase 0 sandbox scaffolding."

**Phase 1 (production cutover) requires**:
- Etsy app scope review APPROVED (external dependency; Owner submitted critical-path 2026-04-13)
- Spec 003 `multichannel_hub_core` module installed (delivers `EtsyChannelAdapter` Protocol + `EtsyOrderIngestor` + `EtsyOrderPayload`)
- Module rename (T085–T087) applied so `etsy_channel_email` exists as peer to `etsy_channel_api`

**Phase 2 (remaining shops + webhooks)**: US4 (T072–T077) and US6 (T078–T084) layer on top of Phase 1.

## Parallel execution examples

Within Foundational (Phase 2): T006, T007, T009, T010, T011, T012 are all parallelisable.
Within US2 (Phase 4): T024, T025, T028, T029, T030, T031, T033 are parallelisable.
Within US8 (Phase 7): T048, T051, T053, T056, T057, T059, T060, T061, T063 are parallelisable.

## Test coverage targets

- Phase-2 ORM unit: 80%+ across `etsy_channel_api/services/`
- VCR cassettes: ≥50 representative receipts in `tests/fixtures/vcr_cassettes/` covering different currencies, gift messages, multi-line receipts, edge cases (empty buyer_message, missing listing_id)
- Adapter parity test (T089): API and email canonical payloads agree on required fields for the same receipt

## Cross-references

- spec.md US1–US8 (each task maps to a User Story phase)
- plan.md (Stage 4.2 refresh) — module structure, ADR alignments
- data-model.md (Stage 4.2 refresh) — model definitions
- research.md R7–R10 — design decisions encoded
- ADRs: 001 (split), 002 (sync_mode partially superseded), 003 (4-module), 005 (carrier), 008 (API-first), 008a v2 (source-switching)
- SRS v2.2 §3 (REQ-SRC-01..04), §10 (REQ-MSG-01), §11 (module map)
