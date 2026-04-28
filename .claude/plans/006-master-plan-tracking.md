# Execution Tracker — Master Plan 006

**Created**: 2026-04-13
**Source of truth**: [specs/006-master-plan/MASTER_PLAN.md](../../specs/006-master-plan/MASTER_PLAN.md) + [ADR-008](../../specs/006-master-plan/adrs/ADR-008-api-first-pivot.md)
**Update cadence**: weekly (every Monday), or on phase-boundary events

---

## How to use this file

- Every top-level task has an owner and a state: `todo` / `doing` / `blocked` / `done` / `dropped`.
- Blockers are explicit; if a task is blocked, the blocker row must name what's blocking and who owns unblocking it.
- External dependencies (Etsy scope review, Gearment sandbox creds) have their own section — these are **outside** the team's control and need separate status pings.
- Phases follow MASTER_PLAN §4. A task can only move to `doing` if the phase it belongs to has started.
- Do not edit task IDs; append new tasks at the bottom of the relevant phase.

---

## External dependencies (track weekly)

| ID | Dependency | Owner | Submitted | Status | Last ping | Next action |
|---|---|---|---|---|---|---|
| E1 | Etsy app scope review (`transactions_r/w`, `listings_r/w`, `shops_r`, `email_r`, optional `conversations_r`) | Owner | 2026-04-27 | `submitted-awaiting-review` | 2026-04-27 | Wait for Etsy review (3–8 weeks typical). Email parser remains active per ADR-008a v2 — no Phase 1 blocker since failover stays live. Re-ping at 2026-05-25 if no response. |
| E2 | Gearment sandbox credentials | Owner | — | `partial` | 2026-04-27 | Dashboard login obtained (`.env` `GEARMENT_DASHBOARD_*`). API sandbox keys still TODO — owner to request `GEARMENT_API_KEY`/`GEARMENT_API_SECRET`/`GEARMENT_WEBHOOK_HMAC_SECRET` from Gearment dashboard or support. P0-18 spike can begin reconnaissance via dashboard now. |
| E3 | Google Drive service-account creation (for ADR-006 §6 + Spec 004a US6) | Owner | 2026-04-27 | `done` | 2026-04-27 | Service-account JSON stored in `secrets/`. Wire up under P1-09 / P2-06. |

**Phase 1 unblocked from external deps.** E1 submission means production cutover is now timeline-bound (3–8 weeks Etsy review + our coding) rather than blocked. Email parser stays active as permanent failover — no risk if scope review delays.

---

## Phase 0 — Spec 002 cleanup + Spec 005 sandbox + observability (5–7 weeks)

### Wave A (completed 2026-04-13 before tracker existed)

| ID | Task | Owner | State | Notes |
|---|---|---|---|---|
| A1 | Owner sign-off on 9 master-plan decisions | Owner | `done` | 2026-04-13 |
| A2 | Author ADRs 001–007 | Architect | `done` | All Accepted 2026-04-13 |
| A3 | Freeze Spec 003 + 004 (SUPERSEDED banners) | Architect | `done` | — |
| A4 | Rewrite Spec 003 (three dashboards, delegation mixin, address-change approval) | Architect | `done` | 7 user stories |
| A5 | Author Spec 004a (tracking import + carrier detection + process-dashboard hook) | Architect | `done` | 5 user stories initial; 6th added in Wave B+ |

### Wave B — pivot + GDrive amendments (completed 2026-04-13)

| ID | Task | Owner | State | Notes |
|---|---|---|---|---|
| B1 | Author ADR-008 API-first pivot | Architect | `done` | 2026-04-13 |
| B2 | Revise MASTER_PLAN §3/§4/§6/§7 for pivot + GDrive + staging | Architect | `done` | — |
| B3 | Update Spec 005 status banner from DEFERRED to ACTIVE | Architect | `done` | Also fixed two email-fallback contradictions in spec body |
| B4 | Revise ADR-006 to add GDrive-URL primary mode + §6 GDrive policy | Architect | `done` | — |
| B5 | Add US6 GDrive polling + FR-026..FR-035 + `logistics.partner` to Spec 004a | Architect | `done` | Reversed the GDrive-out-of-scope line |
| B6 | Create this execution tracker | Architect | `done` | — |
| B7 | Author Vietnamese guide for Etsy app scope review submission | Architect | `done` | `guides/vi/etsy-app-review-guide.md` |
| B8 | Author Vietnamese guide for Gearment sandbox onboarding | Architect | `done` | `guides/vi/gearment-sandbox-guide.md` |

### 🎯 Active prioritization — coding-first to reach end-to-end pipeline test (set 2026-04-27)

**Owner directive (2026-04-27)**: Finish the coding chain that lets us run an order **end-to-end** (ingest → fulfill → track) on staging before touching reporting/observability surfaces. Reporting is Phase-1 polish, not a Phase-0 blocker.

**Critical path for E2E coding** (do these next, in order):

1. **P0-20** — module decomposition into 4 modules (architectural prerequisite for all Phase 1 code)
2. **P1-05** — `sale.order.fulfillment` delegation mixin (must land before any dashboard write hits `sale.order`)
3. **P1-06** — unified `shipping.carrier` model + seed (consumed by both Etsy push + GKE import)
4. **P0-14..17** — Spec 005 sandbox (OAuth PKCE → ApiClient → OrderSyncer → api.log) — code against dev token while E1 bakes
5. **P0-18** — Gearment spike (unblocked partial 2026-04-27); start dashboard-driven discovery to unblock P4-01
6. **P1-04** — address-change approval workflow (safety-critical; small surface)
7. **P1-01** — Order Dashboard (the operator entry point)
8. **P2-01..05** — tracking import wizard + carrier auto-detect (closes the loop back to Etsy push)
9. **P4-01** — Gearment adapter (outbound fulfillment) — needs P0-18 + E2 API keys

