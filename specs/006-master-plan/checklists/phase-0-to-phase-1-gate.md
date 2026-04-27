---
title: "Phase-0 → Phase-1 Entry-Gate Checklist"
date: "2026-04-27"
revision: "v1 — Stage 4.5 of master-plan execution"
purpose: "Single checklist that gates the transition from Phase-0 sandbox to Phase-1 production cutover. Per playbook, this is the once-per-major-phase-boundary heavyweight gate."
status: "Active — must reach 100% before any production shop flips to active_source='api'"
authority: "Master plan §4 (Phase 0 → Phase 1 transition); ADR-008a v2 §2-§6"
---

# Phase-0 → Phase-1 Entry-Gate Checklist

This is the **single project-level gate** that must pass before Phase-1 production cutover begins. Every item is a verifiable assertion, not a "feels ready" judgment.

> **When to run**: once Phase-0 sandbox work feels complete. The first failing item halts the gate and routes back to the responsible owner.
>
> **How to run**: walk through each section in order; check the box only when the verification command/observation passes; record evidence (commit SHA, log path, screenshot).
>
> **Exit**: 100% green → Phase 1 may begin. <100% → fix or document-then-fix; do NOT bypass.

---

## A. External dependencies (out of project's control — start ASAP)

- [ ] **A1. Etsy app scope review APPROVED** — all required scopes granted: `transactions_r`, `transactions_w`, `listings_r`, `listings_w`, `shops_r`, `email_r`. Confirmation email or app-dashboard screenshot archived in `specs/006-master-plan/clarifications/`. *(Owner submitted on critical-path 2026-04-13; expect 3–8 weeks turnaround.)*
- [ ] **A2. Conversations scope status documented** — confirmed REJECTED by Etsy; REQ-MSG-01 design pivoted to `buyer_message` ingestion via existing `transactions_r` scope. (No action if still rejected — this is the expected state.)
- [ ] **A3. Gearment sandbox credentials obtained** (for parallel Spec 004b spike — non-blocking for Phase 1 but tracked as a master-plan critical-path item per §6 decision 9)

## B. Spec 002 must be shipped first (per master-plan C1)

- [ ] **B1. 17,659 historical orders normalised** — Spec 002 reconciliation report shows row counts match Excel-source within tolerance; BA Lead has signed.
- [ ] **B2. 423 $0-price orders resolved** — either recovered from source OR archived with documented reason; zero `sale.order` rows remain with `amount_total=0` AND `state IN ('draft', 'sent')`.
- [ ] **B3. Customer dedup wizard run** with BA approval; merged-partner CSV archived; no auto-merges.
- [ ] **B4. `etsy.sync.health` model + dashboard tile live** showing per-integration `last_run`, `row_count`, `error_count`. Master-plan green tile observed for ≥7 consecutive days.

## C. Spec 003 module foundation must be installed (per ADR-001 + ADR-003)

- [ ] **C1. `multichannel_hub_core` module installed** on staging. `ir_module_module.state='installed'`. Models loaded: `shipping.carrier`, `etsy.address.change.request`, `design.file`, `design.file.route`, `design.print.batch`, `order.pipeline`, `order.pipeline.state`, `pipeline.team`, `order.pipeline.transition.log`.
- [ ] **C2. Default seed pipelines loaded** — three pipelines from `data/order_pipeline_seed.xml` (`vn_internal_production` v1 with 17 stages, `gearment_pod` v1 with 4 stages, `multi_technique_hybrid` v1 with 3 stages).
- [ ] **C3. `shipping.carrier` seed entries loaded** (7 rows: USPS, UniUni, YunExpress, 4PX, DHL eCommerce, FedEx SmartPost, GKE Local) — each with valid `etsy_carrier_name` mapping or explicit `other`.
- [ ] **C4. `sales_channel` backfill complete** — every existing `sale.order` row has `sales_channel='etsy'` AND `channel_order_ref=etsy_order_id` (FR-024/FR-025 verification SQL: `SELECT COUNT(*) FROM sale_order WHERE sales_channel IS NULL` returns 0).
- [ ] **C5. Three dashboards visible** — Order Dashboard, Tracking Dashboard, Process Dashboard all render in <3s with the 17K+ row dataset on staging. Performance verified via DevTools Network tab.

## D. Spec 003 safety-critical workflows verified

