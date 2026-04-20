# Implementation Plan: Etsy API v3 Channel Integration

**Branch**: `005-etsy-api-channel` | **Date**: 2026-04-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-etsy-api-channel/spec.md`

> **Deferred to Phase 3** (post-MVP) per [master plan](../006-master-plan/MASTER_PLAN.md) — owner sign-off 2026-04-13. Only Phase 0 work from this spec: submit Etsy app scope review. Implementation (Phases A/B/C below) begins after Etsy approves scopes. See `spec.md` deferral notice.

## Summary

Replace the fragile email-based order ingestion (43 regex patterns) with direct Etsy API v3 integration. Adds OAuth2 PKCE authentication, incremental order sync, tracking number push, webhook receiver for real-time events (P2), rate limiting, and bidirectional listing management. Uses a **one-way per-shop cutover** (`email_only` → `api_only`, with a 1–2 week `sync_audit_mode` validation phase) to migrate shops individually. Dual-writer mode was rejected per [ADR-002](../006-master-plan/adrs/ADR-002-drop-dual-sync-mode.md).

## Technical Context

**Language/Version**: Python 3.12+ (Odoo 19 CE)
**Primary Dependencies**: Odoo 19 CE (sale_management, stock, contacts, mail), requests (bundled)
**Storage**: PostgreSQL 16+ via Odoo ORM
**Testing**: Odoo TransactionCase (integration), pytest (service layer unit tests)
**Target Platform**: Linux server (Docker Compose)
**Project Type**: Odoo module extension (custom_addons/etsy_integration)
**Performance Goals**: 500+ orders/sync cycle, ~10 req/sec Etsy QPS limit, <60s webhook-to-order latency
**Constraints**: Etsy QPS (~10 req/sec) + QPD (rolling 24h) rate limits, OAuth2 tokens expire 3600s / refresh 90 days
**Scale/Scope**: Multi-shop (5+ shops), ~1000 orders/month, ~2300 products

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Odoo-Native First | PASS | Extends sale.order, res.partner, product.product/template, etsy.shop. No parallel data structures. |
| II. Email Parser Isolation | PASS | New EtsyApiClient is a standalone service class (no ORM dependency). Parallel to GmailClient pattern. |
| III. Data Integrity First | PASS | Atomic order creation via existing OrderCreator. Dedup by etsy_order_id SQL UNIQUE constraint. Forward-only sync prevents data conflicts. |
| IV. Test-Driven Development | PASS | Service layer (EtsyApiClient, EtsyOrderSyncer) testable without Odoo. Integration tests for model extensions. |
| V. Incremental Migration | PASS | Per-shop one-way cutover with `sync_audit_mode` read-only validation phase (ADR-002). Phased: P1 (auth + orders + tracking), P2 (webhooks + listings). |
| VI. Security by Default | PASS | Tokens stored in ir.config_parameter with group_system restriction. HMAC-SHA256 webhook signature verification. PKCE for OAuth2. |
| VII. Simplicity Over Completeness | PASS | Forward-only sync, Etsy-wins conflict resolution, status-only order updates. No back-sync, no messaging (deferred). |

No violations. No complexity justification needed.

## Project Structure

### Documentation (this feature)

```text
specs/005-etsy-api-channel/
├── plan.md              # This file
├── spec.md              # Feature specification (8 user stories, 35 FRs)
├── research.md          # Phase 0: Etsy API research, decisions
├── data-model.md        # Phase 1: Entity definitions, field specs
├── quickstart.md        # Phase 1: Developer setup guide
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (created by /speckit-tasks)
```

### Source Code (extending existing module)

```text
custom_addons/etsy_integration/
├── __manifest__.py                      # [MODIFY] Add new data files, version bump
├── models/
│   ├── etsy_shop.py                     # [MODIFY] Add API credentials, tokens, sync_mode
│   ├── sale_order.py                    # [MODIFY] Add sync_source, tracking push fields, API cron
│   ├── sale_order_line.py               # [MODIFY] Add etsy_listing_id on line
│   ├── product_product.py              # [MODIFY] Add etsy_listing_id, listing_state
│   ├── res_config_settings.py           # [MODIFY] Add Etsy API config fields + actions
│   ├── etsy_api_log.py                  # [NEW] API call audit trail model (supports source='audit')
│   └── etsy_webhook_event.py            # [NEW] Webhook event log model (P2)
# etsy_carrier_mapping.py removed per ADR-005 — mapping moves to shipping.carrier.etsy_carrier_name
├── services/
│   ├── etsy_api_client.py               # [NEW] Central HTTP client (auth, rate limit, retry)
│   ├── etsy_order_syncer.py             # [NEW] Receipt JSON -> OrderCreator bridge
│   ├── etsy_tracking_pusher.py          # [NEW] Batch tracking push service
│   └── etsy_listing_syncer.py           # [NEW] Pull/push listing sync service
├── controllers/
│   ├── oauth.py                         # [MODIFY] Add Etsy PKCE OAuth2 flow (or new file)
│   └── webhook.py                       # [NEW] Webhook callback controller
├── data/
│   └── ir_cron_data.xml                 # [MODIFY] Add API sync, tracking push, listing sync crons
#   shipping_carrier_data.xml with etsy_carrier_name mapping lives in multichannel_hub_core per ADR-005
├── views/
│   ├── res_config_settings_views.xml    # [MODIFY] Add API configuration section
│   ├── etsy_api_log_views.xml           # [NEW] API log tree/form views (audit-source filter)
│   └── etsy_webhook_event_views.xml     # [NEW] Webhook event views (P2)
├── security/
│   ├── ir.model.access.csv             # [MODIFY] Add ACLs for new models
│   └── etsy_security.xml               # [MODIFY] Add record rules for new models
└── tests/
    ├── test_etsy_api_client.py          # [NEW] Unit tests for API client
    ├── test_etsy_order_syncer.py        # [NEW] Integration tests for order sync
    ├── test_etsy_tracking_pusher.py     # [NEW] Tests for tracking push
    └── test_etsy_webhook.py             # [NEW] Tests for webhook handling