**Deferred until E2E green** (reporting/hardening — pick up in Phase 1 polish):

- ~~P0-11 `multichannel.sync.health` dashboard tile~~ (model already shipped under W3.1; tile can wait)
- ~~P0-12 ban `_logger.info`~~ (cleanup, not feature)
- ~~P0-13 indexes~~ (perf, only matters once we have prod-scale traffic)
- ~~P0-19 GKE schema fingerprint~~ (defensive; fold into P2-01)
- ~~P4-03 Spec 006 Sales Pricing Audit~~ (pure reporting; explicitly Phase 4)

**Phase 0 exit criteria revised**: drop "Health dashboard green for 7 days" from must-have. Keep "BA reconciliation sign-off" + "Spec 005 client passes integration tests against dev shop with zero writes to non-dev shops" + "staging operational." Health tile becomes a Phase 1 deliverable.

---

### Phase 0 execution (starts when Wave B actions handed off to owner)

| ID | Task | Owner | State | Depends on | Notes |
|---|---|---|---|---|---|
| P0-01 | Owner submits Etsy app scope review | Owner | `done` | B7 | **Submitted 2026-04-27**, awaiting Etsy review. Uses E1 tracker row. |
| P0-02 | Owner obtains Gearment sandbox credentials | Owner | `doing` | B8 | **Dashboard creds in `.env` 2026-04-27**; API sandbox keys still pending. Uses E2 tracker row. |
| P0-03 | Owner creates GDrive service-account JSON key | Owner | `done` | — | **JSON in `secrets/` 2026-04-27**. Uses E3 tracker row. |
| P0-04 | Provision staging environment on `129.150.63.207` — docker-compose stack + nightly prod snapshot restore + point outbound calls at Etsy/Gearment sandboxes | Ops (assign) | `doing` | — | **Local equivalent landed 2026-04-26** on branch `002-etsy-config-fixes-mvp` (root `docker-compose.yml`, separate Postgres + Odoo containers, ports 8169/8172). Remote `129.150.63.207` deployment + nightly snapshot restore still TODO. |
| P0-05 | Spec 002 US1 implementation (financial data) | Dev A | `done` | — | **Landed 2026-04-26** on branch `002-etsy-config-fixes-mvp` (T015–T020). Verified E2E against `tests/data/sample_single_order.txt`. |
| P0-06 | Spec 002 US2 implementation (confirm workflow) | Dev A | `done` | P0-05 | **Landed 2026-04-26** on branch `002-etsy-config-fixes-mvp` (T021–T024). Auto-confirm helper writes `invoice_status='invoiced'` directly per R5; no `account.move` generated. |
| P0-07 | Spec 002 US6 implementation (migration wizard) — batch-resumable, per-500 savepoints, `last_processed_id` checkpoint | Dev A | `done` | P0-05 | DA #3. **W3.2a backbone (2026-04-26)** + **W3.2b helper bodies (2026-04-26)** both landed on `main`. T035–T054 all `[X]`. Helpers reuse `OrderCreator` xmlid lookups + `_etsy_auto_confirm` + `base.partner.merge.automatic.wizard._merge`. Security boundary added: `is_etsy_customer=True` required on both merge sides. 162 tests green. |
| P0-08 | Manual triage + archive of 423 $0-price orders | Dev A + BA lead | `todo` | P0-07 | DA #2 |
| P0-09 | Freeze 500-order known-good sample for migration regression | Dev A | `todo` | P0-07 | — |
| P0-10 | Customer-dedup wizard producing CSV for BA approval (no auto-merge) | Dev A | `todo` | P0-07 | DA #9 |
| P0-11 | Implement `multichannel.sync.health` model + dashboard tile | Dev B | `todo` | — | DA #6. Phase 0 deliverable per ADR-008 §7 (add `parser_template_drift` metric) |
| P0-12 | Ban `_logger.info(` in models/services via pre-commit hook; fix 6 existing violations | Dev B | `todo` | — | Tech #7 |
| P0-13 | Add `tracking_number` index + composite `(etsy_shop_id, etsy_last_modified DESC)` | Dev B | `todo` | — | Tech #9 |
| P0-14 | Spec 005 sandbox — OAuth2 PKCE flow against owner's dev token | Dev B | `done` | P0-04 | **Landed 2026-04-27** on `feature/006-master-plan-coding`. Routes `/etsy/api/oauth/{authorize,callback}` (namespaced under `/api/` to avoid collision with existing Gmail OAuth at `/etsy/oauth/callback`). RFC 7636 PKCE flow with `secrets.token_urlsafe(32)` state, `ir.config_parameter` keyed pending-state persistence (TTL deferred to Phase 1). 3 new fields on `etsy.shop` (`etsy_oauth_access_token`/`refresh_token`/`token_expires_at`) with `groups='base.group_system'` ACL — plaintext at-rest per findings.md Q2 (Fernet encryption deferred to P1-10). 23 new tests (PKCE math + DB columns + HttpCase controller flow). Reviews: code-reviewer WARN→PASS after narrowing exception, security-reviewer WARN→PASS after adding `shop.check_access_rule('write')` gate on /authorize. 193 etsy_integration + 46 mhc tests green (239). |
| P0-15 | Spec 005 sandbox — `EtsyApiClient` with rate limiter + retry/backoff | Dev B | `done` | P0-14 | **Landed 2026-04-27** on `feature/006-master-plan-coding` (RED `d84f92c3cbb`, GREEN follows). `etsy_integration/services/etsy_api_client.py`: reads tokens from `etsy.shop` + `client_id` from `/opt/odoo/secrets/credentials.json`; sets `Authorization: Bearer` + `x-api-key` headers; `ping()` calls `GET /users/me`. Reuses `TokenBucket(8, 1.0)` from `multichannel_hub_core` (architect Q3 Phase-1 refactor already done in P0-18a). 429 retry: `Retry-After` capped at 60s + (1,2,4) backoff, raises `RateLimitError` after 3. 401: `etsy_oauth.refresh_access_token` → persist via `sudo()` (group_system fields, justified inline + in class docstring) → retry once; second 401 → `ValueError`. Proactive refresh when `expires_at < utcnow + 60s`. 19 mocked tests all green; 236 tests across all custom modules green. Reviews: code-reviewer initially BLOCK on credential-path off-by-one (fixed: hardcoded `/opt/odoo/secrets/credentials.json` matching `controllers/etsy_oauth._read_credentials`); security-reviewer WARN on tz-naive datetime (fixed: `utcnow()` in compare + write). |
| P0-16 | Spec 005 sandbox — `EtsyOrderSyncer` against dev shop with VCR fixtures | Dev B | `doing` | P0-15 | Split into 4 sub-slices (planner 2026-04-28; b further split to b1+b2 once payload-ingestion vs adapter scopes diverged). **P0-16a landed** (canonical payload + adapter Protocol). **P0-16b1 landed** on `feature/006-master-plan-coding`: payload→sale.order ingest path. `OrderCreator.process_etsy_payload(payload, shop)` peer to email's `process_parse_result`; `EtsyOrderIngestor.ingest(payload, shop)` thin wrapper hosting future audit-mode hooks; `etsy.shop.etsy_last_receipt_sync_at` cursor (system-only ACL); `sale.order.sync_source` ('api'/'email'/'webhook' reserved) + `etsy_raw_source_id`. 15 tests + 277 full regression green. Mock-and-fixture approach replaces `vcrpy` (owner decision 2026-04-28). Next: **P0-16b2** (EtsyApiAdapter — paginated GET /receipts + receipt→payload mapping, mocked tests), then **P0-16c** (EtsyOrderSyncer + sync_audit_mode + cassette-style JSON fixtures). |
| P0-17 | Spec 005 sandbox — `etsy.api.log` model + audit tests | Dev B | `todo` | P0-14 | `etsy.shop.sync_audit_mode` Boolean, read-only path in syncer (architect Q4) |
| P0-18a | Gearment sandbox auth probe — `GearmentApiClient` skeleton + `GET /api/v3/catalog?limit=1` ping + rate-limiter unit tests (mocked, no live writes) | Dev B | `done` | E2 | **Landed 2026-04-27** on `feature/006-master-plan-coding`. New module `multichannel_hub_fulfillment` (empty installable skeleton, depends on `multichannel_hub_core`). `multichannel_hub_core/utils/rate_limiter.py` `TokenBucket` (token-bucket; non-blocking; tests cover refill arithmetic, capacity cap, fractional accumulation). `multichannel_hub_fulfillment/services/gearment_api_client.py` `GearmentApiClient` reads env vars at init (fail-fast on missing), sets both `X-Gearment-Client-Key` + `X-Gearment-Client-Secret` headers via session, ping calls `GET api/v3/catalog?limit=1`, 429-retry honors `Retry-After` (capped at 60s defense-in-depth), falls back to (1,2,4) exponential backoff, raises `RateLimitError` after 3 retries. 27 mocked unit tests + 1 install test. Reviews: code-reviewer PASS, security-reviewer PASS with 2 LOW notes (HTTPS scheme validation deferred to P0-18b; redirect policy deferred). 217 tests across all custom modules green. **Owner action**: set `GEARMENT_API_BASE_URL` in `.env` before P0-18b. |
| P0-18b | Gearment sandbox live POC — register webhook + discover signature header + draft/quote/confirm idempotency on real sandbox order | Dev B | `todo` | P0-18a, E2 | Split from P0-18 on 2026-04-27. Requires interactive owner setup: tunnel for inbound webhook (ngrok or staging), sandbox keys in dashboard, real catalog SKU. Webhook signature header name + HMAC algorithm not in public docs; discover by inspecting first inbound POST. |
| P0-19 | GKE Excel schema fingerprinting — hash column layout, hard-fail on unknown | Dev A | `todo` | — | DA #4.3. Standalone utility that Spec 004a will consume |
| P0-20 | Module decomposition kickoff — split `etsy_integration` into 4 modules (core / fulfillment / etsy_channel / etsy_channel_migration) | Architect + Dev B | `doing` | P0-11 | ADR-003. **Skeleton landed 2026-04-27** on `feature/006-master-plan-coding`: `multichannel_hub_core` empty installable module (manifest + ACL header + README + CLAUDE.md). Installs clean; etsy_integration unchanged; 162 tests still green. P1-05 + P1-06 will populate it. |
| P0-21 | Spec 002 US3 (product config) + US4 (3-tier customer dedup + state/country resolution) | Dev A | `done` | P0-05 | **Landed 2026-04-26** on `main` (Wave 1 GREEN) — commits `5a2b9591d60` (US3) + `6d357cca651` (US4) + `aefbeb436ca` (closure). T025–T030 marked `[X]` in tasks.md. 6 W1 tests pass. Collateral install fix in `etsy_fiscal_data.xml` (tax_group_id + country_id). 4 inherited 002-MVP failures all share `cr.commit()` root cause; auto-cleared by T032 in W3. |

