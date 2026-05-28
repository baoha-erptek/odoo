# Findings — Spec 001 Etsy Order Migration

Surprises, deviations, and deferred decisions encountered while implementing Spec 001 slices and operating the resulting code. Append-only — never delete entries; supersede with a new dated entry instead.

This file was created retroactively on 2026-05-10 to host the E2E surfacing register for spec 001 (Etsy ingest / email parsing / Gmail OAuth / order creation). Prior surprises lived in commit messages and `.claude/plans/006-master-plan-tracking.md` history rather than here; reconstructing them is out of scope.

---

## E2E surfacing (live)

Defects surfaced during E2E runs on staging that map to this spec. Each row links to `docs/E2E_DEFECTS_<date>.md` and the hotfix slice in `.claude/plans/006-master-plan-tracking.md` ("E2E Defects in Flight"). See `.claude/plans/006-implementation-playbook.md` §"E2E run defect intake" for capture/triage/routing rules.

| Date | Run § | Symptom | Severity | Hotfix slice | State |
|------|-------|---------|----------|--------------|-------|
| _(none yet)_ |
