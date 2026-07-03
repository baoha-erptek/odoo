---
title: odoo19_esty Documentation Index
date: 2026-07-03
status: Active
source_of_truth: Central index for all project documentation
---

# odoo19_esty Documentation

## Quick Navigation

This repository's documentation is organized by audience and purpose. Start here:

- **Business stakeholders** → [owner/](./owner/) (Vietnamese business flows, UAT reports, status)
- **Engineers implementing features** → [sds/](./sds/) (system design, architecture, integration guides)
- **System administrators** → [deployment/](./deployment/) (infrastructure, setup, runbooks)
- **QA & testing** → [engineering/](./engineering/) (E2E tests, UAT procedures)
- **Historical/archived docs** → [archive/](./archive/) (timestamped superseded docs, prior analyses)

---

## Documentation Structure

### `/srs/` — Functional Requirements
Consolidated feature specifications and user story inventory across all implemented phases.

| File | Purpose |
|------|---------|
| `README.md` | Overview of feature scope and status |
| `01-overview.md` | Project vision, user personas, phase roadmap |
| `02-channel-etsy.md` | Etsy channel: order ingestion, OAuth, tracking, listing sync |
| `03-orders-fulfillment.md` | Order routing, design workflows, fulfillment delegation |
| `04-catalog-listings.md` | Product catalog, Etsy listings, inventory sync, pricing |
| `05-operations-admin.md` | Dashboards, approvals, admin configuration, monitoring |

**Status**: Actively maintained. Each document maps user stories to implementation status (Shipped / Partial / Planned).

### `/sds/` — System Design Specification
Technical architecture, data models, integration points, and deployment topology.

| File | Purpose |
|------|---------|
| `README.md` | System architecture overview |
| `01-modules-architecture.md` | 8-module decomposition, inheritance patterns, dependencies |
| `02a-data-model.md` | Core models (sale.order, etsy.shop, product extensions) |
| `02b-data-model.md` | Domain models (design.file, carrier, pipeline, fulfillment) |
| `03-integrations.md` | External APIs: Etsy v3, Gearment, GKE Logistics, Gmail, GDrive |
| `04a-sequence-flows.md` | Order ingestion, fulfillment, design workflow sequences |
| `04b-sequence-flows.md` | Listing sync, tracking import, address-change approval sequences |
| `05-security.md` | Access control, record rules, audit logging, secure integrations |

**Status**: Actively maintained as code evolves. Diagrams (ER, system architecture, sequence flows) in progress.

### `/owner/` — Business Documentation
Vietnamese operator-facing docs, business process flows, UAT reports. **Synced to Confluence Space HEP** via `.githooks/post-commit`.

| Subdirectory | Contents | Audience |
|---|---|---|
| `/` | Strategic docs (BRD, SRS, STATUS, JIRA sync) | BA lead, owner |
| `/business-flows/` | Swimlane diagrams + step-by-step how-tos (4 flows) | BA operators |
| `/design-system/` | UI mockups, design tokens, phase-3 scope | Design team, stakeholders |
| `/img/` | Supporting graphics for flows and mockups | — |

**Maintenance policy**:
- Do not edit in non-owner/ directories; mirror content to owner/ if needed
- Bypass Confluence sync with `[skip-confluence]` commit tag or `SKIP_CONFLUENCE_SYNC=1` env var
- All Vietnamese docs follow naming convention `*_VN.md`

### `/engineering/` — Engineering & Testing
Test strategies, E2E test guides, UAT results, smoke-test checklists.

| Subdirectory | Contents |
|---|---|
| `E2E_TESTING_GUIDE.md` | Playwright E2E test infrastructure, browser tours, critical-path scenarios |
| `uats/` | Phase-by-phase UAT test results (2026-05-26 through 2026-06-07) |

**Scope**: Phase 1 (order ingest, dashboards, design workflows) and Phase 2 (tracking, GKE import) are fully UAT'd and documented.

### `/design/` — Design System
Brand identity and theme files.