- [ ] **D1. Address-change approval workflow ON** — manual smoke test (per Spec 003 quickstart §5) passes: MP request → BA-lead activity → approve → atomic apply → fields editable. Server-side write attempt during pending state raises `UserError`. Bulk-action exclusion observed.
- [ ] **D2. Design-file lifecycle ON** — full smoke test (per Spec 003 quickstart §6) passes: upload (small) → upload (URL) → 10 MB cap rejection → approve → reject (rejection_reason required) → re-upload (parent_file_id chain, version=2) → routed via queued job → bulk-print wizard generates A4 PDF.
- [ ] **D3. Vietnamese UI 100% coverage CI gate green** — `tests/test_i18n_coverage.py` passes; manual review of Order/Tracking/Process Dashboards in `Tiếng Việt` shows zero missing translations. UTF-8 round-trip test passes on diacritic fixture.

## E. Spec 005 sandbox must produce the canonical contract

- [ ] **E1. `etsy_channel_api` module installed** on staging dev shop. Loads `etsy.shop.source.change.log`, `etsy.api.log`, `etsy.buyer.message`, `etsy.webhook.event` (P2 may be skipped) models.
- [ ] **E2. OAuth2 PKCE flow round-trip** verified end-to-end on dev shop: tokens stored encrypted, auto-refresh works, "Test Connection" returns shop name + Etsy user.
- [ ] **E3. Order sync against dev shop** runs cleanly: ≥50 receipts ingested, dedup works (re-sync produces 0 new orders), status-only update preserves operator data.
- [ ] **E4. Canonical `EtsyOrderPayload` contract** validated: `EtsyApiAdapter` and `EtsyEmailAdapter` produce identical canonical records on the same receipt (parity test passes; only source-specific nullable fields differ — `buyer_email`, `listing_id` from API only).
- [ ] **E5. VCR cassettes recorded** — ≥50 representative receipts captured in `tests/fixtures/vcr_cassettes/`. Phase-2 unit tests run offline against cassettes; CI green.
- [ ] **E6. Rate limiter + retry policy verified** — load test of 50 simultaneous calls shows ~10 req/s throttle; mocked 5xx triggers backoff retry (3 attempts max); mocked 403 does NOT retry.

## F. Source-switching mechanism (REQ-SRC-01..04, the new core) verified

> **This is the gate-defining section.** ADR-008a v2 source-switching is the architectural hinge. If F1-F4 don't all pass, the whole gate fails — defer Phase 1 cutover until they do.

- [ ] **F1. `etsy.shop.active_source` field present** with values `api`/`email`. Bootstrap migration ran: every shop has at least one `etsy.shop.source.change.log` row with `reason='bootstrap'`.
- [ ] **F2. Health-check cron live** (`cron_etsy_health_check`, default 5 min). Verified by inducing 3 consecutive API health-check failures on dev shop → confirmed:
   - `etsy.shop.active_source` flipped from `api` to `email`
   - New row in `etsy.shop.source.change.log` with `reason='auto-failover'`, `health_check_failures_at_change=3`, `actor_user_id=NULL`
   - HIGH alert raised (visible on the master health dashboard)
- [ ] **F3. Recovery-probe cron live** (`cron_etsy_recovery_probe`, default 1 hour, only runs when shop in failover). Verified by repairing the API + observing 6 successful probes → confirmed:
   - `etsy.shop.active_source` flipped back from `email` to `api`
   - New row with `reason='recovery-probe'`, `actor_user_id=NULL`
- [ ] **F4. Sticky override (`auto_recovery=False`) tested** — set on a shop in failover, confirmed recovery probe does NOT auto-switch back even after 6 successes. (Manual flip required for unstuck.)
- [ ] **F5. Manual flip path tested** — admin user flips a shop's `active_source` via UI → confirmed:
   - New row with `reason='manual'`, `actor_user_id=<admin>`
   - `tracking=True` chatter row on `etsy.shop`
- [ ] **F6. End-to-end observed cycle** — at least ONE complete `OK → auto-failover → auto-recovery` cycle observed on the dev shop without data loss; OR 30 calendar days of clean operation (no failover events) on Phase-0 sandbox. Whichever comes first.

## G. Health-dashboard tiles permanent (per ADR-008a §6)

- [ ] **G1. `active_source_per_shop` tile** populated — table of shop → current source.
- [ ] **G2. `auto_failover_count_7d` tile** populated — count of `auto-failover` rows in last 7 days. Alert threshold tuned (default: spike > 3× rolling-mean).
- [ ] **G3. `time_since_last_recovery_probe_success` tile** populated for any shop in failover — alerts when > 24h.
- [ ] **G4. `parser_template_drift` tile** populated — health metric on the email adapter (regex match-rate trend; alerts on degradation).

