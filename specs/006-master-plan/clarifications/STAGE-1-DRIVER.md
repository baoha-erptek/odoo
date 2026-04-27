---
title: "Stage-1 Driver — Status as of 2026-04-26 (late evening, v4 — Stage 3 cleanup batch DONE)"
date: "2026-04-26"
revision: "v4 — Stage-3 cleanup batch (U7-U10) executed: ADR-002/003 supersession annotations, MASTER_PLAN refresh, E2 v1.2, SRS_VN v2.2 mirror"
status: STAGE 1 CLOSED. Stage 2 ADRs landed. **Stage 3 CLOSED** (SRS_EN v2.2 done; SRS_VN v2.2 mirror done; E2 v1.2 done; MASTER_PLAN refresh done; ADR-002/003 annotations done). Stage 4 (`/speckit-plan` + `/speckit-tasks`) is the next discrete execution — held pending feature-branch worktrees per playbook caveat.
playbook: ../guides/execution-playbook.md
---

# Stage 1 — CLOSED

All clarification packs answered. All Stage-2 ADRs written. Decision-log shows 7 RESOLVED + 1 WITHDRAWN + 1 critical-path OPEN (D-20 module-split confirmation, one-line yes/no) + 13 non-critical opens (have stated weeks per E2 §8).

## Resolved today (full list)

| ID | Outcome |
|---|---|
| **D-11** (B2) | Configurable order pipeline per ADR-010 |
| **D-12** (H1) | Resource assignment folded into ADR-010 §6 |
| **D-13** (B1) | API primary; email permanent failover; single pipeline; source-switching |
| **D-14** (B3) | WITHDRAWN — wrong metric |
| **D-16** | Hybrid technique products subsumed by configurable pipelines |
| **D-17** (H8) | Message hub: ingest `buyer_message` via `transactions_r`; new `etsy.buyer.message` model |
| **D-19** | Discord stays permanent (no sunset) |
| **D-22** | GDrive service account; tiered on-call; queue + backoff |

## Stage-2 ADRs landed today

| ADR | Status |
|---|---|
| `ADR-008a-email-as-mandatory-backup.md` (v2) | Accepted — single-pipeline source-switching |
| `ADR-009-file-lifecycle.md` | Accepted — design.file + design.file.route + design.print.batch |
| `ADR-010-configurable-order-pipeline.md` | Accepted — combined pipeline + resource assignment (collapses ADR-011) |
| `ADR-012-gdrive-failover.md` | Accepted — service account, queue+backoff, Discord permanent escape hatch |

**No further ADRs needed for Phase 0**:
- ADR-011 was collapsed into ADR-010 §6
- ADR-013 (multi-technique routing) is no longer needed — Owner-confirmed direction is "create a Multi-Technique pipeline" per ADR-010

## Stage-3 progress

