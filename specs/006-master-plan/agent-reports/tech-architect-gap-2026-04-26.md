# Technical Architect Gap Analysis — odoo19_esty Multichannel Hub (2026-04-26)

**Lens**: Data model coherence, architectural claims, ADR alignment, implementation impact  
**Target docs**:
1. `.0temp/deliverables/E2_Quy_trinh_san_xuat.md` (v1.1, owner-facing process guide, Vietnamese)
2. `specs/006-master-plan/agent-reports/devils-advocate-post-redpen.md` (new, 2026-04-26)
3. `specs/006-master-plan/SRS_Multichannel_Hub_EN.md` (v2.1, 2026-04-26)

**Current state references**: ADRs 001–008, MASTER_PLAN.md (2026-04-13), tech-architect.md (prior), `custom_addons/etsy_integration/__manifest__.py` (v19.0.2.1.0), git commits W1 GREEN + W3.2b.

---

## 1. Executive Summary

| Consequential drift | Severity | Source | Status |
|---|---|---|---|
| **REQ-FIL-01..03 (file lifecycle + routing) + REQ-AUT-01 (auto-transition) are NEW architecture**, not documented in any prior ADR. | P0 | E2 §3.1, SRS §10 | UNVERIFIED — missing model spec + ADR. Must create ADR-009. |
| **17 sub-states (E2 §6, SRS §7 REQ-PRO-03) lack transition graph.** Linear assumption unsafe; "VN-Packed 1" and "[Fix]VN-Dish" semantics undefined. | P0 | E2 §6, devil's advocate N2 | CONTRADICTED vs MASTER_PLAN (which treats state space as binary). Needs ADR-010. |
| **REQ-PRO-09 (WC reassignment audit) is NEW but governance undefined.** Who signs off? Frequency? Block MO in-flight? | P0 | SRS §7 REQ-PRO-09, devil's advocate N3 | UNVERIFIED — no audit model spec. Requires ADR-011. |
| **REQ-MSG-01 (Customer Message Hub export-only) vs Etsy Conversations scope (rejected).** SRS doesn't flag scope rejection explicitly. | P1 | SRS §10 REQ-MSG-01, E2 §10.2 | CONTRADICTED — export-only limitation not front-loaded in SRS body. |
| **Spec 005 business case (email error rate <1% → why API?) remains BLOCKER** per devil's advocate N1. SRS §3 REQ-SYN-00 flags but E2 does not. | P0 | SRS §3 REQ-SYN-00, devil's advocate N1 | UNVERIFIED — decision memo required before Phase 0 code. |

---

## 2. Per-Document Gap Tables

### A. E2_Quy_trinh_san_xuat.md (v1.1, 2026-04-26)

