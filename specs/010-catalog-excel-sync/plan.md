# Implementation Plan: Catalog Excel Recurring Sync (Spec 010)

- **Branch**: `feature/006-master-plan-coding` | **Date**: 2026-05-23 | **Spec**: [spec.md](spec.md)
- **Authority**: [ADR-014](../006-master-plan/adrs/ADR-014-central-product-hub.md) §3

## Summary

Four implementation slices, all under `multichannel_hub_core`:

| Slice | Delivers |
|---|---|
| **P-HUB-XLS-PARSE** | openpyxl streaming parser → staging records `product.catalog.import.line`; per-sheet schema mapping; SKU grammar v2 advisory check |
| **P-HUB-XLS-INGEST** | Upsert from staging → `product.template`; ADR-014 §3 conflict matrix; multi-currency pricelist seed |
| **P-HUB-XLS-CRON** | Daily cron + manual wizard; GDrive primary / local fallback; run report |
| **P-HUB-IMAGES** | Image download from Excel "Image 1/2" columns; content-hash idempotency; error-tolerant |

## Technical Context

- Python 3.12+ (Odoo 19 CE); PostgreSQL 16+ via ORM.
- Module: `multichannel_hub_core` (channel-agnostic).
- Reuses: GDrive plumbing from P1-09 / P2-06 (GdriveUploader.list_files/download_file with Shared-Drive flags); openpyxl streaming pattern from P2-01 (`tracking.import.wizard`); image downloader from `etsy_integration/services/image_downloader.py`; rate limiter `multichannel_hub_core/utils/rate_limiter.py` (token bucket for image-download throughput).
- Coordinates with: Spec 009 (writes into `product.template`); Spec 011 (downstream consumer of the populated catalog).

## Design Decisions

1. **Staging-table pattern.** Per-row staging records (`product.catalog.import.line`) are written first; the upsert pass is a separate transaction. Same pattern as P2-01 `tracking.import.line` for replayability and error isolation.
2. **Per-sheet savepoint.** A parse failure on sheet 4 does not roll back sheets 1–3.
3. **Idempotent re-runs.** Same Excel re-ingested yields the same result; content-hash on image refs prevents re-download.
4. **Excel "Availability" column is NOT auto-mapped to `x_channel_applicability_ids` in this spec.** Default is empty on create; operator opt-in via the product form. The auto-mapping ADR-014 §3 promises is a follow-up slice (`P-HUB-XLS-AVAILABILITY-MAP`, deferred — see spec.md "Channel Scope" deviation note).
5. **Successful rows do NOT persist a per-line audit row** to keep the audit table small. Only error rows persist. The run-level summary holds the full counts.
6. **First-import vs subsequent-import branching is detected per row by the existence of `product.template` with that `default_code`.** No global "first import ever" flag; each new SKU triggers its own pricelist seed for that SKU's currency columns.

## Implementation Phases

### Slice P-HUB-XLS-PARSE — Parser + Staging (~2 weeks)

Deliverables:
- `models/product_catalog_import_run.py` — header model (start/end/sheet counts/upsert counts/error counts/source path).
- `models/product_catalog_import_line.py` — per-row staging (only error rows persist after upsert; pre-upsert all rows persist transiently then most are cleared).
- `services/excel_catalog_parser.py` — openpyxl streaming; per-sheet column mapping (LINE SP / Order / Product / Availability / SKU / Image 1 / Image 2 / Dimensions / Description / Price USD / Price EU / Price CAD / Price VND / Shipping Fees); validates required columns; emits parse error per-cell with row number.
- `data/product_catalog_sheet_map.xml` (or Python constants) — sheet name → category mapping + column header → field mapping.
- ACL CSV rows.
- Two-Phase tests: parser truth table per sheet against a small fixture file (committed; 5–10 rows per sheet); error row emission; SKU grammar v2 advisory status correctly populated.

### Slice P-HUB-XLS-INGEST — Upsert + Conflict Matrix (~2 weeks)

Deliverables:
- `services/catalog_ingestor.py` — `upsert(env, run, lines)` batches `product.template.search` once per sheet, applies ADR-014 §3 conflict matrix per field, emits per-line error if upsert fails (rolled back per row).
- Multi-currency pricelist seed (US5) — first-import branch.
- Two-Phase tests: upsert new row creates template; upsert existing row preserves `x_channel_applicability_ids` (Odoo-override-wins); Excel-wins fields overwrite; missing-from-Excel row flagged but not archived; first-import seeds pricelist items, second import preserves; row-level error rolls back row only.

