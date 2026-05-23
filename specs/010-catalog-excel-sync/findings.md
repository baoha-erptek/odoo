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

## E2E surfacing (live)

_(none yet — implementation not started)_