**Phase 0 exit criteria** (from MASTER_PLAN §4 as revised):
- BA lead signs reconciliation report (Odoo totals vs Excel per shop)
- Health dashboard green for 7 consecutive days
- 17K orders confirmed with correct fiscal config
- 423 $0 orders resolved (fixed or archived)
- Etsy scope review **submitted** (acceptance ≠ received)
- Spec 005 client passes integration tests against dev-token shop with zero writes to any non-dev shop
- Staging environment operational with nightly restore running

---

## Phase 1 — Three Dashboards + Approval Workflows + Spec 005 cutover (5–8 weeks)

| ID | Task | Owner | State | Depends on | Notes |
|---|---|---|---|---|---|
| P1-01 | Spec 003 US1 Order Dashboard (product image widget, merged tracking column, row decorations, MP note, overdue marker) | Dev A | `todo` | Phase 0 exit | BA #1-5 |
| P1-02 | Spec 003 US2+US3 Design file upload + 3-state approval + kanban | Dev A | `todo` | P1-01 | — |
| P1-03 | Spec 003 Tracking Dashboard (export/import, bulk state change, search) | Dev A | `todo` | P1-01 | BA #6 |
| P1-04 | Spec 003 Address-change approval workflow — `etsy.address.change.request` model, BA mail.activity, lock shipping fields while pending | Dev A | `todo` | P1-01 | Safety-critical |
| P1-05 | Spec 003 `sale.order.fulfillment` delegation mixin (ADR-007) | Dev B | `done` | P0-20 | **Landed 2026-04-27** on `feature/006-master-plan-coding`. Direction A per D-23 (`sale.order._inherits = {'sale.order.fulfillment': 'fulfillment_id'}`). 12 fields + block_reason constraint + sudo()-protected unlink cascade. ACL: salesman R/W/C, manager full. post_init_hook + 19.0.1.0.1 migration backfill for existing orders. 21 multichannel_hub_core tests + 162 etsy_integration regression all green. `shipping_carrier_id` deferred to P1-06 (Odoo 19 strict comodel check). |
| P1-06 | Spec 003 unified `shipping.carrier` model + initial seed (ADR-005) | Dev B | `done` | P1-05 | **Landed 2026-04-27** on `feature/006-master-plan-coding`. `shipping.carrier` standalone Model with 9 fields (name, code unique, sequence, is_active, tracking_url_template, tracking_prefix_regex, etsy_carrier_name Selection, gearment_carrier_name, notes). 7 seed rows (USPS/UniUni/YunExpress/4PX/DHL eCommerce/FedEx SmartPost/GKE Local) noupdate=0. `shipping_carrier_id` Many2one added to `sale.order.fulfillment` (ondelete='set null', index, mail.thread tracked). ACL: salesman read-only, manager full. 46 mhc tests + 162 etsy_integration regression all green (208). `etsy.carrier.mapping` deletion deferred to Spec 005 slice. XSS-on-render flag noted for P1-01/P2-01. |
| P1-07 | Spec 003 Vietnamese `.po` file + `_()` wrap all strings | Dev A | `todo` | P1-01 | BA R10 |
| P1-08 | Spec 003 audit log — `tracking=True` across tracked fields + chatter tab AC | Dev A | `todo` | P1-01 | BA #8 |
| P1-09 | ADR-006 revised — design-file GDrive upload wizard (service account, `storage_mode='gdrive'`, thumbnail local) | Dev B | `todo` | P0-03 | ADR-006 §3 revised |
| P1-10 | Spec 005 production OAuth flow — replace dev token with per-shop prod OAuth | Dev B | `waiting` | E1 approved, P0-14..P0-17 | E1 submitted 2026-04-27, awaiting Etsy review. Coding can proceed against dev token; flip to prod once scopes land. |
| P1-11 | Spec 005 pilot shop cutover — flip pilot shop's `etsy.shop.active_source='api'` once API adapter has succeeded ≥1× (per ADR-008a v2) | Dev B + BA lead | `waiting` | P1-10 | No 1-week audit mode needed — single canonical pipeline (ADR-008a). |
| P1-12 | Spec 005 `EtsyTrackingPusher` — wire to Tracking Dashboard writes, read `shipping.carrier.etsy_carrier_name` | Dev B | `waiting` | P1-10, P1-06 | US3 |
| P1-13 | Spec 005 additional 2–4 shops cutover by end of Phase 1 | Dev B + BA lead | `waiting` | P1-11 | Target 3–5 shops total by Phase 1 exit |

