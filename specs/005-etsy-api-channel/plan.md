# Implementation Plan: Etsy API v3 Channel Integration (with Email as Permanent Failover)

**Branch**: `005-etsy-api-channel` | **Date**: 2026-04-27 (Stage 4.2 refresh) | **Spec**: [spec.md](spec.md)
**Authority**: [SRS_Multichannel_Hub_EN.md v2.2](../006-master-plan/SRS_Multichannel_Hub_EN.md) §3 (single pipeline + source switching) + §10 (REQ-MSG-01) + §11 (module map)
**ADRs**: [001](../006-master-plan/adrs/ADR-001-spec-004-split.md) (split) · [002](../006-master-plan/adrs/ADR-002-drop-dual-sync-mode.md) (partially superseded — see Stage-2 deltas) · [003](../006-master-plan/adrs/ADR-003-module-decomposition.md) (4-module split, amended naming) · [008](../006-master-plan/adrs/ADR-008-api-first-pivot.md) (API-first pivot) · **[008a v2](../006-master-plan/adrs/ADR-008a-email-as-mandatory-backup.md) (source-switching contract)**

## Summary

Build the Etsy API v3 ingestion path as the **default upstream source** for new orders, with the existing Etsy email parser preserved as a **permanent per-shop failover source** behind a single canonical ingestion pipeline. Both upstream sources (`EtsyApiAdapter`, `EtsyEmailAdapter`) implement the same interface and produce the same canonical record (`etsy.order.payload`) — downstream code (`OrderCreator`, `sale.order` writes, dashboards, reporting) is source-agnostic. Source-switching is per-shop via `etsy.shop.active_source` (`api` | `email`) with health-check-driven auto-failover (3 consecutive failures → switch) and recovery-probe auto-recovery (6 consecutive successes → switch back, unless sticky-override).

Spec 005 also delivers tracking-push to Etsy (`EtsyTrackingPusher` reading `shipping.carrier.etsy_carrier_name` per ADR-005), webhook receiver (P2), bidirectional listing management (P2), and rate-limit-aware HTTP client. Customer Message Hub (REQ-MSG-01) lands here too: `buyer_message` field ingestion via the existing `transactions_r` scope into the new `etsy.buyer.message` model.

## Stage-2 ADR deltas vs spec.md (2026-04-09 + ADR-002 amendment 2026-04-13)

Spec.md was last revised 2026-04-13 with the ADR-002 sync_mode-enum-with-two-values + sync_audit_mode design. ADR-008a v2 (2026-04-26 afternoon) supersedes both. This plan integrates the deltas; spec.md remains useful for FR-001..FR-035 narrative but is augmented as follows:

| Spec.md FR | 2026-04-13 intent | ADR-008a v2 refinement |
|---|---|---|
| **FR-013** `sync_mode` enum (`email_only` / `api_only`) + `sync_audit_mode` Boolean for 1–2 week read-only audit | Two-value enum + audit Boolean; one-way cutover with admin override to revert | **Replaced**: `etsy.shop.active_source` (`api` | `email`), fully bidirectional via auto-failover + recovery probe. `sync_audit_mode` is **removed** — both adapters produce the same canonical record so there is nothing to "audit"; a misbehaving adapter is detected by health-check, not by parallel-running. Migration: `email_only → active_source='email'`, `api_only → active_source='api'`. |
| **FR-007** incremental sync via Etsy receipt listing endpoint | Direct API call producing `sale.order` rows | Same call, but now: API client is `EtsyApiAdapter`, returns `etsy.order.payload` (canonical), passes to `EtsyOrderIngestor` (single ingestion service) which writes `sale.order`. Email parser becomes a peer `EtsyEmailAdapter` returning the same canonical record from the parsed email. |
| **FR-015** Etsy carrier mapping moved from `etsy.carrier.mapping` to `shipping.carrier.etsy_carrier_name` | Per ADR-005 | Unchanged — already correct |
| **US7 / FR not-yet-numbered** Etsy Conversations deferred (scope rejected) | Defer entirely | **REQ-MSG-01 (NEW v2.2)**: ingest `buyer_message` field via existing `transactions_r` scope (no Conversations dependency). New model `etsy.buyer.message`. Per-receipt row when `buyer_message` non-empty. Surfaces on order form + Customer Message Hub view. |
| **Module destination** `etsy_channel` + `etsy_channel_legacy` per ADR-003 original | Channel monolith with legacy-marked sub-module | **Renamed**: `etsy_channel_api` (API connector) + `etsy_channel_email` (peer module — email parser is **NOT legacy**). Per ADR-008a §5. |
| **30-day shadow logging post-cutover** + Gmail cron stop after all shops cutover | Limited window then disable email cron | **Removed**: per ADR-008a §4 the email cron stays operational forever; no post-cutover sunset. The 30-day shadow-logging window is replaced by health-check + recovery-probe semantics. |
| **DA risk R7 — race conditions in dual-mode** | Mitigated by removing `dual` mode | **Definitively closed**: only ONE adapter is active per shop at any moment per ADR-008a §1. No reconciliation logic, no merge code, no field-authority table. |

