# Tasks: Etsy Listings & Inventory Sync (Spec 008)

Dependency-ordered, slice-specific. Two implementation slices; Slice 3 deferred. Each implementation slice runs the MP006 9-phase loop and Two-Phase Testing.

Status legend: `[ ]` todo · `[~]` doing · `[X]` done.

---

## Slice 1 — P-LIST-PULL (Listing Metadata Ingestion)

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T001 | Finalize `etsy.listing` fields/constraints/indexes in data-model.md | — | plan | Source of truth = data-model.md §1 |
| T002 | `models/etsy_listing.py`: model + computed `variant_count`/`unlinked_variant_count`/`drift_status` + `init()` C-LIST-001 raw-SQL UNIQUE mirror | T001 | GREEN | `pg_constraint IF NOT EXISTS` pre-check (project_sql_constraints_drift) |
| T003 | `security/ir.model.access.csv`: `etsy.listing` read group_user / write group_system | T002 | GREEN | ACL mandatory for new model |
| T004 | `services/etsy_listing_adapter.py`: `fetch_listings(shop, limit=100, min_last_modified)` (paginated) + `ingest(shop, payload)` upsert (immutable `url`/`created_at`) + soft-delete missing | T002 | GREEN | Reuse Spec 005 incremental-sync pattern |
| T005 | `data/ir_cron_etsy_listing_sync.xml`: 5-min cron → `etsy.listing._cron_sync_listings()` | T004 | GREEN | Audit each call to `etsy.api.log` `source='listing_pull'` |
| T006 | RED Phase 1 (DB): table/columns, C-LIST-001 UNIQUE, soft-delete semantics | T001 | RED | Register file in `tests/__init__.py` (tdd-guide gap) |
| T007 | RED Phase 2 (ORM): `ingest()` upsert + immutability + state→deleted; cron error→audit (mocked API) | T004,T005 | RED | Run with `--http-port=8170` (port-8169 gotcha) |
| T008 | GREEN: make T006/T007 pass | T006,T007 | GREEN | Min implementation |
| T009 | Review: code-reviewer + security-reviewer in parallel | T008 | Review | Block on CRITICAL/HIGH; verify diff with `git diff --stat` before applying findings |
| T010 | Verify: `-u etsy_integration --stop-after-init` exit 0; `--test-tags` green; ruff; grep `_logger.info`/`print(` | T009 | Verify | |
| T011 | Commit (conventional, cite T001–T010); tracker P-LIST-PULL → done; findings.md surprises; `/learn` | T010 | Land | |

**Exit (P-LIST-PULL)**: all `[X]`; tests pass ≥80% changed lines; module installs clean; ACL present; constraint mirrored in `init()`; tracker + findings updated; `/learn` captured.

---

## Slice 2 — P-LIST-INV-PULL (Variant Snapshot + SKU Matching + Drift)

| ID | Task | Depends | Phase | Notes |
|---|---|---|---|---|
| T012 | Finalize `etsy.listing.product` + `product.product.etsy_listing_variant_id` in data-model.md | P-LIST-PULL done | plan | data-model.md §2/§3 |
| T013 | `models/etsy_listing_product.py`: model + computed `odoo_qty`/`qty_drift` + C-LPROD-002 `@api.constrains` + `init()` C-LPROD-001 raw-SQL UNIQUE mirror | T012 | GREEN | `pg_constraint IF NOT EXISTS` pre-check |
| T014 | Extend `models/product_product.py`: add `etsy_listing_variant_id` Many2one (`ondelete='set null'`, indexed) | T012 | GREEN | No existing-ACL change |
| T015 | `security/ir.model.access.csv`: `etsy.listing.product` read group_user / write group_system | T013 | GREEN | |
| T016 | `services/etsy_inventory_adapter.py`: `fetch_variants(listing)` + `ingest_variants(listing, payload)` with soft-delete of removed variants | T013 | GREEN | |
| T017 | SKU matching in `ingest_variants`: search `product.product` by `(company_id, default_code==sku)`; set FK if single match; **closest-match-only** for multi-variant vs single product (ADR-013 Q-c); warn-log duplicate `default_code` (R-L1); never overwrite manual FK; skip empty sku/default_code | T016 | GREEN | ADR-013 Q-a: no auto-create |
| T018 | `services/etsy_listing_drift_reporter.py`: `get_unlinked_variants` / `get_qty_drifts` / `get_orphan_products` (indexed queries) | T017 | GREEN | NFR < 2 s @ 500 variants |
| T019 | Views: tree/search on `etsy.listing.product` — sku, quantity, odoo_qty, qty_drift, product_id, drift filters/decorations | T018 | GREEN | |
| T020 | RED Phase 1 (DB): variant table/columns, C-LPROD-001 UNIQUE, FK `set null`, soft-delete | T012 | RED | Register in `tests/__init__.py` |
| T021 | RED Phase 2 (ORM): ingest_variants; SKU match edge cases (no sku, dup default_code, empty default_code, manual-link-preserved, closest-only); drift reporter outputs | T016,T017,T018 | RED | `--http-port=8170` |
| T022 | GREEN: make T020/T021 pass | T020,T021 | GREEN | |
| T023 | Review: code-reviewer + security-reviewer parallel (esp. drift-report query plan / N+1) | T022 | Review | |
| T024 | Verify: `-u etsy_integration --stop-after-init` exit 0; `--test-tags` green; ruff; debug-stmt grep; drift-report query-plan < 2 s @ 500 | T023 | Verify | |
| T025 | Commit; tracker P-LIST-INV-PULL → done **and** P-LIST-SPEC remains done; findings.md; `/learn` | T024 | Land | |

**Exit (P-LIST-INV-PULL)**: all `[X]`; tests ≥80% changed lines; module installs clean; ACL present; constraints mirrored in `init()`; drift report meets < 2 s NFR; tracker + findings updated; `/learn` captured.

---

## Slice 3 — P-LIST-INV-PUSH (Inventory Writeback) — DEFERRED

Reserved T026–T040. Entire-array-resubmit `PUT /v3/application/listings/{id}/inventory`, rate-limit aware, audit `source='listing_push'`, sandbox dry-run, wizard. Dispatch after Slice 2 acceptance + E2E sign-off.

---

## Dependency Graph

```
P-LIST-SPEC (done) → P-LIST-PULL (T001→T011) → P-LIST-INV-PULL (T012→T025) → P-LIST-INV-PUSH (deferred)
```

## Notes

- All implementation slices: Two-Phase Testing; coverage ≥ 80 % changed lines; module installs clean.
- New models MUST ship `ir.model.access.csv` rows; UNIQUE constraints MUST be mirrored in `init()` raw SQL with a `pg_constraint IF NOT EXISTS` pre-check (this codebase never deploys `_sql_constraints` — canonical template in `etsy_integration` `design_file.py`).
- RED gate: orchestrator runs `--test-tags` itself with `--http-port=8170` and reads the failure tail (tdd-guide "RED confirmed by inspection" gap; in-container port-8169-in-use is silent).
- Reviewer findings about diff bloat must be verified with `git diff --stat HEAD` before acting (reviewer diff-hallucination precedent).
