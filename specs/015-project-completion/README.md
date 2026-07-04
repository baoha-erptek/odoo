# Spec 015: Project Completion Consolidation

**Date**: 2026-07-03 (alignment update 2026-07-04)  
**Status**: Draft for Owner Review  
**Purpose**: Final closure spec consolidating all non-shipped work across Master Plan 006 (specs 001–014)

## This Spec Supersedes

Open remainders of specs 001–014 are consolidated here. Those specs remain **archived as historical record** but are **no longer the active execution reference** for remaining work.

## What Remains

**2026-07-04 alignment update**: a code-verification audit found 23 backlog items already shipped on `main` (entire publish pipeline, product hub, catalog Excel sync, tracking import). Phase 3 is ~85% code-complete, not 1%. The production gate is now the **Main-Flow E2E Gate** (MF-E2E-0..4 in spec.md): prove all 5 owner flows end-to-end (python runner + Playwright + BA sign-off, T073 umbrella). Five new audit items (AUD-01..05) cover doc-promised features that never existed.

**Master Plan 006 baseline (2026-07-03)** — 82.7% complete (153/185):
- **Phase 0–2**: Mostly done (inbound pipeline + staging E2E validated)
- **Phase 3**: ~85% code-complete (was misreported ~1%); E2E verification outstanding
- **Phase 4–5**: Partial (Gearment complete; returns/inventory deferred)

## Three Priority Buckets

1. **P1 (Production Cutover)**: Main-Flow E2E Gate (MF-E2E-0..4) + Etsy pilot flip + email→API rebind
2. **P2 (Hardening)**: Shop cutovers + i18n completion + design polish
3. **P3 (Polish & Reporting)**: Returns/refunds, pricing audit, Amazon/website channels

## Files in This Spec

- **spec.md** — Exhaustive backlog with 60 non-done items (P0–P5), grouped by priority
- **tasks.md** — Execution order with exit criteria per bucket
- **README.md** — This file (orientation)

See `spec.md` for consolidated backlog with model/field evidence. See `tasks.md` for critical-path ordering and P1/P2/P3 bucketing.