> **New requirements introduced by ADR-008a v2** (not in spec.md but driven by SRS v2.2 REQ-SRC-01..04):
> 1. Canonical `etsy.order.payload` schema (in-memory dataclass; not a DB model). Used as the input contract to `EtsyOrderIngestor`.
> 2. `etsy.shop.active_source` field (Selection: `api`/`email`) with admin override.
> 3. Health-check cron (5min, 3-failure threshold, severity HIGH on switch).
> 4. Recovery-probe cron (1h when in failover, 6-success threshold).
> 5. `etsy.shop.source.change.log` model — append-only, who/when/from→to/reason (`auto-failover` | `manual` | `recovery-probe`).
> 6. `etsy.shop.auto_recovery` Boolean (default `True`; sticky False prevents auto-switch-back when admin manually escalated to email).

## Technical Context

**Language/Version**: Python 3.12+ (Odoo 19 CE)
**Primary Dependencies**: Odoo 19 CE (`sale_management`, `stock`, `contacts`, `mail`); `requests` (bundled); `multichannel_hub_core` (per ADR-001 §11 module map). Optional: VCR.py for test fixtures.
**Storage**: PostgreSQL 16+ via Odoo ORM. New tables: `etsy_api_log`, `etsy_webhook_event` (P2), `etsy_buyer_message`, `etsy_shop_source_change_log`. Existing `etsy_shop` extended.
**Testing**: TransactionCase + HttpCase + VCR-replayed cassettes recorded against Etsy dev shop. Two-Phase Testing per project rule.
**Target Platform**: Linux Docker container (Odoo 19 CE on PostgreSQL 16). Dev shop OAuth tokens in Phase 0; per-shop production OAuth in Phase 1.
**Project Type**: Two Odoo modules per ADR-001 §11: **`etsy_channel_api`** (this plan's primary deliverable) and **`etsy_channel_email`** (existing parser code migrated, NOT deprecated). Both depend on `multichannel_hub_core`.
**Performance Goals**: 5-min cron sync per shop; 500+ orders per cycle without timeout; tracking push within 5 min of label entry; webhook (P2) within 60 s. Health-check cron 5min, recovery probe 1h.
**Constraints**: Etsy API v3 rate limits (~10 req/s, daily quota); OAuth2 PKCE only (no client-secret-only flow); HMAC-SHA256 webhook signature verification; UTF-8 round-trip for buyer messages with diacritics; **NO dual-write under any circumstances** (per ADR-008a §1).
**Scale/Scope**: 19 shops × 5-min sync × ~3 receipts/min/shop avg = ~400 receipts/hour avg (peak 4×). Health-check cron 19 shops × 5min = 228 probes/hour. Recovery-probe cron only when in-failover, hourly.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

> **Note**: Constitution v1.0.0 (2026-04-02) Principle II ("Email Parser Isolation") explicitly supports the source-adapter pattern: "parser can be tested without Odoo, parser can be replaced with Etsy API integration later, email format changes require updating only the parser, not Odoo models." ADR-008a v2 reinterprets this principle: instead of "replaced with API", parser sits beside API as a peer. This is the inverse of "deprecation" but consistent with the **isolation** intent. The constitution gate passes; below documents per-principle alignment.

| Principle | Status | Notes |
|---|---|---|
| I. Odoo-Native First | PASS | Etsy API client is a thin layer over `requests`; no custom HTTP framework. OAuth flow uses Odoo's controller + session for the redirect dance. Webhook controller (P2) inherits from `multichannel_hub_core/controllers/webhook_base.py`. Health-check + recovery-probe crons are plain `ir.cron` records. Single canonical-payload dataclass = pure Python; no parallel ORM. |
| II. Email Parser Isolation | PASS | Parser remains in `etsy_channel_email` (renamed from `etsy_channel_legacy` per ADR-008a §5) — orthogonal module to `etsy_channel_api`. Both expose `EtsyChannelAdapter` interface to `multichannel_hub_core/services/etsy_order_ingestor.py`. **Stronger isolation than the original constitution envisioned**: the email parser is now a *peer* swappable adapter, with the same input/output contract as the API adapter, validated by VCR-style fixtures. |
| III. Data Integrity First | PASS | Canonical `etsy.order.payload` is the single contract — dedup by `etsy_order_id` UNIQUE; idempotency keyed on `(shop_id, etsy_receipt_id)`. Source-change writes to `etsy.shop.source.change.log` are atomic with the `etsy.shop.active_source` write. No silent partial writes — one source per shop at any moment. |
| IV. Test-Driven Development | PASS | TDD enforced. Test artifacts: VCR cassettes for both API and email adapters fed identical canonical payloads (parity tests). Phase-1 (DB) tests verify `etsy.shop.active_source` transitions; Phase-2 (ORM unit) tests cover the `EtsyApiClient.refresh_token`, the rate-limiter, the health-check cron, the recovery-probe cron, and HMAC signature verification. 80%+ coverage on `etsy_channel_api`. |
| V. Incremental Migration | PASS | Phase 0 (sandbox dev shop, no production data) → Phase 1 (per-shop production cutover via `active_source='api'` flip — fully reversible via auto-failover) → Phase 2 (remaining shops + webhooks). Each phase ships independently. The "cutover" is no longer one-way — `active_source` flips both directions on health signal. |
| VI. Security by Default | PASS | OAuth2 PKCE + token refresh; tokens stored in `ir.config_parameter` (encrypted) per shop. HMAC-SHA256 webhook signature verification (P2). All API call logs scrub `Authorization` header. The `etsy.shop.source.change.log` audits every source switch. |
| VII. Simplicity Over Completeness | PASS | The single-pipeline-with-swappable-adapter design is **simpler** than the dual-write-reconciliation alternative considered (and rejected) on 2026-04-26 morning. No match-window, no late-arrival upgrade rules, no field-authority table — just one source active at a time. |

## Project Structure

### Documentation (this feature)

```text
specs/005-etsy-api-channel/
├── plan.md              # This file (Stage 4.2 refresh)
├── research.md          # Phase 0 — resolved questions
├── data-model.md        # Phase 1 — full model definitions per ADR-008a v2
├── quickstart.md        # Phase 1 — verification walkthrough
├── findings.md          # Existing — architect advisory on sandbox open questions (DO NOT overwrite)
├── checklists/          # Existing
└── tasks.md             # Phase 2 — generated by /speckit-tasks (Stage 4.4)
```

### Source Code

```text
custom_addons/etsy_channel_api/             # NEW module per ADR-001 §11 + ADR-008a §5
├── __manifest__.py                         # version 19.0.1.0.0; depends: multichannel_hub_core
├── models/
│   ├── __init__.py
│   ├── etsy_shop.py                        # extends with API tokens, active_source, auto_recovery
│   ├── etsy_api_log.py                     # FR-034 audit trail
│   ├── etsy_buyer_message.py               # REQ-MSG-01 (Customer Message Hub)
│   ├── etsy_shop_source_change_log.py      # ADR-008a §3 source-switch audit
│   ├── etsy_webhook_event.py               # P2
│   ├── product_template.py                 # extends with etsy_listing_id, etsy_listing_state
│   └── shipping_carrier.py                 # extends ONLY etsy_carrier_name (already in core)
├── services/
│   ├── __init__.py
│   ├── etsy_api_client.py                  # OAuth2 PKCE + rate limiter + retry + HMAC verify
│   ├── etsy_api_adapter.py                 # implements `EtsyChannelAdapter` interface
│   ├── etsy_order_syncer.py                # incremental sync + canonical payload emission
│   ├── etsy_tracking_pusher.py             # FR-014, reads shipping.carrier.etsy_carrier_name
│   ├── etsy_buyer_message_syncer.py        # REQ-MSG-01 buyer_message ingestion
│   ├── etsy_health_checker.py              # 5-min cron, 3-failure threshold (ADR-008a §3)
│   └── etsy_recovery_prober.py             # 1h cron, 6-success threshold (ADR-008a §3)
├── controllers/
│   ├── __init__.py
│   ├── etsy_oauth_callback.py              # PKCE redirect handler
│   └── etsy_webhook.py                     # P2 — extends multichannel_hub_core/webhook_base
├── views/
│   ├── etsy_shop_views.xml                 # Settings + Authorize + Health badge
│   ├── etsy_buyer_message_views.xml        # Customer Message Hub
│   ├── etsy_api_log_views.xml
│   └── etsy_shop_source_change_log_views.xml
├── data/
│   ├── ir_cron_data.xml                    # health-check + recovery-probe + tracking-push crons
│   └── ir_config_parameter.xml             # rate limit, retention, etc.
├── security/
│   ├── ir.model.access.csv
│   └── etsy_channel_api_security.xml
├── i18n/
│   └── vi_VN.po
└── tests/
    ├── __init__.py
    ├── test_oauth_flow.py                  # PKCE + refresh
    ├── test_api_adapter.py                 # canonical payload parity
    ├── test_order_syncer.py                # incremental sync, dedup, status-only update
    ├── test_tracking_pusher.py
    ├── test_buyer_message_syncer.py
    ├── test_health_check_failover.py       # 3-failure → switch
    ├── test_recovery_probe.py              # 6-success → switch back
    ├── test_source_change_log.py
    ├── test_rate_limiter.py
    ├── test_webhook_hmac.py                # P2
    └── fixtures/
        └── vcr_cassettes/                  # recorded against dev shop

custom_addons/etsy_channel_email/           # RENAMED from existing etsy_integration parser bits per ADR-008a §5
├── __manifest__.py                         # depends: multichannel_hub_core
├── models/                                 # email_log, gmail_oauth, etc.
├── services/
│   ├── email_parser.py                     # KEPT — peer adapter to API
│   ├── email_adapter.py                    # implements `EtsyChannelAdapter` (returns canonical payload)
│   └── gmail_client.py
├── data/
│   └── ir_cron_data.xml                    # email cron — STAYS OPERATIONAL FOREVER per ADR-008a §4
└── ...
```

> Module-rename script in `etsy_channel_email/migrations/19.0.1.0.1/pre-migrate.py` renames the `etsy_integration` module record to `etsy_channel_email` in `ir_module_module` per ADR-003 §Implementation notes.

**Structure Decision**: Two separate Odoo modules — `etsy_channel_api` (new — this plan's primary deliverable) and `etsy_channel_email` (renamed from the existing email-parser portion of `etsy_integration`). Both depend on `multichannel_hub_core` (delivered by Spec 003). The split mirrors ADR-001 §11. The split is hard: no source dependencies between the two channel modules; they are peers.

## Implementation Phases

### Phase 0 — Sandbox (in flight, parallel with Spec 002)

Scope: OAuth2 PKCE scaffolding, `EtsyApiClient`, rate limiter, `EtsyApiAdapter` (canonical payload emission), `EtsyOrderSyncer` against dev shop only, `etsy.api.log`, VCR cassettes.

US coverage: US1 (OAuth) + US2 (Order sync) + US5 (Rate limiting) + US8 (`active_source` mechanism, but NOT yet wired to `multichannel_hub_core/services/etsy_order_ingestor.py`).

Exit criteria: dev shop produces canonical `etsy.order.payload` records identical (within tolerance) to what `EtsyEmailAdapter` produces for the same receipt; cassettes captured for at least 50 representative receipts.

### Phase 1 — Production cutover (gated on Etsy scope approval)

Scope: production OAuth flow per shop; first 3-5 shops flipped `active_source='email' → 'api'`; health-check cron live; recovery-probe cron live; `etsy.shop.source.change.log` populated; tracking push (US3) wired into the Tracking Dashboard's `shipping_carrier_id` write.

REQ coverage: REQ-SRC-01..04 all live in production for pilot shops. REQ-MSG-01 starts ingesting `buyer_message`.

Exit criteria: at least one observed `auto-failover → auto-recovery` cycle completes cleanly OR 30 days clean operation without failover; tracking push round-trip works for ≥10 orders.

### Phase 2 — Remaining shops + webhooks

Scope: remaining 14-16 shops to `active_source='api'`; webhook receiver (US4); listing management (US6, P2). The email cron stays operational forever (ADR-008a §4).

### Phase 3 — Customer Message Hub UI polish

Scope: REQ-MSG-01 dashboard view (Customer Message Hub) with cross-shop search and filter. The buyer-message ingestion is already running from Phase 1.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Two-module split (`etsy_channel_api` + `etsy_channel_email`) instead of single `etsy_channel` | Per ADR-008a §5 + ADR-001 §11 the modules are peers; one cannot be marked "legacy" | Single module → forces conditional code in service layer ("if active_source == api else email"), couples lifecycles, defeats the isolation intent of constitution Principle II |
| Health-check + recovery-probe crons (5min + 1h) instead of single threshold | ADR-008a §3 — 3-fail-threshold avoids false-positive flapping; 6-success-recovery avoids fast bounce | Single threshold → either too aggressive (single transient failure flips shop) or too lenient (sustained outage masked) |
| Canonical `etsy.order.payload` dataclass (not an ORM model) | Pure Python contract; passes between adapter and ingestor; out of DB | ORM model → unnecessary persistence; the canonical payload is ephemeral, only written through to `sale.order` |
| `etsy.shop.source.change.log` as separate model (not chatter on `etsy.shop`) | Append-only audit; supports analytics queries (`auto_failover_count_7d`) | Chatter alone → harder to query; chatter is for human-readable threads, not for structured analytics |

## Dependencies

| This plan needs | From | When |
|---|---|---|
| `multichannel_hub_core` module installed | Spec 003 | Before Phase 1 production cutover (Phase 0 dev work can stub the dependency) |
| `shipping.carrier.etsy_carrier_name` populated for active carriers | Spec 003 (`shipping_carrier_seed.xml`) | Before tracking push (US3) goes live |
| `etsy.shop.active_source` field exists | This plan | Phase 0 — first model migration |
| Etsy app scope approval (`transactions_r/w`, `listings_r/w`, `shops_r`, `email_r`) | External (Owner submitted critical-path 2026-04-13) | Before Phase 1 production cutover |
| Constitution gate revalidation | This plan §Constitution Check | Done above |

| Other deliverables need from this | What |
|---|---|
| Spec 003 Tracking Dashboard | `EtsyTrackingPusher` service is called on `shipping_carrier_id` + `tracking_number` write completion |
| Spec 003 Customer Message Hub view | `etsy.buyer.message` model populated by REQ-MSG-01 ingestion |
| Spec 002 reconciliation report | `etsy.api.log` (source=`audit` rows during cutover) — still useful diagnostic even without `sync_audit_mode` |
| Spec 004b Gearment | None directly; both write to `sale.order.fulfillment.tracking_number` |

## Revision History

- **2026-04-09**: v1 plan (single API client, dual-mode-rejected before authoring; 110-task tasks.md generated 2026-04-26 in commit `bfda694`)
- **2026-04-13**: Spec.md amended for ADR-008 (API-first pivot) and ADR-002 (sync_mode 2-value enum + sync_audit_mode); plan.md NOT regenerated at the time
- **2026-04-27**: Stage 4.2 plan refresh — integrates ADR-008a v2 (source-switching, email-as-permanent-failover); `sync_mode` superseded by `active_source`; `sync_audit_mode` removed; module split into `etsy_channel_api` + `etsy_channel_email` peers; new REQ-SRC-01..04 + REQ-MSG-01 surface area
