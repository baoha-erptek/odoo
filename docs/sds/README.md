# System Design Specification (SDS)

**Title**: odoo19_esty Multichannel Hub System Design  
**Date**: 2026-07-03  
**Status**: Draft-for-owner-review  
**Version**: 1.0  
**Source of Truth**: Consolidated from Master Plan 006, specs/ tree, implementation code, and Confluence owner docs  

---

## Overview

This is the System Design Specification (SDS) for the odoo19_esty multichannel e-commerce platform: a Odoo 19 CE implementation orchestrating order ingest from Etsy, product design workflows, dropship fulfillment via Gearment POD, and internal VN production. The SDS documents the architectural decisions, deployment topology, data models, security posture, and design patterns that enable the system to scale from single-shop pilot (JaHandmadeArt) to 19-shop production operation.

**Maturity Level**: Phase 1 (order ingest + fulfillment tracking) complete and E2E validated on staging. Phase 3 (central product hub + Odoo→Etsy publish) in-progress.

---

## Document Structure

The SDS consists of 5 parts, authored by distributed teams. This README indexes all parts and provides reading guidance.

| Part | File | Scope | Ownership | Status |
|------|------|-------|-----------|--------|
| **1** | `01-architecture.md` | System context, module topology, deployment, ADR digest | Tech writer + architect | **This session** ✓ |
| **2** | `02-data-model.md` | Entity-relationship diagrams, model responsibilities, field inventory | Data architect (scheduled) | Pending |
| **3** | `03-integrations.md` | Etsy v3 API, Gearment v3 API+webhook, Gmail OAuth, GDrive sync, Confluence | Integration architect (scheduled) | Pending |
| **4** | `04-sequence-flows.md` | Sequence diagrams: order-ingest, design-approval, gearment-quote, publish | UX/BA (scheduled) | Pending |
| **5** | `05-security.md` | ACLs, record rules, role matrix, sudo() audit, webhook HMAC, OAuth PKCE | Security reviewer | **This session** ✓ |

---

## Reading Guide

### For Architects & Leads
- Start with **Part 1** (this session) for system context and module topology
- Then **Part 2** (data model) to understand the order pipeline and product catalog
- Then **Part 3** (integrations) for API contracts
- **Part 5** (security) required before any feature touching auth/payment/sensitive data

### For Developers Implementing Phase 3 (Catalog Hub + Publish)
- **Part 1** § Section (e) — Deployment & docker setup
- **Part 1** § Section (d) — Layering conventions (ORM-free service pattern)
- **Part 2** (data model) § Product catalog section
- **Part 3** (integrations) § Etsy v3 POST/PUT/PATCH operations
- **Part 4** (sequence flows) § Publish sequence

### For QA & Testing
- **Part 4** (sequence flows) for test-case derivation
- **Part 5** (security) § FR-017 write-level defense pattern for regression tests

### For Operations & Deployment
- **Part 1** § Section (e) — Deployment view (ports, databases, staging)
- **Part 3** (integrations) § Environment variables and secrets
- **Part 5** (security) § Role matrix and ACL audit

---

## Key Architectural Decisions

For detailed rationale, see `specs/006-master-plan/adrs/` directory. Quick digest:

| ADR | Title | Decision One-Liner |
|-----|-------|-------------------|
| **ADR-001** | Odoo 19 CE Base | Odoo CE (no Enterprise modules) with standard ≥ custom per Standard-Odoo-First |
| **ADR-003** | Four-Module Decomposition | Monolithic etsy_integration split → multichannel_hub_core + etsy_integration + multichannel_hub_fulfillment + design (channel-agnostic bases + channel-specific layers) |
| **ADR-004** | No Enterprise Modules | All code runs on Odoo 19 CE; no enterprise_* deps; standard Dropship/MTO routes |
| **ADR-005** | Unified Carrier Model | Single `shipping.carrier` master per (carrier_code, country_pair); replaces per-channel fragmentation |
| **ADR-006** | GDrive Primary | Design files + mockups + product images stored via GDrive API; Filestore (ir.attachment) ≤2 MB fallback for previews |
| **ADR-007** | Fulfillment Delegation | `sale.order.fulfillment` reverse-delegated from sale.order; unifies tracking/label/production state per ADR-DASH-MERGE |
| **ADR-010** | Hybrid Dropship+MTO | Sales channel switches between Dropship (Gearment) and MTO (Internal VN) via product category; shared state machine |
| **ADR-014** | Central Product Hub | Phase 3 amendment: Odoo as source of truth; Excel bidirectional sync + Etsy API publish chain |
| **ADR-018a** | Webhook HMAC v2 | Gearment webhooks signed HMAC-SHA256(secret, url_path+nonce+timestamp+base64url(body)); 10-second clock skew tolerance |
| **ADR-018b** | OAuth2 PKCE | Etsy OAuth grant via /users/me redirect + shop discovery; stateless client refresh; per-user shop scope ACL |

