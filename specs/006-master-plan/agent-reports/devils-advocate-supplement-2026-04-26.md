# Devil's Advocate Supplement — 2026-04-26 (post-synthesis)

**Scope**: Items the synthesis identified that the post-redpen DA report (`devils-advocate-post-redpen.md`) missed. This is a **supplement**, not a replacement — read the original first; this file lists only the gaps.

**Why a supplement**: The post-redpen DA was dated 2026-04-26 and explicitly framed as "DO NOT repeat prior findings." The synthesis review showed 4 substantive risks slipped through that filter. This file captures them so the audit trail stays intact (do not edit `devils-advocate-post-redpen.md` in place).

**Calibration upfront**: Of the 8 NEW risks the post-redpen DA listed (N1–N7 + C1–C3), the gap-review estimated **~70% were re-framings of risks already raised in the prior `devils-advocate.md`** (R1, R4.2, R4.4, etc.) presented under new labels. That is not a criticism of the post-redpen DA — restating risks for visibility after a red-pen revision is reasonable. But the calibration matters: readers should not double-count when downstream artifacts (decision log, ADRs) cite both reports.

---

## N8 — ADR-001 module split is not reflected in any of the three target docs (HIGH)

**Evidence**:
- `MASTER_PLAN.md` line 78 mandates the 4-module split per `ADR-001`.
- E2 §3.2 step 1 still references a single `gearment_outbound_request` (no module boundary).
- SRS_EN v2.1 has no module map — REQ-IDs are flat across the system without a section that says which module owns which REQ.
- Post-redpen DA did not flag this.

**Why it matters**: Phase-1 code that lands in the wrong module is a refactor cost — and the 4-module split is precisely the kind of decision that gets harder to enforce after the first 5,000 lines of code commit to the single-module shape the docs imply.

**Severity**: HIGH (Phase-1 code blocker if the team starts implementing without integrating the split).

**Required action**:
- Add SRS §11 (or annotate each REQ-ID) with the owning module per ADR-001.
- Update E2 §3 references to use the new module names (`etsy_channel_email`, `etsy_channel_api`, `multichannel_hub_core`, `gearment_partner_*` — exact names per ADR-001 + ADR-008a's `etsy_channel_email` rename).
- Decision log entry: `D-19` (new) — "Confirm ADR-001 4-module split is in force; SRS v2.2 must add module map."

**Resolves**: synthesis H7.

---

## N9 — REQ-MSG-01 ("export-only") contradicts E2 pain #17 ("dashboard tổng hợp tin nhắn") (HIGH)

**Evidence**:
- E2 §2.2 pain #17 (Vietnamese): "Không có dashboard tổng hợp tin nhắn khách — phải mở từng đơn hoặc Etsy Messages, dễ bỏ sót yêu cầu (đổi địa chỉ, ghi chú đặc biệt)."
- SRS_EN v2.1 §10 REQ-MSG-01: "Customer Message Hub. Export-only. Does NOT ingest content (Etsy Conversations scope rejected)."
- These are incompatible. Pain #17 explicitly demands content aggregation; REQ-MSG-01 forbids it. Post-redpen DA noted REQ-MSG-01's scope-rejection but did not flag the contradiction with the pain it claims to address.

**Why it matters**: Spec 008 cannot be designed against contradictory inputs. Whatever is built will satisfy one of pain #17 or REQ-MSG-01, not both.

**Severity**: HIGH (Spec 008 design blocker; partial scope on Spec 005 if buyer-note ingestion is the resolution).

**Required action**: Run [`../clarifications/message-hub-scope.md`](../clarifications/message-hub-scope.md) with Owner + MP. Q1 picks the direction (rename, ingest buyer-note only, retry Conversations scope, or email-fallback with TOS risk).

**Resolves**: synthesis H8.

---

## N10 — Synthesis B3 was DISSOLVED, not closed (BLOCKER → withdrawn)

**Evidence**:
- The original DA C3 demanded evidence for the "<1% email error rate" claim.
- The synthesis treated this as evidence-gathering required.
- The actual Owner reframing ([`../clarifications/spec-005-roi-memo.md`](../clarifications/spec-005-roi-memo.md)) showed the question itself was malformed — historic error rate isn't the relevant metric; uncontrolled-template-drift risk is.

**Why it matters here**: Without this supplement, future readers of the post-redpen DA (and the synthesis) might still chase the `<1% evidence` artifact and waste cycles on a question that no longer applies.

**Severity**: WITHDRAWN (was BLOCKER).

**Required action**: Mark DA C3 as WITHDRAWN in the decision log; do not pursue the historical-evidence ask. The reframed risk profile is captured in `ADR-008a-email-as-mandatory-backup.md` and the ROI memo.

**Resolves**: synthesis B3 (dissolved); supersedes DA C3 framing.

---

## N11 — Severity calibration: prior DA's R4.2 / R4.4 risks remain unmitigated despite post-redpen restating them (HIGH)

**Evidence**:
- Prior DA R4.2 (Gearment draft orphaning cost) — flagged 2026-04-10. Post-redpen N5 restated 2026-04-26. **No mitigation in either.**
- Prior DA R4.4 (GDrive OAuth expiry after 6 months idle) — flagged 2026-04-10. Post-redpen N4 restated 2026-04-26. **No mitigation in either.**
- The synthesis put these into ADR-012 (GDrive failover) and an open Gearment-support contact, but until those land, the risks remain open.

**Why it matters**: It is easy to mistake "the DA flagged it twice" for "the DA mitigated it." Neither happened. The mitigations live in skill-chain Stage-2 (ADR-012, Gearment contact) and Stage-3 (SRS reconciliation rules from ADR-008a §5).

**Severity**: HIGH (operational risk persists until mitigations land).

**Required action**: Track in decision log as D-20 (Gearment contact) and D-21 (GDrive token-refresh + Discord sunset). Both feed ADR-012 / future ADR. Question pack [`../clarifications/gdrive-failover-questions.md`](../clarifications/gdrive-failover-questions.md) (U4) collects the inputs.

**Resolves**: synthesis H4 + H6 visibility (mitigations already chained — this entry just makes the persistence visible).

---

## What the post-redpen DA got right (do not retread)

For audit-trail completeness, the post-redpen DA's genuinely-new contributions are:
- **N3** — WC reassignment audit-trail gap. Genuinely new tier; feeds ADR-011.
- **N6** — Multi-technique product routing. Legitimately new; feeds future ADR-013 or explicit Phase-2 deferral.
- **C1** — Single-sheet open-edit model contradicts "<1% error" framing. Now subsumed by N10/ADR-008a (the underlying claim is withdrawn).
- **C2** — 12-state enum under-scoped. Genuinely useful; feeds ADR-010 + the question pack.

These are tracked elsewhere; no supplement needed.

---

## Closing

This supplement closes the audit-trail gap from the synthesis. With the four items above tracked in the decision log and routed to their respective ADRs / question packs, the post-redpen DA + this supplement together cover the full risk surface as of 2026-04-26.

**File status**: Read-only after acceptance. New risks discovered after 2026-04-26 belong in a fresh DA round, not in this file.

**Author**: Synthesis review (2026-04-26).
