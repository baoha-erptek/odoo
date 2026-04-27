# BA / Odoo Consultant Gap Analysis — 2026-04-26
## Fresh Document Review: E2_Quy_trinh_san_xuat.md (v1.1), devils-advocate-post-redpen.md, SRS_Multichannel_Hub_EN.md (v2.1)

**Date**: 2026-04-26  
**Reviewer Lens**: Business Analyst + Odoo Functional Consultant  
**Scope**: Gap analysis of three fresh documents against current state of specs, shipped work, and MASTER_PLAN.md  
**Reference**: Prior round ba-consultant.md (2026-04-10) — do NOT repeat those 12 gaps  

---

## 1. Executive Summary

- **BLOCKER: REQ-SYN-00 (Etsy API business case) stated in SRS v2.1 but unresolved in E2 v1.1 and devils-advocate-post-redpen.md flags as N1 — Owner must issue written ROI memo before Spec 005 Phase-0 proceeds. E2 §8 decision #13 acknowledges the flag but records no resolution.**
  
- **Critical role ambiguity unresolved across all three docs**: MP (Product Designer) "duyệt" (approves) design files but E2 §5 and SRS confirm BA "làm" (creates). However, workflow sequence (E2 §3 to-be, SRS REQ-FIL-01) shows MP approval *before* BA hand-off to PD — needs explicit RACI in Spec 003 design docs.

- **17 PD sub-states formally enumerated (E2 §6, SRS REQ-PRO-03) but state machine semantics undefined**: "VN-Packed 1" meaning unclear (operator variant? pack iteration?), "[Fix]VN-Dish" rework trigger undefined (who initiates? cost clawback?). Devils-advocate N2 and E2 §8 decision #7 surface this; SRS REQ-PRO-03 does not. **Recommend: State diagram with explicit transitions before Spec 003 design begins.**

- **File lifecycle (REQ-FIL-01..03, new in SRS v2.1) maps to E2 §2.2 pain point #7 ("Thiết kế & điều hướng tệp phức tạp") but E2 does not explain single-upload multi-recipient pattern**. SRS REQ-FIL-02 stipulates MP bulk-download + Photoshop A4 layout; E2 §3 does not specify tool, sequence, or resubmit loop. GDrive failover to Discord (devils-advocate N4) is not documented in either SRS or E2.

- **18 open decisions remain in E2 §8** (14 from v1.0 + 4 new in v1.1); devils-advocate-post-redpen.md flags 8 as BLOCKER/HIGH (N1-N7 + C3). **No sign-off memo recorded for any.** Recommend: Owner decision log (separate doc, linked in both E2 and SRS) with timestamp + rationale for each.

---

## 2. Per-Document Gap Analysis

### 2.1 E2_Quy_trinh_san_xuat.md (v1.1, Owner-facing, VN, Non-Technical)

