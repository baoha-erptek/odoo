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
| E1 | Etsy app scope review (`transactions_r/w`, `listings_r/w`, `shops_r`, `email_r`, optional `conversations_r`) | Owner | — | `todo` | — | Owner submits this week per ADR-008 §4. Follow guide at [guides/vi/etsy-app-review-guide.md](../../specs/006-master-plan/guides/vi/etsy-app-review-guide.md) |
| E2 | Gearment sandbox credentials | Owner | — | `todo` | — | Owner contacts Gearment. Follow guide at [guides/vi/gearment-sandbox-guide.md](../../specs/006-master-plan/guides/vi/gearment-sandbox-guide.md) |
| E3 | Google Drive service-account creation (for ADR-006 §6 + Spec 004a US6) | Owner | — | `todo` | — | Owner creates GCP project, enables Drive API, generates service-account JSON key |

**If E1 is not submitted by end of week**, escalate. E1 is on the critical path for Phase 1 cutover.

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

### Phase 0 execution (starts when Wave B actions handed off to owner)

| ID | Task | Owner | State | Depends on | Notes |
|---|---|---|---|---|---|
| P0-01 | Owner submits Etsy app scope review | Owner | `todo` | B7 | Uses E1 tracker row |
| P0-02 | Owner obtains Gearment sandbox credentials | Owner | `todo` | B8 | Uses E2 tracker row |
| P0-03 | Owner creates GDrive service-account JSON key | Owner | `todo` | — | Uses E3 tracker row |
| P0-04 | Provision staging environment on `129.150.63.207` — docker-compose stack + nightly prod snapshot restore + point outbound calls at Etsy/Gearment sandboxes | Ops (assign) | `doing` | — | **Local equivalent landed 2026-04-26** on branch `002-etsy-config-fixes-mvp` (root `docker-compose.yml`, separate Postgres + Odoo containers, ports 8169/8172). Remote `129.150.63.207` deployment + nightly snapshot restore still TODO. |
| P0-05 | Spec 002 US1 implementation (financial data) | Dev A | `done` | — | **Landed 2026-04-26** on branch `002-etsy-config-fixes-mvp` (T015–T020). Verified E2E against `tests/data/sample_single_order.txt`. |
| P0-06 | Spec 002 US2 implementation (confirm workflow) | Dev A | `done` | P0-05 | **Landed 2026-04-26** on branch `002-etsy-config-fixes-mvp` (T021–T024). Auto-confirm helper writes `invoice_status='invoiced'` directly per R5; no `account.move` generated. |
| P0-07 | Spec 002 US6 implementation (migration wizard) — batch-resumable, per-500 savepoints, `last_processed_id` checkpoint | Dev A | `todo` | P0-05 | DA #3 |
| P0-08 | Manual triage + archive of 423 $0-price orders | Dev A + BA lead | `todo` | P0-07 | DA #2 |
| P0-09 | Freeze 500-order known-good sample for migration regression | Dev A | `todo` | P0-07 | — |
| P0-10 | Customer-dedup wizard producing CSV for BA approval (no auto-merge) | Dev A | `todo` | P0-07 | DA #9 |
| P0-11 | Implement `multichannel.sync.health` model + dashboard tile | Dev B | `todo` | — | DA #6. Phase 0 deliverable per ADR-008 §7 (add `parser_template_drift` metric) |
| P0-12 | Ban `_logger.info(` in models/services via pre-commit hook; fix 6 existing violations | Dev B | `todo` | — | Tech #7 |
| P0-13 | Add `tracking_number` index + composite `(etsy_shop_id, etsy_last_modified DESC)` | Dev B | `todo` | — | Tech #9 |
| P0-14 | Spec 005 sandbox — OAuth2 PKCE flow against owner's dev token | Dev B | `todo` | P0-04 | ADR-008 §2. Owner accepted architect Q1–Q5 recommendations 2026-04-26 (revisit at W7 E2E). Spec 005 tasks.md generated (110 tasks). |
| P0-15 | Spec 005 sandbox — `EtsyApiClient` with rate limiter + retry/backoff | Dev B | `todo` | P0-14 | Per-client token bucket for sandbox, shared bucket as Phase 1 refactor (architect Q3) |
| P0-16 | Spec 005 sandbox — `EtsyOrderSyncer` against dev shop with VCR fixtures | Dev B | `todo` | P0-15 | One-per-test VCR cassettes in `tests/fixtures/vcr/`, quarterly refresh (architect Q1) |
| P0-17 | Spec 005 sandbox — `etsy.api.log` model + audit tests | Dev B | `todo` | P0-14 | `etsy.shop.sync_audit_mode` Boolean, read-only path in syncer (architect Q4) |
| P0-18 | Gearment sandbox POC — 3-day spike (auth, rate limits, HMAC, draft/quote/confirm idempotency) | Dev B | `blocked` | E2 | Cannot start without creds |
| P0-19 | GKE Excel schema fingerprinting — hash column layout, hard-fail on unknown | Dev A | `todo` | — | DA #4.3. Standalone utility that Spec 004a will consume |
| P0-20 | Module decomposition kickoff — split `etsy_integration` into 4 modules (core / fulfillment / etsy_channel / etsy_channel_migration) | Architect + Dev B | `todo` | P0-11 | ADR-003. Must complete before Phase 1 code |
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
| P1-05 | Spec 003 `sale.order.fulfillment` delegation mixin (ADR-007) | Dev B | `todo` | P0-20 | Before any US1 writes |
| P1-06 | Spec 003 unified `shipping.carrier` model + initial seed (ADR-005) | Dev B | `todo` | P1-05 | Delete `etsy.carrier.mapping` here |
| P1-07 | Spec 003 Vietnamese `.po` file + `_()` wrap all strings | Dev A | `todo` | P1-01 | BA R10 |
| P1-08 | Spec 003 audit log — `tracking=True` across tracked fields + chatter tab AC | Dev A | `todo` | P1-01 | BA #8 |
| P1-09 | ADR-006 revised — design-file GDrive upload wizard (service account, `storage_mode='gdrive'`, thumbnail local) | Dev B | `todo` | P0-03 | ADR-006 §3 revised |
| P1-10 | Spec 005 production OAuth flow — replace dev token with per-shop prod OAuth | Dev B | `blocked` | E1 approved, P0-14..P0-17 | Cannot flip to prod without scopes |
| P1-11 | Spec 005 pilot shop cutover — `sync_audit_mode=True` 1–2 weeks, BA review, flip `api_only` | Dev B + BA lead | `blocked` | P1-10 | ADR-002 cutover procedure |
| P1-12 | Spec 005 `EtsyTrackingPusher` — wire to Tracking Dashboard writes, read `shipping.carrier.etsy_carrier_name` | Dev B | `blocked` | P1-10, P1-06 | US3 |
| P1-13 | Spec 005 additional 2–4 shops cutover by end of Phase 1 | Dev B + BA lead | `blocked` | P1-11 | Target 3–5 shops total by Phase 1 exit |

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
| R2 | 17K migration OOM / partial rollback | mitigated by design (batch-resumable); verify in W3 (US5/US6 — P0-07). 4 import-wizard tests currently blocked on `cr.commit()` (T032 fix) | 2026-04-26 |
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
