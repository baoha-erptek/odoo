---
title: "Synthesis — 3-Agent Gap Review of E2 v1.1 + SRS EN v2.1 + DA-Post-Redpen"
date: "2026-04-26"
inputs:
  - ba-consultant-gap-2026-04-26.md
  - tech-architect-gap-2026-04-26.md
  - devils-advocate-gap-2026-04-26.md
target_docs:
  - .0temp/deliverables/E2_Quy_trinh_san_xuat.md  (v1.1)
  - specs/006-master-plan/SRS_Multichannel_Hub_EN.md  (v2.1)
  - specs/006-master-plan/agent-reports/devils-advocate-post-redpen.md  (new)
status: ready-for-owner-decision
---

# Synthesis

Three reviewers (BA/Odoo Consultant, Tech Architect, Devil's Advocate) audited the three target documents against the current state (8 ADRs, MASTER_PLAN, EXECUTIVE_OVERVIEW, specs 001/002/003/004/004a/005, the live `custom_addons/etsy_integration/` codebase, and the last 50 commits). This file consolidates their findings into a single change list and a recommended skill chain.

The full per-agent reports are kept verbatim as siblings:
- `ba-consultant-gap-2026-04-26.md` — functional / RACI / business-flow lens
- `tech-architect-gap-2026-04-26.md` — data model / ADR alignment / implementation impact lens
- `devils-advocate-gap-2026-04-26.md` — adversarial / evidence / contradiction lens

---

## 1. Cross-agent consensus — blockers (all 3 agents flagged)

| # | Issue | Severity | What blocks | Required artifact |
|---|---|---|---|---|
| **B1** | **Spec 005 (Etsy API) business case unsigned** — REQ-SYN-00 / N1 | BLOCKER | Phase 0 sandbox code | Owner 1-page ROI memo (why API over working email). Must cite quantified email error evidence or accept investor-narrative framing. |
| **B2** | **MO state machine (17 sub-states) has no transition graph** — N2 / REQ-PRO-03 / E2 §6 | BLOCKER | Spec 003 design-review | New **ADR-010** with explicit DAG. Owner + PD sign-off on "VN-Packed 1" and "[Fix]VN-Dish" semantics. |
| **B3** | **"<1% email error" claim unsubstantiated** — C3 / E2 §2.3 #2 | BLOCKER | B1 (it's the evidence B1 needs) | Owner data: date range, sample size, error definition. Memory note: 423 $0 orders contradict the claim. |
| **B4** | **Owner decision log missing** — 18 open decisions in E2 §8, no sign-offs | BLOCKER | Phase 0 close-out | Separate `decision-log.md` linking each decision → DA risk → Owner position → date → SRS impact. |

## 2. Cross-agent consensus — high-priority gaps

| # | Issue | Severity | Required artifact |
|---|---|---|---|
| **H1** | **WC reassignment governance undefined** — REQ-PRO-09 / N3 | HIGH | New **ADR-011**: cadence, sign-off role, lock-on-progress, audit log model. |
| **H2** | **File lifecycle models not in any ADR** — REQ-FIL-01..03 / E2 §3.1 | HIGH | New **ADR-009**: `design.file`, `design.file.route`, `design.print.batch`. |
| **H3** | **Auto-transition mechanism rationale absent** — REQ-AUT-01 / E2 §3.1 step 13 | HIGH | New **ADR-009b**: server action vs `base.automation`, idempotency contract. |
| **H4** | **GDrive failover / Discord sunset undocumented** — REQ-FIL-04 / N4 | HIGH | New **ADR-012**: token-refresh cron, alert SLA, Discord sunset date. |
| **H5** | **MP design-approval RACI + SLA missing** — E2 §5 / SRS §2 | HIGH | RACI matrix in Spec 003 design (e.g., MP-approval 4h SLA → PD-download 8h SLA → resubmit loop). |
| **H6** | **Gearment draft-orphan cost policy unknown** — REQ-TRF-09 / N5 | HIGH | Gearment-support contact + Spec 004a/b cost-clawback memo. Block REQ-TRF-05 until known. |
| **H7** | **ADR-001 module split not reflected in E2/SRS** — caught by Devil's Advocate only | HIGH | Update SRS namespace + manifest dependencies; revise E2 §3 references from single `gearment_outbound_request` to module boundaries. |
| **H8** | **REQ-MSG-01 scope contradiction** — pain #17 ("dashboard") vs SRS "export-only" — caught by DA only | HIGH | Either rescope REQ-MSG-01 (admit it's a routing/file hub, not a message hub), or move scope-rejection note to SRS §1 overview. |
| **H9** | **Phase 0 / Phase 1 split ambiguous in SRS §1** | HIGH | Revise SRS §1 tables: Phase 0 = sandbox (OAuth, dev shop). Phase 1 entry-gate = scope approval received. |

## 3. Cross-agent consensus — medium-priority gaps

| # | Issue | Required action |
|---|---|---|
| **M1** | RD daily pricing-check workflow ambiguous (manual vs auto-flag vs auto-pause) — N7 | Spec 006 clarification + RD interview before code. |
| **M2** | Multi-technique product routing (3+ WC) undefined — N6 | New **ADR-013** OR explicit Phase-2 deferral with PD volume assessment. |
| **M3** | Vietnamese-jargon glossary missing (VN-Packed 1, [Fix]VN-Dish, duyệt, hàng ngày, etc.) | Glossary appendix in SRS before sign-off. |
| **M4** | MASTER_PLAN.md (2026-04-13) is stale vs target docs (2026-04-26) | Refresh master plan to v2.1 to reflect red-pen, link to all new ADRs. |
| **M5** | Currency normalization (REQ-MIG-03: EUR/GBP/CAD/VND) enumerated in docs but never modeled in code | Verify in `models/sale_order.py` and either implement or revise REQ. |
| **M6** | E2 §3 says "Etsy webhook hoặc API v3" as if Phase-1 baseline; contradicts ADR-008 | Add Phase-tag in E2: "API path is Phase-1 cutover-target, not current state." |
| **M7** | Devil's Advocate post-redpen overlap with prior DA report (~70% recycled framing) | Acknowledge in document header that some risks are restated for visibility; mark genuinely-new (N3, N6, C1, C3, plus H7/H8 caught here). |

---

## 4. Per-document change list

### 4.1 `E2_Quy_trinh_san_xuat.md` (v1.1 → v1.2)

| § | Change | Source |
|---|---|---|
| Header | Bump version to v1.2; reference this synthesis + Owner decision log | All |
| §2.1 #2 | Soften "<1% lỗi" — flag as **owner claim, evidence pending** | DA · BA |
| §2.2 #7 | Add subsection: tooling decision (GDrive primary, Odoo filestore secondary, Discord fallback) — link to ADR-012 once written | BA · TA |
| §3 intro | Add note: Etsy API path = Phase-1 cutover target per ADR-008; current state is email-feed | DA |
| §3.1 footnote on WC reassign | Add: "Audited via `mrp.routing.assignment.change`. MOs in-flight retain `x_routing_id_at_creation`. Reassign forbidden while `mrp.production.state='progress'`. ADR-011." | TA |
| §3.1 step 7 | Reconcile "auto-deduct NL" with WC reassign causality; document the snapshot decision | DA |
| §3.1 step 13 | Either reword pain ("Vận hành phải tự chuyển") to match REQ-AUT-01, or admit it's still manual at MVP | DA |
| §6 | Add prose definition of "VN-Packed 1" and "[Fix]VN-Dish" once PD signs off (B2) | All |
| §7.5 | Add Gearment orphan-cost policy paragraph (or "TBD pending Gearment confirmation") | DA · BA |
| §8 | Replace ad-hoc decision list with link to formal `decision-log.md` (B4) | All |
| Appendix (new) | Vietnamese-jargon glossary | M3 |

### 4.2 `SRS_Multichannel_Hub_EN.md` (v2.1 → v2.2)

| § / REQ | Change | Source |
|---|---|---|
| Header | Bump to v2.2; link this synthesis | All |
| §1 roadmap | Split Phase 0 (sandbox: OAuth scaffold, dev shop) vs Phase 1 (production cutover). Phase-1 entry-gate = scope approval received. | TA · BA |
| §1 overview | Front-load Etsy Conversations scope-rejection note (currently buried in REQ-MSG-01) | TA · DA |
| §3 REQ-SYN-00 | Mark BLOCKER with explicit "owner memo required" language; add memo template reference | All |
| §6 REQ-006 / pricing | Disambiguate read-only dashboard vs auto-pause workflow; reference RD interview output | DA · BA |
| §7 REQ-PRO-03 | Link to **ADR-010** (state machine DAG) once written; add "transition rules in ADR-010" inline | All |
| §7 REQ-PRO-04 | Reference **ADR-013** for multi-technique routing (or explicit Phase-2 deferral) | TA · DA |
| §7 REQ-PRO-09 | Link to **ADR-011**; add governance fields (cadence, approver, lock-on-progress) | All |
| §9 REQ-TRF-09 | Add "block Phase 2 REQ-TRF-05 until Gearment policy confirmed"; link spike task | TA · BA |
| §10 REQ-FIL-01..03 | Link to **ADR-009** (data model) | All |
| §10 REQ-FIL-04 | Link to **ADR-012** (failover); add Discord sunset date placeholder | All |
| §10 REQ-AUT-01 | Link to **ADR-009b**; add idempotency requirement | TA |
| §10 REQ-MSG-01 | Either rename ("export-only" makes "Customer Message Hub" misleading) or scope-correct: it's a *file/notification* hub, not a message-content hub. Resolve H8. | DA · TA |
| §11 module map (new) | Reference ADR-001 4-module split; list module names + dependencies (H7) | DA |
| Appendix (new) | Vietnamese-jargon glossary | M3 |

### 4.3 `devils-advocate-post-redpen.md` (supplement, do NOT edit in place)

The post-redpen DA report stands as a snapshot. Add a sibling `devils-advocate-supplement-2026-04-26.md` capturing what it missed:

- **N8 (NEW HIGH)** — ADR-001 module split not integrated into E2/SRS (H7).
- **N9 (NEW HIGH)** — REQ-MSG-01 scope contradicts pain #17 (H8).
- **N10 (NEW BLOCKER)** — `<1% error` claim has not been pursued for evidence (B3 escalation).
- **N11 (NEW HIGH)** — Severity recalibration: original DA's R4.2/4.4 risks remain unmitigated; post-redpen restated them with weaker mitigation language.
- **Calibration note** — ~70% of post-redpen risks are restatements of prior DA. Document this transparently so readers don't double-count.

---

## 5. Owner-actionable items (chronological)

| When | Item | Owner | Output |
|---|---|---|---|
| **0-48h** | Provide email error-rate evidence (logs / sample size / definition) — resolves B3 | Owner | Memo or rescope-decision |
| **0-48h** | Sign or cancel Spec 005 ROI memo — resolves B1 | Owner | 1-page memo or "Phase 0 cancelled" |
| **0-3d** | Define "VN-Packed 1" and "[Fix]VN-Dish" with PD lead — feeds B2 | Owner + PD | Text definition for ADR-010 |
| **0-1w** | Sign WC reassign governance memo — feeds H1 | Owner + PD | Inputs for ADR-011 |
| **0-1w** | Contact Gearment support re: draft cost policy — feeds H6 | Owner + Tech Lead | Email thread + memo for Spec 004a/b |
| **0-1w** | Sign Discord sunset date — feeds H4 | Owner + PD | Date for ADR-012 |
| **0-2w** | Approve revised SRS §1 Phase 0/1 split — feeds H9 | Owner | Sign-off on SRS v2.2 §1 |

---

## 6. Recommended skill chain (concrete inputs → outputs)

The user asked specifically for "speckit skills or reasonable skills." Below is the prioritized chain. Skills marked `(speckit)` are spec-kit-family; `(sc)` are SuperClaude; `(gstack)` are gstack/local. All are presently installed.

### Stage 0 — Owner unblock (no skill, owner action)
- Items B1, B3, plus the 0-48h chronological list above.

### Stage 1 — Forensic clarification (parallel)
| Skill | Input | Output | Why |
|---|---|---|---|
| `/speckit-clarify` (speckit) | E2 §6 + SRS §7 REQ-PRO-03 + DA N2 | `specs/006-master-plan/clarifications/state-machine-questions.md` | Force PD/Owner to answer the 17×17 transition matrix questions before any model code. Resolves B2. |
| `/speckit-clarify` (speckit) | SRS §10 REQ-MSG-01 + E2 pain #17 + DA H8 | `clarifications/message-hub-scope.md` | Decide: rename vs rescope. Resolves H8. |
| `/office-hours` (gstack) | Post-redpen DA N1 + B3 evidence ask | `clarifications/spec-005-roi-memo.md` (forcing-question session) | Push Owner to articulate desperate-specific reason for API. Resolves B1 if memo emerges. |

### Stage 2 — Architecture decisions (sequential after Stage 1)
| Skill | Input | Output |
|---|---|---|
| `/sc:design` (sc) | State-machine clarifications + E2 §6 | `adrs/ADR-010-mo-state-machine.md` (Mermaid DAG, conditional paths) |
| `/sc:design` (sc) | WC governance memo (owner) + REQ-PRO-09 | `adrs/ADR-011-wc-reassign-governance.md` |
| `/sc:design` (sc) | REQ-FIL-01..03 + ADR-006 + E2 §3.1 | `adrs/ADR-009-file-lifecycle.md` (data model) + `adrs/ADR-009b-auto-transition.md` |
| `/sc:design` (sc) | Discord sunset memo + REQ-FIL-04 | `adrs/ADR-012-gdrive-failover.md` |
| `/sc:design` (sc) (optional) | DA N6 + PD volume data | `adrs/ADR-013-multi-technique-routing.md` (or explicit Phase-2 deferral note) |

### Stage 3 — Document refresh (after ADRs)
| Skill | Input | Output |
|---|---|---|
| `/sc:document` (sc) or manual edit | All Stage-2 ADRs + this synthesis | `SRS_Multichannel_Hub_EN.md` v2.2 + VN mirror v2.2 |
| `/sc:document` (sc) or manual edit | This synthesis + decision log | `E2_Quy_trinh_san_xuat.md` v1.2 + regenerate `E2_*.pdf` |
| Manual write | Open decisions from E2 §8 + Stage 2 outputs | `specs/006-master-plan/decision-log.md` (resolves B4) |
| Manual write | DA-supplement items | `agent-reports/devils-advocate-supplement-2026-04-26.md` |
| `/document-release` (gstack) | Stage-2 ADRs + Stage-3 docs | Refreshed `MASTER_PLAN.md` v2.1 + `EXECUTIVE_OVERVIEW.md` |

### Stage 4 — Re-plan (regenerate task lists)
| Skill | Input | Output |
|---|---|---|
| `/speckit-plan` (speckit) | Refreshed SRS + ADRs | Updated `specs/003-*/plan.md` |
| `/speckit-tasks` (speckit) | Updated plan + ADRs | Regenerated `tasks.md` for Spec 003 (and Spec 004a if module split affects scope) |
| `/speckit-checklist` (speckit) | Refreshed SRS REQ-IDs | Phase-0 / Phase-1 entry-gate checklist |

### Stage 5 — Final review gate (parallel; before Phase 0 code merges)
| Skill | Input | Output |
|---|---|---|
| `/plan-eng-review` (gstack) | Refreshed SRS + new ADRs + new task lists | Engineering plan review (locks architecture) |
| `/plan-ceo-review` (gstack) | Refreshed MASTER_PLAN + decision log | Executive plan review (challenges scope) |
| `/sc:analyze` (sc) | Refreshed SRS vs git log | Coverage gap map: REQs without tasks, tasks without REQs |
| `/codex` (gstack — independent diff review) | First Spec 003 PR using new ADR-009/010 | Independent verification before merge |

---

## 7. What we did NOT recommend (and why)

- **Do not edit `devils-advocate-post-redpen.md` in place** — it's a dated snapshot. Add a supplement instead so the audit trail is preserved.
- **Do not refactor module decomposition (ADR-001) inside Spec 003** — that's an `architect` agent job ahead of W3.x code; treat it as a doc-update at this stage.
- **Do not run `/ship` or `/land-and-deploy` until Stage 5 passes** — every skill chain step above is upstream of code merging to `main` for new architecture.

---

## 8. Open risks the synthesis itself may carry

- The synthesis aggregates three independent reads; one or more of the agents may have over-claimed (DA report self-flagged 3 areas of possible over-claim).
- "Owner memo not signed" assumes no Slack/email evidence exists; verify before treating B1/B3 as hard blockers.
- New ADRs (009..013) are scoped from doc-side review only; actual model design may force renumber/merge.

---

*End of synthesis. Next step: present this file to Owner, confirm B1-B4 resolution path, then enter Stage 1.*