| Section | Current State | What's Actually True Now | Recommended Action | Priority |
|---------|---------------|--------------------------|-------------------|----------|
| §2.1 As-is email auto-feed | "auto-feeds Etsy emails into Sheets. Manual error rate <1%." | Email pipeline is working, BUT Spec 005 (Etsy API OAuth) is now Phase-0 sandbox + Phase 1 production per API-first pivot (2026-04-13). API ROI unsubstantiated (devils-advocate C3). | Cite REQ-SYN-00 status and link to pending Owner ROI memo. Clarify email is Phase 1 fallback, not primary. | BLOCKER |
| §2.2 Pain point #7 | "Thiết kế & điều hướng tệp phức tạp" (design file hand-over unclear) | SRS v2.1 introduces REQ-FIL-01..03: single-upload multi-recipient, MP bulk-download, PD re-routing. But sequence and tooling (GDrive vs. Discord vs. Odoo filestore) not specified. | Add subsection explaining file lifecycle: BA uploads → MP approves → PD downloads A4 → resubmit loop. Map to SRS REQ-FIL-01..03. Link failover strategy (devils-advocate N4: GDrive token expiry risk). | HIGH |
| §3 To-be flow (routes A/B/C) | Routes named but not mapped to spec phases or modules. | Route A (nội bộ 12 families) = MRP in Spec 003/004. Route B (Gearment POD 7 families) = Spec 004a (Gearment fulfillment). Route C (MUG/TUM) = Spec 004b (deferred to Phase 2). | Explicitly label routes with spec IDs and phase gates. Reference Gearment 4-step flow (REQ-TRF-06: draft → quote → approve → confirm) and note orphan-draft cost risk (devils-advocate N5). | MEDIUM |
| §5 Role matrix | MP "duyệt" (approves), BA "làm" (creates), RD "kiểm tra giá hàng ngày" (daily checks). | Roles correct per SRS §2 and memory context. BUT workflow sequence (§3 to-be) shows MP approval before BA hand-off — needs RACI timing. RD "daily" implies process automation not yet sketched (devils-advocate N7). | Create explicit RACI with decision gates: BA creates file → MP reviews+approves (SLA?) → PD downloads → [loop on reject]. For RD, clarify: automated daily flag or manual inspection? | HIGH |
| §6 Status table (x_substate mapping) | Maps 17 PD sub-states to draft/progress/done lifecycle. | SRS REQ-PRO-03 enumerates same 17 states, but transition conditions undefined. "VN-Packed 1" and "[Fix]VN-Dish" semantics missing. Gearment rework (REQ-TRF-06) conflicts with linear assumption. | Link to state diagram (TBD in Spec 003). Document: Does "Packed 1" mean operator A vs. B? Partial pack? Repack iteration? Can MO jump backward on reject? | BLOCKER |
| §8 Open decisions | 18 decisions listed; no sign-off memo or Owner approval recorded. Decisions #13-18 (new in v1.1) reference devils-advocate N1-N7 implicitly. | All 18 remain open as of 2026-04-26 per EXECUTIVE_OVERVIEW.md ("scope review pending", "Gearment creds not obtained", etc.). Devils-advocate-post-redpen.md surfaces N1, N2, N3, N4, N5, N6, N7 as BLOCKER/HIGH needing explicit resolution. | Create Owner decision log (separate md file) with: decision ID, description, devil's-advocate risk ref, Owner position (+date), approver sign-off, SRS impact. Freeze Spec 005-Phase-0 until N1 memo issued (per devils-advocate synthesis). | BLOCKER |

**Needs-owner-confirmation**: 
- E2 §2.1 "<1% error" rate: date range, sample size, definition of error (row count vs. customer-visible failure). Link to data logs or reject as anecdotal (devils-advocate C3).
- E2 §8 decision #7 ("VN-Packed 1" semantics): operator variant, pack iteration number, inventory bin sub-category, or quality checkpoint?
- E2 §8 decision #14 ("Spec 005 business case"): link to Owner ROI memo once issued.

---

### 2.2 devils-advocate-post-redpen.md (NEW, 2026-04-26, Technical Analysis)

