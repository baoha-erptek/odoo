# Executive Overview — odoo19_esty Multichannel Hub

**Audience**: CEO / Project Manager (helicopter view)
**Created**: 2026-04-26
**Last updated**: 2026-04-26
**Source of truth for detail**: [MASTER_PLAN.md](MASTER_PLAN.md) · [Execution tracker](../../.claude/plans/006-master-plan-tracking.md) · [ADRs](adrs/)

> **How to read**: This file is the 5-minute briefing. Numbers, dates, and decisions only. Drill into MASTER_PLAN.md or ADRs for the "why".
> **How to maintain**: Update the *Status snapshot* and *Next 2 weeks* sections every Monday, or whenever a phase boundary, ADR, or major blocker changes. Do not duplicate content from MASTER_PLAN.md — link to it.

---

## 1. What the project does

A central **Odoo 19 CE hub** that ingests orders from external sales channels (Etsy first; Amazon and Website later), runs them through a **design-approval + production** pipeline, and pushes fulfillment to **external partners** (Gearment) or **internal production** — with tracking flowing back to the channel of origin.

In one sentence: *replace the Google Sheet + 19 Etsy shop emails + manual workflows with a single Odoo system that 5 departments (BA, Marketing, PD, Sales-Audit, Ops) operate in.*

---

## 2. Vision

One operational system for the whole order lifecycle:

```
Channels (Etsy / Amazon / Website)
        │
        ▼
   Order intake (API primary, Email fallback/parallel — see Open Decisions)
        │
        ▼
   Design approval workflow (Cho duyệt → Duyệt → Cần chỉnh lại)
        │
        ▼
   Production routing (External: Gearment | Internal: VN/US)
        │
        ▼
   Tracking + fulfillment back to channel
```

Three operational dashboards backing it: **Order Dashboard** (BA + Marketing), **Tracking Dashboard** (BA + Ops), **Process Dashboard** (PD).

---

## 3. Features in short

### Shipped (Spec 001)
- Etsy email ingestion via Gmail API + regex parsers (43 patterns)
- Historical Excel import (~17,659 orders loaded, but mostly draft + data-quality issues)

### MVP scope (Phases 0–2, target 13–16 weeks)
- **Spec 002** — Make Spec 001 real: confirm 17K orders, fix 423 $0-price, customer dedup, fiscal/tax data, batch-resumable migration wizard
- **Spec 003** — Three dashboards (Order/Tracking/Process), design-file 3-state approval, address-change approval workflow, Vietnamese UI
- **Spec 004a** — Tracking import (GKE Excel) with schema fingerprint + GDrive polling cron + carrier auto-detection
- **Spec 005** — Etsy API v3 channel: OAuth2, order pull, tracking push, per-shop cutover (sandbox in Phase 0, production in Phase 1–2)
- **Cross-cutting** — `multichannel.sync.health` observability model + dashboard tile

### Post-MVP (Phases 4–5)
- **Spec 004b** — Gearment fulfillment adapter (draft/quote/confirm + HMAC webhook)
- **Spec 004c** — Returns / refunds / minimal ticket system on `sale.order`
- **Spec 006** — Sales Pricing Audit (multi-currency EUR rollup + delta vs catalogue)
- **Spec 007** — Raw-material inventory + 1/3/12-month forecasting (native `stock` + `stock_forecasted`)
- **Spec 008** — Catalog Dashboard per product
- **Spec 009** — Barcode scan sheet
- **Spec 010** — Amazon channel
- **Spec 011** — Website channel

### Architecture commitments (already signed off)
- 4-module decomposition: `multichannel_hub_core`, `multichannel_hub_fulfillment`, `etsy_channel`, `etsy_channel_migration` ([ADR-003](adrs/ADR-003-module-decomposition.md))
- `sale.order.fulfillment` delegation mixin to avoid 40+ field bloat ([ADR-007](adrs/ADR-007-fulfillment-delegation-mixin.md))
- Unified `shipping.carrier` model ([ADR-005](adrs/ADR-005-carrier-unification.md))
- GDrive-URL primary for design files, filestore for thumbnails, 10 MB cap ([ADR-006](adrs/ADR-006-design-file-storage.md))
- API-first pivot: Spec 005 is critical path, email parsing in maintenance mode ([ADR-008](adrs/ADR-008-api-first-pivot.md))

---