```

**Structure Decision**: Extend the existing `etsy_integration` module rather than creating a separate module. The API integration shares data models (etsy.shop, sale.order, product.product), services (OrderCreator), and configuration (res.config.settings) with the email-based pipeline.

## Implementation Phases

### Phase 0 (pre-implementation, runs in parallel with Spec 002)

**Deliverable**: Etsy app scope review submitted (transactions_r/w, listings_r, shops_r, email_r). External clock 3–8 weeks. No code.

### Phase A: Authentication + Order Sync + Audit Mode (P1, US1 + US2 + US5 + US8)

**Deliverables**: EtsyApiClient, OAuth2 PKCE flow, receipt sync cron, `sync_mode` (2 values) + `sync_audit_mode` read-only path
**Dependencies**: Etsy scopes approved; Phase 1 delegation mixin (ADR-007) landed; `multichannel.sync.health` available
**Files**: etsy_api_client.py, etsy_order_syncer.py, etsy_shop.py, sale_order.py, res_config_settings.py, oauth.py, ir_cron_data.xml

### Phase B: Tracking Push (P1, US3)

**Deliverables**: Tracking push cron reading from `shipping.carrier.etsy_carrier_name` (ADR-005)
**Dependencies**: Phase A (API client); Phase 2 `shipping.carrier` seed data
**Files**: etsy_tracking_pusher.py

### Phase C: Webhooks + Listings (P2, US4 + US6)

**Deliverables**: Webhook controller (HMAC + idempotency), bidirectional listing sync, image upload
**Dependencies**: Phase A; shared `webhook_base` controller from `multichannel_hub_core`
**Files**: etsy_listing_syncer.py, webhook.py, etsy_webhook_event.py, product_product.py views

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Module structure | Lives in `etsy_channel` post-decomposition (ADR-003) | Four-module split lands during Phase 1 before 005 code begins |
| API client pattern | Standalone service (like GmailClient) | Testable without Odoo, no ORM dependency |
| Order creation | Reuse OrderCreator with new `process_api_result()` | Preserves partner/product matching logic |
| Token storage | ir.config_parameter per shop | Consistent with existing Gmail credential pattern |
| Rate limiting | In-memory token bucket in EtsyApiClient | No external dependency, respects response headers |
| Conflict resolution | Etsy wins on pull, explicit push for local changes | Prevents accidental marketplace data corruption |
| Order re-sync | Status fields only | Preserves operator annotations |
| Historical sync | Forward-only from connection date | Avoids migration complexity and rate limit issues |
| Dual-mode sync | **Dropped** — one-way cutover per shop with 1–2 week `sync_audit_mode` validation | Race conditions and dedup-key mismatches unmanageable (ADR-002) |
| Carrier Etsy enum | `shipping.carrier.etsy_carrier_name` (single source) | Eliminates `etsy.carrier.mapping` (ADR-005) |

## Revision History

- **2026-04-10**: Initial plan authored.
- **2026-04-13**: Deferred to Phase 3 per master-plan sign-off. Dual-mode sync dropped; `sync_audit_mode` added. Carrier mapping consolidated into `shipping.carrier`. Webhook receiver downgraded P1 → P2. Phase A/B/C dependencies rescoped to require Etsy scope approval + delegation mixin + `multichannel.sync.health`.
