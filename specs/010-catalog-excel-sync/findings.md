# Findings — Spec 010 (Catalog Excel Recurring Sync)

## P-HUB-SPEC (planning slice) — 2026-05-23

- **Owner directive: Excel stays canonical.** Owner answer 2/4 (2026-05-23) on Master-Plan-scoping questions: catalog import is a **recurring sync** (not a one-time migration). Excel is canonical; Odoo follows. ADR-014 §3 codifies the field-level direction matrix; this spec implements the parser/ingestor end.
- **Excel file size.** `.0temp/raw/[2025] Product Catalog.xlsx` is 109 MB, 7 sheets. Streaming parse (`openpyxl read_only=True, data_only=True, keep_links=False`) keeps memory bounded; the same pattern from P2-01 (GKE tracking import wizard) handles it.
- **Sheet schema drift is the biggest practical risk.** BA hand-edits the spreadsheet; column reorders are common. R-010-2 mitigation is a per-sheet fingerprint model (`product.catalog.sheet.fingerprint`) — a promotion of the P2-01 ICP-based GKE fingerprint pattern to a Model because the multi-sheet catalog needs per-sheet granularity that ICPs cannot express cleanly. Documented in data-model.md §3.
- **Channel-applicability deviation from ADR-014 §3.** ADR-014 says "Excel 'Availability' column derives a default; Odoo overrides persist". Spec 010 first cut leaves `x_channel_applicability_ids` empty on create — operator opt-in is required. This is a *safety deviation* (avoid over-publishing on first run) documented in spec.md "Channel Scope" + tasks.md notes. Follow-up slice `P-HUB-XLS-AVAILABILITY-MAP` raised to land the auto-mapping later, after the safety cost has been observed in practice.
- **Audit table sizing.** Daily cron × per-row audit would balloon to 1M+ rows/year. Decision: persist only error rows post-upsert; success/unchanged rows are summarised in the run-level `summary_json` and counts, then deleted at commit. Tradeoff: BA loses forensic visibility on individual successful rows; the run-level summary is enough for daily ops. Documented in data-model.md §5.
- **Multi-currency pricelist seeding (US5) is intentionally a first-import-only branch.** Subsequent edits go through Odoo's pricelist UI (ADR-014 §3 reinforces this). Importer never overwrites pricelist items it didn't create. The seeded pricelist items are `noupdate=1`.
- **Coordination point with Spec 011.** New `etsy.api.log` `source` values needed for catalog ops (`catalog_import_run`, `catalog_image_download`) — to be added in Spec 011's audit-source extension slice (cleaner co-location since Spec 011 also extends the Selection for publishing). Cross-referenced in Spec 011 plan + this finding.
- **Pure-doc slice.** No code/tests; Two-Phase Testing N/A for P-HUB-SPEC. Implementation slices carry the testing burden.

## Tracker reconciliation — 2026-05-28

- **Phantom-slice drift caught during `/dispatch-slice next`** (memory gotcha #142). The dispatcher resolved "next" to `P-HUB-XLS-PARSE-SERVICE`, but verification showed the **entire 3c Excel-sync chain was already shipped 2026-05-23** while the tracker still read `doing`/`todo`. Commits: `P-HUB-XLS-PARSE-MODELS` d4e82d839cb, `P-HUB-XLS-ICP-DEFAULTS` f3c3ef9d42b, `P-HUB-XLS-PARSE-SERVICE` c7c8ef1cfad, `P-HUB-XLS-INGEST core` 29cf95eeb4a, `P-HUB-XLS-CRON orchestrator` 03881e201d7, `P-HUB-XLS-MANUAL-WIZARD` 0d9a6f3a283, `P-HUB-XLS-CRON schedule` 357ab57b178, `P-HUB-IMAGES MVP` a783d63cf2d.
- **Verification on reconcile**: `-u multichannel_hub_core --stop-after-init` exit 0; catalog tests = **8 Phase-1 DB + 24 Phase-2 ORM = 32, 0 failed / 0 error** (`TestPhase1CatalogDB`, `TestPhase1CatalogICPDB`, `TestExcelCatalogParserORM`, `TestCatalogIngestorORM`, `TestCatalogOrchestratorORM`, `TestCatalogGdriveFetcherORM`, `TestExcelCatalogImageDownloaderORM`).
- **Tracker + tasks.md updated** 2026-05-28: P-HUB-XLS-PARSE `doing`→`done`; P-HUB-XLS-CRON `todo`→`done`; P-HUB-IMAGES `todo`→`done`.
- **Filename drift** (planned → shipped): `catalog_image_downloader.py`→`excel_catalog_image_downloader.py`; `catalog_import_wizard.py`→`catalog_import_run_wizard.py`; `gdrive_catalog_fetcher.py`→`gdrive_uploader_helper.py` + orchestrator method. Functionally equivalent; tasks.md notes the drift.

### Residual 3c follow-ups (genuinely not shipped)

- **T011 multi-currency pricelist seed (US5)** — explicitly deferred in `catalog_ingestor.py:16`. Incremental enhancement; non-blocking.
- **T022 Image 2 / `product.image` One2many** — deferred: no `product.image` model in Odoo 19 CE (same constraint as Spec 011 P-PUB-IMAGES option B). Image 1 → `image_1920` is live; secondary-image gallery would reuse the `multichannel.product.image` mini-gallery from P-PUB-MULTI-IMAGE if needed later.
- **P-HUB-XLS-AVAILABILITY-MAP** — deferred post-MVP (auto-derive `x_channel_applicability_ids` from Excel "Availability" column); raise only if BA wants the default-derivation.

## E2E surfacing (live)

_(none yet — no live cron/wizard run captured)_