## 4. Status snapshot

**Current phase**: Phase 0 (execution underway — Spec 002 US1–US4 + observability landed)
**Current branch**: `main` (canonical trunk promoted 2026-04-26; single-workspace-on-main workflow per playbook revision 1)
**Estimated completion to MVP exit (end of Phase 2)**: 13–16 weeks of effective dev time, 12–18 months realistic per ADR-008 sign-off.

| Phase | Window | State | What "done" means |
|---|---|---|---|
| 0 — Spec 002 cleanup + Spec 005 sandbox + observability | 5–7 weeks | **In progress** — Spec 002 US1–US4 + `etsy.sync.health` model done (4 of ~6 P0 sub-deliverables); Spec 005 sandbox tasks.md generated and P0-14..17 unblocked; W3 (US5+US6 migration wizard) is next | 17K orders confirmed; health dashboard green; Etsy scope review submitted; Spec 005 client passes integration tests against dev shop |
| 1 — Three dashboards + Spec 005 production cutover begins | 5–8 weeks | Not started | Google Sheet read-only; address-change approval live; ≥1 pilot shop on `api_only` |
| 2 — Tracking import + Process Dashboard + remaining shop cutovers | 4–5 weeks | Not started | All 19 shops on `api_only`; daily GKE Excel imports automated |
| 3 — REMOVED | — | Folded into 0–2 per ADR-008 | — |
| 4 — Gearment + Returns + Pricing Audit (Spec 006) | 6–8 weeks | Not started | Gearment live; ticket system live; pricing audit dashboard live |
| 5 — Inventory (007), Catalog (008), Scan (009), Amazon (010), Website (011) | parallel tracks | Not started | Per-spec exit criteria |

**Progress to-date (functional, not LOC)**: ~40% of Spec 001 has business value; **Spec 002: US1–US4 complete (4/10 user stories, ~58% by story count, ~75% of new-import cleanup)**; Specs 003+004a+005 have plans/ADRs (Spec 005 also has 110-task tasks.md generated 2026-04-26).

**Health flags**:
- 🟢 Planning: 8 ADRs accepted, 5 specs frozen/rewritten, execution tracker live, implementation playbook live
- 🟢 Workflow: single-workspace-on-main pattern proven via Wave 1 (Spec 002 US3+US4) — 3 commits, 6 tests pass, ruff clean
- 🟢 Spec 005 sandbox: tasks.md generated (110 tasks); architect open-questions accepted as defaults; P0-14..17 unblocked
- 🟡 External dependencies: Etsy scope review **still not submitted** (3–8 week clock — every week of slip widens Phase 1 cutover); Gearment sandbox creds **not obtained**; GDrive service account **not created**
- 🟡 Staging environment: target `129.150.63.207` not yet provisioned (local docker-compose works for forward dev)
- 🟡 Spec 001 data quality: financial config + auto-confirm landed (US1+US2); migration wizard for 17K + $0-order triage are W3 (US5/US6) — not yet started but unblocked

---

## 5. Next 2 weeks (priorities)

Owner actions (these are the gating items — without them, dev work stalls):
1. **Submit Etsy app scope review** ([guide](guides/vi/etsy-app-review-guide.md)) — still pending. Every week of delay pushes Phase 1 cutover by the same amount.
2. **Request Gearment sandbox credentials** ([guide](guides/vi/gearment-sandbox-guide.md))
3. **Create GDrive service-account JSON key** for ADR-006 + Spec 004a polling

Dev actions (forward work on `main` per single-workspace-on-main playbook):
1. **W3 — Spec 002 US5 (import wizard robustness, T031–T034) + US6 (17K migration wizard, batch-resumable)** — critical path; T032 also auto-clears 4 inherited test failures from MVP slice
2. **W5 — Spec 005 sandbox GREEN** — execute the 110 tasks (Setup/Foundational + US1+US2+US5+US8 against dev token); blocked only on staging env or owner's dev-token availability
3. **Provision staging** on `129.150.63.207` (docker-compose + nightly prod snapshot restore)
4. GKE Excel schema fingerprinting utility (P0-19) — can run in parallel with W3
5. Module decomposition kickoff (P0-20) — sandbox lands in `etsy_integration` per architect Q5 then re-homes during ADR-003 Phase 1

For task-level state and owners, see [`.claude/plans/006-master-plan-tracking.md`](../../.claude/plans/006-master-plan-tracking.md).

