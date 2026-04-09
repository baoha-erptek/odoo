# Investigation Report: Three-Angle Analysis of Multi-Channel E-Commerce System

**Date**: 2026-04-07
**Analysts**: BA/Odoo Consultant, Technical Architect, Devil's Advocate (AI agents)
**Scope**: Gap analysis between owner's system vision and Spec 003 coverage

## 1. Inputs Analyzed

- Owner's hand-drawn system architecture diagram (Channels -> Dashboard -> Design -> Push Logic)
- Google Sheet "NOI DUNG CAC COT TRONG CAC BANG" (6 tabs identified, data not accessible)
- Gemini analysis of the system diagram
- Existing specs: 003-dashboard-design-multichannel (spec.md, plan.md, tasks.md, data-model.md, research.md)
- Existing codebase: custom_addons/etsy_integration (~1,776 lines)

## 2. System Architecture (Owner's Vision)

```
 CHANNELS                    DASHBOARD                  ORDER DETAILS              FULFILLMENT
 --------                    ---------                  -------------              -----------
 Etsy ----+                  CRM (messages)             Personalization            Push Logic
 Amazon --+--> Dashboard --> Sales Orders (priority) --> Design Files ---------> Partner (API sync)
 Website -+                  Status/Tracking            Approval Workflow          Internal Production
                                                        Shipping/Tracking          (status + inventory)
```

Google Sheet row mapping: Rows 2-7 (Dashboard), Rows 10-21 (Order Details/Design), Rows 26-32 (Fulfillment Routing)

## 3. Coverage Matrix

| Vision Component | Spec 003? | Status | Gap Assessment |
|-----------------|-----------|--------|----------------|
| Etsy channel intake | Spec 001 | BUILT | Email parser + Gmail client working |
| Amazon channel | Field only | PLANNED | sales_channel field, no connector |
| Website channel | Field only | PLANNED | sales_channel field, no connector |
| Operational Dashboard (21 cols) | US1 | PLANNED | Replaces Google Sheets tab 1 |
| CRM / 2-way Etsy messaging | NONE | **GAP** | Now addressed in Spec 004 US6 |
| Design file upload | US2 | PLANNED | order.design.file model |
| Design approval workflow | US3 | PLANNED | 3-state: Pending/Approved/Needs Adjustment |
| Multi-channel foundation | US4 | PLANNED | sales_channel + channel_order_ref fields |
| Order priority | US5 | PLANNED | normal/high/urgent |
| Fulfillment status tracking | US6 | PLANNED | 7 stages (manual) |
| Label status | US7 | PLANNED | 3 states |
| Partner API auto-sync | NONE | **GAP** | Now addressed in Spec 004 US3 |
| Internal production tracking | NONE | **GAP** | Now addressed in Spec 004 US4 |
| Raw material inventory | NONE | **GAP** | Now addressed in Spec 004 US5 |
| Returns/refunds flow | NONE | **GAP** | Now addressed in Spec 004 US7 |
| Inventory sync (overselling) | NONE | **GAP** | Future spec (005+) |

## 4. Google Sheet Tab Analysis

| Sheet Tab | Purpose | Spec 003? | Odoo Mapping |
|-----------|---------|-----------|--------------|
| Dashboard v1 (Rows 2-7) | Operational overview | YES | Operational Dashboard list view |
| Dashboard MP | Marketing/Marketplace metrics | NO | Future: Sales analysis reports |
| Dashboard BA | Business/Finance analysis | NO | Future: Accounting reports |
| Dashboard PD (Rows 10-21) | Production/Design queue | PARTIAL | Design queue kanban + approval |
| Policy/Price/Audit (Rows 26-32) | Config/SLA reference | NO | Future: Config settings |
| Other Proposals | Ideas/backlog | NO | External tool |

## 5. Risk Assessment

### CRITICAL Severity (6 issues)

1. **CRM messaging in diagram but nowhere in specs** -- Owner specifically wants 2-way Etsy CRM sync. **Resolution**: Added as Spec 004 US6, contingent on Etsy API approval.

2. **Fulfillment routing deferred but blocks design workflow** -- Design approval has no "next step" without routing. **Resolution**: Spec 004 created with routing data model; Spec 003 now has dependency note.

3. **Binary fields = storage risk** -- 17K orders x 2 files x 5MB = ~170GB potential. No archival policy. **Status**: Documented as edge case in Spec 003 (10MB max per file). Full storage strategy deferred.

4. **No inventory sync across channels** -- Overselling risk when multi-channel is active. **Status**: Noted as out of scope for Spec 003/004. Future spec (005+).

5. **No returns/refunds flow** -- Fulfillment status only goes forward. **Resolution**: Added as Spec 004 US7.

6. **Partner API unreliability** -- No fallback/retry specified. **Resolution**: Spec 004 US3 includes retry logic (3 retries, exponential backoff, escalation).