| Risk # | Current State in Doc | What's Actually True Now | Recommended Action | Priority |
|--------|---------------------|--------------------------|-------------------|----------|
| N1 (BLOCKER) | Etsy API ROI missing when email error rate <1%. Correction states email system already works. | Email pipeline operational; Spec 005 is investor narrative, not technical necessity. Owner moved it to Phase-0 sandbox for business reasons (API-first story) but did not document ROI. | Issue Owner memo: "Spec 005 business case — why API over email?" If answer is investor narrative only, rename Phase-0 to "Branding" and risk-downgrade. If technical SLA gaps exist, quantify (latency? coverage?). Freeze Phase-0 until memo arrives. | BLOCKER |
| N2 (HIGH) | "VN-Packed 1" and "[Fix]VN-Dish" state semantics undefined. | SRS REQ-PRO-03 lists both states but provides no semantics. E2 §6 status table shows them but does not explain. Gearment rework loop (REQ-TRF-06) implies [Fix]VN-Dish is a replan trigger, not a simple status. | State diagram with explicit transitions and rework paths before Spec 003 code begins (per devils-advocate mitigation). Include: "Does MO jump backward on design reject?" "Does [Fix]VN-Dish trigger new MO or status change?" "Who initiates [Fix]?" | HIGH |
| N3 (HIGH) | Work-center reassignment has no audit trail or sign-off. | SRS REQ-PRO-09 (new v2.1) states "Admin can reassign families per period" but no governance model defined. E2 does not address. Devils-advocate correctly flags: is "per period" weekly/monthly/event-driven? Does reassignment lock MO mid-flow? | Add work_center.assignment.log model (Spec 003 design). Define "per period" (suggest: quarterly + ad-hoc with Owner approval). Forbid reassignment while MO active in that line unless explicit unlock. | HIGH |
| N4 (HIGH) | File storage failover to Discord not documented. | SRS REQ-FIL-01..03 moves to GDrive + Odoo filestore. No mention of Discord fallback. GDrive OAuth tokens expire after 6 months inactivity; service key rotation risk acknowledged in devil's advocate. | Document Discord as explicit fallback in Spec 004a design. Add GDrive health check cron + exponential backoff + dead-letter queue for failed uploads. Staging env (pending provision) must test failover. | HIGH |
| N5 (HIGH) | Gearment draft/quote orphaning cost not addressed. | SRS REQ-TRF-06 defines Gearment 4-step flow but does not mention draft superseding or cost clawback. Gearment support FAQ likely has policy; Owner must confirm before Phase-0 ends. | Contact Gearment support: draft lifecycle + cancellation policy. Document in Spec 004a. If cost clawback required, add to MO.cancel() behavior (Spec 003). | HIGH |
| N6 (MEDIUM) | Multi-technique products (e.g., dish+ceramic+embroidery) routing undefined. | SRS REQ-PRO-02 lists 9 techniques; no multi-technique test case exists. Single-WC routing assigns to one line; MO split logic absent. | Test with 3-technique product in Phase 2 (post-MVP). Add product.technique Many2many field (Spec 003). Decide: sub-MOs per technique or sequential line hop? | MEDIUM |
| N7 (MEDIUM) | "RD checks pricing DAILY" implies automation not yet sketched. | E2 §5 role matrix confirms RD "kiểm tra giá hàng ngày". No automation workflow defined in SRS. Spec 006 (Pricing Audit dashboard) was "read-only reporting" in prior plan; daily implies automation (auto-pause, email alert?). | Interview RD workflow: What triggers check? What action follows (pause order, email customer, adjust costing)? Is automation forbidden or desired? Spec 006 design must clarify before code. | MEDIUM |
| C1 (MEDIUM) | Single-sheet, open-edit model contradicts <1% error + pristine data integrity claim. | Email system is indeed single-sheet (not the "3-sheet chaos" assumed in prior devils-advocate). But if error rate is <1% *despite* open edit, either team has exceptional discipline or downstream catches errors (not upstream prevention). | Rebaseline Spec 002 (reconciliation) data quality targets against single-sheet reality. Pull Google Sheet audit logs: revert patterns, edit frequency, timestamp deltas. Measure error as "customer-visible failures" not row count. | MEDIUM |
| C2 (MEDIUM) | 12-state enum under-scoped in Spec 003 design. | SRS REQ-PRO-03 enumerates 17 states (was treated as binary in prior DA report). Spec 003 state enum must match all 17 + transition rules before design-review. | Spec 003 design review must include state diagram with all 17 states + transitions. Not after code. Use Odoo selection field (x_substate) with explicit YAML enum. | MEDIUM |
| C3 (MEDIUM) | "<1% error" claim is unsubstantiated. | No data provided: logs, date range, sample size, error definition. Owner assertion is anecdotal. | Require Owner to provide evidence before locking Spec 005 deferral. If error rate is 3-5%, API ROI changes. | MEDIUM |

**Needs-owner-confirmation**:
- N1: ROI memo for Spec 005 (why API over email?). Timeline: before Phase-0 cutover.
- N5: Gearment draft lifecycle + cost policy. Timeline: before Phase-0 ends.

---

### 2.3 SRS_Multichannel_Hub_EN.md (v2.1, Formal Specification)

