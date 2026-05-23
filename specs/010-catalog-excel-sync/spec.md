# Feature Specification: Catalog Excel Recurring Sync (Spec 010)

- **Feature Branch**: work lands on `feature/006-master-plan-coding` (Master Plan 006 Phase 3)
- **Created**: 2026-05-23
- **Status**: PLANNED — planning slice (P-HUB-SPEC) authoring; implementation slices `todo`
- **Authority**: [ADR-014](../006-master-plan/adrs/ADR-014-central-product-hub.md) §3 (sync direction matrix)
- **Input**: MP006 tracker Phase 3 (new); plan file `.claude/plans/actually-need-to-check-polymorphic-crayon.md`

## Overview

Recurring sync of `.0temp/raw/[2025] Product Catalog.xlsx` (109 MB, 7 sheets) into `product.template`. Excel stays canonical for now (owner answer 2/4 on 2026-05-23). Odoo follows. The conflict-resolution rules per ADR-014 §3 are codified in the ingestor.

Sheets:
- Accessories, Pet, Apparel, Drinkware, Home Decor → product rows
- Combo → bundle rows (mapping deferred — see findings.md "Open items")
- Các chi phí khác ("Other costs") → per-product `x_additional_cost` overrides

**This spec depends on Spec 009 landing** (model + fields it writes into).

Out of scope:
- Bidirectional sync back to Excel (Odoo→Excel) → never; Excel is canonical.
- Combo-sheet modelling decision (bundle product vs separate model) → deferred to Spec 009 plan addendum or follow-up slice; ingestor records combo rows in staging but does not yet write them to product domain.
- Image hosting beyond what's referenced in Excel "Image 1/2" columns → see P-HUB-IMAGES contract below.
- Etsy publishing of imported products → Spec 011.

## User Scenarios & Acceptance Criteria

### US1 — Daily Recurring Sync (P1)

As a BA, I want overnight Excel changes reflected in Odoo by morning.

**Acceptance Criteria**
1. `cron_catalog_excel_sync` runs daily (default 02:00 UTC; configurable via `ir.config_parameter`).
2. Sync reads the Excel from GDrive (primary) or local mount (fallback) per ADR-006 §6 pattern.
3. Each cron run creates one `product.catalog.import.run` row with start/end/sheets/rows/upserts/errors metrics.
4. A new product (SKU not yet in Odoo) creates a new `product.template`.
5. An existing product is upserted: only fields tagged "Excel wins" per ADR-014 §3 are overwritten; others (notably `x_channel_applicability_ids`) preserved.
6. A row in Excel that is *gone* (SKU removed) is **not** auto-archived — flagged in the run report; archival is operator action.

### US2 — Manual Run Wizard (P1)

As a BA, I want to fire a sync on-demand after editing the spreadsheet.

**Acceptance Criteria**
1. `catalog.import.wizard` (BA-gated, FR-017) lets operator pick an upload path (GDrive folder or local upload) and a dry-run flag.
2. Dry-run mode parses the file and emits a `product.catalog.import.run` report **without** writing any `product.template`.
3. Commit mode writes the products; same audit row but with `mode='commit'`.
4. The wizard pre-flight refuses files larger than `multichannel_hub.large_file_threshold_bytes × 20` (default 200 MB) — the Excel is 109 MB and growing; oversize files indicate a parse-not-import bug.

### US3 — Per-Sheet Error Surfacing (P1)

As a BA, I want to see which rows failed and why, so I can fix Excel and re-run.

**Acceptance Criteria**
1. Hard parse errors (missing required columns, malformed price cell, file unreadable) populate `product.catalog.import.line.state='error'` with `error_message`.
2. Non-canonical SKUs are NOT errors — they ingest fine; their `x_sku_v2_status` lands as `non_canonical` per Spec 009 (ADR-014 §4 policy).
3. The run report groups errors by sheet + error kind, with row numbers from the source Excel.
4. Re-running the same Excel re-attempts the failed lines; previously-succeeded lines upsert idempotently.

### US4 — Image Source Handling (P1)

As a BA, I want product images uploaded from the Excel "Image 1/2" columns.

**Acceptance Criteria**
1. The ingestor detects per-cell content kind: GDrive URL / HTTPS URL / filename in a shared Drive folder.
2. Images are downloaded once per content hash (reuse `etsy_integration/services/image_downloader.py` pattern + GDrive plumbing from P1-09 / P2-06).
3. Downloaded images attach to `product.template.image_1920` (Image 1 = main) + `product.image` One2many (Image 2 = secondary).
4. A re-run with unchanged image references does NOT re-download (content-hash idempotency).
5. Image download failures do NOT block the row's product upsert — they emit a warning + an error line with `error_kind='image_download'` so the catalog data still lands.

### US5 — Multi-Currency Pricelist Seeding (P2)

As a BA, I want the Excel USD / EU / CAD / VND columns to seed default per-currency pricelists on first import.

**Acceptance Criteria**
1. On the **first** import of a product (no prior `product.template` row), the four currency columns seed four `product.pricelist.item` rows (one per currency).
2. On subsequent imports, the pricelist items are NOT overwritten — operator manages pricelists in Odoo (ADR-014 §3).
3. If a currency column is empty for a row, no pricelist item is created for that currency.
4. The seeded pricelists are named `Catalog Default {CURRENCY}` and `noupdate=1`-protected.

## Channel Scope

Channel-agnostic. The catalog populates `product.template` regardless of which channel will later publish. `x_channel_applicability_ids` is **not** derived from the Excel "Availability" column by default (would over-publish on first run); instead the column suggests defaults that BA accepts per-row via a future "Confirm channel applicability" wizard. Until that wizard lands, `x_channel_applicability_ids` is set by operator on the product form.

> **Deviation note**: ADR-014 §3 says "Excel 'Availability' column derives a default; Odoo overrides persist". For safety, the first cut of the importer leaves `x_channel_applicability_ids` empty on create; operator opt-in is required. The ADR-014-promised default-derivation lands in a follow-up slice (`P-HUB-XLS-AVAILABILITY-MAP`).

## Dependencies

- ADR-014 accepted.
- Spec 009 P-HUB-PROD-MODEL landed (the model the importer writes into).
- GDrive service account configured (E3 ✓ done 2026-04-27; reused per P1-09 / P2-06 pattern; memory `feedback_staging_gdrive_provisioning`).
- openpyxl available in the container (already declared in `multichannel_hub_fulfillment/__manifest__.py` since Spec 004a P2-01).

## Non-Functional Requirements

- Full import of 7 sheets × ~500 rows each completes in ≤ 15 min on staging container.
- Streaming parse: openpyxl `read_only=True, data_only=True, keep_links=False` to keep memory bounded under 1 GB despite the 109 MB file size.
- Per-sheet checkpoint: a failed sheet does not roll back successful sheets (per-sheet savepoint).
- No N+1 product lookups: batch `product.template.search([('default_code', 'in', skus)])` once per sheet before upsert loop.
- Audit row per run; per-line row for errors only (success lines do not bloat the audit table; row count = errors-only).
