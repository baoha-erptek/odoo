---
title: "Owner Decision Log — Multichannel Hub (Spec 006 family)"
date_created: "2026-04-26"
last_updated: "2026-04-26 (afternoon — v3 reflects Owner accepted recommended designs across all open packs; D-11/D-12/D-16/D-17 RESOLVED; ADR-009 + ADR-010 written)"
purpose: "Single source of truth for every open / resolved decision the Owner has signed off on. Every ADR, SRS REQ-ID, and DA risk that requires Owner sign-off appears here. NOT a discussion forum — outcomes only."
status: 7 RESOLVED + 1 WITHDRAWN + 14 OPEN (none on Phase-0 critical path; all critical clarifications closed)
how_to_use: |
  - Each row is one decision. Columns: ID, decision, owner-of-decision, when-needed, status, signed-off-by + date, links.
  - When a decision is taken, fill the "Decision taken" column with the chosen option and update Status.
  - Never delete rows — set Status to SUPERSEDED and add a new row that supersedes it.
  - This file is the source for synthesis, ADRs, SRS REQ-* sign-off, and post-mortems.
resolves_blockers:
  - Synthesis B4 (no Owner decision log)
related:
  - SYNTHESIS-gap-2026-04-26.md (Stage-1 source)
  - guides/execution-playbook.md (chosen skill chain)
  - clarifications/STAGE-1-DRIVER.md (v2 status)
  - adrs/ADR-008a-email-as-mandatory-backup.md (D-13/D-14 outcome — single-pipeline source-switching)
  - adrs/ADR-012-gdrive-failover.md (D-19/D-22 outcome)
  - clarifications/spec-005-roi-memo.md (D-13/D-14 reasoning, v2)
  - clarifications/state-machine-questions.md (D-11 input — reframed v2)
  - clarifications/wc-reassign-governance-questions.md (D-12 input — reframed v2)
  - clarifications/message-hub-scope.md (D-17 input)
---

# Decision Log