| Section / REQ-ID | Current State | What's Actually True Now | Recommended Action | Priority |
|------------------|---------------|--------------------------|-------------------|----------|
| §1 Phase 1 MVP acceptance | "<1% drift over 1 month parallel run." | No baseline for "drift" defined. Metric could mean order count mismatch, status divergence, or transaction value gap. Measurement method unclear. | Add to Spec 002 (reconciliation) acceptance criteria: measure drift as \|(email orders - Etsy API orders) / email orders\| per day, rolling 7-day average <1%. Staging env must implement metrics cron. | HIGH |
| REQ-SYN-00 (BLOCKER) | "Etsy API business case under Owner review." Status = draft. | Owner red-pen (2026-04-26) prompted devils-advocate N1. Owner has not issued ROI memo. Spec 005-Phase-0 sandbox work ongoing (110 tasks generated per EXECUTIVE_OVERVIEW.md) but business rationale unresolved. | Owner must issue 1-page memo: "Spec 005 ROI — why API over email?" Reference devils-advocate N1 + C3. Freeze Phase-0 sandbox work pending memo. Link memo in SRS §1. | BLOCKER |
| §2 Roles (Owner/BA/MP/PD/RD/Warehouse) | Described qualitatively. MP "duyệt" (approves), BA "làm" (creates), RD "kiểm tra giá" (checks pricing). | Roles correct per E2 §5. BUT workflow sequence (§3 flow sketches) shows approval *before* hand-off timing unclear. RD "daily" checking implies automation scope not in SRS. | Add explicit RACI matrix with decision gates and SLA windows (BA creates file → MP approval window 4h → PD download window 8h → ...). Spec 003 design must operationalize. | HIGH |
| REQ-FIL-01, REQ-FIL-02, REQ-FIL-03 | File lifecycle: single-upload, MP bulk-download, PD re-routing. | E2 §2.2 pain #7 maps to this. But tooling (GDrive, Odoo filestore, Discord) not specified. Discord fallback absent (devils-advocate N4). GDrive OAuth token expiry risk. | Spec 004a design must include: primary path (GDrive? Odoo filestore?), fallback (Discord), health check cron, exponential backoff, dead-letter queue. SLA for file availability: 99.9%? Test failover in staging. | HIGH |
| REQ-PRO-02 | Work-center grouping by 9 techniques: paper/fabric/wood/engrave/ceramic-print/ceramic-stamp/heatpress/embroidery/assembly/personalize. | Correct per E2 §3 route A. But multi-technique products (devils-advocate N6) not covered. Single-WC routing undefined. | Spec 003 design: add product.technique Many2many. Decide: sub-MOs per technique or sequential line hop? Add test case: dish+ceramic+embroidery. Phase 2 implementation. | MEDIUM |
| REQ-PRO-03 | 17 PD sub-states enumerated (CHỜ FILE → ... → VN-Fulfilled). | Devils-advocate N2 correctly flags "VN-Packed 1" and "[Fix]VN-Dish" semantics undefined. State transition rules absent. | State diagram with explicit transitions + rework paths before Spec 003 code. Include: Can MO jump backward on reject? Does [Fix] trigger new MO? Who initiates [Fix]? | BLOCKER |
| REQ-PRO-09 (NEW v2.1) | "Admin can reassign families to lines per period." | Devils-advocate N3 flags: "per period" (weekly/monthly/event-driven) undefined. No audit trail. No sign-off workflow. | Spec 003 design: work_center.assignment.log model. Define "per period" (suggest quarterly + ad-hoc). Forbid reassignment while MO active in line. | HIGH |
| REQ-TRF-06 | Gearment 4-step flow: draft → quote → approve → confirm. | Orphan-draft cost risk (devils-advocate N5) not addressed. Gearment cancellation policy unknown. | Contact Gearment support: draft lifecycle + cost clawback. Document in Spec 004a. If cost clawback required, add MO.cancel() behavior (Spec 003). | HIGH |
| REQ-DAS-01, -02, -03 (Dashboards) | Order, Tracking, Process dashboards defined. | Role matrix (§2) correct but no SLA targets for dashboard latency/refresh. Process dashboard must display 17 sub-states + transition rules (REQ-PRO-03). | Spec 007 design: add refresh SLA (suggest <5s for real-time, <1min for background crons). Process dashboard state filter + drill-down to MO details. | MEDIUM |
| REQ-MSG-01 (NEW v2.1) | "Message hub for PDF export, label generation, tracking pushback." | E2 §2.2 pain #18 ("Thông báo & phối hợp") maps to this. Scope vs. Spec 008 (notification) not clarified. Format unclear (email? SMS? in-app?). | Spec 008 design: clarify message hub scope (PDF export only? label generation? tracking pushback via which channel?). Test with Gearment USPS label integration. | MEDIUM |
| REQ-AUT-01, -02 (Auto-transitions) | "Auto-trigger state changes on events (e.g., Gearment ship → VN-Fulfilled)." | No event schema defined. Gearment webhook integration (Spec 005 prerequisite?) not documented. | Spec 003 design: event/webhook handlers for MO state machine. Gearment integration testing in Phase 1 (per EXECUTIVE_OVERVIEW.md "creds not obtained"). | MEDIUM |
| REQ-PRO-06 (Address-change approval) | "Address-change must be approved before label purchase to prevent duplicate charges." | Correct per memory context (safety-critical). But approval SLA and escalation path not defined. | Spec 003 design: address-change approval workflow with 2h SLA. If not approved in time, MO pause or auto-reject? Test with staging Gearment. | HIGH |
| REQ-EXT-14 (NEW v2.1, AI analytics) | "AI-based analytics for demand forecasting / seasonal trends." | Scope vague. Is this Spec 008 (deferred to Phase 2)? Required ML library? Data retention? | Clarify: is AI req in-scope for Phase 1 MVP? Or Phase 2 nice-to-have? If Phase 1, define MVP (suggest: weekly demand forecast vs. 1-week rolling avg). | MEDIUM |

