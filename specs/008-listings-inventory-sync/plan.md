# Implementation Plan: Etsy Listings & Inventory Sync (Spec 008)

- **Branch**: `feature/006-master-plan-coding` | **Date**: 2026-05-16 | **Spec**: [spec.md](spec.md)
- **Authority**: [ADR-013](../006-master-plan/adrs/ADR-013-etsy-listing-architecture.md); Spec 005 plan.md (adapter/ingestor pattern); MP006 tracker Wave 2

## Summary

Three new persistence surfaces (`etsy.listing`, `etsy.listing.product`, `product.product.etsy_listing_variant_id`) plus a 5-min cron that syncs listing metadata then variant inventory, with SKU-based drift detection. No writeback (deferred Phase 3). Split into two implementation slices.

## Technical Context

- Python 3.12+ (Odoo 19 CE); PostgreSQL 16+ via ORM.
- Etsy API v3: `GET /v3/application/shops/{shop_id}/listings`, `GET /v3/application/listings/{listing_id}/inventory`.
- Scope `listings_r` (E1 approved 2026-05-12).
- Module: `etsy_channel_api` per [ADR-003](../006-master-plan/adrs/ADR-003-module-decomposition.md); until decomposition lands, implement in `etsy_integration`.
- Cron interval: 5 min (mirrors order sync).
- Audit: `etsy.api.log` `source='listing_pull'` (Selection value already exists).

## Design Decisions (from ADR-013)

1. `etsy.listing` standalone Model (not `_inherits('product.template')`).
2. Dual-index mapping: `product.product.etsy_listing_variant_id` FK + SKU-based discovery.
3. Soft deletes (`is_active=False`) for listings and variants — never hard `unlink()`.
4. Snapshot rows are timestamped (`last_synced_at`); updated in place per variant, soft-deleted when removed upstream.
5. Owner-confirmed (2026-05-16): unmatched SKU → leave unlinked + flag (no auto-create); deactivation deferred; multi-variant vs single product → closest-SKU link only.

## Implementation Phases

### Slice 1 — P-LIST-PULL: Listing Metadata Ingestion (~3–4 weeks)

Deliverables: `models/etsy_listing.py`; `services/etsy_listing_adapter.py` (fetch + upsert + soft-delete); `data/ir_cron_*.xml` (`cron_etsy_listing_sync`); ACL CSV rows; Two-Phase tests (DB structure + ORM ingest/cron); audit via `etsy.api.log`.

### Slice 2 — P-LIST-INV-PULL: Variant Snapshot + SKU Matching + Drift (~4–5 weeks)

Deliverables: `models/etsy_listing_product.py`; `product.product.etsy_listing_variant_id` extension; `services/etsy_inventory_adapter.py` (fetch variants + SKU matching); `services/etsy_listing_drift_reporter.py`; tree/search views with drift indicators; Two-Phase tests.

### Slice 3 — P-LIST-INV-PUSH: Inventory Writeback (DEFERRED)

Entire-array-resubmit `PUT` + wizard + sandbox dry-run. Scheduled after Slice 2 acceptance.

## Testing Strategy (Two-Phase)

- **Phase 1 (DB)**: table existence, columns, UNIQUE/constraint enforcement, soft-delete semantics.
- **Phase 2 (ORM)**: adapter ingest (upsert, no overwrite of immutable fields), SKU matching edge cases (no SKU, duplicate SKU, empty `default_code`), drift-reporter outputs, cron error handling with mocked API (pattern from Spec 005 P0-15).
- Coverage ≥ 80 % on changed lines. VCR/mocked cassettes against the Spec 005 dev shop; zero writes to non-dev shops.

## Risks (carried into implementation slices)

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-L1 | Duplicate `default_code` → ambiguous SKU match | Med | Med | Warn-log per collision; document SKU-uniqueness expectation |
| R-L2 | Drift report slow on 500+ variants | Low | High | Indexes per data-model.md; security review checks query plan |
| R-L3 | Large shop initial pull hits rate limit | Low | Low | Paginate (limit=100); honour `X-RateLimit-Remaining`; audit to `etsy.api.log` |
| R-L4 | Snapshot row accumulation unbounded | Low | Low | Soft-delete bounded by listing×variant count; revisit retention > ~5k variants |

## Exit Criteria — P-LIST-SPEC (this planning slice, pure-doc)

- [x] ADR-013 written + owner sign-off (2026-05-16)
- [x] spec.md, plan.md, data-model.md, tasks.md authored
- [x] Open questions resolved + recorded (ADR-013 table; findings.md)
- [ ] Tracker P-LIST-SPEC → `done`; P-LIST-PULL / P-LIST-INV-PULL → `todo` with deps
- [ ] findings.md records the ADR-012→013 number correction + stale ADR README index
- [ ] `/learn` capture (or explicit "no new pattern")
- Two-Phase Testing N/A for this slice (no code/tests); noted in commit body.

## Cross-References

- ADR-013 (load-bearing for both implementation slices)
- ADR-007 (delegation precedent — Spec 008 deliberately takes the opposite call)
- ADR-003 (module ownership: Etsy channel module)
- Spec 005 research.md (incremental-sync pattern reused by P-LIST-PULL)