| Item | Status |
|---|---|
| `SRS_Multichannel_Hub_EN.md` v2.2 | ✅ Done (REQ-SYN-00 RESOLVED, new REQ-SRC-01..04 + REQ-PIP-01..09, REQ-PRO-03/04/09 reframed, REQ-MSG-01 rewritten, §11 Module map per ADR-001) |
| `SRS_Multichannel_Hub_VN.md` v2.2 mirror | ✅ Done (U10 — full mirror of EN v2.2 in Vietnamese) |
| `E2_Quy_trinh_san_xuat.md` v1.2 | ✅ Done (U9 — §2.1#2 template-drift framing, §3 intro single-pipeline source-switching, §3.1 footnote configurable pipeline, §6 default-seed framing, §8 link to `decision-log.md`) |
| `MASTER_PLAN.md` refresh | ✅ Done (U8 — banner points to ADR-008a/009/010/012; §4 retirement language stripped from Phase 1 + Phase 2 cutover sections; §6 ADRs 14-17 added) |
| ADR-002 + ADR-003 supersession annotations | ✅ Done (U7 — supersession banners pointing to ADR-008a v2 §2 / §5) |
| `SRS_Multichannel_Hub_VN.xlsx` regen | ⏳ Optional — run `build_srs.py` after Owner reviews VN v2.2 markdown |

**Stage 3 CLOSED.** All Stage-3 documentation is now coherent with the Stage-2 ADRs.

---

# Stage 4 — what to run next (per playbook)

The playbook (`../guides/execution-playbook.md`) calls for:

| Step | Tool | Notes |
|---|---|---|
| 4.1 | `/speckit-plan` against `specs/003-*/` | Regenerate plan from new SRS REQ-SRC, REQ-PIP, updated REQ-PRO, REQ-MSG-01 rewrite |
| 4.2 | `/speckit-plan` against `specs/005-etsy-api-channel/` | Regenerate plan from new REQ-SRC source-switching contract |
| 4.3 | `/speckit-tasks` against Spec 003 | Regenerate tasks |
| 4.4 | `/speckit-tasks` against Spec 005 | Regenerate tasks (drop reconciliation tasks; add adapter-interface + health-check + recovery-probe + source-change log) |
| 4.5 | `/speckit-checklist` | Phase-0 / Phase-1 entry-gate checklist |

**Branch caveat**: per memory note 2026-04-26, the team works on `main`. `/speckit-plan` and `/speckit-tasks` operate on the active feature spec discovered via `.specify/scripts/bash/check-prerequisites.sh`. From `main`, the prereqs script returns "Not on a feature branch" — meaning these commands need to be invoked from within a `003-…` or `005-…` worktree. The playbook accommodates this; the user (or future Claude) should `git worktree add` before running.

Alternative: hand-author the spec/plan/task updates directly per the SRS v2.2 deltas. This bypasses spec-kit entirely. The playbook prefers `/speckit-plan` + `/speckit-tasks` because the project already uses them (commit `bfda694`).

---

# Owner's TODO (the very short version)

1. ✅ Done — all four clarification sessions resolved by accepting the recommended designs.
2. ✅ Done — Stage-2 ADRs (ADR-008a v2, ADR-009, ADR-010, ADR-012) all signed in `decision-log.md`.
3. **One-line confirmation**: D-20 — confirm ADR-001 4-module split is in force? (yes/no). Default assumption: yes.
4. **Schedule (when ready)**: a single 30–60 min batch for Stage-3 deferred docs (SRS_VN mirror, E2 v1.2, MASTER_PLAN refresh, ADR-002/003 annotations). No new decisions needed; pure transcription.
5. **Schedule (when ready)**: Stage-4 task-list regeneration (`/speckit-plan` + `/speckit-tasks` per playbook, in worktrees for Spec 003 + Spec 005).

---

# Things I can do without further input (Stage-3 cleanup batch)

✅ **All four executed in one parallel batch (2026-04-26 late evening):**

| # | Item | Outcome |
|---|---|---|
| **U7** | Annotate ADR-002 (sync_mode → active_source supersession) and ADR-003 (legacy → email rename) | DONE — supersession banners added to both files; the original Decision blocks remain intact for traceability. |
| **U8** | Update `MASTER_PLAN.md` to point to ADR-008a v2 + ADR-009 + ADR-010 + ADR-012; strip retirement language from §4 | DONE — top banner refreshed with all 4 Stage-2 ADRs; Phase 1 cutover language ("flip `sync_mode='api_only'`", "30-day shadow-logging window") rewritten as `active_source='api'` + health-check + recovery probe; Phase 2 ("Gmail cron stops polling any live shop") rewritten as "email cron stays operational as permanent failover"; §6 decisions 14-17 added for ADRs 008a/009/010/012. |
| **U9** | Targeted edits to `E2_Quy_trinh_san_xuat.md` v1.2 | DONE — version bumped to v1.2; v1.2 changelog block added; §2.1#2 reframed with template-drift footnote; §3 intro replaced with single-pipeline source-switching paragraph; §3.1 configurable-pipeline footnote added; §6 reframed as "default seed of `Vietnam Internal Production` pipeline"; §8 lead-in points to `decision-log.md` as single source of truth + summarises D-11..D-22. |
| **U10** | Mirror `SRS_Multichannel_Hub_VN.md` v2.2 from EN v2.2 | DONE — full Vietnamese mirror written; structure matches EN v2.2 (§3 single-pipeline source-switching, §10.5 configurable pipeline, §11 module map, REQ-SRC-01..04, REQ-PIP-01..09, REQ-FIL-05/06, REQ-ORD-16, REQ-MIG-07; REQ-MSG-01 rewritten; old §11 → §12, old §12 → §13). |

Stage-3 cleanup batch closed. Stage 4 (`/speckit-plan` + `/speckit-tasks` for Spec 003 + 005) is the next discrete execution — held pending feature-branch worktrees per the playbook caveat (`/speckit-plan` and `/speckit-tasks` operate on the active feature spec; from `main` the prereqs script returns "Not on a feature branch").
