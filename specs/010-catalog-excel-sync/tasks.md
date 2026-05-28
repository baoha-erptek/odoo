# Tasks: Catalog Excel Recurring Sync (Spec 010)

Dependency-ordered, slice-specific. Four implementation slices, all in `multichannel_hub_core`. Each runs the MP006 9-phase loop and Two-Phase Testing.

Status legend: `[ ]` todo · `[~]` doing · `[X]` done.

**All slices depend on Spec 009 P-HUB-PROD-MODEL landing.**

---

## Slice P-HUB-XLS-PARSE — openpyxl Parser + Staging

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T001 | [X] Schemas finalized | Spec 009 ✓ | plan | |
| T002 | [X] 3 models (`product.catalog.import.run` + `import.line` + `sheet.fingerprint`) + sequence + C-CIL-001 + C-CSF-001 init() mirrors + composite indexes | T001 | GREEN | |
| T003 | [X] openpyxl parser service (`services/excel_catalog_parser.py`) | T002 ✓ | GREEN | Shipped `P-HUB-XLS-PARSE-SERVICE` c7c8ef1cfad (2026-05-23); reconciled 2026-05-28 |
| T004 | [X] sheet map + fixture xlsx | T003 | GREEN | In-test openpyxl fixture (no committed binary); reconciled 2026-05-28 |
| T005 | [X] ACL rows (6 — 3 models × 2 groups) | T002 | GREEN | |
| T006 | [X] RED Phase 1 (DB) — 8 tests | T001 | RED | port 8175 |
| T007 | [X] Phase 2 parser tests (`test_phase2_excel_parser_orm.py`) | T003,T004 | GREEN | Part of 24 Phase-2 ORM post-tests, 0 failed (verified 2026-05-28) |
| T008 | [X] GREEN (Phase 1 + parser) | T006 | GREEN | |
| T009 | [X] Verify + Commit | T008 | Land | `P-HUB-XLS-PARSE-SERVICE` shipped the openpyxl parser + fingerprint compute + row emission |

---

## Slice P-HUB-XLS-INGEST — Upsert + Conflict Matrix + Pricelist Seed

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T010 | [X] `services/catalog_ingestor.py` — `upsert(env, run, lines)` batches `product.template.search` once per sheet; applies ADR-014 §3 conflict matrix per field; per-row savepoint; emits error line on per-row failure | P-HUB-XLS-PARSE ✓ | GREEN | Shipped `P-HUB-XLS-INGEST core` 29cf95eeb4a (2026-05-23) |
| T011 | [ ] Multi-currency pricelist seed helper (US5) — `_seed_pricelist_items_first_import(env, product, line)` writes 1 item per non-empty currency column; idempotent (no overwrite); seeded pricelists `noupdate=1` | T010 | — | **Still deferred** — `catalog_ingestor.py:16` explicitly notes "Multi-currency pricelist seed (T011/US5) is deferred to a follow-up". Incremental enhancement, non-blocking. |
| T012 | [X] RED Phase 2 (ORM): upsert new row creates template; existing row preserves `x_channel_applicability_ids`; Excel-wins fields overwrite; missing-from-Excel row flagged but not archived; per-row failure rolls back row only | T010 | RED | pricelist-seed assertions deferred with T011 |
| T013 | [X] GREEN (`test_phase2_catalog_ingestor_orm.py`) | T012 | GREEN | Part of 24 Phase-2 ORM post-tests, 0 failed (verified 2026-05-28) |
| T014 | [X] Review + Verify + Commit | T013 | Review→Land | |

---