| ID | Decision | Owner | When needed | Status | Decision taken | Signed-off by + date | Links |
|---|---|---|---|---|---|---|---|
| **D-1** | Tuyến MUG (in-house heat-press vs Gearment sublimation) | Owner + PD lead | Tuần 2 Phase B | OPEN | _____ | _____ | E2 §8 #1 |
| **D-2** | Tuyến TUM (similar to MUG) | Owner + PD lead | Trước cutover | OPEN | _____ | _____ | E2 §8 #2 |
| **D-3** | Warehouse topology — 1 company multi-warehouse vs 2 companies | Owner + Finance | Tuần 4 Phase B (with D3) | OPEN | _____ | _____ | E2 §8 #3 |
| **D-4** | Lot vs Serial tracking per family | PD lead | Tuần 4 Phase B (in D3) | OPEN | _____ | _____ | E2 §8 #4 |
| **D-5** | Map Gearment catalog for DMT/RUG/TAT/APR/PIL/BAG/APP | Ops + Gearment | Tuần 4 Phase C | OPEN | _____ | _____ | E2 §8 #5 |
| **D-6** | KCH / KSK / SGN — keep in scope? | Owner | Tuần 2 Phase B (with D1 sign-off) | OPEN | _____ | _____ | E2 §8 #6 |
| **D-7** | Personalization labor pricing — fixed or per-minute | Finance + PD | Tuần 6 Phase B (in D3) | OPEN | _____ | _____ | E2 §8 #7 |
| **D-8** | Carrier priority per route (USPS / UniUni / YunExpress) | BA + Shipping | Tuần 3 Phase B | OPEN | _____ | _____ | E2 §8 #8 |
| **D-9** | SKU prefix for Amazon (if SP-API rejects 3-char FAM codes) | Ecommerce | Spec 008+, no MVP block | OPEN | _____ | _____ | E2 §8 #9 |
| **D-10** | Website scope — all families or in-house only | Owner + Ecommerce | Spec 008+ | OPEN | _____ | _____ | E2 §8 #10 |
| **D-11** | Configurable order pipeline — scope, edit semantics, transitions, default seed | Owner + PD | Before Spec 003 code | **RESOLVED** | **Per-product with category default (Q1=C); manual on mixed-pipeline orders (Q2=D); freely reassignable with audit (Q3=A); admin+PD-lead can edit (Q4=B); versioned on first-use (Q5=A); reorder via versions only (Q6=C); DAG with admin override (Q7=C); manual transitions in Phase 1 (Q8=D); pre-seed 17 Vietnamese stages as default (Q9=A).** | Owner, 2026-04-26 (recommended defaults accepted) | E2 §8 #11; DA-N2 (mitigation: user-editable defaults); [state-machine-questions.md v2](clarifications/state-machine-questions.md); [ADR-010](adrs/ADR-010-configurable-order-pipeline.md) |
| **D-12** | Configurable resource assignment per pipeline stage — scope, lock semantics | Owner + PD | Before Spec 003 code | **RESOLVED** | **Custom `pipeline.team` model decoupled from MRP (Q1=A); per-stage default with per-order override (Q2=B); in-flight orders snapshot resource on entry (Q3=A); single audit log via order.pipeline.transition.log change_type field (Q4=A); reassignment reversibility = just create another reassignment (Q5=A).** | Owner, 2026-04-26 (recommended defaults accepted) | E2 §8 #12; DA-N3; [wc-reassign-governance-questions.md v2](clarifications/wc-reassign-governance-questions.md); [ADR-010 §6](adrs/ADR-010-configurable-order-pipeline.md) |
| **D-13** | Spec 005 (Etsy API) — business case + design | Owner | **BLOCKER — before Phase 0** | **RESOLVED** | **API primary, email permanent failover behind a single pipeline. Both adapters output the same canonical record. Source-switching, not dual-write.** | Owner, 2026-04-26 (recorded via Stage-1 synthesis; refined same-day on architecture) | E2 §8 #13; DA-N1 + C3 (closed); [spec-005-roi-memo.md v2](clarifications/spec-005-roi-memo.md); [ADR-008a v2](adrs/ADR-008a-email-as-mandatory-backup.md) |
| **D-14** | <1% email error rate evidence | Owner | Was BLOCKER | **WITHDRAWN** | **Question malformed; metric is template-drift risk, not historic error rate.** | Owner, 2026-04-26 (via D-13 reframing) | E2 §2.3 #2; DA-C3; [spec-005-roi-memo.md v2](clarifications/spec-005-roi-memo.md) |
| **D-15** | RD daily price check — auto-flag/pause vs read-only dashboard | Owner + RD | Tuần 4 Phase B | OPEN | _____ | _____ | E2 §8 #14; DA-N7 |
| **D-16** | Hybrid technique products (dish + ceramic + embroidery) — sub-MO vs sequential routing | Tech + PD | Tuần 4 Phase B | **RESOLVED** | **Naturally handled by configurable pipelines: create a "Multi-Technique" pipeline with sequential stages per technique. Resource assignment per stage (ADR-010 §6) handles work-center routing. No new model, no special case, no separate ADR-013.** | Owner, 2026-04-26 (subsumed by D-11 resolution) | E2 §8 #15; DA-N6; [ADR-010](adrs/ADR-010-configurable-order-pipeline.md); [state-machine-questions.md v2](clarifications/state-machine-questions.md) Q2 |
| **D-17** | Customer message hub — direction (rename, ingest buyer-note, retry Conversations scope, or email-fallback) | Owner | Tuần 2 Phase B | **RESOLVED** | **Q1=B — Ingest `buyer_message` field via existing `transactions_r` scope. New `etsy.buyer.message` model linked 1:N to sale.order. Surfaced on per-order tab + top-level Hub view. Read access: MP+BA+Owner. Does NOT ingest Conversations content (scope rejected).** | Owner, 2026-04-26 (recommended defaults accepted; honors "stay in Odoo internal") | E2 §8 #16; H8/N9; [message-hub-scope.md v2](clarifications/message-hub-scope.md) |
| **D-18** | AI analytics (REQ-EXT-14) — MVP scope or Phase 3+ defer | Owner | Tuần 2 Phase B | OPEN | _____ | _____ | E2 §8 #17 |
| **D-19** | Discord fallback — sunset window after `design.file.route` go-live | BA + PD | Cutover memo | **RESOLVED** | **Discord stays permanent as manual escape hatch (no sunset). No auto-failover; manual workflow only. Mirrors email-as-permanent-failover pattern.** | Owner, 2026-04-26 (recommended defaults accepted) | E2 §8 #18; DA-N4; [ADR-012 §4](adrs/ADR-012-gdrive-failover.md) |
| **D-20** | ADR-001 4-module split — confirmed in force; SRS v2.2 must add module map | Owner + Architect | Before Phase 1 code | OPEN | _____ | _____ | DA supplement N8; SYNTHESIS H7 |
| **D-21** | Gearment draft-orphaning cost policy (contact Gearment support) | Owner + Tech Lead | Before Phase 2 code (REQ-TRF-05) | OPEN | _____ | _____ | DA supplement N11; SYNTHESIS H6; future Spec 004b memo |
| **D-22** | GDrive credential type + token refresh policy + on-call | Owner + DevOps | Before Spec 004a code | **RESOLVED** | **Service account (preferred); fallback to OAuth-user with 30-day proactive refresh if tenant blocks. On-call tiered: auth=business hours, complete-outage=24/7. Pending uploads queue with exponential backoff. No auto-Discord-fallback.** | Owner, 2026-04-26 (recommended defaults accepted) | DA supplement N11; SYNTHESIS H4; [ADR-012 §1, §3, §5](adrs/ADR-012-gdrive-failover.md) |