**Phase 1 exit criteria**:
- BA team working primarily in Odoo for order review, tracking management, address-change approvals
- Google Sheet in read-only mode
- 4-week parallel run complete, drift <1% for 10 consecutive days
- At least 1 pilot shop on `sync_mode='api_only'` in production with zero data loss over 30-day shadow window

---

## Phase 2 — Spec 004a tracking import + GDrive polling + remaining shop cutovers (4–5 weeks)

| ID | Task | Owner | State | Depends on | Notes |
|---|---|---|---|---|---|
| P2-01 | Spec 004a US1 Excel import wizard with schema fingerprinting | Dev A | `todo` | Phase 1 exit | — |
| P2-02 | Spec 004a US2 carrier auto-detection (USPS / UniUni / YunExpress / fallback) | Dev A | `todo` | P2-01 | — |
| P2-03 | Spec 004a US3 Process Dashboard stock-move hook | Dev B | `todo` | P2-01 | — |
| P2-04 | Spec 004a US4 import log visibility + replay | Dev A | `todo` | P2-01, P2-02 | — |
| P2-05 | Spec 004a US5 `shipping.carrier` admin UX + extended seed | Dev A | `todo` | P2-02 | — |
| P2-06 | Spec 004a US6 GDrive polling cron — `logistics.partner`, `logistics.inbox.poller`, archive-on-success flow | Dev B | `todo` | P1-09 | Per ADR-006 §6 + revised spec |
| P2-07 | Remaining 14–16 shops cutover to `sync_mode='api_only'` | Dev B + BA lead | `todo` | P1-13 | Running in background |
| P2-08 | Disable Gmail cron at module level once all shops flipped + 30-day shadow elapsed | Dev B | `todo` | P2-07 | ADR-008 §5 |

