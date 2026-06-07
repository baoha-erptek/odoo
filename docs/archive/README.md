# Archived docs

Snapshots of superseded documentation. Files moved here are preserved in git
history at their original paths; this directory keeps them browsable without
cluttering the active docs/ tree.

## 2026-06-07 — UAT automation sweep cleanup

Triggered by the Wave 2/3 UAT pass + ESTY-187..199 closure. Files archived:

| Subdir | Count | Source pattern | Reason superseded |
|---|---|---|---|
| `2026-06-07/e2e-run-logs/` | 9 | `docs/E2E_DEMO_*_2026-05-*.md` | Timestamped run captures; superseded by `docs/E2E_TESTING_GUIDE.md` (the maintained spec) |
| `2026-06-07/e2e-defects/` | 3 | `docs/E2E_DEFECTS_2026-05-1*.md` | Defect intake logs from the May E2E sweep; defects either landed as slices or were closed in `.claude/plans/006-master-plan-tracking.md` |
| `2026-06-07/e2e-prep/` | 2 | `docs/E2E_RUN_PREP_*.md`, `docs/E2E_RERUN_PREP_*.md` | Point-in-time run checklists; superseded by `docs/E2E_TESTING_GUIDE.md` |
| `2026-06-07/legacy/` | 2 | `docs/HUONG_DAN_NGUOI_DUNG.md`, `docs/GEARMENT_SUPPORT_EMAIL_DRAFT.md` | First legacy is replaced by the structured `docs/owner/HUONG_DAN_*_VN.md` family; second is an ad-hoc email draft |

Files moved OUT of root but kept in active use:
- `docs/UAT_RESULTS_2026-05-26_SKU_BUILDER.md`, `..._ALL_FIELDS.md`, `..._REAL_APRON.md` → `docs/engineering/uats/` (engineer-facing reports, distinct from `docs/owner/UAT_FINDINGS_*.md`).

To restore a file:
```bash
git mv docs/archive/2026-06-07/<subdir>/<file>.md docs/<file>.md
```
