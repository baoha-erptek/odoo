# Data Model: Catalog Excel Recurring Sync (Spec 010)

- **Date**: 2026-05-23 | **Spec**: [spec.md](spec.md) | **ADR**: [ADR-014](../006-master-plan/adrs/ADR-014-central-product-hub.md) §3

## Entity Overview

| Entity | Status | Module | Description |
|---|---|---|---|
| `product.catalog.import.run` | NEW | `multichannel_hub_core` | Per-cron-run / per-wizard-run audit header |
| `product.catalog.import.line` | NEW | `multichannel_hub_core` | Per-row staging (transient before upsert; persisted only for error rows post-upsert) |
| `product.catalog.sheet.fingerprint` | NEW | `multichannel_hub_core` | Schema fingerprint per known sheet — admin-approved whitelist (R-010-2 mitigation) |
| `product.template` | EXTENDED (Spec 009) | — | This spec writes into the fields Spec 009 adds; no further schema change here |

---

## 1. `product.catalog.import.run` (NEW)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `name` | Char | Yes | sequence | `CAT-IMP-YYMMDD-NNNN`-style sequence; indexed |
| `start_at` | Datetime | Yes | `now()` | When parse began |
| `end_at` | Datetime | No | — | When upsert finished or aborted |
| `state` | Selection | Yes | `parsing` | `parsing` / `previewed` (dry-run only) / `imported` / `error` / `cancelled` |
| `mode` | Selection | Yes | — | `dry_run` / `commit` |
| `source_kind` | Selection | Yes | — | `gdrive` / `local` / `manual_upload` |
| `source_path` | Char | Yes | — | GDrive file ID or local path |
| `file_size_bytes` | Integer | No | — | For audit |
| `sheets_parsed` | Integer | Yes | 0 | Count of sheets successfully parsed |
| `rows_total` | Integer | Yes | 0 | Sum across all sheets |
| `rows_upserted` | Integer | Yes | 0 | New + updated |
| `rows_unchanged` | Integer | Yes | 0 | No diff against existing template |
| `rows_error` | Integer | Yes | 0 | |
| `images_downloaded` | Integer | Yes | 0 | |
| `images_skipped_unchanged` | Integer | Yes | 0 | |
| `images_failed` | Integer | Yes | 0 | |
| `triggered_by` | Many2one(`res.users`) | No | — | Wizard runs only; cron leaves NULL |
| `summary_json` | Text (JSON) | No | — | Per-sheet breakdown for the run report |
| `line_ids` | One2many(`product.catalog.import.line`, `run_id`) | — | — | Error lines only (success lines cleared on commit) |

**ACL**: read `base.group_user`; write `base.group_system` (cron + sudoed wizard).

**Indexes**: `(start_at DESC)` for run report; `(state, mode)`.

---

## 2. `product.catalog.import.line` (NEW)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `run_id` | Many2one(`product.catalog.import.run`) | Yes | — | `ondelete='cascade'`; indexed |
| `sheet_name` | Char | Yes | — | e.g. "Accessories" |
| `row_number` | Integer | Yes | — | 1-based row index in source sheet |
| `sku` | Char | No | — | From Excel SKU column; indexed |
| `name` | Char | No | — | From Excel Product column |
| `availability` | Char | No | — | From Excel Availability column (advisory; see Channel Scope deviation) |
| `price_usd` | Float | No | — | |
| `price_eu` | Float | No | — | |
| `price_cad` | Float | No | — | |
| `price_vnd` | Float | No | — | |
| `shipping_fee` | Float | No | — | |
| `image_1_ref` | Char | No | — | Raw cell content (GDrive URL / HTTPS URL / filename) |
| `image_2_ref` | Char | No | — | Same |
| `state` | Selection | Yes | `pending` | `pending` / `upserted` / `unchanged` / `error` |
| `error_kind` | Selection | No | — | `parse` / `validation` / `upsert` / `image_download` / `duplicate_sku` |
| `error_message` | Text | No | — | Human-readable; max 4 KB |
| `target_product_id` | Many2one(`product.template`) | No | — | Set when row maps to existing template; useful for replay |
| `suggested_sku` | Char | No | — | Grammar v2 advisory (informational; ingest does NOT use this to write `default_code`) |
| `sku_v2_status` | Selection | No | — | `matches` / `non_canonical` / `msc_catchall` (advisory) |