- `HATAFA.design.md` — Design token file (Google `@google/design.md` format, v0.3.0). Defines brand palette, typography, spacing. Source of truth for CSS/OWL theming.

### `/process-flows/` — Swimlane Diagrams
High-level process diagrams (AS-IS / TO-BE) in DrawIO format with PNG/SVG exports.

- `AS-IS_Quy_trinh_hien_tai.*` — Current manual process (before Odoo)
- `TO-BE_Voi_Odoo_Standard.*` — Target process (with Odoo 19 CE)

### `/archive/` — Archived & Superseded Documentation
Dated snapshots of stale/superseded docs. Preserved in git history; organized by timestamp for easy audit trails.

| Date | Contents | Reason |
|---|---|---|
| `2026-06-07/` | E2E run logs, defect reports, UAT prep | Session cleanup post-UAT automation |
| `2026-06-20/` | Mockup comparison reports | Post-UAT design verification |
| `2026-07-03/` | Stale analyses, session prompts, design-phase docs | Documentation reorganization |

**Policy**:
- Never delete; reorganize into dated subdirectories
- Use for historical reference and compliance audits
- Searchable via `git log --follow` if needed

---

## Cross-Links to Specifications & Planning

### `/specs/` — Feature Specifications & Master Plan
Located at `specs/` (adjacent to docs/), contains detailed feature specs and implementation planning docs.

- **Specs 001–014**: Detailed specifications for implemented phases (multi-file structure: spec.md, plan.md, tasks.md, data-model.md, ADRs)
  - Specs 001, 004a marked **Completed** (all P1/P2 user stories shipped)
  - Specs 002, 003, 005+ marked **Active** (implementation ongoing)
  - Spec 004 marked **Superseded → Split** (split into 004a/b/c)
  
- **Spec 015** — `015-project-completion/` — Consolidated completion spec summarizing all delivered work, acceptance criteria met, open issues, lessons learned (authoring in progress)

- **Master Plan 006** — `.claude/plans/006-master-plan-tracking.md` — Daily-updated roadmap, 200+ slices, phase status, blocker tracking, external dependencies
  - `.claude/plans/006-implementation-playbook.md` — 9-phase per-slice execution loop (binding contract)
  - `.claude/plans/006-overview.md` — High-level vision, scope, timeline

### ADRs — Architecture Decision Records
Located at `specs/006-master-plan/adrs/`, 19 ADRs documenting key architectural decisions.

- **Key ADRs**:
  - ADR-001: Spec 004 split (into 004a GKE, 004b Gearment, 004c returns)
  - ADR-002: Drop dual sync mode (single email_only vs api_only)
  - ADR-003: Module decomposition (8-module isolation)
  - ADR-008: API-first pivot (Etsy v3 as primary ingest)
  - ADR-010: Configurable order pipeline (hybrid dropship + MTO)
  - ADR-014: Central product hub (Odoo as catalog master)

Index & timeline: [ARCHITECTURE_DECISION_RECORDS.md](./architecture/ARCHITECTURE_DECISION_RECORDS.md) (in progress)

---

## API & Integration References

### External APIs
- `GEARMENT_API_REFERENCE.md` — Gearment v3 API (fulfillment, webhook dispatcher, state machine)
- `sds/03-integrations.md` — Consolidated: Etsy v3, GKE Logistics, Gmail polling, GDrive file sync

### Internal Controllers & Endpoints
Documented in `sds/03-integrations.md`:
- Etsy OAuth token exchange (`etsy_integration/controllers/etsy_oauth.py`)
- Gearment webhook receiver (`multichannel_hub_fulfillment/controllers/gearment_webhook.py`)

### Cron Jobs & Webhooks
Comprehensive inventory in progress:
- Email polling (10-min interval)
- Etsy API sync (5-min interval)
- GKE tracking import (manual + GDrive polling cron)
- Gearment webhook dispatcher (real-time)

---

## Environment & Configuration

### `.env` Schema
All environment variables documented with credential names only (no hardcoded secrets).