**Note**: ADR-018 numbering collision flagged in tracker; both a/b variants documented here. Specs/015 consolidation to rename collision target.

---

## Compliance & Standards

- **Security**: OAuth2 PKCE, HMAC webhook signing, record-level ACLs, no hardcoded secrets (env vars only)
- **Testing**: Two-Phase contract (DB schema + ORM unit tests), minimum 80% coverage on changed lines, zero debug statements
- **Code Quality**: PEP 8, ruff linting, max file/function lengths per `.claude/rules/common/coding-style.md`
- **Git Workflow**: Conventional commits, squash-before-merge to main (feature/006-master-plan-coding consolidated 2026-07-03)

---

## External Dependencies

| ID | System | Status | Owner | Next Action |
|----|--------|--------|-------|-------------|
| **E1** | Etsy OAuth scopes | ✅ Approved 2026-05-12 | Etsy | 4 scopes active; `conversations_r` excluded (P1-MSG family blocked) |
| **E2** | Gearment API keys | 🟨 Partial (dashboard only) | Business owner | API keys still pending request from Gearment dashboard |
| **E3** | Google Drive service account | ✅ Ready | Business owner | JSON in `secrets/`; wired up in P1-09 + P2-06 |
| **Staging Server** | Ubuntu VPS 129.150.63.207 | ✅ Live | Ops | SSH access, rsync, `esty_odoo19` DB restore nightly |
| **Confluence Space** | HEP | ✅ Ready | Ops | Auto-sync from `docs/owner/**/*.md` via `.githooks/post-commit` |

---

## Critical Path to Production

**Timeline estimate** (conservative, from 2026-07-03):
1. **P-HUB-SPEC completion** (planner in-progress) → 1–2 weeks
2. **Phase 3 implementation** (15 slices: P-HUB-PROD-MODEL, P-PUB-CLIENT, catalog sync, publish chain) → 6–8 weeks
3. **Phase 1+2 exit criteria** (P1-11 pilot cutover, P2-07 email→API rebind) → 2–3 weeks
4. **E2E validation sprint** → 1–2 weeks
5. **Production merge + Phase 4/5 parallel** → 10–14 weeks total from today, targeting **late August 2026**

**Blockers resolved**:
- ✅ Etsy OAuth approved (E1)
- 🟨 Gearment keys pending (E2) — owner action
- ✅ GDrive ready (E3)

---

## Document Maintenance

- **Owner**: Technical writing team + architect
- **Frequency**: Updated before each major release (Phase gates)
- **Sync**: Push to Confluence HEP space if ownership extends; currently local repo only
- **Reviews**: Before production cutover (P1-11), post-E2E sprint, and pre-Phase-5 (inventory)

---

## Part-by-Part Links

- [Part 1: Architecture](./01-architecture.md) — System context, topology, deployment
- [Part 2: Data Model](./02-data-model.md) — ERD, model inventory, field spec (scheduled)
- [Part 3: Integrations](./03-integrations.md) — API contracts, credential handling (scheduled)
- [Part 4: Sequence Flows](./04-sequence-flows.md) — Sequence diagrams, happy paths (scheduled)
- [Part 5: Security](./05-security.md) — ACLs, roles, sudo audit, HMAC, OAuth

---

*SDS Part 1 authored 2026-07-03. Expect Parts 2–4 within one week; Part 5 (security) finalized in parallel.*