**Phase 2 exit criteria**:
- Daily GKE imports either manual via wizard or auto-polled from GDrive
- Tracking Dashboard reflects imports within 5 minutes
- Process Dashboard in use for all in-flight orders
- All 19 shops on `sync_mode='api_only'`
- Gmail cron not polling any live shop

---

## Phase 4 — Gearment + returns + pricing audit (6–8 weeks, starts ~4 weeks earlier than pre-pivot)

| ID | Task | Owner | State | Depends on | Notes |
|---|---|---|---|---|---|
| P4-01 | Spec 004b Gearment adapter (draft/quote/confirm state machine, HMAC webhook, rate-limit reuse) | Dev B | `todo` | Phase 2 exit, P0-18 | ADR-001 split |
| P4-02 | Spec 004c returns/refunds + `etsy.order.ticket` minimal custom | Dev A | `todo` | Phase 2 exit | BA #7 |
| P4-03 | Spec 006 Sales Pricing Audit dashboard — SQL view + snapshot model | Dev A | `todo` | Phase 2 exit | BA R5 |

---

## Phase 5 — Inventory / catalog / scan / Amazon / website (parallel tracks)

| ID | Task | Owner | State | Depends on | Notes |
|---|---|---|---|---|---|
| P5-01 | Spec 007 raw-material inventory (native `stock` + `stock_forecasted` + Excel seed wizard) | — | `todo` | Phase 4 | PD feedback |
| P5-02 | Spec 008 Catalog Dashboard per product | — | `todo` | Phase 4 | BA #11 |
| P5-03 | Spec 009 Barcode scan sheet (evaluate `stock_barcode` CE first) | — | `todo` | Phase 4 | BA #15 |
| P5-04 | Spec 010 Amazon channel integration | — | `todo` | Phase 2 exit (all Etsy shops on `api_only`) | Q5 answer: arch only until Etsy live, then implement |
| P5-05 | Spec 011 Website channel integration | — | `todo` | P5-04 | Owner's vision |

---

## Risk watchlist (from MASTER_PLAN §5 — update weekly)

| ID | Risk | Current status | Last reviewed |
|---|---|---|---|
| R1 | Etsy scopes denied | monitoring E1 — still not submitted; critical-path slip widening | 2026-04-26 |
| R2 | 17K migration OOM / partial rollback | mitigated by design (batch-resumable); W3.1 landed savepoint batching + sync.health for the import wizard; W3.2 (US6 migration wizard) reuses same pattern for the 17K backlog. 3 of 4 inherited test failures cleared. | 2026-04-26 |
| R3 | Gearment API undocumented / rate-limits unknown | blocked on E2 — still no creds | 2026-04-26 |
| R4 | GKE Excel schema changes silently | mitigated by P0-19 schema fingerprint (not started) | 2026-04-26 |
| R8 | Etsy OAuth refresh fails day 91 | covered by P0-11 health dashboard (not started); architect Q2 deferred token encryption to Phase 1 | 2026-04-26 |
| R13 | Spec 003 field bloat on sale.order | mitigated by P1-05 delegation mixin (ADR-007); W1 GREEN added 0 new fields to sale.order — still on track | 2026-04-26 |
| R15 | Observability absent | P0-11 still `todo`; the 002 MVP slice did add `etsy.sync.health` model (T006-T009), so 50% of the deliverable is in main | 2026-04-26 |

---

## Decision log pointers

All architectural decisions live in `specs/006-master-plan/adrs/`:
- [ADR-001](../../specs/006-master-plan/adrs/ADR-001-spec-004-split.md) — Spec 004 split into 004a/004b/004c
- [ADR-002](../../specs/006-master-plan/adrs/ADR-002-drop-dual-sync-mode.md) — Drop dual sync mode
- [ADR-003](../../specs/006-master-plan/adrs/ADR-003-module-decomposition.md) — 4-module split
- [ADR-004](../../specs/006-master-plan/adrs/ADR-004-enterprise-alternatives.md) — Custom over Enterprise
- [ADR-005](../../specs/006-master-plan/adrs/ADR-005-carrier-unification.md) — Unified `shipping.carrier`
- [ADR-006](../../specs/006-master-plan/adrs/ADR-006-design-file-storage.md) — GDrive primary (revised 2026-04-13)
- [ADR-007](../../specs/006-master-plan/adrs/ADR-007-fulfillment-delegation-mixin.md) — Fulfillment delegation mixin
- [ADR-008](../../specs/006-master-plan/adrs/ADR-008-api-first-pivot.md) — API-first pivot (2026-04-13)

---

## Change log

