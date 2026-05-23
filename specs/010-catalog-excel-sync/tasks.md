# Tasks: Catalog Excel Recurring Sync (Spec 010)

Dependency-ordered, slice-specific. Four implementation slices, all in `multichannel_hub_core`. Each runs the MP006 9-phase loop and Two-Phase Testing.

Status legend: `[ ]` todo · `[~]` doing · `[X]` done.

**All slices depend on Spec 009 P-HUB-PROD-MODEL landing.**

---

## Slice P-HUB-XLS-PARSE — openpyxl Parser + Staging

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T001 | Finalize `product.catalog.import.run` / `import.line` / `sheet.fingerprint` schemas in data-model.md | Spec 009 ✓ | plan | |
| T002 | `models/product_catalog_import_run.py` + `models/product_catalog_import_line.py` + `models/product_catalog_sheet_fingerprint.py` + sequence + `init()` raw-SQL mirrors for C-CIL-001 + C-CSF-001 | T001 | GREEN | `pg_constraint IF NOT EXISTS` pre-check |
| T003 | `services/excel_catalog_parser.py` — openpyxl `read_only=True, data_only=True, keep_links=False`; per-sheet header fingerprint compute; column → field mapping table; row → `import.line` emission; advisory grammar v2 status compute (calls `sku_grammar_v2.evaluate`) | T002, Spec 009 services/sku_grammar_v2.py ✓ | GREEN | Streaming, per-sheet savepoint |
| T004 | `data/product_catalog_sheet_map.xml` (or Python constants module) — sheet→category, header→field maps; commit a 5-row-per-sheet fixture xlsx for tests | T003 | GREEN | Fixture small (KB), not the 109 MB real file |
| T005 | `security/ir.model.access.csv` — 3 rows | T002 | GREEN | |
| T006 | RED Phase 1 (DB): tables, UNIQUE mirrors, indexes | T001 | RED | Register in `tests/__init__.py` |
| T007 | RED Phase 2 (ORM): parser truth table per sheet (using fixture); error row emission on missing column / malformed price / unreadable; non-canonical SKU advisory flag set but no error; oversize file rejected (`catalog_excel_max_mb`) | T003,T004 | RED | `--http-port=8170` |
| T008 | GREEN | T006,T007 | GREEN | |
| T009 | Review + Verify + Commit | T008 | Review→Land | code-reviewer + security-reviewer parallel |

---

## Slice P-HUB-XLS-INGEST — Upsert + Conflict Matrix + Pricelist Seed

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T010 | `services/catalog_ingestor.py` — `upsert(env, run, lines)` batches `product.template.search` once per sheet; applies ADR-014 §3 conflict matrix per field; per-row savepoint; emits error line on per-row failure | P-HUB-XLS-PARSE ✓ | GREEN | No N+1; first-import detection via search-miss |
| T011 | Multi-currency pricelist seed helper (US5) — `_seed_pricelist_items_first_import(env, product, line)` writes 1 item per non-empty currency column; idempotent (no overwrite); seeded pricelists `noupdate=1` | T010 | GREEN | First-import branch only |
| T012 | RED Phase 2 (ORM): upsert new row creates template; existing row preserves `x_channel_applicability_ids`; Excel-wins fields overwrite; missing-from-Excel row flagged but not archived; first-import seeds pricelist items; second import preserves items; per-row failure rolls back row only (other rows succeed) | T010,T011 | RED | `--http-port=8170` |
| T013 | GREEN | T012 | GREEN | |
| T014 | Review + Verify + Commit | T013 | Review→Land | |

---

## Slice P-HUB-XLS-CRON — Cron + Wizard + Run Report View

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T015 | `wizards/catalog_import_wizard.py` — file picker (GDrive folder ID or local upload base64) + dry-run flag + `_check_ba_or_raise()` + `action_preview` / `action_commit` | P-HUB-XLS-INGEST ✓ | GREEN | FR-017 22nd confirmation: gate before parse+upsert |
| T016 | `data/ir_cron_catalog_excel_sync.xml` — daily 02:00 UTC; gated on ICP `multichannel_hub_core.catalog_excel_source` non-empty | T015 | GREEN | If ICP empty, cron logs warning and exits 0 |
| T017 | `services/gdrive_catalog_fetcher.py` — reads ICP `catalog_excel_source` (folder ID); picks newest .xlsx via GDrive list_files; downloads to temp path; passes to parser+ingestor; cleans up | T015, P2-06 GDrive plumbing ✓ | GREEN | Reuses GdriveUploader extended in P2-06 |
| T018 | Run report view — tree + form on `product.catalog.import.run` with smart button to error `line_ids` | T015 | GREEN | |
| T019 | RED Phase 2 (ORM): cron picks newest Excel from GDrive folder (mocked); manual-run wizard dry-run writes no products; manual-run wizard commit-mode writes products; FR-017 gate refuses non-BA; cron with empty ICP logs+exits | T015,T016,T017 | RED | Mock `GdriveUploader._build_service` per P2-06 pattern |
| T020 | GREEN | T019 | GREEN | |
| T021 | Review + Verify + Commit | T020 | Review→Land | |

---

## Slice P-HUB-IMAGES — Image Download from Excel "Image 1/2" Columns

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T022 | `services/catalog_image_downloader.py` — detect content kind (GDrive URL / HTTPS URL / filename); content-hash SHA-256 on bytes for idempotency; persist to `product.template.image_1920` (Image 1) + `product.image` One2many (Image 2); reuse `etsy_integration/services/image_downloader.py` patterns | P-HUB-XLS-INGEST ✓ | GREEN | TokenBucket throttle (2/sec, burst 10) |
| T023 | Wire image download into ingest pass — emit warning + error line on download failure, but don't roll back the row's product upsert | T022 | GREEN | Image failure ≠ row failure |
| T024 | ICP `multichannel_hub_core.catalog_max_images_per_run` (default 500) — cron cap to avoid quota burn | T022 | GREEN | |
| T025 | RED Phase 2 (ORM): GDrive URL → download; HTTPS URL → download; filename → resolve in configured folder; re-download skipped on unchanged content hash; download failure emits warning + error line without rolling back product upsert; per-run cap honored | T022,T023,T024 | RED | Mock HTTP + GDrive |
| T026 | GREEN | T025 | GREEN | |
| T027 | Review + Verify + Commit | T026 | Review→Land | |

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
