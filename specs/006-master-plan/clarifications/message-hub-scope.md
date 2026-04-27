---
title: "Clarification Pack — Customer Message Hub scope (REQ-MSG-01)"
date: "2026-04-26"
revision: "v2 — Owner answered 2026-04-26 afternoon (Q1=B; conditional answers below)"
status: ANSWERED
audience: "Owner + MP lead (primary), BA (secondary)"
purpose: "Resolve the scope contradiction in REQ-MSG-01 — pain #17 wants 'message aggregation dashboard'; SRS v2.1 says 'export-only'. Pick one direction or rescope."
resolves_blockers:
  - Synthesis H8 (REQ-MSG-01 contradiction) — RESOLVED
  - DA gap report internal-contradiction #5 — RESOLVED
  - DA gap report supplement N9 — RESOLVED
related_constraints:
  - Etsy Conversations API scope was reviewed and rejected (memory note)
  - SRS REQ-MSG-01 currently states "export-only; does NOT ingest content"
  - E2 §2.2 pain #17 says "Không có dashboard tổng hợp tin nhắn khách"
how_to_use: |
  Read Context. Pick A, B, C, or D in Q1 (the only mandatory question).
  Answer Q2–Q4 only if the answer to Q1 needs them.
  Then either: write follow-up edits directly into SRS, or hand to architect for SRS v2.2.
---

# Owner answers (2026-04-26 afternoon)

Owner's principles: "Flexible, cover all known issues, **stay in Odoo internal system, avoid going outside to fetch information**, utilise all resources we have (API primary, email fallback)."

| Q | Answer | Rationale |
|---|---|---|
| **Q1** | **B — Ingest only the buyer-note field that Etsy DOES expose** (via `transactions_r` scope). Surface inline in Odoo + on a hub view. | Honors "stay in Odoo internal" — no portal hops. Honors "utilise all resources" — `buyer_message` is in scope, free signal. |
| **Q2** | **B — New model `etsy.buyer.message`** linked 1:N to `sale.order` | Future-proof for thread support if Etsy ever exposes it. Cleaner search and reporting than a single Text field. |
| **Q3** | N/A (Q1=B not A) |  |
| **Q4** | N/A (Q1=B not D) |  |
| **Q5** | **C — Both: top-level Hub view for MP + per-order tab for everyone** | Honors "flexible, cover all known issues" — MP gets the bird's-eye view; PD/BA get inline visibility in the order context. |
| **Q6** | **B — MP + BA + Owner** (read access) | Covers immediate need without over-restricting. Phase-2 can extend to PD if there's demand. |

**Effective REQ-MSG-01 rewrite** (lands in SRS v2.2 §10):

> **REQ-MSG-01** *(rev v2.2)* — **Customer Message Hub (buyer-note ingestion)**: Cron pulls `buyer_message` field on `GET /v3/application/shops/:shop_id/receipts` (already in scope under `transactions_r`). Stored in new model `etsy.buyer.message` (one row per receipt that has a non-empty buyer message). Surfaced (a) on the order form as a tab with the message body + timestamp, and (b) in a top-level "Customer Message Hub" view that MP can scan + search across shops. Read access: MP + BA + Owner. **Does NOT ingest Etsy Conversations content** (that scope was reviewed and rejected).

This rewrite is the definitive source for SRS v2.2; the question pack body below is preserved for audit.

---

# Context (read first)

The **MP/BA pain point #17** in E2 §2.2 reads (Vietnamese):

> "Không có dashboard tổng hợp tin nhắn khách — phải mở từng đơn hoặc Etsy Messages, dễ bỏ sót yêu cầu (đổi địa chỉ, ghi chú đặc biệt)."
>
> *(No dashboard aggregating customer messages — must open each order or Etsy Messages, easy to miss requests like address changes or special notes.)*

The **SRS v2.1 §10 REQ-MSG-01** reads (English):

> "Customer Message Hub. Export-only. Does NOT ingest content (Etsy Conversations scope rejected)."

These two statements are incompatible:
- Pain #17 explicitly asks for **content aggregation** ("tổng hợp tin nhắn") so MP can scan messages without opening each order.
- REQ-MSG-01 says **no content ingestion** because Etsy denied the Conversations API scope.

Without picking one, Spec 008 cannot be designed: a non-ingesting "export-only" hub does not solve pain #17, and an ingesting hub violates the API scope reality.

---

# Section A — Direction (1 mandatory question)

## Q1. What does "Customer Message Hub" actually deliver?

Pick exactly one.

