# Software Requirements Specification (SRS) — Consolidated View

**Title:** odoo19_esty Multichannel E-Commerce Platform  
**Date:** 2026-07-03  
**Status:** Draft-for-owner-review  
**Source of Truth:** This document aggregates requirements from `.claude/plans/006-master-plan-tracking.md`, `specs/**/spec.md`, and module feature inventories (module-*.md analysis reports).

---

## Purpose & Audience

This SRS consolidates functional and non-functional requirements for the Odoo 19 CE multichannel e-commerce platform serving Etsy orders, Gearment POD dropship fulfillment, and internal VN production. It is organized by capability domain and traceability between:

- **Specs** (001–014 under `specs/`) — Business requirements
- **Modules** (4 custom addons) — Implementation containers  
- **Models** — Data structures and business logic
- **Status** — Shipped / Partial / Planned (with evidence or tracker reference)

**Audience:** Product owner, business analysts, engineering team.

---

## Document Organization

| Section | Focus | Key Outputs |
|---------|-------|-------------|
| [01-overview.md](01-overview.md) | Product vision, actors, scope, fulfillment pipelines (3 routes) | Vision, role matrix (5 roles + 7 BA groups), scope boundaries, pipeline diagram |
| [02-channel-etsy.md](02-channel-etsy.md) | Etsy shop management, OAuth, order ingest (API + email), listing sync | SRS-ETSY-01 through SRS-ETSY-14 (Etsy shop, OAuth, order ingest, listing sync, taxonomy, shipping, currency) |
| [03-orders-fulfillment.md](03-orders-fulfillment.md) | Order lifecycle, design workflow, dropship PO + Gearment quote, MTO, tracking, address approval | SRS-ORD-01 through SRS-ORD-18 (order pipeline, design file routing, Gearment quote, MTO, picking, tracking, Etsy push, address approval) |
| [04-catalog-listings.md](04-catalog-listings.md) | Product hub, bulk catalog sync (Excel), multichannel.listing family, publish workflow | SRS-CAT-01 through SRS-CAT-12 (product hub, Excel sync, listing model, variants, overrides, publish, currency) |
| [05-operations-admin.md](05-operations-admin.md) | Dashboards, health monitoring, API logs, config, import wizards, migration, security roles | SRS-OPS-01 through SRS-OPS-16 (dashboards, sync health, logs, config, import wizards, data migration, ACLs, groups) |

---

## Requirement ID Scheme

Requirements are numbered **SRS-`<area>`-`<nn>`** where:

- `<area>` ∈ {ETSY, ORD, CAT, OPS} — domain abbreviation
- `<nn>` ∈ {01..99} — sequential within domain

**Example:** `SRS-ETSY-03` = Requirement 3 in Etsy channel domain.

---

## Traceability Legend

Each requirement entry includes:

| Column | Meaning |
|--------|---------|
| **ID** | SRS-`<area>`-`<nn>` |
| **Statement** | What must be true (user-facing or system-facing) |
| **Rationale** | Why it matters (1 line) |
| **Origin Spec(s)** | Spec 001–014 source IDs (e.g., Spec 001 US1, Spec 004 P-HEALTH) |
| **Implementing Module + Key Model** | Where it lives + main data model (e.g., `etsy_integration` / `etsy.shop`) |
| **Status** | **Shipped** (live code evidence) / **Partial** (partial code evidence + blockers) / **Planned** (tracker slice ID + date estimate) |

### Status Definitions

- **Shipped:** Feature is implemented, tested, and deployable. Evidence: file paths, model names, method signatures.
- **Partial:** Feature is partially implemented or has known blockers. Evidence: existing code + gap description + remediation tracker ID.
- **Planned:** Feature is sliced and tracked but not yet implemented. Evidence: tracker slice ID + phase target.

---

## Key Definitions

### Fulfillment Pipelines (3 routes per ADR-010)

1. **Internal VN Production** — Design-to-print workflow, in-house production, picking, domestic shipping (phase 2 + phase 4 integration)
2. **Gearment POD Dropship** — API order → Gearment quote → PO acceptance → dropship fulfillment via GKE (phase 1 + phase 2)
3. **Hybrid (MTO + Dropship)** — Mixed: some SKUs internal, some Gearment; decision per category + design (phase 4)

### Key Models (Namespace Summary)

| Model | Purpose | Module |
|-------|---------|--------|
| `etsy.shop` | Etsy seller account (OAuth, config, order host) | etsy_integration |
| `sale.order` | Multi-channel order header (state machine, fulfillment delegation) | multichannel_hub_core |
| `sale.order.line` | Order line item (variants, personalization, design link) | sale_management + etsy_integration |
| `order.pipeline` | Fulfillment route (VN internal, Gearment dropship, hybrid) | multichannel_hub_core |
| `order.pipeline.state` | Pipeline stage (e.g., "Ready for Design", "Design Complete", "Scheduled to Print") | multichannel_hub_core |
| `design.file` | Design file (image, mockup, approval, GDrive link) | multichannel_hub_core |
| `design.file.route` | Delivery routing (from design to production/partners) | multichannel_hub_core |
| `multichannel.listing` | Channel-specific listing intent (split, variants, overrides) | multichannel_hub_core |
| `sale.order.fulfillment` | Fulfillment lifecycle (tracking, carrier, label status) | multichannel_hub_core |
| `shipping.carrier` | Carrier master (USPS, UniUni, YunExpress, GKE) | multichannel_hub_core |
| `label.status.option` | Carrier label state (Label Requested, Label Printed, Label Voided, Shipped, Delivered) | multichannel_hub_core |

---

## Cross-References

- **Master Plan 006:** `.claude/plans/006-master-plan-tracking.md` (execution roadmap, 82.7% complete as of 2026-07-03)
- **Specs:** `specs/{001..014}-*/spec.md` (detailed business requirements per slice)
- **Module Reports:** `docs/understand/module-{design,etsy_integration,multichannel_hub_core,multichannel_hub_fulfillment}.md` (comprehensive model/feature inventories)
- **Gap Matrix:** `docs/analysis/gap-matrix.md` (feature-vs-built verification)
- **Owner Docs:** `docs/owner/{BRD,SRS}_VN.md` (Vietnamese business-facing SRS)

---

## Next Steps

1. Review each section (01–05) for completeness against module inventories
2. For Partial items, consult referenced tracker slices to understand blockers
3. For Planned items, refer to `.claude/plans/006-master-plan-tracking.md` for phase and dependency info
4. Cross-check with `docs/analysis/gap-matrix.md` for UI/UX delivery status

---

**Document Version:** 1.0  
**Last Updated:** 2026-07-03  
**Prepared By:** Claude Code (consolidated from evidence base)