| Section / claim | Tech claim in doc | Reality (ADR / model / commit) | Recommended fix | Priority |
|---|---|---|---|---|
| §3.1 step 3: "BA tự nhận ghi chú cá nhân hóa và link GDrive" | MO auto-links GDrive file ID from `sale.order` | ADR-006 specifies file storage (GDrive primary). `order.design.file` model not yet in code. `multichannel_hub_core` module spec'd in tech-architect.md but module decomposition not yet landed. | Add explicit statement: "Design file reference is stored on `sale.order.design_file_id` (link to `design.file` model); GDrive URL stored in `design.file.gdrive_url`." Clarify w/ Spec 003 impl who owns the data-model field binding. | P1 |
| §3.1 step 5: WC re-grouping "Admin có quyền thay đổi" | "Các nhóm SP có thể thay đổi line tùy từng thời điểm — quản trị viên có quyền thay đổi" per footnote (v1.1) | ADR-008 does not spec audit trail. SRS §7 REQ-PRO-09 adds it post-redpen: `mrp.routing.assignment.change` log + `x_routing_id_at_creation` on MO. E2 does not mention lock-on-progress or approval signoff. | Update §3.1 footnote: "Admin reassignment is audited (who/when/reason). MOs in-flight retain original routing; new MOs post-date use new routing. Reassign forbidden while MO.state = progress (see ADR-011)." | P0 |
| §3.1 step 7: "Odoo log `mrp.workorder.duration` để phân tích năng suất" | Workorder logging for productivity analytics | No `mrp.workorder.duration` model in codebase or specs. Standard Odoo has `mrp.workorder` with `date_planned_start/end` but duration log is custom. E2 claims it but SRS does not require it (REQ-PRO-08 mentions "4 internal sub-states" but not duration logging). | Either: (a) remove the claim from E2 if analytics not critical, or (b) add explicit REQ-PRO-10 "Log workorder duration on button_finish" to SRS Phase 1 scope. Clarify with PD if needed. | P2 |
| §6: "VN-Packed 1" semantics | Defined as "biến thể của VN-Packed (ví dụ: line 1 / shift 1 / packed nhưng lô nhỏ)" | Devil's advocate N2 flags: "1" is ambiguous (operator, shift, partial pack?). SRS §7 REQ-PRO-03 lists it but does not clarify semantics. No state-transition graph provided. | Create a state-transition ADR-010 documenting the 17-state graph with explicit conditional paths (e.g., "CHỜ DUYỆT → CHỜ FILE if MP rejects"). Define "VN-Packed 1" per PD (line 1? shift 1? partial?) and pin to `x_substate` enum. | P0 |
| §3.1 step 13: Auto-transition "server action gọi khi `button_finish`" | Server action advances MO sub-state on workorder finish | SRS §10 REQ-AUT-01 specifies: "NOT base.automation (fragile)". E2 does not explain why. ADR-009 (file lifecycle) is new — this is ADR-009b (auto-transition). | Create ADR-009b: "MO sub-state auto-advance on workorder button_finish — server action, not base.automation. Rationale: base.automation re-evaluates on every write; server action is scoped to a single action call. Test: ensure idempotency (button_finish twice = state advance once)." | P1 |
| §7.2: Replace/refund ticket flow | "Mở ticket `multichannel.order.ticket` gắn vào đơn gốc. States: draft → submitted → approved → executing → closed." | Model name correct per MASTER_PLAN. Not yet in code. commit 05592e9f2f5 (W3.2b) landed data migration wizard but no ticket system. | Create Spec 003 task list item: "Implement `multichannel.order.ticket` model with state machine + mail.activity workflow (phase 2)." SRS §8 REQ-DUY-06..08 exists but ticket implementation deferred past MVP. | P1 |
| §8 decision #11: "VN-Packed 1" clarification before Phase 1 code | Flagged as unresolved | Devil's advocate post-redpen N2 re-surfaces this. SRS does not resolve it. | Block Phase 1 code entry until PD + Owner + Architect sign-off memo defining the state. Record in MASTER_PLAN phase-gate. | P0 |
| §8 decision #13: "Spec 005 (Etsy API) — business case?" | "Email auto-feed đã <1% lỗi → có cần đẩy lên API ngay?" | ADR-008 (API-first pivot, accepted 2026-04-13) answers: "Email is legacy-only; API is primary." But E2 treats it as still unresolved (§8 #13 "Owner"). Devil's advocate N1 + C3 say: <1% error claim is unsubstantiated. SRS §3 REQ-SYN-00 (v2.1 NEW) flags "business-case decision" as BLOCKER. | Owner to provide: (a) evidence of <1% error rate (logs, date range, sample size), and (b) written memo accepting ADR-008 or re-opening it. Required before Phase 0 code. | P0 |

---

### B. devils-advocate-post-redpen.md (2026-04-26)

| Risk # | Risk claim | Reality | Recommended fix | Priority |
|---|---|---|---|---|
| **N1** | Etsy API business case evaporates if email <1% error | ADR-008 accepted but relies on owner's ~"email is legacy" statement; no quantified evidence presented. SRS §3 REQ-SYN-00 flags as BLOCKER. | Owner memo: "Email <1% error is measured. Justification for API: [investor narrative / timeliness SLA / scope / features]." Evidence required before Phase 0 code lands. | **BLOCKER** |
| **N2** | VN-Packed 1 + [Fix]VN-Dish semantics undefined | E2 §6 lists ~17 sub-states, devil's advocate N2 flags conditional transitions. SRS §7 REQ-PRO-03 enumerates the states but no transition graph. | Create ADR-010: "MO state machine — 17 sub-states, transition graph (DAG), decision points (design rejection → [Fix], audit fail → NG, etc.)." PD + Architect jointly author. | **P0** |
| **N3** | Admin WC reassign has no audit trail / sign-off | SRS §7 REQ-PRO-09 (v2.1 NEW) adds audit log. No governance (who approves, cadence, lock-on-progress). E2 §8 #12 flags "cần làm rõ." | ADR-011: "WC reassignment governance — effective_date_start/end + mrp.routing.assignment.change audit log. Forbid reassign while MO.state=progress. Owner + PD sign-off required per reassignment cycle." | **P0** |
| **N4** | Discord fallback not documented; GDrive OAuth expiry risk | ADR-006 (revised 2026-04-13) promotes GDrive to primary. SRS §10 REQ-FIL-04 (v2.1 NEW) says "Discord retained as documented fallback." E2 §7.8 brief mention. No token-refresh SLA or fallback plan. | ADR-012 (new): "GDrive failover — OAuth token refresh on 30-day idle; alert on failure. Discord documented as cutover memo fallback; sunset date signed by Owner. Spec 004a adds token-refresh cron." | **P1** |
| **N5** | Gearment draft orphaning cost on [Fix]VN-Dish | E2 §7.5: [Fix] triggers redesign → MO cancel + new MO. Gearment draft (old design) orphaned. SRS §9 REQ-TRF-09 (v2.1 NEW) notes "cancel or auto-expire." No policy. | Contact Gearment before Phase 2 code. Document: draft/quote TTL, cancel refund policy, auto-expire behavior. Block REQ-TRF-05 until policy known. Add to Spec 004b tasks. | **P1** |
| **N6** | Multi-technique products (dish + ceramic + embroidery) routing undefined | E2 §3.1 lists WC by technique. Product "dish + stamp + embroidery" requires 3 WCs. Routing must be sequential or split MOs. SRS §7 REQ-PRO-04 groups by technique but no multi-WC routing spec. | ADR-013: "Multi-technique products — routing strategy: (a) sequential line assignments + transfer time, or (b) sub-MOs per technique. Test case: dish (wood-engrave + ceramic-stamp + embroidery). Implement Phase 2; test Phase 1." | **P1** |
| **N7** | RD daily pricing check implies automation gap | E2 §2.3 #5 + §4 row #5 flag daily check. SRS §6 mentions pricing audit dashboard. Devil's advocate N7: is it a report (read-only) or a workflow (auto-flag/pause)? | SRS §11 (Pricing Audit) must clarify: (a) dashboard is read-only flag, or (b) server-side auto-pause on variance >X%. If auto-pause, add auto-resume condition + RD approval flow. Spec 006 scope refinement required. | **P2** |