**Needs-owner-confirmation**:
- REQ-SYN-00: ROI memo for Spec 005. Timeline: BLOCKER for Phase 0 proceed.
- REQ-PRO-03: "VN-Packed 1" and "[Fix]VN-Dish" state semantics. Timeline: before Spec 003 design-review.
- REQ-PRO-09: "per period" definition (weekly/monthly?). Timeline: before Spec 003 code.
- REQ-TRF-06: Gearment draft cost policy. Timeline: before Phase-0 ends.
- REQ-MSG-01: Message hub scope (PDF/label/tracking channel). Timeline: before Spec 008 design.

---

## 3. Cross-Document Inconsistencies

### 3.1 File Lifecycle Narrative

| Document | States | Implied Tooling | Failover | Gap |
|----------|--------|-----------------|----------|-----|
| E2 v1.1 | §2.2 pain #7: "Thiết kế & điều hướng tệp phức tạp"; §3 to-be mentions "bulk-download" | Not specified | Not mentioned | Tool unknown (GDrive? Odoo filestore?). No fallback plan. |
| SRS v2.1 | REQ-FIL-01..03: single-upload, MP bulk-download A4 layout, PD re-routing | Not specified (implied GDrive for bulk-download) | Not mentioned | Devils-advocate N4: GDrive OAuth token expiry risk. Discord fallback missing. |

**Recommendation**: Spec 004a design must specify primary (GDrive + Odoo filestore?) and fallback (Discord). Add health check + exponential backoff cron. Test failover in staging.

### 3.2 Design-File Approval Workflow

| Document | Sequence | SLA / Timing | Approval Authority | Gap |
|----------|----------|--------------|-------------------|-----|
| E2 v1.1 | §5 role matrix: MP "duyệt" (approves), BA "làm" (creates) | Not specified | MP (Product Designer) | Approval window unclear. Can MP reject? Resubmit SLA? |
| SRS v2.1 | §2 role matrix: same as E2 | Not specified | MP (Product Designer) | Same gaps as E2. |

**Recommendation**: Add explicit RACI with timing windows (BA creates → MP approval window 4h → PD download window 8h → resubmit on reject). Spec 003 design must operationalize.

### 3.3 PD Sub-State Enumeration and Rework

| Document | States | Rework Path | Backward Jump | Gap |
|----------|--------|-------------|---------------|-----|
| E2 v1.1 | §6 status table: 17 states from CHỜ FILE to VN-Fulfilled | "[Fix]VN-Dish" mentioned as state, not trigger | Implied by status names but not explicit | "VN-Packed 1" meaning unclear. "[Fix]VN-Dish" semantics undefined. |
| SRS v2.1 | REQ-PRO-03: same 17 states, linear narrative | Gearment rework implied (REQ-TRF-06) but not mapped to state machine | No explicit backward transition rule | Same gaps. Transition conditions absent. |

**Recommendation**: State diagram with all 17 states + explicit transitions (forward + backward + rework paths) before Spec 003 design-review. Include decision gates for reject/rework.

### 3.4 RD Pricing Check Workflow

| Document | Frequency | Trigger | Action | Automation | Gap |
|----------|-----------|---------|--------|-----------|-----|
| E2 v1.1 | §5: "hàng ngày" (daily) | Not specified | Not specified | Implied manual? | Devils-advocate N7: is daily manual inspection or automation? |
| SRS v2.1 | REQ-EXT-14 / implicitly Spec 006 | Not specified | Not specified | Not specified | Spec 006 design has no automation sketch. |

**Recommendation**: Interview RD on actual workflow: What triggers check? (New order? Time-based? Manual?). What action follows? (Pause order? Email customer? Auto-adjust costing?). Spec 006 design must operationalize (suggest: automated daily flag + RD manual approval gate).

### 3.5 Gearment Rework and Cost Accountability