### Slice P-HUB-XLS-CRON — Cron + Wizard (~1 week)

Deliverables:
- `wizards/catalog_import_wizard.py` — file picker (GDrive folder ID or local path) + dry-run flag + FR-017 BA-group gate.
- `data/ir_cron_catalog_excel_sync.xml` — daily 02:00 UTC; reads ICP `multichannel_hub_core.catalog_excel_source` (GDrive folder ID for the catalog).
- Run report view (tree + form on `product.catalog.import.run`).
- Two-Phase tests: cron picks newest Excel from GDrive folder; manual-run wizard dry-run writes no products; manual-run wizard commit-mode writes products; FR-017 gate refuses non-BA.

### Slice P-HUB-IMAGES — Image Download (~1 week)

Deliverables:
- `services/catalog_image_downloader.py` — extends `etsy_integration/services/image_downloader.py` pattern; handles GDrive URL / HTTPS URL / filename; content-hash idempotency via SHA-256 on download bytes; persists to `product.template.image_1920` + `product.image` One2many.
- Token bucket throttle (`TokenBucket(rate=2, burst=10)`) to avoid swamping GDrive API + HTTPS targets.
- Two-Phase tests: GDrive URL path; HTTPS URL path; filename-in-folder path; re-download skip on unchanged hash; download failure emits warning + error line but row's product still upserts.

## Testing Strategy (Two-Phase)

- **Phase 1 (DB)**: tables exist, columns, indexes, ACL.
- **Phase 2 (ORM)**: parser truth tables (small fixture xlsx, committed); ingest conflict matrix; cron + wizard happy paths + FR-017 gate; image idempotency.
- Mock GDrive API at `GdriveUploader._build_service` level (per P2-06 pattern); never hit real Drive in CI.
- Use openpyxl `read_only=True` in tests too; ensures memory characteristics match production.
- Run with `--http-port=8170`; register all test files in `tests/__init__.py`.
- Coverage ≥ 80 % on changed lines.

## Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-010-1 | 109 MB Excel parse exceeds cron memory budget | Med | Med | Streaming `read_only=True, keep_links=False`; per-sheet checkpoint; sheet-by-sheet sequential parse (not parallel); ICP `multichannel_hub_core.catalog_excel_max_mb` (default 200) refuses oversized files |
| R-010-2 | Sheet column order / header text drifts between Excel revisions | High | High | Schema fingerprint per sheet (column header SHA-256); compare to a whitelist (similar to P2-01 GKE schema fingerprint); hard-fail on unknown schema; admin appends new fingerprint via wizard approval step |
| R-010-3 | BA copies a row in Excel and ends up with a duplicate SKU | Med | Med | Parser groups by SKU; emits an error line per duplicate; ingest writes the first occurrence only and flags the rest |
| R-010-4 | Cron silently fails (GDrive permission revoked, file moved) | Low | High | Run report row with empty rows-parsed flags it as an alert; sync.health row optional (when `etsy.sync.health` present); operator notification deferred (no email pipe in MP006) |
| R-010-5 | First-import pricelist seed creates rows BA didn't expect | Low | Low | `noupdate=1` on seeded pricelist items; documented in run report; operator can disable seed via wizard flag |
| R-010-6 | Image downloads burn GDrive API quota | Med | Med | Content-hash skip; token-bucket throttle; per-run cap (`max_images_per_run` ICP, default 500) |
| R-010-7 | Excel "Availability" column intended to drive channel applicability but spec defers it (deviation from ADR-014 §3) | Med | Low | Documented in spec.md "Channel Scope" + this row; follow-up slice `P-HUB-XLS-AVAILABILITY-MAP` raised |

## Exit Criteria — P-HUB-SPEC (planning) cross-references

This spec's exit criteria are tracked under Spec 009 P-HUB-SPEC since they're all-or-nothing on the planning slice. The implementation-slice exits are per-slice in tasks.md.

## Cross-References

- ADR-014 (sync direction matrix is load-bearing)
- Spec 009 plan.md (data model that this spec writes into)
- Spec 011 plan.md (downstream consumer)
- P2-01 `tracking.import.wizard` (precedent for openpyxl + staging pattern + FR-017 gate)
- P2-06 `logistics.inbox.poller` (precedent for GDrive primary + cron pattern)
- Memory `feedback_staging_gdrive_provisioning` (Shared Drive flags, container googleapiclient install)