---

### C. SRS_Multichannel_Hub_EN.md (v2.1, 2026-04-26)

| Section / Req ID | Req claim | Reality | Recommended fix | Priority |
|---|---|---|---|---|
| §3 REQ-SYN-00 | "Etsy API business-case decision — Owner signs memo" | NEW v2.1. Flags as BLOCKER. Devil's advocate N1 + C3 provide evidence it's missing. ADR-008 accepted but no owner memo on the evidence. | Owner to provide memo with evidence of email error rate + ROI justification. Link memo to MASTER_PLAN phase gate (Phase 0 entry). | **P0** |
| §7 REQ-PRO-03 | "17 colored production sub-states" | Lists states but no transition graph. Devil's advocate N2 + E2 §6 highlight conditional paths (design rejected → CHỜ FILE?, NG → rework MO?). Linear assumption not safe. | Create ADR-010 transition graph (DAG). Spec 003 state-machine task must include explicit conditional paths + test coverage per state pair. | **P0** |
| §7 REQ-PRO-04 | "Work-center grouping by printing technique. Admin can reassign family → line." | Technique grouping is notation clarification (matches E2 §3.1). Reassignment governance underspecified. SRS adds REQ-PRO-09 (audit log) but no sign-off cadence / lock-on-progress. | ADR-011 must define: frequency (event-driven / weekly / monthly?), approval sign-off (Owner / PD lead?), lock-on-progress enforcement, audit trail. Spec 003 task. | **P0** |
| §7 REQ-PRO-09 | "Audit log + governance for WC reassignment" | NEW v2.1 (post-redpen). Adds `mrp.routing.assignment.change` log + `x_routing_id_at_creation`. Forbid reassign while MO in progress. Governance (who approves, cadence) not stated. | ADR-011 (see above). Phase 1 Spec 003 must implement with governance memo (Owner + PD co-signed). | **P0** |
| §10 REQ-FIL-01..03 | "design.file model — single upload, multi-route. design.file.route — read-permission per recipient. design.print.batch — bulk A4 layout." | NEW v2.1 (3 reqs derived from E2 pain points #11–#18). Not in any prior ADR. Matches E2 §3.1 step 2 (MO auto-links GDrive). No schema in Spec 003 yet. | Create ADR-009: "File lifecycle — design.file + design.file.route models. `design.file` stores GDrive ID (per ADR-006). `design.file.route` tracks recipient + delivery state. `design.print.batch` wizard generates A4 PDF. Test: bulk download with 50 files." Phase 1 Spec 003 task. | **P0** |
| §10 REQ-AUT-01 | "Auto status transition on mrp.workorder.button_finish. Server action (NOT base.automation)." | NEW v2.1. Matches E2 §3.1 step 13. Rationale (fragility of base.automation) not explained. ADR-009b needed. | ADR-009b: "MO sub-state auto-advance — server action on button_finish, not base.automation. Why: base.automation re-evaluates on every write (risk of repeat transitions); server action scoped to single action call (idempotent). Test: button_finish twice → state advance once, no duplicate transitions." | **P1** |
| §10 REQ-FIL-04 | "Discord retained as documented fallback. Sunset date signed by Owner." | NEW v2.1. Matches devil's advocate N4. No SLA on token refresh or fallback activation. | ADR-012 (see above). Spec 004a includes token-refresh cron + alert on failure. Cutover memo documents Discord sunset window (e.g., "30 days post-go-live"). | **P1** |
| §10 REQ-MSG-01 | "Customer Message Hub (export-only). Does NOT ingest content (Etsy Conversations scope rejected)." | NEW v2.1. Explicit scope limitation flagged (correct per Etsy scope review result). **But**: SRS body (§2 role desc, §10 header) does NOT mention scope rejection up front. Impl detail buried in req description. | Move scope rejection to SRS §1 overview or footnote: "Etsy Conversations scope was requested but rejected. Customer Message Hub exports message summaries (shop/buyer/subject/count) without message content — read-only view that links to Etsy portal. Deferred to Phase 2." | **P1** |
| §9 REQ-TRF-09 | "Gearment orphan policy on [Fix]VN-Dish — document policy with Gearment." | NEW v2.1. Flags cost recovery but defers decision to Gearment support (BLOCKER). No Phase 2 entry gate. | Phase 0 task: "Contact Gearment support before Phase 2 code — document draft/quote lifecycle, TTL, cancel policy, auto-expire behavior." Block Phase 2 REQ-TRF-05 entry until policy confirmed. Record memo in Spec 004b. | **P1** |
| §1 roadmap | "Phase 1 — MVP (~3-4 months)" scope lists Spec 005 as "API live" | ADR-008 says Phase 0 (sandbox) + Phase 1 (production cutover after scopes approved). SRS roadmap table doesn't reflect the sandbox/cutover split or scope-approval blocking condition. | Revise §1 Phase 0 + Phase 1 tables: Phase 0 includes "Spec 005 sandbox work (OAuth scaffolding, client, dev-shop integration)." Phase 1 entry gate: "Etsy scope review approved." Cutover of N shops happens within Phase 1 post-approval. | **P1** |

---

## 3. Architecture Claims Verification

### Claims from E2 + SRS — verification matrix

| Claim | Source | Category | Verification status | Evidence / ADR |
|---|---|---|---|---|
| **MO auto-links GDrive file ID** | E2 §3.1 step 3 | Design file ref | UNVERIFIED | ADR-006 specifies GDrive primary storage; model binding not in code or Spec 003 data-model yet. |
| **17 MO sub-states with auto-transition** | E2 §6, SRS §7 REQ-PRO-03 | State machine | UNVERIFIED | States listed but transition graph missing. Devil's advocate N2 flags conditional transitions. No ADR spec'd. |
| **WC reassign audited + governance** | SRS §7 REQ-PRO-09 (v2.1) | Audit trail | UNVERIFIED | ADR-008 does not spec audit. SRS adds `mrp.routing.assignment.change` but no sign-off / frequency / lock. ADR-011 needed. |
| **File lifecycle (design.file + route)** | SRS §10 REQ-FIL-01..03 (v2.1) | File mgmt | UNVERIFIED | NEW v2.1, not in ADRs or Spec 003 code. ADR-009 needed. |
| **Auto-transition via server action, not base.automation** | SRS §10 REQ-AUT-01 (v2.1) | Automation | UNVERIFIED | Requirement stated; rationale not in SRS. ADR-009b needed. |
| **GDrive OAuth + Discord fallback** | SRS §10 REQ-FIL-04 (v2.1) | Resilience | CONTRADICTED | ADR-006 specifies GDrive primary + 10 MB cap. SRS adds Discord fallback + token-refresh monitoring. No SLA. ADR-012 needed. |
| **Etsy API justification** | SRS §3 REQ-SYN-00 (v2.1) | Business case | CONTRADICTED | ADR-008 accepts API-first. Devil's advocate N1 + C3 flag email error rate is unsubstantiated. Owner memo required. |
| **Email <1% error rate** | E2 §2.1 + devil's advocate N1 | Data quality | UNSUBSTANTIATED | Mentioned without logs/date range/sample size. Claim blocks Spec 005 priority decision. Evidence required. |
| **Customer Message Hub export-only (not ingest content)** | SRS §10 REQ-MSG-01 (v2.1) | API scope | VERIFIED | Aligns with Etsy Conversations scope rejection (post-2026-04-26 review). SRS correctly limits to export. Scope rejection should be front-loaded in SRS §1. |
| **Design file re-upload at every handover (pain point #18)** | E2 §2.3 #18, SRS §10 REQ-FIL-02 | Pain point | VERIFIED | E2 documents the pain; SRS §10 REQ-FIL-02 proposes `design.file.route` to fix. Spec 003 task. |
| **Auto-deduct raw materials on MO Done (pain point #3)** | E2 §3.1 step 7 | Pain point | VERIFIED | Standard Odoo `mrp.production` → `stock.move.raw` on Done. Spec 003 / Spec 007 implementation. |
| **Tracking Dashboard gathers all carriers (pain points #8, #16)** | E2 §2.3 #8, #16, SRS §6 REQ-TRK-02 | Dashboard | VERIFIED | SRS §6 specifies dedicated Tracking page with 13 columns + carrier unification (ADR-005). Spec 003 task. |
| **Multi-technique product routing (dish + engrave + embroidery)** | E2 §3.1 + devil's advocate N6 | Routing | UNVERIFIED | E2 lists WC by technique. N6 flags multi-WC case (3+ techniques on 1 product). Routing strategy (sequential vs sub-MO) not spec'd. ADR-013 needed. |
| **MO retains x_routing_id_at_creation on WC reassign** | E2 §3.1 footnote + SRS §7 REQ-PRO-09 | Routing history | UNVERIFIED | SRS adds this but no model spec. Spec 003 task; verifiable in MO model via @api.depends. |
| **Admin reassign forbidden while MO.state=progress** | SRS §7 REQ-PRO-09 | Constraint | UNVERIFIED | Requirement stated. Implementation constraint not in `mrp.production` model spec. Spec 003 task. |

---

## 4. ADR Coverage — Recommendations for New ADRs

| ADR title (proposed) | 1-line summary | Scope | Blockers | Phase |
|---|---|---|---|---|
| **ADR-009: File Lifecycle & Routing** | `design.file` + `design.file.route` models for multi-recipient design distribution + `design.print.batch` bulk A4 wizard. | Spec 003 US2/US3 data model. Covers REQ-FIL-01..03. | None (ADR-006 design file storage already accepted). | Phase 1 (Spec 003) |
| **ADR-009b: Auto-status Transitions (server action, not base.automation)** | MO sub-state auto-advance on `mrp.workorder.button_finish` via server action (idempotent, scoped). | Spec 003 US3 workflow. Covers REQ-AUT-01. | Spec 003 state machine (ADR-010). | Phase 1 (Spec 003) |
| **ADR-010: MO State Machine — 17 Sub-States + Transition Graph** | Explicit DAG of MO state transitions, conditional paths (design rejection, audit failure, rework), terminal states, loop handling. | Spec 003 US2 data model. Covers REQ-PRO-03. | Owner + PD lead sign-off on "VN-Packed 1" + "[Fix]VN-Dish" semantics. | **Phase 0** (BLOCKER for Phase 1 code) |
| **ADR-011: Work-Center Reassignment Governance** | Admin reassignment audit log + approval sign-off + effective_date_start/end + lock-on-progress enforcement. | Spec 003 US2 workflow. Covers REQ-PRO-09. | Owner + PD definition of frequency (weekly / event-driven), approval role. | Phase 1 (Spec 003) |
| **ADR-012: GDrive Failover & Token Refresh** | OAuth token refresh cron, fallback to Discord (documented, sunset date), alert on failure. | Spec 004a + 006 (cutover memo). Covers REQ-FIL-04. | Operationalizing token refresh SLA (30-day idle refresh). | Phase 0 (parallel with Spec 005 sandbox) |
| **ADR-013: Multi-Technique Product Routing** | Sequential line assignments vs sub-MOs for products requiring 3+ work centers (dish + ceramic + embroidery). Test case + performance analysis. | Spec 003 US2 (or Spec 003+ if complexity deferred). Covers REQ-PRO-04 edge case. | PD assessment of volume (how many products are hybrid?). | Phase 2 (Spec 003+) |

---

## 5. Implementation Impact — Per Spec Slice

### Spec 001 (email ingestion — maintenance mode per ADR-008)
**Changes required**: None (ADR-008 freeze applies). Email parser stays on `main` but no new features.

---

### Spec 002 (data migration)
**SRS changes (none)**: SRS 002 not touched by redpen.  
**Model impact (none)**: Wizard finalization (commit 05592e9f2f5, W3.2b) on track.  
**Risk**: None identified in gap analysis.

---

### Spec 003 (dashboards + workflows + file lifecycle)
**SRS changes**:
- §4 (Order Dashboard): Add REQ-ORD-16 column for design file status (Awaiting/Approved/Revision-needed), reference to `design.file_id`.
- §5 (Tracking): REQ-TRK-08 (tracking state from carrier webhooks) marked P2 — confirm Phase 1 vs Phase 2 scope.
- §7 (Process Dashboard): REQ-PRO-03 transition graph must be added before code (link to ADR-010). REQ-PRO-09 governance memo must be signed.
- §8 (Approval flows): REQ-DUY-01..05 (design approval, address change, ticket creation) — add explicit role assignments (MP approves, BA reviews, Owner/PD sign-off per flow).
- §10 (NEW): REQ-FIL-01..04 + REQ-AUT-01..02 require ADR-009 + ADR-009b data model before code entry.

**Model impact**:
- `sale.order`: Add `design_file_id` (M2O → `design.file`), `design_file_route_ids` (O2M), `address_change_pending` (Boolean flag, locks label-buy).
- NEW `design.file` (GDrive ID, preview URL, file path); NEW `design.file.route` (recipient, delivery state, timestamp).
- NEW `etsy.address.change.request` (Requested/Approved/Rejected states, mail.activity).
- `mrp.production`: Add `x_substate` (Selection, 17 options per ADR-010), `x_routing_id_at_creation` (M2O → `mrp.routing` @ MO creation time).
- `mrp.routing.assignment.change` (audit log model): NEW per ADR-011.

**New wizards**:
- `design.print.batch` (tick files, generate A4 PDF).
- Address-change approval (MP request → BA approve/reject → update address).

**Risk**: ADR-010 state graph must be finalized by Phase 1 code entry, else state machine implementation will make wrong assumptions. **Blocker**.

---

### Spec 004a (tracking import + carrier detection)
**SRS changes**: SRS 004a scope (new spec per ADR-001) not yet published. Assume baseline from MASTER_PLAN + devil's advocate.

**Model impact**:
- `tracking.import.log`, `tracking.import.line` (per ADR-001 scope).
- `shipping.carrier` (unified carrier ref; merge `etsy.carrier.mapping` fields here per tech-architect.md CONFLICT-1).
- `sale.order.carrier_id` (M2O → `shipping.carrier`, replaces Char field from Spec 003).

**Risk**: GKE Excel schema fingerprinting (MASTER_PLAN phase 0 task) must land before Phase 1 code, or import will fail silently on schema drift.

---

### Spec 004b (Gearment fulfillment — post-MVP)
**SRS changes**: SRS 004b scope not published. Baseline from ADR-001.

**Model impact**:
- `fulfillment.partner`, `partner.sync.log`, `gearment_outbound_request`, webhook event models.

**Risk (N5)**: Gearment draft orphaning cost policy must be confirmed before Phase 2 code. **Blocking Task**.

---

### Spec 005 (Etsy API v3 — Phase 0 sandbox + Phase 1 production)
**SRS changes**:
- §1 Phase 0 / Phase 1 tables: Clarify sandbox work (OAuth, client, dev-shop integration) separate from production cutover (post-scope-approval). Link scope-approval as phase-gate decision.
- §3 REQ-SYN-00: Owner memo required before Phase 0 code (evidenced email error rate + ROI).

**Model impact**:
- `etsy.api.log`, `etsy.webhook.event`, `etsy.carrier.mapping` (per tech-architect.md §1).

**Risk**: Scope-approval critical path. If delayed >4 weeks, Phase 1 cutover slips correspondingly. **Blocking external dependency**.

---

### Spec 006 (Pricing Audit — new per MASTER_PLAN)
**SRS changes**: SRS 006 spec not published. Baseline: MASTER_PLAN + devil's advocate N7.

**Model impact**:
- SQL view `sale.order_pricing_audit` (read-only; no table) for dashboard, **or**
- `sale.order.pricing.audit` snapshot model for historical reports (per tech-architect.md §1.7).

**Risk (N7)**: RD workflow undefined — is dashboard read-only flag, or auto-pause orders? Requires Spec 006 clarification.

---

### Spec 007 (Raw-material inventory + forecasting — new per MASTER_PLAN)
**SRS changes**: SRS 007 spec not published. Baseline: use native `stock` + `stock_forecasted` (tech-architect.md §1.8).

**Risk**: None identified if leveraging Odoo native (not building parallel model).

---

## 6. Security & Compliance Notes

| Topic | Status | Action |
|---|---|---|
| File storage cap (10 MB on `ir.attachment`) | VERIFIED per ADR-006 §2 | Spec 003 task: implement `IrAttachment.create()` override raising `ValidationError` on >10 MB. Test: upload 150 MB design file → rejected. |
| GDrive auth token expiry | UNVERIFIED | ADR-012 task: implement token-refresh cron on 30-day idle. Test: token-refresh failure → alert admin. |
| MO in-flight reassign lock | UNVERIFIED | Spec 003 task: add constraint forbidding WC reassignment while `mrp.production.state = 'progress'`. Test: attempt reassign with in-progress MO → error. |
| Design file audit trail | VERIFIED per SRS §10 REQ-FIL-02 | `design.file.route` tracks delivery state + timestamp. `design.file` has `created_by/on`, `write_by/on` (standard). Test: trace file route from BA upload → MP approval → PD download. |
| Etsy scope rejection (Conversations) | VERIFIED per SRS §10 REQ-MSG-01 | SRS explicitly limits export-only. No private message content ingested. Compliant. |

---

## 7. Workflow & Skill Recommendations

### Immediate actions (Phase 0 — before Spec 003 code entry)

1. **Create ADR-010 memo** (PD lead + Architect, ~2 hours)
   - Skill: `/sc:design` or manual (detailed state DAG + conditional paths).
   - Deliverable: 1-page ADR-010 with 17-state graph (Mermaid or ASCII).
   - Gate: Must be approved by Owner + PD before Spec 003 code review.

2. **Confirm email error rate evidence** (Owner, ~30 min)
   - Skill: (investigative work only, no tooling needed).
   - Deliverable: Memo with date range, sample size, error definition, <1% claim evidence.
   - Gate: Spec 005 Phase 0 code entry.

3. **Refine SRS §1 Phase 0 / Phase 1 tables** (Architect, ~1 hour)
   - Skill: `/speckit-clarify` or manual document edit.
   - Change: Split "Spec 005" into "Phase 0 (sandbox)" + "Phase 1 (production cutover after scope approval)."
   - Deliverable: Revised SRS §1 tables + phase-gate decision list.
   - File: Update `SRS_Multichannel_Hub_EN.md` (and VN mirror).

4. **Create Spec 003 data-model.md with ADR-009 + ADR-010 binding** (Architect, ~3 hours)
   - Skill: `/sc:design` (data model + state machine UML).
   - Deliverable: Spec 003 data-model.md covering `design.file`, `design.file.route`, `mrp.production.x_substate`, `mrp.routing.assignment.change`, transitions.
   - Gate: Before code-review on Spec 003 Spec 003 US1 (model structure).

5. **Gearment draft policy spike** (Spec 004b owner, ~4 hours contact + documentation)
   - Skill: (customer communication + RFP writing).
   - Deliverable: Email to Gearment support documenting draft/quote TTL, cancel policy, auto-expire behavior, cost recovery.
   - Gate: Phase 0 (parallel with Phase 1 code, but required before Phase 2 REQ-TRF-05 implementation).

---

### Parallel work during Phase 1 code (Spec 003)

1. **ADR-011 governance memo** (Owner + PD co-signed, ~2 hours)
   - Defines: frequency of WC reassign (event-driven / weekly / monthly?), approval role, lock-on-progress, audit trail.
   - Gate: Before Spec 003 REQ-PRO-09 code review.

2. **ADR-012 GDrive token-refresh + fallback memo** (Architect, ~1 hour)
   - Defines: token-refresh SLA (30-day idle), Discord fallback duration, alert criteria.
   - Gate: Before Spec 004a (tracking import) code review.

3. **Spec 005 scope review status ping** (Owner, weekly)
   - Milestone: Week 1 (submit if not done), then weekly status.
   - Gate: Phase 1 cutover cannot begin without scope approval.

4. **Spec 003 code-review checklist** (Reviewer, per-PR)
   - Verify: state transitions tested for all 17 × 17 pairs (comprehensive matrix test).
   - Verify: ADR-010 transition graph enforced in model constraints.
   - Verify: `x_routing_id_at_creation` on MO correctly snapshotted at creation time.
   - Verify: `design.file.route` audit trail complete (created_by, write_by, delivery_state timestamps).

---

### Skill recommendations — next steps

| Task | Skill | Rationale |
|---|---|---|
| Refine E2 + SRS sections 3.1, 6, 7 | `/speckit-clarify` | Flag conflicts + missing state graph. 30-min session. |
| Create ADR-010 state machine graph | `/sc:design` or manual | Mermaid DAG; 2-3 hours. |
| Audit SRS vs MASTER_PLAN phase gates | `/sc:analyze` | Identify blocking dependencies (scope approval, ADR decisions, external tasks). 1 hour. |
| Design ADR-011 approval workflow | `/sc:design` + `/sc:workflow` | Draw approval flow (Owner / PD sign-off cadence). 2 hours. |

---

## 8. Technical Debt & Risks

### High-severity risks (must resolve before Phase 1 code)

| Risk | Source | Mitigation | Owner |
|---|---|---|---|
| VN-Packed 1 semantics undefined → wrong state machine | E2 §6 + devil's advocate N2 | **ADR-010 + PD sign-off memo (due Phase 0).** Block Phase 1 code entry on this. | PD lead + Owner |
| Email error rate claim unsubstantiated → Spec 005 justification collapses | Devil's advocate N1 + C3 | **Owner memo with evidence of <1% (logs/date/sample/definition) — due Phase 0.** Required for Spec 005 Phase 0 code approval. | Owner |
| GDrive OAuth expiry + Discord fallback timing uncertain | ADR-006 rev + devil's advocate N4 | **ADR-012 memo defining token-refresh SLA + Discord sunset — due Phase 0.** Implement cron in Spec 004a Phase 1. | Architect |
| Multi-technique product routing not spec'd (3+ WC case) | Devil's advocate N6 | **ADR-013 scope determination Phase 1:** Is this a Phase 2 edge case, or Phase 1 must-have? PD volume assessment. | PD lead + Architect |

### Medium-severity risks (resolve before Phase 2 code)

| Risk | Mitigation |
|---|---|
| Gearment draft orphaning cost policy unknown (N5) | Phase 0 task: contact Gearment. Block Phase 2 REQ-TRF-05 on this. |
| RD daily pricing check workflow (auto-pause vs read-only flag) (N7) | Spec 006 clarification task (parallel with Phase 1). |
| MO sub-state transitions not tested end-to-end | Spec 003 code-review checklist: test all 17×17 transition pairs. |

---

## 9. Summary: Files & Decisions to Update

| File | Update | Deadline | Owner |
|---|---|---|---|
| **MASTER_PLAN.md §4** | Add Phase 0 gate: ADR-010 + ADR-011 sign-off + email error evidence. | Before Phase 1 code | Architect |
| **SRS_Multichannel_Hub_EN.md §1** | Clarify Phase 0 (sandbox) vs Phase 1 (production cutover after scope). Scope approval as phase gate. | Before Phase 1 code | Architect |
| **SRS_Multichannel_Hub_EN.md §3** | REQ-SYN-00 status: require owner memo for approval. | Before Phase 0 code | Owner |
| **SRS_Multichannel_Hub_EN.md §7** | REQ-PRO-03: link to ADR-010 transition graph. REQ-PRO-09: link to ADR-011 governance memo. | Before Phase 1 code | Architect |
| **SRS_Multichannel_Hub_EN.md §10** | REQ-FIL-01..04: link to ADR-009. REQ-AUT-01: link to ADR-009b. REQ-FIL-04: link to ADR-012. REQ-MSG-01: move scope-rejection note to SRS §1 overview. | Before Phase 1 code | Architect |
| **Create ADR-009** | File lifecycle + routing (`design.file`, `design.file.route`, `design.print.batch`). | Before Spec 003 code review | Architect |
| **Create ADR-010** | MO state machine — 17 states + transition graph + conditional paths. **BLOCKER.** | **Before Phase 0 end** | PD lead + Architect |
| **Create ADR-011** | WC reassignment governance — frequency, approval, lock-on-progress, audit. | Before Spec 003 code review | Owner + PD |
| **Create ADR-012** | GDrive token-refresh + Discord fallback SLA. | Before Spec 004a code review | Architect |
| **Create ADR-013** (if needed) | Multi-technique product routing — scope determination. | Phase 1 or Phase 2 decision | PD lead + Architect |
| **E2_Quy_trinh_san_xuat.md** | Footnote §3.1 WC reassign: "Audited (who/when/reason). MOs in-flight retain original routing (x_routing_id_at_creation). Forbid reassign while MO.state=progress (ADR-011)." | Before Phase 1 (informational) | Owner |

---

## Closing

The three documents (E2 v1.1, devil's advocate post-redpen, SRS v2.1) introduce **5 NEW requirement families** (REQ-FIL-01..04, REQ-AUT-01..02, REQ-PRO-09, REQ-SYN-00, REQ-TRF-09) that are not in any prior ADR. All require explicit ADRs before Phase 1 code entry. The most critical blockers are:

1. **ADR-010 (MO state machine)** — defines 17-state semantics + transitions. Required before Spec 003 modeling.
2. **Owner evidence memo (email error rate)** — justifies Spec 005 priority vs deferral. Required before Phase 0 code approval.
3. **ADR-011 (WC reassignment governance)** — defines approval cadence + lock-on-progress. Required before Spec 003 code review.

None of these block the **business case** — Spec 002 + Spec 003 + tracking delivery (Spec 004a) ship on schedule regardless. The ADRs ensure Spec 003's state machine and file-routing architecture align with actual operational workflows (as documented in E2), not assumed ones.