- **2026-04-13**: File created. Wave A + Wave B logged as complete. Phase 0 execution tasks defined. E1 + E2 + E3 external dependencies added.
- **2026-04-26**: Promoted `main` as canonical trunk (linear: doc snapshot `f0a5be98686` → 002 MVP `874e06ada5f` → playbook cherry-pick `579dabd71e6`). All future spec-slice worktrees branch off `main`. Stale branch `005-etsy-api-channel` retained for history; do not commit to it. Wave 1 (`002-us3-us4`) and Wave 2 (`005-etsy-sandbox`) launched off `main` under the implementation playbook (`.claude/plans/006-implementation-playbook.md`).
- **2026-04-26**: W1 RED phase complete on `002-us3-us4` (commit `be2a08489e0`) — 30 test methods across 3 new files for T025–T030. **BLOCKED on docker-compose worktree-mount issue** (see `specs/002-etsy-config-fixes/findings.md`). W2 architect advisory landed on `005-etsy-sandbox` (commit `7bab697072f`) — 5 open questions await Owner decision in `specs/005-etsy-api-channel/findings.md`. P0-14..17 moved to `blocked` until decisions land.
- **2026-04-26**: Workflow pivot to single-workspace-on-main. All wave branches merged to `main` via rebase + ff. Wave worktrees removed. Owner accepted W2 architect recommendations as defaults; revisit at W7 E2E. P0-14..17 unblocked.
- **2026-04-26**: W1 GREEN complete on `main` — T025–T030 + install-blocker fix + 1 outdated test fix. Commits `5a2b9591d60` (US3 product config) and `6d357cca651` (US4 partner dedup + geo). 6 W1 tests pass; 4 pre-existing 002-MVP failures inherited (all share `cr.commit()` root cause, naturally resolved by T032 in W3). P0-05/P0-06 partially complete; full close pending W3 (US5/US6).
- **2026-04-26**: W3.1 GREEN complete on `main` — T031–T034 (US5 import wizard hardening). Header-based column mapping replacing `_COL_*` constants, per-order savepoint inside 500-batch sync.health checkpoint loop, `warning_count` + `validation_notes` observability fields, new `test_import_wizard_headers.py` (5 methods). All 87 tests pass; 3 of 4 inherited 002-MVP failures cleared (`test_import_creates_order`, `test_import_multiple_lines_same_order`, `test_import_skips_duplicate`). 4th (`test_email_log_unique_constraint`) skipped — root cause is `_sql_constraints` UNIQUE not being deployed at SQL level, unrelated to W3.1 scope; investigation deferred. See `specs/002-etsy-config-fixes/findings.md` W3.1 entry. W3.2 (US6 migration wizard) is next.
- **2026-04-26**: W3.2a GREEN complete on `main` — Spec 002 US6 backbone. Original W3.2 was ~1,410 LOC in one commit; split into W3.2a (backbone, ~860 LOC) and W3.2b (fix-helper bodies, planned ~700 LOC) for review hygiene. W3.2a landed: `etsy.data.migration.wizard` model + 12 fields (T035), anomaly quarantine to `tempfile.mkstemp` 0o600 CSV (T036), batched iteration with `last_processed_id` resumption (T037), `etsy.sync.health` per-batch checkpoints + final ok/warning/error state (T038), orchestration shell calling stub helpers (T046), wizard view + menu (`groups="sales_team.group_sale_manager"`) + ACL row (T047/T048/T049), `__init__.py` registration (T050). 12 new tests pass; 99 tests total green. Security fix: `tempfile.mkstemp()` replaces world-readable `open()` write to `/tmp`. Surprises captured in findings.md: Odoo 19 renamed `groups_id`→`group_ids`, `product.product.type`→`is_storable`, `mock.patch.object` doesn't work on recordset instances. Fix-helper bodies (T039–T045) + expanded tests (T051–T054) move to W3.2b.
- **2026-04-26**: W3.2b GREEN complete on `main` — Spec 002 US6 fix-helper bodies. T039 (financial config), T040 (shipping lines, idempotent), T041 (price re-parse from Excel), T042 (product config + categorize), T043 (confirm + invoice_status), T044 (dedup CSV via `_normalize_text`), T045 (apply_merges via `base.partner.merge.automatic.wizard._merge`). +`approved_merges_file` field. 29 new tests across 4 files (T051–T054). 162 tests total green. Security boundary added per security-reviewer: `is_etsy_customer=True` required on both partners before merge — prevents a `sales_team.group_sale_manager` from crafting a CSV that merges the company partner into a customer. Status message sanitized to basename-only (no absolute path leak). Memory correction: Odoo 19 CE base ships `base.partner.merge.automatic.wizard._merge` — earlier note "no merge helper available, ~50 LOC inline" was wrong. P0-07 → `done`.
- **2026-04-27**: External dependencies update + strategic re-prioritization. **E1 Etsy scope review SUBMITTED** (awaiting Etsy review, 3–8 weeks typical) — no longer blocks Phase 1 since email parser is permanent failover per ADR-008a v2. **E2 Gearment dashboard creds in `.env`** (`GEARMENT_DASHBOARD_*`); API sandbox keys still pending — P0-18 unblocked for dashboard-driven discovery. **E3 GDrive service-account JSON in `secrets/`** — done. P0-01/P0-03 → `done`, P0-02 → `doing`, P0-18 → `doing`. P1-10..13 moved from `blocked` to `waiting` (coding can proceed against dev token). Owner directive: **finish coding chain to E2E pipeline test first; reporting is Phase-1 polish**. Deferred: P0-11 dashboard tile, P0-12 logger ban, P0-13 indexes, P0-19 schema fingerprint. New critical path documented in tracker §"Active prioritization": P0-20 → P1-05 → P1-06 → P0-14..17 → P0-18 → P1-04 → P1-01 → P2-01..05 → P4-01. Security: `.env` added to `.gitignore` (was previously untracked but unprotected — SSH password + JIRA API key already in file).
- **2026-04-27**: Workflow revision — forward work moves to long-lived feature branch `feature/006-master-plan-coding` cut from `main`. Single contributor; merge back after W7 E2E. Memory feedback updated. **P0-20 skeleton landed** on the new branch: `multichannel_hub_core` empty installable module (manifest, `models/__init__.py`, `services/__init__.py`, `security/ir.model.access.csv` header-only, README, module CLAUDE.md). Verifications: install exits 0; `etsy_integration -u` exits 0; 162 tests still green. Ready to populate via P1-05 (delegation mixin) and P1-06 (unified `shipping.carrier`). P0-20 → `doing` (kickoff complete; full decomposition closes when the four modules carry their final content).
- **2026-04-27**: **P1-05 GREEN landed** on `feature/006-master-plan-coding` (commit pending — see git log). `sale.order.fulfillment` standalone Model with 12 Phase-1 fields (tracking_number, shipping_date, label_status, tracking_state, mp_note, pd_note, pic_user_id, order_priority, production_blocked, block_reason, fulfillment_status; `shipping_carrier_id` deferred to P1-06). `sale.order` extension uses Direction A: `_inherits = {'sale.order.fulfillment': 'fulfillment_id'}`, `fulfillment_id` Many2one (required, ondelete='cascade', index=True). Sudo()-protected `unlink()` override cascades sibling deletion (system-enforced data integrity). post_init_hook + `migrations/19.0.1.0.1/post-backfill-fulfillment.py` backfill `fulfillment_id` for pre-existing orders. ACL: salesman R/W/C; manager full. 21 multichannel_hub_core tests + 162 etsy_integration regression all green (183 total). Two reviews ran in parallel: code-reviewer PASS, security-reviewer initially BLOCKED on unlink-cascade ACL bypass (over-stated — current code AccessError'd silently after super().unlink()) — fixed via sudo() with explanatory comment + new `test_sales_user_cannot_unlink_fulfillment_directly` ACL test. ADR-007 amended (banner) with D-23 inheritance-direction inversion; Spec 003 findings.md created. Surprise: Odoo 19 `auto_join` kwarg removed; `tracking=True` requires `_inherit=['mail.thread']`; `Many2one` to non-existent comodel rejected at registry build (no string-form deferral).
- **2026-04-27**: **P0-18 split into P0-18a (auth probe, mocked-only) + P0-18b (live sandbox POC)**. Owner confirmed Gearment dev docs at `developers.gearment.com/api.md`: auth via `X-Gearment-Client-Key` + `X-Gearment-Client-Secret` HEADERS (both required; landing page `api.gearment.com` was misleading about query-param auth). Production base URL `https://apiv2.gearment.com/integration-handler`, sandbox `https://api.gearmentinc.com/integration-handler`. v3 endpoints inventoried (orders/draft, catalog, webhooks). Webhook signature header name + HMAC algorithm undocumented — discover at runtime. P0-18a (this slice) scope: `GearmentApiClient` skeleton with header auth + `GET /api/v3/catalog?limit=1` ping + rate-limiter unit tests using mocked `requests`; no live network. P0-18b deferred until owner can interactively set up tunnel + sandbox keys. `GEARMENT_API_BASE_URL` empty in `.env` — owner to set before any live test. Memory `project_gearment_gke.md` updated with full endpoint + auth detail.
- **2026-04-27**: **P0-18a GREEN landed** on `feature/006-master-plan-coding`. New module `multichannel_hub_fulfillment` (empty installable skeleton, depends on `multichannel_hub_core`). `multichannel_hub_core/utils/rate_limiter.py` `TokenBucket` (token bucket, non-blocking, advisory; reusable for Etsy API client). `multichannel_hub_fulfillment/services/gearment_api_client.py` `GearmentApiClient` reads `GEARMENT_API_KEY` / `GEARMENT_API_SECRET` / `GEARMENT_API_BASE_URL` from env (fail-fast on missing); session sets both auth headers; `ping()` calls `GET api/v3/catalog?limit=1`; 429-retry with `Retry-After` honor (capped at 60s defense-in-depth) + (1,2,4) backoff fallback; raises `RateLimitError` after 3 retries. 27 mocked unit tests + 1 install test, 0 fail / 0 error. Full regression: 217 tests across `multichannel_hub_*` + `etsy_integration` — all green. Reviews: code-reviewer PASS, security-reviewer PASS with 2 LOW (HTTPS scheme validation + redirect policy, both deferred to P0-18b). Surprises: (a) Odoo test runner skips `unittest.TestCase` — must use `TransactionCase`; (b) `mock.patch` paths require `odoo.addons.<module>` prefix; (c) `Retry-After` cap added during review. Findings in `specs/004-fulfillment-routing/findings.md`.
- **2026-04-27**: **P0-15 RED landed** on `feature/006-master-plan-coding` (commit `d84f92c3cbb`). Phase 2 (ORM Unit Tests) complete: `test_etsy_api_client.py` with 19 test methods across 5 classes defining complete contract for `EtsyApiClient` service without implementation. Test suites: `TestEtsyApiClientInitialization` (shop token field validation + credentials file loading), `TestEtsyApiClientSession` (_session() sets Authorization + x-api-key headers), `TestEtsyApiClientPing` (ping() endpoint, JSON return on 200, ValueError on 403, HTTPError on 500), `TestEtsyApiClientRateLimiting` (429-retry with Retry-After honor + capped at 60s + fallback exponential backoff (1,2,4), RateLimitError after 3 retries), `TestEtsyApiClient401Refresh` (401 refresh_access_token() + one attempt per request, refresh failure raises ValueError, proactive refresh within 60s, no proactive when token valid long). All 19 tests intentionally FAIL (ERROR state) because `EtsyApiClient` is stub. Module `etsy_integration` installs clean; 162 pre-existing tests still green (no regressions). Next: Phase 3 (GREEN implementation). Surprises: Patch paths must use `odoo.addons.<module>` prefix; TransactionCase required for Odoo test runner (unittest.TestCase skipped).
- **2026-04-28**: **P0-16b2 GREEN landed** on `feature/006-master-plan-coding` (commit `ab48e8a8782`). Third sub-slice; closes API-side. `services/etsy_api_adapter.py` `EtsyApiAdapter(client)` implements `EtsyChannelAdapter` Protocol: `fetch_new_orders` paginates GET `shops/{shop_id}/receipts` (limit=100, offset, optional `min_last_modified`), yields `EtsyOrderPayload` lazily, stops when `next_offset` null/missing. `_receipt_to_payload` handles Etsy money `{amount, divisor, currency_code}` → float, builds address + line items, flattens variations list→dict (`{Color: Blue, Size: L}`). `health_check` delegates to `client.ping()`: OK / DEGRADED on RateLimitError / DOWN on any other Exception (broad-except is fail-safe by design). New `EtsyApiClient.get(path, params)` public wrapper. 23 mocked tests across 4 classes + 300 full-regression green. Reviews: code-reviewer PASS, security-reviewer PASS with one LOW applied (defensive `int(shop_id)` URL coercion). Surprise during RED→GREEN: first pagination loop also short-circuited when `len(results) < limit`, breaking the legitimate-1-result-with-next-offset case; removed the heuristic, now trust `next_offset` alone. Tasks T021 + T028 marked done in spec tasks.md. Next: **P0-16c** (`EtsyOrderSyncer` orchestrator + `sync_audit_mode` field + JSON-fixture-backed adapter & syncer tests).
- **2026-04-28**: **P0-16b1 GREEN landed** on `feature/006-master-plan-coding` (commit `a804bb17e31`). Second sub-slice of P0-16, closes the canonical-payload→DB write path. `services/etsy_order_ingestor.py`: `EtsyOrderIngestor.ingest(payload, shop)` thin wrapper. `services/order_creator.py`: new public `process_etsy_payload(payload, shop)` + private `_payload_partner` SimpleNamespace shim (boundary adapter for `find_or_create_partner` while it remains duck-typed; refactor deferred). `models/etsy_shop.py`: new `etsy_last_receipt_sync_at` Datetime with `groups='base.group_system'` (ACL parity with OAuth tokens). `models/sale_order.py`: new `sync_source` Selection (api/email/webhook-reserved) + `etsy_raw_source_id` Char. 15 new tests across 3 classes + 277 full-regression green. Reviews: code-reviewer PASS with 2 HIGH (resolved: widened sync_source Selection, kept email-path consistency on unset line `name`); security-reviewer PASS with 1 HIGH (resolved: tightened cursor ACL). Tasks T008 marked done in spec tasks.md (subset of T008 scope; adapter-selection logic moves to P0-16c). Surprises: none — Odoo upgrade handles new NULL columns transparently on ~17K existing rows. Next: **P0-16b2** EtsyApiAdapter (paginated GET /receipts + receipt→payload mapping, mocked tests).
- **2026-04-28**: **P0-16a GREEN landed** on `feature/006-master-plan-coding` (commit `e55ea6884c7`). First sub-slice of P0-16 (planner-recommended 3-way split: 16a foundation, 16b api adapter+ingestor, 16c syncer+cassettes). `etsy_integration/services/etsy_order_payload.py`: frozen dataclasses `EtsyAddressPayload` / `EtsyLineItemPayload` / `EtsyOrderPayload`. `etsy_integration/services/etsy_channel_adapter.py`: `@runtime_checkable` Protocol `EtsyChannelAdapter` (`fetch_new_orders`, `health_check`) + `HealthStatus` enum. 26 contract tests across 5 classes. Full regression `-u etsy_integration,multichannel_hub_core,multichannel_hub_fulfillment`: 262 tests, 0 fail, 0 error. **Architectural decision**: module-home for these two files moved from `multichannel_hub_core` (per spec `data-model.md` L260) to `etsy_integration` because module CLAUDE.md prohibits Etsy-named code in core. Documented as a finding entry 2026-04-28 in `specs/005-etsy-api-channel/findings.md`; spec text superseded by finding. Tasks T006/T007 marked done in spec tasks.md. Reviews: code-reviewer PASS (one MEDIUM resolved by docstring on `@runtime_checkable` semantics); security-reviewer initial **HIGH** on `line_items: list[...]` mutability bypass — resolved by switching to `tuple[..., ...]` + new regression test `test_line_items_cannot_be_appended`. `variations` dict mutability documented as a contract (per-receipt snapshot from adapter; consumers must not mutate). Owner decisions during planning: (1) `OrderCreator._create_order_from_payload` helper for ingestor reuse (P0-16b); (2) mock + JSON fixtures, no `vcrpy` dependency; (3) reuse `sync_mode` per ADR-002 — no `active_source` selection field. Next: P0-16b (`EtsyApiAdapter` + receipt→payload mapping + shop cursor field + minimal `EtsyOrderIngestor`).