**Constraints**
- C-CIL-001: UNIQUE `(run_id, sheet_name, row_number)`. Mirror via `init()` raw SQL with `pg_constraint IF NOT EXISTS`.

**ACL**: read `base.group_user`; write `base.group_system`.

**Indexes**: `(run_id, state)` for error-row filter; `(sku)` for de-duplication scan; `(state, error_kind)` for run report grouping.

**Lifecycle**: rows are written transiently during parse; on commit, rows where `state in ('upserted', 'unchanged')` are deleted at the end of the run (volume control); error rows persist forever for BA review.

---

## 3. `product.catalog.sheet.fingerprint` (NEW — R-010-2 mitigation)

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `sheet_name` | Char | Yes | — | e.g. "Accessories"; indexed |
| `column_headers_sha256` | Char | Yes | — | SHA-256 of the comma-joined header row (lower-cased + stripped) |
| `column_headers_preview` | Text | Yes | — | The raw header row for human review |
| `approved` | Boolean | Yes | False | Admin approval flag |
| `approved_by` | Many2one(`res.users`) | No | — | |
| `approved_at` | Datetime | No | — | |
| `first_seen_at` | Datetime | Yes | `now()` | |
| `last_seen_at` | Datetime | Yes | `now()` | |

**Constraints**
- C-CSF-001: UNIQUE `(sheet_name, column_headers_sha256)`. Mirror in `init()`.

**ACL**: read `base.group_user`; write `base.group_system`; approval action via BA-manager wizard gate.

**Behaviour**: at parse time, compute the header fingerprint per sheet. If `approved=False` (new fingerprint or revoked), the parser refuses the run with a clear error and writes a `product.catalog.import.run` row in state `error` with a pointer to the unapproved fingerprint. Admin reviews + approves via a wizard. Same defense-in-depth pattern as P2-01 GKE schema fingerprint (`multichannel_hub_fulfillment.gke_schema_hashes` ICP), promoted to a model because the multi-sheet catalog needs per-sheet granularity.

---

## 4. Computed / Sequenced

```python
# Sequence for run.name — registered in ir_sequence_data.xml
# Prefix CAT-IMP-, %(y)s%(month)s%(day)s, 4-digit padding

# product.catalog.import.run summary_json structure (informal):
{
  "Accessories": {"rows": 245, "upserted": 240, "unchanged": 3, "error": 2},
  "Pet":         {"rows": 87,  "upserted": 87,  "unchanged": 0, "error": 0},
  ...
}
```

---

## 5. Rationale Notes

- **Why a sheet fingerprint model and not just an ICP?** P2-01 uses an ICP list of approved fingerprints for a single GKE Excel; the catalog has 7 sheets with independent schemas. A model lets the admin approve one sheet at a time, see when each fingerprint was first seen, and revoke approval. ICP would either bundle all 7 into one JSON (brittle) or use 7 ICPs (awkward).
- **Why delete success rows on commit?** A daily cron writes ~3000 rows × N runs; over a year that's 1M+ audit rows of mostly noise. Errors persist for BA review (the actionable subset); successes are summarised in the run-level counts and `summary_json`. If a forensic need arises later, the cron writes to `etsy.api.log` `source='catalog_import_*'` (audit source values added in Spec 011's audit-source extension — coordination point).
- **Why is `target_product_id` on the line?** Replay: BA fixes one row in Excel, the cron re-ingests, and the line shows which template it acted on. Also useful for the "row was matched to template T but Excel SKU drifted" forensic case.
- **Why no `mail.thread` on the run model?** Audit volume; chatter overhead unjustified at one-row-per-day cadence × multi-year retention.