## H. Tracking push (US3 of Spec 005, gates first dashboards-driven cutover)

- [ ] **H1. `EtsyTrackingPusher` round-trip** — for ≥10 dev-shop orders: BA enters tracking + carrier on Tracking Dashboard → push within 5 min → tracking visible on Etsy Seller Portal.
- [ ] **H2. Carrier mapping fallback works** — order with `etsy_carrier_name='other'` pushes successfully with warn-log to `etsy.api.log`.
- [ ] **H3. Push status state machine clean** — `none → pending → pushed | failed`; failed pushes re-attempt up to 3× then surface to BA via chatter.

## I. Operational readiness

- [ ] **I1. Staging environment provisioned** at `129.150.63.207:8169` with nightly prod DB snapshot restore (master-plan §6 decision 13). Cron job verified.
- [ ] **I2. Tiered on-call rotation defined** for source-failover incidents — Owner + Tech Lead + (optional) BA Lead. Incident response runbook published in `specs/006-master-plan/guides/`.
- [ ] **I3. GDrive failover policy documented** — service account credentials provisioned, alert + queue + backoff verified, Discord remains the manual escape hatch (per ADR-012).
- [ ] **I4. Rollback path documented** — if Phase 1 cutover causes issues, the path to flip a shop back to `active_source='email'` (manual override) is one-click in the admin UI; verified.

## J. Sign-offs

- [ ] **J1. BA Lead** signs off on reconciliation report (Spec 002) + dashboards usability (Spec 003 quickstart sections 2/3/4) + address-change workflow (Spec 003 §5).
- [ ] **J2. Production Lead (PD)** signs off on Process Dashboard + design-file lifecycle (Spec 003 §6).
- [ ] **J3. Owner** signs off on Phase-0 → Phase-1 transition with explicit go/no-go decision recorded in `specs/006-master-plan/decision-log.md`.
- [ ] **J4. Tech Lead** confirms 80%+ test coverage on `multichannel_hub_core`, `etsy_channel_api`, `etsy_channel_email` and CI green on staging.

---

## Failure modes & escalation

| Section failing | Owner | Likely cause | Escalation |
|---|---|---|---|
| A | Owner | External (Etsy app review pending) | Wait; do not cut over without scope grant |
| B | Spec 002 lead | Migration not finished | Resume Spec 002 work; do not start Phase 1 |
| C | Spec 003 lead | Module not yet installed | Install + run smoke tests |
| D | BA Lead | Workflow gaps | Open ticket against Spec 003 |
| E | Tech Lead (Spec 005) | Sandbox incomplete | Resume sandbox tasks T001-T046 |
| **F** | Tech Lead (Spec 005) | Source-switching not exercised | **DO NOT** cutover; verify F1-F6 cleanly first |
| G | Tech Lead (multichannel_hub) | Health tiles not wired | Patch health-dashboard model (extends Spec 002 `multichannel.sync.health`) |
| H | Tech Lead (Spec 005) | Tracking push not round-tripping | Diagnose via `etsy.api.log` |
| I | Owner + Tech Lead | Infra gaps | Provision staging + write runbook before cutover |
| J | Owner | Sign-offs missing | Schedule the gate review meeting |

## After this gate passes

Phase 1 begins. First action: pilot shop flips `active_source='api'` per ADR-008a §2 + master-plan §4 Phase 1. Target: 3-5 shops cutover by end of Phase 1; remaining 14-16 shops in Phase 2.

This checklist is not re-run for each shop's cutover — it gates the *whole programme's* Phase-1 entry. Per-shop cutover follows the runbook in `specs/006-master-plan/guides/` (to be authored as part of operational readiness — task I2).

## Cross-references

- Master plan §4 (3-phase roadmap), §6 (decisions), §7 (this-week actions, partly applicable for sign-offs)
- ADR-008a v2 (source-switching contract — defines F1-F6 fully)
- ADR-009 (file lifecycle — defines D2)
- ADR-010 (configurable pipeline — implicitly D3 via Vietnamese stage names)
- ADR-012 (GDrive failover — defines I3)
- Spec 002 quickstart (defines B1-B4)
- Spec 003 quickstart (defines C1-C5, D1-D3)
- Spec 005 quickstart (defines E1-E6, F1-F6, G1-G4, H1-H3)
