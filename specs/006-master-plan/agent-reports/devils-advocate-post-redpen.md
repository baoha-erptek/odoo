# Devil's Advocate Post-Redpen Review — Spec 006 Corrections (2026-04-26)

**Scope**: Owner's red-pen corrections to MASTER_PLAN.md, submitted after plan publication.  
**Finding**: 8 NEW risks introduced by the corrections; 3 internal contradictions; 1 missing business case.

> **DO NOT repeat prior findings** from [devils-advocate.md](devils-advocate.md). This report surfaces ONLY NEW risks from the corrections.

---

## New Risk Profile

### BLOCKER — Business Case Collapse

**N1: The Etsy API business case evaporates if email auto-feed is already <1% error**

Correction states: "Existing legacy system already auto-feeds Etsy emails into Sheets. Manual error rate is already <1%."

**Risk**: Spec 005 (OAuth/webhooks, 50-90 tasks, 6-8 weeks) is premised on replacing a broken email system. If the system is already **working** with <1% error, what is the ROI on a 2-month detour to API-first?

- Email parsing is 0% risk to Spec 001's completion.
- Etsy API is 3-8 week external dependency (scope review is still pending as of 2026-04-26).
- The Gearment fulfillment flow (Spec 004) works with either email-parsed orders or API orders equally.

**Question**: Is the pivot to Spec 005-Phase-0 actually justified? Did owner quantify what API solves that email doesn't (timeliness? reliability? feature unlock)? Or is this a sunk-cost escalation on a working system?

**Mitigation**: Freeze Spec 005 sandbox work until owner articulates the business case in writing. Keep email-only as Phase 1 baseline. Optional: benchmark current email latency + error distribution against API SLA assumptions.

---

### HIGH — Data Integrity / Process Assumptions

**N2: PD's "~12 sub-states" — is this the actual state machine or a flat list of observation tags?**

Correction names: "CHỜ FILE → CHỜ DUYỆT → ĐÃ GỬI PROOF → US-od/Vietnam-od → VN-Dish/VN-Dish NG/[Fix]VN-Dish/VN-SP mới/VN-Apron/VN-Handkerchief → VN-Packed/VN-Packed 1 → VN-Fulfilled"

**Risks**:
- **VN-Packed 1** — what does "1" mean? Operator A vs Operator B? Partial pack? Repack? Different inventory sub-bin? If the team can't explain "1" in 30 seconds, the state machine is **not modelled correctly**.
- **[Fix]VN-Dish** — suggests a status triggered by a rework decision. But who initiates [Fix]? What happens to the original WO's stock moves and labor cost? Is the original MO still counted in completion KPIs, or hidden? Risk: production analytics double-count rework labor.
- Linearity assumption: are all states traversed in order, or can a MO jump from CHỜ DUYỆT back to CHỜ FILE if design is rejected? If conditional, the diagram is a DAG not a state machine — requires explicit transitions modelled.

**Mitigation**: Before Spec 003 code starts, diagram the **actual** transition graph with owner+PD. Include rework paths. Clarify "Packed 1" semantics.

---

**N3: Admin can reassign product families to work centers "per period" — but no sign-off or audit trail**

Correction: "Admin can reassign families to lines per period."

**Risk**: 
- If rebalancing happens weekly, you're rebuilding BOMs on every MO every week.
- If it happens quarterly, you risk mid-MO line changes breaking the costed BOM.
- No mention of who approves, when approval happens, or what audit trail exists.
- Conflicting scenario: if an admin reassigns "wood pieces" from Line-A to Line-B while a wooden-dish MO is in CHỜ FILE, does the old costing remain valid? Does stock deduct from old line?

**Mitigation**: Define "per period" precisely (weekly? monthly? event-driven?). Add `work_center.assignment.log` model with state_id + user + timestamp. Forbid reassignment while MO is active in that line (or allow with explicit unlock).

---

### HIGH — File Storage / System Resilience

**N4: File routing replaces Discord — but no failover if Odoo filestore is down**

Correction: "File routing not upload-once" + "PD bulk-download/Photoshop A4 layout."

**Risk**:
- Old flow: Discord as de-facto shadow system. Always available (unless Discord is down).
- New flow: Odoo file storage + GDrive as primary. If Odoo or GDrive auth fails, PD has no rollback.
- GDrive OAuth is not long-lived; user token expires after 6 months of inactivity. If the service account key expires or is rotated, uploads silently fail.

**Mitigation**: Keep Discord as **documented fallback**. Add health check for GDrive token refresh; alert on failures. Spec 004a's GDrive cron should implement **exponential backoff + dead-letter queue** for failed uploads.

---

### HIGH — Product Categorization / Rework Loop

**N5: If [Fix]VN-Dish triggers re-design, who reimburses Gearment for the scrapped draft/quote?**

Correction: "[Fix]VN-Dish triggers re-design. What happens to in-progress workorders?"

This is **not** new — it's highlighted in my prior report as risk R4.2. But the correction **surface** it without resolution.

**Risk**: 
- Gearment draft created at date D. Costing locked. Quote TTL 24h.
- Design rejected; [Fix]VN-Dish state transition.
- New design uploaded; Gearment draft **superseded** (old draft orphaned).
- Old draft charges storage $X/day. Does owner eat the cost? Is it clawed back from customer? Does Gearment auto-expire drafts?

**Mitigation**: Contact Gearment support before Phase 0 ends. Document draft/quote lifecycle + cancellation / refund policy.

---

### MEDIUM — Multi-Technique Routing

**N6: Work-center grouping by print technique breaks on hybrid products**

Correction: "Work-center grouping rewritten by print technique (paper/fabric/wood/engrave/ceramic-print/ceramic-stamp/heatpress/embroidery/assembly/personalize)."