### HIGH Severity (9 issues)

- 21-column tree view performance (17K records) -- Spec 003 has indexes + pagination; load test task added (T051)
- Selection field for sales_channel vs Many2one -- Decision: keep Selection, revisit when 4th channel needed
- No handoff between "design approved" and "in production" -- Resolved by Spec 004 fulfillment routing
- Google Sheet 6 tabs, only 1.5 replaced -- Documented in Out of Scope
- Amazon SP-API compliance requirements -- Future spec scope
- Design file versioning not addressed -- Documented as edge case (separate records, no parent-child)
- No specification of who decides internal vs partner -- Spec 004 US1: operations manager manual decision
- Computed design_status N+1 query risk -- Consider stored computed field in implementation
- Test coverage at ~50-70% on existing services -- Pre-existing; not a Spec 003 issue

## 6. Architecture Assessment

### Current State: 8.5/10 Separation of Concerns

- **Pure Python services**: email_parser (570 lines, no ORM dependency)
- **Clean Gmail client**: 291 lines, lightweight HTTP
- **Reusable OrderCreator**: 290 lines, ORM service pattern
- **SSRF-protected ImageDownloader**: 131 lines, domain allowlist

### Multi-Channel Readiness: 7/10

- Service layer is cleanly isolated and testable
- Partner/product models are channel-agnostic
- OrderCreator pattern can be subclassed per channel
- Cron architecture supports multiple jobs
- BUT: OrderCreator is Etsy-hardcoded, image downloader allowlist is Etsy-only, no adapter pattern

### Recommended Adapter Pattern

```
OrderAdapter (abstract)
  |-- EtsyOrderAdapter (email -> parser -> creator)
  |-- AmazonOrderAdapter (SP-API -> parser -> creator)
  |-- WooCommerceOrderAdapter (webhook -> parser -> creator)
```

## 7. BA Assessment: Phasing Strategy

**Spec 003 scope is CORRECT for Phase 1 MVP.** It achieves the critical goal: teams stop using Google Sheets.

| Spec | Scope | Status | Dependency |
|------|-------|--------|------------|
| 001 | Etsy email ingestion | BUILT | - |
| 002 | Config fixes, auto-confirm | IN PROGRESS | 001 |
| **003** | **Dashboard + Design + Multi-channel foundation** | **PLANNED** | **002** |
| **004** | **Fulfillment routing + Production + Returns** | **SPECCED** | **003** |
| 005 | Amazon SP-API connector | NOT SPECCED | 003, 004 |
| 006 | WooCommerce/Website connector | NOT SPECCED | 003, 004 |
| 007 | Multi-channel reporting + analytics | NOT SPECCED | 005, 006 |

## 8. Decisions Made

| Decision | Answer | Rationale |
|----------|--------|-----------|
| Google Sheet data | Skip for now | Continue with diagram + Gemini analysis |
| sales_channel field type | Keep Selection | Simple approach; revisit for 4th channel |
| Fulfillment routing | Spec 004 data model FIRST | Design approval needs routing context |
| Next action | Update specs + create Spec 004 | Complete |

## 9. Actions Taken

1. Created Spec 004 (`specs/004-fulfillment-routing/`) with:
   - spec.md (7 user stories, 20 FRs, 8 success criteria)
   - plan.md (implementation plan with project structure)
   - research.md (8 technical decisions)
   - data-model.md (3 new models, sale.order extensions, webhook contract)
   - quickstart.md (verification steps)
   - checklists/requirements.md (quality validation)

2. Updated Spec 003:
   - Added "Out of Scope" section (10 explicitly excluded items)
   - Added "Investigation Reference" section
   - Added file size validation edge case
   - Added design file versioning edge case
   - Added Spec 004 dependency note to tasks.md
   - Added T052 (file size validation) and updated T051 (load test with script)

3. Created this investigation report for team reference.

## 10. File Manifest

| File | Lines | Purpose |
|------|-------|---------|
| `specs/004-fulfillment-routing/spec.md` | ~210 | Feature specification |
| `specs/004-fulfillment-routing/plan.md` | ~80 | Implementation plan |
| `specs/004-fulfillment-routing/research.md` | ~120 | 8 technical decisions |
| `specs/004-fulfillment-routing/data-model.md` | ~180 | 3 new models + extensions |
| `specs/004-fulfillment-routing/quickstart.md` | ~60 | Verification guide |
| `specs/004-fulfillment-routing/checklists/requirements.md` | ~30 | Quality checklist |
| `specs/003-dashboard-design-multichannel/spec.md` | Updated | Added Out of Scope + edge cases |
| `specs/003-dashboard-design-multichannel/tasks.md` | Updated | Added T052, updated T051 |
| `specs/003-dashboard-design-multichannel/investigation.md` | This file | Three-angle analysis |