---

## 6. Risks (top 5 only — full list in MASTER_PLAN §5)

| # | Risk | Likelihood | Impact | Mitigation owner |
|---|---|---|---|---|
| R1 | Etsy `transactions_w` scope denied | Medium | High | Owner — submit review now |
| R2 | 17K migration partially rolls back / leaves data in mixed state | High | High | Dev A — batch-resumable wizard, overnight run, rollback plan |
| R3 | Gearment v3 API undocumented / rate limits unknown | High | Medium | Dev B — 3-day Phase 0 sandbox spike |
| R4 | GKE Excel schema changes silently corrupt tracking data | High | High | Dev A — schema fingerprint + hard-fail on unknown |
| R12 | Timeline 2–3× under-estimated | High | High | PM — re-communicate 12–18 month realistic to stakeholders |

---

## 7. Open decisions / questions awaiting CEO

| ID | Question | Why it matters | Recommendation |
|---|---|---|---|
| OD-2 | Team size — how many developers actually available? | 12–18 month estimate assumes 2 devs. 1 dev → 24+ months. | Owner to confirm headcount. |
| OD-3 | $0-price orders (423 of them) — who decides recovery price? Etsy API back-fill possible? | Blocks Spec 002 US1 closure. | BA lead + owner. |
| OD-4 | Customer dedup historical scope — 17K back-merge or future-only? | Affects Spec 002 wizard size and GDPR exposure. | BA lead. |
| OD-5 | Multi-warehouse — separate VN/US `stock.location` per warehouse, or logical only? | Affects Spec 007 inventory design. | PD + Ops. |
| OD-6 | `stock_barcode` CE availability in Odoo 19 | Determines Spec 009 build vs reuse. | Architect spike (1 day). |

Detailed open questions in [MASTER_PLAN §8](MASTER_PLAN.md#8-open-questions-for-follow-up).

---

## 8. Recently signed-off decisions (reference)

All accepted 2026-04-13 (full list in MASTER_PLAN §6):
- 12–18 month realistic timeline; 13–16 week MVP (Phases 0–2)
- Spec 004 split into 004a / 004b / 004c ([ADR-001](adrs/ADR-001-spec-004-split.md))
- Drop `dual` sync mode; keep `email_only` / `api_only` ([ADR-002](adrs/ADR-002-drop-dual-sync-mode.md))
- 4-module decomposition ([ADR-003](adrs/ADR-003-module-decomposition.md))
- Custom minimal models, no Enterprise buy ([ADR-004](adrs/ADR-004-enterprise-alternatives.md))
- Unified carrier model ([ADR-005](adrs/ADR-005-carrier-unification.md))
- GDrive-URL primary for design files ([ADR-006](adrs/ADR-006-design-file-storage.md))
- Fulfillment delegation mixin ([ADR-007](adrs/ADR-007-fulfillment-delegation-mixin.md))
- API-first pivot ([ADR-008](adrs/ADR-008-api-first-pivot.md))
- **OD-1 resolved 2026-04-26 — Option C**: Both Etsy API and email parsing pipelines remain shipped and maintained in code. Per-shop `sync_mode` toggle (`email_only` / `api_only`, default `api_only`) decides which one is the active writer. **Single-writer invariant per shop is preserved** — no concurrent writes, no conflict-resolution rules needed. ADR-002 and ADR-008 stand as written; "maintenance mode" wording in ADR-008 means *no new email-parser features*, not *deprecate the code path*.

---

## 9. Update log

| Date | Author | Change |
|---|---|---|
| 2026-04-26 | Claude (sonnet) | Initial draft. Captured CEO direction on mandatory-both ingestion as OD-1 (open decision); flagged conflict with ADR-002/ADR-008 for owner resolution. |
| 2026-04-26 | Claude (sonnet) | OD-1 resolved by owner — Option C. Both pipelines stay shipped; per-shop `sync_mode` toggle picks the active writer; single-writer invariant preserved. ADR-002 and ADR-008 stand. |
| 2026-04-26 | Claude (opus) | Status snapshot refreshed: Wave 1 (Spec 002 US3+US4) GREEN on `main`; workflow pivoted to single-workspace-on-main; Spec 005 sandbox tasks.md generated and unblocked. Phase 0 progress section added to MASTER_PLAN.md §4. |