**Risk**: A product like "wooden dish with ceramic stamp + embroidery" requires **three** work centers (wood, ceramic, embroidery). Single-WC routing assigns to one line only.

- Does the MO generate a multi-line production plan (sub-MOs per technique)?
- Or does a single MO hop through lines sequentially (Line-Wood → Line-Ceramic → Line-Embroidery)?
- If sequential, what's the transfer time between lines? Does it block throughput?

**Mitigation**: Add a `product.technique` field (Many2many). Extend MO → manufacturing.bom to generate **split MOLines per technique** or **sequential line assignments**. Test with the 3-technique case in Phase 2.

---

### MEDIUM — Pricing Audit Scope Creep

**N7: "RD checks pricing DAILY" suggests an automation gap**

Correction: "RD checks pricing DAILY (not occasionally)."

**Risk**: 
- If daily is the current manual pattern, it's not a **rate**, it's a **workflow**.
- Spec 006 (Pricing Audit dashboard) was pitched as a one-time reporting layer.
- Daily checks imply either: (a) prices change daily (supply cost, exchange rate volatility), or (b) catalog prices are mis-entered frequently (data quality issue, not dashboard).
- Automation not sketched: auto-flag orders where `amount_total` drifts >5% from `catalogue_price`? Auto-suspend orders and page RD? Or read-only dashboard requiring manual reconciliation?

**Mitigation**: Before Spec 006 code, interview RD on the **actual workflow**: What triggers a check? What action does the check enable (pause order, email customer, adjust costing)? Is automation desired or forbidden?

---

### MEDIUM — Contradictions and Unresolved Claims

**C1: "1 sheet, not 3" + "anyone can edit" conflicts with data integrity claim of "<1% error"**

Correction states: legacy system has 1 sheet (not 3) and **error rate <1%**.

**Implication**: If error rate is <1% despite single-sheet, open-edit model, then either:
- The team has exceptional discipline (unlikely at scale).
- Most errors are **caught downstream** (e.g., Gearment rejects, customer complains) — not prevented upstream.
- The data quality claims for Spec 002 reconciliation need to be re-baselined against single-sheet reality (vs. three-sheet chaos scenario assumed in DA report R2).

**Mitigation**: Pull the actual error logs from the Google Sheet: timestamps, edit patterns, revert rates. Was the <1% measured by count of rows, or count of **customer-visible failures**?

---

**C2: "~12 sub-states" is more granular than the prior crosswalk assumed**

Prior DA report treated PD's state space as **binary-ish** (in-progress vs. done). The 12-state revelation suggests the crosswalk in Spec 003's `sale.order.status_enum` is underspecified.

**Mitigation**: Spec 003 state enum must enumerate all 12 PD states + transitions **before design-review**. Not after code.

---

**C3: "<1% error" claim is unsubstantiated**

No evidence provided: logs, date range, sample size, error definition. Is this owner's anecdotal sense ("in my memory, it's rare") or measured?

**Mitigation**: Require owner to provide the evidence before locking in Spec 005 deferral. If error rate is actually 3-5%, the business case for API changes.

---

## Synthesis: Should Spec 005 Be Frozen?

**The red-pen corrections create a **catch-22**:**
- **Old narrative**: Email system is broken, Spec 005 fixes it.
- **New narrative**: Email system works fine, Spec 005 is "nice-to-have."
- **Timeline impact**: Deferring Spec 005 frees 6-8 weeks in Phase 1. But it delays Etsy's **investor story** (API-integrated multichannel hub) by 3-6 months.

**Recommendation**: Owner must **choose explicitly**:
1. **Defer Spec 005 entirely** (ship email-only Phases 0-2). Save time, reduce risk.
2. **Keep Spec 005-Phase-0 sandbox work** (justify with investor narrative, not error-rate rationale). Budget 8 weeks.

Proceed with Phase 0 only after decision is recorded in a memo, not buried in a master plan revision.

---

## Summary: 6 New Blockers + 2 Contradictions + 1 Missing Business Case

| # | Risk | Severity | Triggering Correction |
|---|---|---|---|
| N1 | Etsy API ROI missing when email error rate <1% | **BLOCKER** | "auto-feeds...error <1%" |
| N2 | "VN-Packed 1" + "[Fix]VN-Dish" state semantics undefined | **HIGH** | "~12 sub-states" |
| N3 | Admin work-center reassignment has no audit trail or sign-off | **HIGH** | "admin can reassign per period" |
| N4 | GDrive/Odoo storage failover to Discord not documented | **HIGH** | "file routing...no Discord" |
| N5 | Gearment draft/quote orphaning cost not addressed | **HIGH** | "[Fix]VN-Dish rework" |
| N6 | Multi-technique products (dish+ceramic+embroidery) routing undefined | **MEDIUM** | "work-center grouping by technique" |
| N7 | "RD checks pricing DAILY" implies process automation not yet sketched | **MEDIUM** | "RD checks...DAILY" |
| C1 | Single-sheet edit model contradicts <1% error + pristine data integrity claim | **MEDIUM** | "1 sheet, not 3" |
| C2 | 12-state enum under-scoped in Spec 003 design | **MEDIUM** | "~12 sub-states" |
| C3 | "<1% error" is anecdotal, not measured | **MEDIUM** | Unsubstantiated claim |
| **Decision Block** | **Spec 005-Phase-0 continuation requires explicit ROI memo from owner** | **BLOCKER** | N1 + C3 |

**Closing**: The corrections are **additive detail**, not clarifications. They widen the scope of unknowns (state semantics, multi-technique routing, GDrive resilience, admin governance) while simultaneously undermining the **technical rationale** for Spec 005. Fix the rationale first. Then code.