| Document | Flow | Draft Orphaning | Cost Clawback | Approval SLA | Gap |
|----------|------|-----------------|---------------|--------------|-----|
| E2 v1.1 | §3 route B: Gearment POD for 7 families | Pain #6 implicitly (design rejection) | Not mentioned | Not specified | Devils-advocate N5: if Gearment quote superseded, who pays for orphan draft? |
| SRS v2.1 | REQ-TRF-06: draft → quote → approve → confirm | Gearment lifecycle assumed | Not mentioned | Not specified | Same gap. Contact Gearment support needed. |

**Recommendation**: Contact Gearment support before Phase-0 ends: draft lifecycle + cost policy. Document in Spec 004a. If cost clawback required, add to MO.cancel() behavior (Spec 003).

---

## 4. Owner-Language vs Spec-Language Drift

### 4.1 Phrases That Won't Survive Translation to Spec

| Owner Phrase (E2 v1.1) | Spec Language (SRS v2.1) | Technical Debt |
|------------------------|--------------------------|-----------------|
| "auto-feeds Etsy emails into Sheets" (§2.1) | Email service is legacy fallback; Spec 005 (Etsy API OAuth) is Phase-0 sandbox + Phase-1 production | Email narrative survives; API rationale does not. REQ-SYN-00 marks API as BLOCKER but unresolved (N1). |
| "Thiết kế & điều hướng tệp phức tạp" (§2.2 pain #7) | REQ-FIL-01..03 single-upload multi-recipient pattern | Pain is acknowledged; solution is named. But tooling + failover + SLA are absent from SRS. |
| "MP duyệt" (§5 role) | §2 role matrix: "Product Designer approves design files" | "duyệt" = approve (correct). But timing window and escalation path missing. |
| "RD kiểm tra giá hàng ngày" (§5 role) | Implied in Spec 006 (Pricing Audit) + REQ-EXT-14 | "Daily" = frequency not operationalized. Is daily automation (flag) or manual inspection (workflow)? |
| "VN-Packed 1" (§6 status table) | REQ-PRO-03 state enumeration | Vietnamese technical jargon ("1") does not translate. Meaning unclear even in source language. |
| "[Fix]VN-Dish" (§6 status table) | Gearment rework implied in REQ-TRF-06, not mapped to state machine | Rework trigger + action not formalized. Who initiates [Fix]? What happens to costing + labor KPI? |

**Recommendation**: Before SRS sign-off, glossary of Vietnamese technical terms with English definitions (e.g., "VN-Packed 1 = packaging iteration count / operator assignment / quality checkpoint?"). Spec 003 design review must include Owner definition of ambiguous terms.

---

## 5. Coverage Gaps (What's in SRS but E2 Doesn't Explain; Vice Versa)

### 5.1 What's in SRS v2.1 but NOT explained in E2 v1.1

| REQ-ID | SRS Content | E2 Coverage | Gap | Impact |
|--------|-------------|-------------|-----|--------|
| REQ-AUT-01, -02 | Auto-trigger state changes on events (e.g., Gearment ship → VN-Fulfilled) | Not mentioned | E2 does not explain automation framework or event schema | Spec 003 must define event handlers + webhook integration (Gearment prerequisite). Scope review STILL PENDING per EXECUTIVE_OVERVIEW.md. |
| REQ-DAS-01, -02, -03 | Three dashboards (Order, Tracking, Process). SLA for latency/refresh. | §4 mentions three dashboards in high-level narrative but no SLA targets | Dashboard refresh rate not specified. Process dashboard must display 17 sub-states. | Spec 007 design must include <5s real-time, <1min background cron SLA. |
| REQ-PRO-09 | Admin work-center reassignment governance with audit trail | Not mentioned | E2 does not explain how reassignment decision is approved or logged | Devils-advocate N3: must define "per period" + forbid reassignment while MO active. Spec 003 design: work_center.assignment.log model. |
| REQ-MSG-01 | Message hub for PDF export, label generation, tracking pushback | E2 §2.2 pain #18 mentions "thông báo & phối hợp" but no scope | Message hub scope unclear (PDF only? SMS? email? in-app?). Gearment USPS label integration dependency. | Spec 008 design must clarify scope + test with Gearment. |
| REQ-EXT-14 | AI-based analytics for demand forecasting / seasonal trends | Not mentioned | AI scope not addressed in E2 | Phase 1 or Phase 2? What's MVP (forecast vs. rolling avg)? |

### 5.2 What's in E2 v1.1 but NOT in SRS v2.1

| E2 Section | Content | SRS Coverage | Gap | Impact |
|-----------|---------|--------------|-----|--------|
| §2.2 Pain point #18 | "Thông báo & phối hợp khó" (messaging + coordination difficult) | REQ-MSG-01 covers message hub but scope vague | E2 pain is acknowledged by SRS but solution is underspecified | Spec 008 design must define message hub scope + channels (email/SMS/in-app?) + test with Gearment. |
| §8 Decision #7 | "[Fix]VN-Dish" state semantics (operator variant? rework iteration?) | REQ-PRO-03 lists "[Fix]VN-Dish" state but no semantics | E2 raises question but SRS does not answer | State diagram with explicit semantics required before Spec 003 code. |
| §8 Decision #13 | "Spec 005 business case (should we do Etsy API if email is working?)" | REQ-SYN-00 marks API as BLOCKER + "under Owner review" | E2 decision #13 acknowledges N1 flag but no resolution | Owner must issue ROI memo. REQ-SYN-00 status = BLOCKER until resolved. |
| §8 Decision #18 | "How long should Discord fallback stay in place?" | Not mentioned in SRS | E2 raises fallback governance; SRS does not | Spec 004a design must document Discord as explicit fallback + expiration policy (suggest: keep for 1 quarter post-GDrive launch). |

---

## 6. Skill / Workflow Recommendations

### 6.1 Immediate Actions (Before Spec 003 Design-Review)

| Action | Recommended Skill(s) | Input File(s) | Expected Output | Owner / Timeline |
|--------|-----------------|-----------|---------|----------|
| **N1: Freeze Spec 005-Phase-0 pending Owner ROI memo** | (Async decision) | devils-advocate-post-redpen.md (N1), E2 §8 decision #13, SRS REQ-SYN-00 | 1-page Owner memo: "Spec 005 ROI — why API over email?" + approval sign-off | Owner | BLOCKER — before Phase-0 cutover |
| **N2+N3+N4+N5+N6+N7+C3: Operationalize devil's-advocate risks** | `/plan-eng-review` (decision log) | devils-advocate-post-redpen.md (all risks), E2 §8 (decisions 7, 13, 14), SRS REQ-* IDs | Owner decision log: risk ID, description, Owner position, sign-off, SRS/spec impact | Owner + Tech Lead | HIGH — within 1 week |
| **State machine + transitions diagram (N2, C2)** | `/design-review` (system design) | E2 §6 status table (17 PD sub-states), SRS REQ-PRO-03, devils-advocate N2 | State diagram with all 17 states + explicit transitions (forward + backward + rework paths) + decision gates for reject/[Fix] | Architect + PD + Owner | BLOCKER — before Spec 003 design-review |
| **File lifecycle + failover (N4, C1 partial)** | `/design-review` (system design) | SRS REQ-FIL-01..03, E2 §2.2 pain #7, devils-advocate N4 | GDrive + Odoo filestore + Discord failover spec with health check cron, exponential backoff, dead-letter queue, SLA targets (<1 min for PDF A4) | Architect + DevOps | HIGH — before Spec 004a code |
| **RACI + SLA for MP design approval (N3 partial, implicit in workflow)** | `/design-consultation` (workflow design) | SRS §2 role matrix, E2 §5 role matrix, SRS REQ-FIL-01 (approval gate), Spec 003 task list | RACI matrix with timing windows (BA creates → MP approval window 4h → PD download 8h → resubmit SLA). Operationalized in Spec 003 design. | PD + BA + Tech Lead | HIGH — before Spec 003 design-review |
| **Gearment cost policy + draft lifecycle (N5)** | (Async vendor contact) | SRS REQ-TRF-06, devils-advocate N5, Gearment API docs | Gearment support response: draft lifecycle, cost clawback policy, cancellation process. Documented in Spec 004a design. | Owner + Gearment | HIGH — before Phase-0 ends |

### 6.2 Phase-0 Parallel Work (After Decisions Resolved)

| Task | Recommended Skill(s) | Input File(s) | Expected Output | Timeline |
|------|-----------------|-----------|---------|----------|
| **Spec 003 design-review (state machine, RACI, WC governance, address-change approval)** | `/plan-eng-review` + `/design-review` + `code-reviewer` | Output from above + Spec 003 draft design doc | Spec 003 design review report: state diagram approved, RACI signed, WC audit.log model approved, address-change SLA confirmed | Within 2 weeks |
| **Spec 004a design-review (file lifecycle, Gearment integration, GDrive failover, pricing dashboard)** | `/design-review` + `code-reviewer` | Gearment cost policy, file lifecycle spec, devils-advocate N4, SRS REQ-TRF-06, REQ-FIL-01..03 | Spec 004a design: file storage primary + fallback, Gearment webhook handlers, address-change approval flow, pricing audit SLA | Within 2 weeks |
| **Spec 006 design-review (RD daily pricing check automation, dashboard SLA, AI scope)** | `code-reviewer` + `/design-review` | E2 §5 role (RD daily check), SRS REQ-EXT-14, devils-advocate N7, prior ba-consultant.md (pricing-audit-homeless gap) | Spec 006 design: RD check automation (flag? email? auto-pause?), dashboard <5s latency SLA, AI MVP scope (forecast vs. rolling avg) | Within 2 weeks |
| **Staging environment provisioning (GDrive failover test, Gearment sandbox creds, metrics cron for "drift <1%")** | (DevOps / Infrastructure) | EXECUTIVE_OVERVIEW.md (pending tasks), SRS §1 Phase-1 MVP acceptance (<1% drift), devils-advocate N4 | Staging at 129.150.63.207 ready: GDrive + Discord failover tested, Gearment sandbox tenant configured, metrics cron deployed for Phase-1 baseline | Within 1 week (critical path blocker) |

### 6.3 Documentation / Knowledge Capture

| Item | Recommended Skill(s) | Input File(s) | Expected Output | Timeline |
|------|-----------------|-----------|---------|----------|
| **Glossary: Vietnamese technical terms to English definitions** | `/document-release` | E2 v1.1 all sections, SRS v2.1 all sections, devils-advocate risks | Glossary: "VN-Packed 1" = ?, "[Fix]VN-Dish" = ?, "duyệt" = approve, "làm" = create, "kiểm tra hàng ngày" = daily check (manual vs automation?), etc. | Before SRS sign-off |
| **Owner decision log** | (Manual doc) | E2 §8 (18 decisions), devils-advocate-post-redpen.md (8 new risks + 3 contradictions) | Decision log: ID, description, devils-advocate risk ref, Owner position, sign-off date, spec impact. Link in both E2 and SRS. | BLOCKER — before Phase-0 proceeds |
| **Master plan refresh (resolve MASTER_PLAN.md stale state)** | `/land-and-deploy` | MASTER_PLAN.md (2026-04-13), EXECUTIVE_OVERVIEW.md (2026-04-26), agent-reports/ directory (all reports) | Refreshed MASTER_PLAN.md v2.1 (2026-04-26): branch reference corrected to "main", agent report citations updated, phase 0 progress snapshot synchronized | Within 1 week |

---

## 7. Synthesis: Critical Path to Phase-0 Proceed

1. **N1 BLOCKER — Owner ROI memo** (Spec 005 why API over email?). Freeze Phase-0 sandbox work pending memo.
2. **State machine diagram** (all 17 PD sub-states + transitions + rework paths). Approved by Owner + Architect before Spec 003 code.
3. **Owner decision log** (all 18 E2 §8 decisions + sign-off). Freezes all 8 devil's-advocate NEW risks (N1-N7 + C3).
4. **Gearment cost policy** (draft lifecycle + cancellation). Documented in Spec 004a before Phase-0 ends.
5. **Staging environment** (GDrive failover tested, Gearment sandbox creds obtained, metrics cron deployed).

Only after steps 1-5 are complete should Spec 003 design-review proceed.

---

## Summary of Recommendations

- **BLOCKER (must-fix before Phase-0 proceeds)**: N1 (Spec 005 ROI memo), N2 (PD state semantics), REQ-SYN-00 (API business case), REQ-PRO-03 (17-state enum + transitions). Owner decision log required.
- **HIGH (must-fix in Phase-0)**: N3 (WC audit trail), N4 (GDrive failover), N5 (Gearment cost policy), N7 (RD automation scope), file lifecycle (REQ-FIL-01..03), RACI + approval SLA, staging environment provisioning.
- **MEDIUM (Phase 1 / Phase 2)**: N6 (multi-technique routing), AI scope (REQ-EXT-14), dashboard SLA (REQ-DAS-01..03), message hub scope (REQ-MSG-01).
- **Documentation debt**: Glossary of Vietnamese technical terms, Owner decision log refresh, MASTER_PLAN.md version sync.

**Report completed**: 2026-04-26. Ready for Owner review and Spec 003 design-review kickoff.