Required sections:
- **Etsy Integration**: `ETSY_APP_ID`, `ETSY_APP_SECRET`
- **Gearment (Fulfillment)**: `GEARMENT_API_KEY`, `GEARMENT_API_SECRET`, `GEARMENT_WEBHOOK_HMAC_SECRET`
- **Gmail/GDrive**: `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GDRIVE_SERVICE_ACCOUNT_JSON`
- **Other**: `TELEGRAM_BOT_TOKEN`, `JIRA_API_KEY`

See `docs/ENVIRONMENT_VARIABLES.md` (in progress) for full inventory.

---

## Key Contact Points

| Role | Responsibility | Location |
|---|---|---|
| **Product Owner** | Feature prioritization, UAT sign-off | `owner/STATUS_VN.md`, `.claude/plans/006-master-plan-tracking.md` |
| **BA/Operations** | Order triage, fulfillment, tracking | `owner/HUONG_DAN_*.md` (how-to guides) |
| **Design Team** | Design file approvals, MO attachment | `owner/design-system/PHASE_3_SCOPE.md` |
| **Engineering** | Implementation, testing, deployment | `sds/`, `specs/*/plan.md`, `specs/*/tasks.md` |
| **QA** | E2E test strategy, UAT execution | `engineering/E2E_TESTING_GUIDE.md`, `engineering/uats/` |

---

## Documentation Maintenance

### Workflow
1. **Spec authoring**: Per-spec README in `specs/NNN-*-slug/`
2. **Implementation**: Update `sds/` + `srs/` as code ships
3. **UAT & verification**: Append results to `engineering/uats/`
4. **Archival**: Move superseded docs to `archive/YYYY-MM-DD/` with dated subdir
5. **Confluence sync**: Changes to `docs/owner/` auto-push via `.githooks/post-commit`

### Version Control
- Specs (001–014, 015) are version-controlled in `specs/` and frozen after completion
- SRS/SDS docs in `docs/srs/` and `docs/sds/` evolve with implementation
- Owner docs in `docs/owner/` are synced to Confluence (see sync policy above)
- Archive tree grows with each reorganization pass (never delete, only move)

### When to Update
- **After each spec completion**: Add `STATUS (YYYY-MM-DD): Completed` banner to spec.md
- **After each phase shift**: Update `.claude/plans/006-master-plan-tracking.md` + owner `STATUS_VN.md`
- **After UAT**: Append results to `engineering/uats/`
- **After stale doc accumulation**: Archive to `archive/YYYY-MM-DD/` with policy note

---

## Quick Reference

### Finding Things
- **"Where is feature X?"** → Check `srs/` for status, then trace to spec/NNN/
- **"How do I set up the system?"** → `owner/` for business setup, `sds/` for technical architecture
- **"What's the current project status?"** → `owner/STATUS_VN.md` (business) + `.claude/plans/006-master-plan-tracking.md` (technical roadmap)
- **"Did we test that?"** → `engineering/uats/` (phase results) + `E2E_TESTING_GUIDE.md` (test strategy)
- **"Why did we make that decision?"** → `specs/006-master-plan/adrs/` (architecture decisions)

### Common Tasks
| Task | Document(s) |
|---|---|
| Approve a design file | `owner/HUONG_DAN_TAO_SAN_PHAM_VN.md` (step 3.2.1) |
| Check order status across channels | `owner/FLOW_DON_HANG_ETSY_VN.md` + `srs/03-orders-fulfillment.md` |
| Add a new Etsy shop | `sds/03-integrations.md` (Etsy OAuth) + `owner/INVENTORY_SETUP_VN.md` |
| Import GKE tracking | `owner/HUONG_DAN_GIAO_HANG_VN.md` (Flow 3) + `specs/004a-tracking-import/` |
| Understand the architecture | `sds/01-modules-architecture.md` (module map) + `sds/02a-data-model.md` (core models) |

---

**Last Updated**: 2026-07-03  
**Status**: Active (consolidated from individual spec docs)  
**Maintenance**: Per "Documentation Maintenance" section above  
**Confluence Sync**: Owner docs only (via `.githooks/post-commit`)