## Slice P-HUB-XLS-CRON — Cron + Wizard + Run Report View

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T015 | [X] manual-run wizard (`wizards/catalog_import_run_wizard.py`) — file picker + dry-run flag + `_check_ba_or_raise()` + preview/commit actions | P-HUB-XLS-INGEST ✓ | GREEN | Shipped `P-HUB-XLS-MANUAL-WIZARD` 0d9a6f3a283 (filename drift: `catalog_import_run_wizard.py`); FR-017 gate before parse+upsert |
| T016 | [X] cron (`data/product_catalog_cron.xml`) — daily 02:00 UTC; local-path source + ICP gate | T015 | GREEN | Shipped `P-HUB-XLS-CRON schedule` 357ab57b178 (filename drift) |
| T017 | [X] GDrive fetcher (`services/gdrive_uploader_helper.py`) — newest .xlsx → parser+ingestor | T015, P2-06 GDrive plumbing ✓ | GREEN | Filename drift; reuses GdriveUploader from P2-06; `test_phase2_catalog_gdrive_fetcher_orm.py` mocks `_build_service` |
| T018 | [X] Run report view — tree + form on `product.catalog.import.run` | T015 | GREEN | Shipped with the wizard/menus commit |
| T019 | [X] RED Phase 2 (ORM): cron + wizard dry-run/commit + FR-017 gate + empty-ICP exit | T015,T016,T017 | RED | `test_phase2_catalog_orchestrator_orm.py` + `test_phase2_catalog_gdrive_fetcher_orm.py` |
| T020 | [X] GREEN | T019 | GREEN | Part of 24 Phase-2 ORM post-tests, 0 failed (verified 2026-05-28) |
| T021 | [X] Review + Verify + Commit | T020 | Review→Land | Orchestrator method shipped `P-HUB-XLS-CRON orchestrator` 03881e201d7 |

---

## Slice P-HUB-IMAGES — Image Download from Excel "Image 1/2" Columns

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T022 | [X-partial] image downloader (`services/excel_catalog_image_downloader.py`) — content kind detection + content-hash SHA-256 idempotency + persist to `product.template.image_1920` (Image 1) | P-HUB-XLS-INGEST ✓ | GREEN | Shipped `P-HUB-IMAGES MVP` a783d63cf2d (filename drift). **Image 2 / `product.image` One2many deferred** — no `product.image` model in Odoo 19 CE (same constraint as P-PUB-IMAGES option B) |
| T023 | [X] Wire image download into ingest pass — image failure emits warning/error line, doesn't roll back product upsert | T022 | GREEN | Image failure ≠ row failure |
| T024 | [X] ICP `catalog_max_images_per_run` (default 500) — per-run cap | T022 | GREEN | |
| T025 | [X] RED Phase 2 (ORM): URL/filename paths + re-download skip on unchanged hash + failure-doesn't-rollback + per-run cap | T022,T023,T024 | RED | `test_phase2_excel_image_downloader_orm.py` (mock HTTP + GDrive) |
| T026 | [X] GREEN | T025 | GREEN | Part of 24 Phase-2 ORM post-tests, 0 failed (verified 2026-05-28) |
| T027 | [X] Review + Verify + Commit | T026 | Review→Land | |

---

## Dependency Graph

```
Spec 009 P-HUB-PROD-MODEL (done)
    → P-HUB-XLS-PARSE (T001–T009)
        → P-HUB-XLS-INGEST (T010–T014)
            → P-HUB-XLS-CRON (T015–T021)
            → P-HUB-IMAGES (T022–T027)
```

Cron + Images can run in parallel after Ingest lands. Both depend on Ingest's `catalog_ingestor.upsert` API.

## Notes

- All implementation slices: Two-Phase Testing; coverage ≥ 80 % on changed lines; module installs clean.
- New models MUST ship `ir.model.access.csv` rows; UNIQUE constraints MUST be mirrored in `init()` raw SQL (memory `project_sql_constraints_drift`).
- Wizards MUST guard `action_*` methods with method-top BA-group check (memory `feedback_fr017_write_defense_in_depth`).
- RED gate: orchestrator runs tests with `--http-port=8170` (memory `feedback_odoo19_test_gotchas`).
- GDrive interactions: mock at `_build_service` level (memory `feedback_staging_gdrive_provisioning`; precedent from P2-06).
- Image downloader reuses content-hash idempotency from `everything-claude-code:content-hash-cache-pattern` skill.