---

# Status legend

- **OPEN** — Decision needed; no Owner action recorded yet.
- **REFRAMED** — Decision is still open, but the question itself has been restated under a newer design (the Decision-taken cell explains the reframing).
- **IN PROGRESS** — Question pack circulating with named owner; expected close date set.
- **RESOLVED** — Owner has signed off; the row's "Decision taken" + "Signed-off by + date" are filled.
- **WITHDRAWN** — Decision is no longer required (e.g., D-14: question was malformed; D-13's resolution made it moot).
- **SUPERSEDED** — Decision was made but later replaced by a new row; this row is kept for audit, but the active outcome lives in the superseding row.

# Sign-off conventions

- The "Signed-off by + date" cell is the only place an Owner signature is recorded. Slack messages, in-line markdown comments, and verbal confirmations do not count.
- An ADR can reference this log as the sign-off source, but the ADR's "Sign-off" line should still echo the date here for redundancy.
- When an entry moves to RESOLVED, fill **all** of: Decision taken, Signed-off by + date. Empty cells = not actually resolved.

# Update workflow

1. Add a row when a new decision surfaces (from a new ADR question, a synthesis review, an SRS REQ-ID that needs Owner endorsement).
2. Move to IN PROGRESS when a question pack is circulating; record the named owner.
3. Move to RESOLVED only when the Owner has read and accepted the chosen option.
4. If a resolved decision needs to change, do NOT edit the row — add a new row that supersedes it, mark the old row SUPERSEDED with a link.

---

# Open count by status (snapshot 2026-04-26 evening — v3)

| Status | Count |
|---|---|
| **RESOLVED** | 7 (D-11, D-12, D-13, D-16, D-17, D-19, D-22) |
| **WITHDRAWN** | 1 (D-14) |
| **OPEN — critical path** | 1 (D-20 module-split confirmation — needs Owner explicit yes/no) |
| **OPEN — non-critical** | 13 (D-1..D-10, D-15, D-18, D-21) |

**No clarification packs remaining open.** All Stage-1 packs are answered. The remaining critical-path open (D-20) is a one-line yes/no confirmation; non-critical opens have stated weeks in the original E2 §8.

---

# Closed-today summary (2026-04-26)

| ID | Outcome |
|---|---|
| **D-11** | Configurable order pipeline per ADR-010 (per-product+category default, versioned on edit, DAG with admin override, pre-seed 17 Vietnamese stages). |
| **D-12** | Resource assignment folded into ADR-010 §6 (custom `pipeline.team`, per-stage default + per-order override, snapshot on stage entry, single audit log). |
| **D-13** | API primary; email permanent failover; single pipeline; source-switching (no dual-write). See ADR-008a v2 + ROI memo v2. |
| **D-14** | Withdrawn (question malformed). |
| **D-16** | Hybrid technique products: subsumed by configurable pipelines (create a "Multi-Technique" pipeline). No new model. |
| **D-17** | Message hub: ingest `buyer_message` via `transactions_r` (no Conversations scope). New `etsy.buyer.message` model + per-order tab + top-level Hub. Read access MP+BA+Owner. |
| **D-19** | Discord stays permanent (no sunset). See ADR-012 §4. |
| **D-22** | GDrive service account; tiered on-call; queue + backoff; no auto-Discord-fallback. See ADR-012. |

# Stage-1 closure note

All Stage-1 question packs (state-machine-questions, wc-reassign-governance, message-hub-scope, gdrive-failover) are answered. Stage 2 ADRs (ADR-008a v2, ADR-009, ADR-010, ADR-012) are written. Stage 3 (SRS v2.2 / E2 v1.2 / MASTER_PLAN refresh) is in progress; SRS_EN v2.2 written same day. Stage 4 (`/speckit-plan` + `/speckit-tasks` regeneration for Spec 003 + Spec 005) is the next discrete execution.