| Option | What we build | What pain #17 gets |
|---|---|---|
| **A — Rename, keep export-only** | A view that exports order-level metadata (shop, buyer email, order date, has-customer-note flag) plus deep-links to the Etsy Messages portal. No message content. Renamed to e.g. **"Customer Coordination Hub"** so the name stops promising message aggregation. | **Partially solved.** MP still has to click through to Etsy for content, but the deep-links + `has_customer_note` flag removes the "scan every order" step. |
| **B — Ingest only the buyer-note field that Etsy DOES expose** | The `buyer_message` / `note_from_buyer` field on the Etsy Receipt is in scope under `transactions_r` (already requested). Pull it into Odoo and surface it on the order + on a hub view. **No Conversations ingestion.** | **Mostly solved.** Buyer notes (the most common pain — special instructions and address change requests) become searchable inline. Anything sent via Etsy Messages after the buyer-note still needs the portal. |
| **C — Ingest buyer-note + retry Conversations scope later** | Same as B for Phase 1. Add a Phase-3 work item to re-apply for Conversations scope after we have proof of revenue / volume thresholds Etsy may use to grant it. | Same as B short-term; pain #17 fully solved in Phase 3 if scope granted. |
| **D — Email-fallback aggregation** | Pull message content from the Gmail backup feed (Etsy notification emails contain message bodies for some message types). Surface in the hub. **Compliance review required** — Etsy's TOS may prohibit using notification emails as a content source. | Solves pain #17 short-term, but with **legal/TOS risk**. Recommend explicit legal review before committing. |

**Owner / MP answer (one of A/B/C/D):** ____________  
**Initials + date:** ____________

> *Why this matters*: Each option has very different scope, data model, and TOS posture. A and B are safe and Phase-1-feasible. C is B + a Phase-3 follow-up. D is risky and may need to be ruled out by counsel.

---

# Section B — Follow-ups conditional on Q1

## Q2. (only if Q1 = B or C) — Where does `buyer_message` live in the Odoo data model?

| Option | Placement |
|---|---|
| **A** | New field `sale.order.x_buyer_message` (Text). Searchable. |
| **B** | New model `etsy.buyer.message` linked to `sale.order` (1:N) — supports multiple notes if Etsy ever exposes a thread |
| **C** | Reuse `mail.message` posted to the order's chatter (gives free history + UI but no SLA on Etsy-sourced visibility) |

**Owner / Architect answer:** ____________  
**Initials + date:** ____________

---

## Q3. (only if Q1 = A) — Does pain #17 need a fallback path for now?

If we pick A, we partially solve pain #17 only. Should we ALSO pursue Q1=B (cumulatively)?

| Option | Decision |
|---|---|
| **A** | No — A is enough for Phase 1. Re-evaluate after MVP. |
| **B** | Yes — A + B together. Build A as the hub view, B as the data layer. (This is effectively Q1=B.) |

**Owner answer:** ____________  
**Initials + date:** ____________

---

## Q4. (only if Q1 = D) — Has counsel cleared use of Etsy notification email content as a data source?

| Option | Status |
|---|---|
| **A** | Yes — written opinion exists. Cite it: ______________ |
| **B** | No — schedule legal review before committing to D. (If unsure, this defaults to "No".) |

**Owner answer:** ____________  
**Initials + date:** ____________

> *If "No", do not pick option D yet — pick A or B as the Phase-1 baseline and revisit D after legal review.*

---

# Section C — UX and surface area (2 questions, useful for any of A–D)

## Q5. Where should the Customer Message Hub live in Odoo navigation?

| Option | Placement |
|---|---|
| **A** | Sidebar under `Sales` (top-level Hub view) |
| **B** | Tab on the Order Dashboard (next to Tracking + Process) |
| **C** | Both — a top-level Hub for MP + a per-order tab for everyone |

**Owner / MP answer:** ____________  
**Initials + date:** ____________

---

## Q6. Who has read access to the Hub?

| Option | Audience |
|---|---|
| **A** | MP only (matches pain #17 owner) |
| **B** | MP + BA + Owner |
| **C** | All internal staff with Sales access |

**Owner / MP answer:** ____________  
**Initials + date:** ____________

---

# What happens after this is answered

| If Q1 = … | Action |
|---|---|
| **A** | Update SRS REQ-MSG-01 to add the rename + deep-link + has-note-flag spec. No new ADR. Add `sale.order.x_has_customer_note` (Boolean computed) to Spec 003 data-model. |
| **B** | Update SRS REQ-MSG-01 to drop "export-only" language; add `etsy.receipt.buyer_message` ingestion to Spec 005 scope. Spec 005 plan + tasks regenerate via `/speckit-tasks`. |
| **C** | Same as B for Phase 1. Add a Phase-3 work item: "Re-apply for Etsy Conversations scope" with eligibility criteria. |
| **D** | Block the decision until legal opinion exists. Default to A or B in the meantime. |

In all cases, also:
- Update **E2 §2.2 pain #17** with whichever level of resolution we picked, in Vietnamese, owner-friendly.
- Update **DA post-redpen** in a sibling supplement noting H8 / N9 is closed.

---

# Open questions NOT in this pack (deferred)

- Pain #18 ("Thông báo & phối hợp khó") — separate pain; the file-routing requirements (REQ-FIL-*) cover most of it. If anything remains, raise as a separate clarification.
- Outbound messaging to customers (e.g., automated proof-approval emails) — not in scope of REQ-MSG-01; would belong to a future REQ-MSG-02 / REQ-OUT-*.
- Multi-shop unified inbox — out of scope until Q1 is answered.
