# 006 — Master Plan

Synthesis of end-user feedback (5 departments) and current specs 001–005, reviewed from three angles: BA/Odoo consultant, technical architect, and devil's advocate.

## Read order

1. **[MASTER_PLAN.md](MASTER_PLAN.md)** — the synthesis, phased roadmap, decisions required
2. [agent-reports/ba-consultant.md](agent-reports/ba-consultant.md) — business process fit & user adoption lens
3. [agent-reports/tech-architect.md](agent-reports/tech-architect.md) — data model, module boundaries, performance lens
4. [agent-reports/devils-advocate.md](agent-reports/devils-advocate.md) — risks, assumptions, failure modes
5. [adrs/](adrs/) — architecture decision records ready for owner sign-off

## ADRs (ready for sign-off)

- [ADR-001](adrs/ADR-001-spec-004-split.md) — Split Spec 004 into 004a / 004b / 004c
- [ADR-002](adrs/ADR-002-drop-dual-sync-mode.md) — Drop dual-mode sync; keep only `email_only` / `api_only`
- [ADR-003](adrs/ADR-003-module-decomposition.md) — Decompose `etsy_integration` into four modules
- [ADR-004](adrs/ADR-004-enterprise-alternatives.md) — Enterprise alternatives via custom minimal implementations
- [ADR-005](adrs/ADR-005-carrier-unification.md) — Unified carrier model via `shipping.carrier`
- [ADR-006](adrs/ADR-006-design-file-storage.md) — Design file storage: filestore/URL only, 10 MB cap
- [ADR-007](adrs/ADR-007-fulfillment-delegation-mixin.md) — `sale.order.fulfillment` delegation mixin

## Related spec updates

- [specs/002-etsy-config-fixes/plan.md](../002-etsy-config-fixes/plan.md) — updated 2026-04-10 with batch-resumable wizard (R4 revised), anomaly quarantine (R9), BA-approval dedup CSV (R10), and `etsy.sync.health` observability (R8). Revision history at the bottom of the file.

## Status

Awaiting owner sign-off on the 9 decisions listed in MASTER_PLAN.md §6.

## Next step after approval

Begin Phase 0: Spec 002 end-to-end + Etsy app review submission + Gearment sandbox spike + observability stub.
