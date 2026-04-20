# 006 — Master Plan

Synthesis of end-user feedback (5 departments) and current specs 001–005, reviewed from three angles: BA/Odoo consultant, technical architect, and devil's advocate.

## Read order

1. **[MASTER_PLAN.md](MASTER_PLAN.md)** — the synthesis, phased roadmap, decisions required
2. [agent-reports/ba-consultant.md](agent-reports/ba-consultant.md) — business process fit & user adoption lens
3. [agent-reports/tech-architect.md](agent-reports/tech-architect.md) — data model, module boundaries, performance lens
4. [agent-reports/devils-advocate.md](agent-reports/devils-advocate.md) — risks, assumptions, failure modes
5. [adrs/](adrs/) — architecture decision records ready for owner sign-off

## ADRs (all accepted 2026-04-13)

- [ADR-001](adrs/ADR-001-spec-004-split.md) — Split Spec 004 into 004a / 004b / 004c
- [ADR-002](adrs/ADR-002-drop-dual-sync-mode.md) — Drop dual-mode sync; keep only `email_only` / `api_only` (default `api_only`)
- [ADR-003](adrs/ADR-003-module-decomposition.md) — Decompose `etsy_integration` into four modules
- [ADR-004](adrs/ADR-004-enterprise-alternatives.md) — Enterprise alternatives via custom minimal implementations
- [ADR-005](adrs/ADR-005-carrier-unification.md) — Unified carrier model via `shipping.carrier`
- [ADR-006](adrs/ADR-006-design-file-storage.md) — Design file storage: filestore/URL only, 10 MB cap
- [ADR-007](adrs/ADR-007-fulfillment-delegation-mixin.md) — `sale.order.fulfillment` delegation mixin

## Related spec updates

- [specs/002-etsy-config-fixes/plan.md](../002-etsy-config-fixes/plan.md) — batch-resumable wizard (R4), anomaly quarantine (R9), BA-approval dedup CSV (R10), and `etsy.sync.health` observability (R8). Revision history at the bottom of the file.
- [specs/002-etsy-config-fixes/data-model.md](../002-etsy-config-fixes/data-model.md) — 2026-04-13 added `etsy_price_anomaly` field, `etsy.sync.health` model, and wizard fields for resumability/anomalies/dedup.
- [specs/005-etsy-api-channel/spec.md](../005-etsy-api-channel/spec.md) + plan.md — 2026-04-13 **deferred to Phase 3**; `sync_mode` reduced to 2 values with `api_only` default; `sync_audit_mode` added; `etsy.carrier.mapping` removed (ADR-005); webhook US4 downgraded P1 → P2.
- [specs/003-dashboard-design-multichannel/tasks.md](../003-dashboard-design-multichannel/tasks.md) — **FROZEN**, pending Wave B rewrite.
- [specs/004-fulfillment-routing/tasks.md](../004-fulfillment-routing/tasks.md) — **FROZEN**, being split into 004a / 004b / 004c in Waves B and C.

## Status

**Accepted 2026-04-13** — owner signed off on all 9 decisions in MASTER_PLAN.md §6. Waves A and B spec updates complete.

## Wave B deliverables (completed 2026-04-13)

- [specs/003-dashboard-design-multichannel/spec.md](../003-dashboard-design-multichannel/spec.md) — **rewritten** (7 user stories: three dashboards + address-change approval + design-file workflow + multi-channel foundation + audit + Vietnamese i18n). Old spec preserved at `specs/003-dashboard-design-multichannel/_archive/spec-2026-04-06.md`.
- [specs/004a-tracking-import/spec.md](../004a-tracking-import/spec.md) — **new** (5 user stories: GKE import wizard with schema fingerprinting, carrier detection, Process Dashboard stock-move hook, import log + replay, carrier admin UX).

## Next steps (Wave C and concurrent Phase 0 work)

1. Plan.md + data-model.md refresh for Spec 003 and Spec 004a (deferred from Wave B to keep the rewrite focused; spec.md is authoritative and sufficient to start implementation planning).
2. Phase 0 execution (does not require spec updates):
   - Submit Etsy app review with all required scopes.
   - Obtain Gearment sandbox credentials.
   - Begin Spec 002 implementation against the batch-resumable wizard design.
3. Wave C specs (after Phase 0 ships): 004b Gearment adapter, 004c Returns/Tickets, Spec 005 rewrite (post Etsy scope approval), Spec 006 Pricing Audit, Spec 007 Raw-material Inventory, Spec 008+ (Catalog, Scan, Amazon, Website).
