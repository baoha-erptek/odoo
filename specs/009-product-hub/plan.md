# Implementation Plan: Central Product Hub (Spec 009)

- **Branch**: `feature/006-master-plan-coding` | **Date**: 2026-05-23 | **Spec**: [spec.md](spec.md)
- **Authority**: [ADR-014](../006-master-plan/adrs/ADR-014-central-product-hub.md)

## Summary

Foundation layer for MP006 Phase 3. Five implementation slices:

| Slice | Delivers |
|---|---|
| **P-HUB-PROD-MODEL** | `multichannel.sales.channel` + `product.channel.status` models + `product.template` field extensions (channel M2M, pricing bookkeeping, SKU drift trio) + ACL + seed channels |
| **P-HUB-WIZARD** | `product.creation.wizard` (operator-facing, BA-gated, non-blocking SKU drift surface) |
| **P-HUB-SKU-DRIFT** | `product.sku.canonicalise.wizard` (Keep-legacy / Accept-canonical with optional Etsy auto-push) + drift review list view + grammar v2 regex compute |
| **P-HUB-BACKFILL** | `etsy.listing.backfill.wizard` (read-only against Etsy; creates/links `product.template`; idempotent) |
| **P-HUB-STATUS-VIEW** | Product form Channels tab + smart button (state visibility; state writes are from Spec 011) |

## Technical Context

- Python 3.12+ (Odoo 19 CE); PostgreSQL 16+ via ORM.
- Module: `multichannel_hub_core` (channel-agnostic, per ADR-014 §5 + memory `feedback_channel_agnostic_groups_in_mhc`).
- Reuses: ADR-013's `etsy.listing` / `etsy.listing.product` / `product.product.etsy_listing_variant_id` (backfill source); ADR-010's `x_gearment_sku` auto-route + `product_mto_bom_wizard` (production mode derivation); SKU grammar v2 from `.0temp/deliverables/D1_product_taxonomy_SKU.xlsx` `family_rules` sheet (frozen regex list).
- Coordinates with: Spec 010 (Excel import populates these fields); Spec 011 (Etsy publisher reads `x_channel_applicability_ids` + writes `product.channel.status`).

## Design Decisions (from ADR-014)

1. Channel applicability is a Many2many on `product.template`, not `_inherits`.
2. Per-channel state lives in `product.channel.status` (One2many child), not on `product.template` directly.
3. Pricing is `product.pricelist` (channel-keyed); the three new `product.template` fields are Excel round-trip bookkeeping only.
4. SKU drift is non-blocking: `default_code` stays Etsy-visible; `x_sku_v2_suggested` is the regex output; `x_sku_v2_status` drives the backlog; `x_sku_legacy` archives after canonicalisation.
5. Backfill is non-destructive (read-only against Etsy; never archives, never edits).
6. Production mode (MTO vs Dropship) is auto-derived from `x_gearment_sku` per ADR-010; the wizard surfaces but does not duplicate it.

## Implementation Phases

### Slice P-HUB-PROD-MODEL — Models + ACL + Seed (~1 week)

Deliverables:
- `models/multichannel_sales_channel.py` — reference model + UNIQUE(code) + `init()` raw-SQL mirror.
- `models/product_channel_status.py` — per-(product, channel) state + UNIQUE(product_tmpl_id, channel_id) + `init()` mirror.
- `models/product_template.py` extensions — 6 fields: `x_channel_applicability_ids` (M2M), `x_listing_price` (Float), `x_shipping_price_internal` (Float), `x_additional_cost` (Float), `x_sku_v2_suggested` (Char computed indexed), `x_sku_v2_status` (Selection), `x_sku_legacy` (Char); plus `x_unit_margin` computed.
- `services/sku_grammar_v2.py` — regex evaluator returning (suggested_sku, status). Family list seeded from `.0temp/deliverables/D1_product_taxonomy_SKU.xlsx` `family_rules` sheet → Python tuple.
- `data/multichannel_sales_channel_seed.xml` — 3 channels (`etsy` active, `amazon` inactive, `website` inactive).
- `security/ir.model.access.csv` — 4 rows.
- Two-Phase tests: Phase 1 (DB structure, UNIQUE mirrors), Phase 2 (M2M write, status One2many, grammar regex truth table).

### Slice P-HUB-WIZARD — Product Creation Wizard (~1 week)

Deliverables:
- `wizards/product_creation_wizard.py` — TransientModel with validation pipeline + create logic.
- `wizards/product_creation_wizard_views.xml` — form view with grouped sections (Identity / Pricing / Channels / Production mode preview).
- `_check_ba_or_raise()` helper + `action_create()` method-top gate (FR-017 21st confirmation).
- Two-Phase tests: validation gate (empty fields refused), happy path creates product + channel status rows, non-canonical SKU passes through (non-blocking).

### Slice P-HUB-SKU-DRIFT — Drift Review + Canonicalisation Wizard (~1 week)

Deliverables:
- `wizards/product_sku_canonicalise_wizard.py` — `action_keep_legacy` + `action_accept_canonical`.
- For Etsy auto-push: defines a service hook `_push_sku_to_channel(product, channel_code)` that `etsy_integration` implements; mhc-side has a no-op fallback so non-Etsy channels degrade gracefully.
- `views/product_sku_drift_views.xml` — tree view + search filters + server action binding the wizard.
- Two-Phase tests: Keep-legacy transition; Accept-canonical without Etsy link (no push); Accept-canonical with mocked Etsy push success/failure (rollback on failure).

### Slice P-HUB-BACKFILL — Etsy Listing Backfill Wizard (~1 week)

Deliverables:
- `wizards/etsy_listing_backfill_wizard.py` (lives in `etsy_integration` — Etsy-specific by nature).
- Read-only against Etsy: only writes `product.template` + `product.channel.status` + links existing `product.product.etsy_listing_variant_id` rows.
- Idempotent: re-running upserts; never duplicates products; never resets fields BA has edited.
- Unmatched-SKU report: line-by-line list with **Create product** / **Skip — flag Etsy-only** per row.
- Two-Phase tests: idempotency (run twice = same state), match-existing-product path, unmatched-SKU creates new template, Etsy-only flag persists.

### Slice P-HUB-STATUS-VIEW — Product Form Channels Tab (~0.5 week)

Deliverables:
- `views/product_template_views.xml` extension — Channels tab + smart button.
- No new model; reads `product.channel.status` One2many.
- Two-Phase tests: Phase 1 view loads; Phase 2 smart-button count matches.

## Testing Strategy (Two-Phase)

- **Phase 1 (DB)**: tables, columns, UNIQUE mirrored in `init()` (Odoo 19 inert `_sql_constraints` — per memory `project_sql_constraints_drift`); indexes per data-model.md.
- **Phase 2 (ORM)**: model methods, wizard validation gates, grammar v2 regex truth table from `family_rules` sheet, FR-017 gates fire before any side effect (memory `feedback_fr017_write_defense_in_depth`).
- Run with `--http-port=8170` in container (port-8169 gotcha; memory `feedback_odoo19_test_gotchas`).
- Register every new test file in `tests/__init__.py` (memory `feedback_tdd_guide_init_py_imports`).
- Coverage ≥ 80 % on changed lines.

## Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-009-1 | Grammar v2 regex evaluation slow on large catalogs | Low | Med | Precompile family regex tuple at module load; computed-indexed field; cached per row |
| R-009-2 | `_inherits` regression on `product.template` after adding 6 fields | Low | High | Coverage on existing product flows (sale.order line creation); existing tests in mhc/mhf/etsy_integration suites stay green |
| R-009-3 | Backfill wizard misidentifies an unmatched variant and creates duplicate | Med | Med | Idempotency test; require `default_code` non-empty before create; warn-log on duplicate `default_code` discovery (R-L1 echo from ADR-013) |
| R-009-4 | SKU canonicalisation auto-push race (BA accepts canonical while order line is in flight) | Low | Med | Wizard reads product → grabs short lock; Etsy push is the entire-array-resubmit path (no partial state); rollback restores prior `default_code` |
| R-009-5 | Channel M2M not visible to BA group | Low | Low | Group-aware field visibility tested; channel reference data read by `base.group_user` |

## Exit Criteria — P-HUB-SPEC (this planning slice, pure-doc)

- [x] ADR-014 written + owner sign-off (2026-05-23, in-session)
- [x] spec.md, plan.md, data-model.md, tasks.md, findings.md authored
- [x] Open questions resolved (ADR-014 §4 SKU policy + §3 sync direction matrix)
- [ ] Tracker Phase 3 inserted (P-HUB-SPEC → done; downstream → todo with deps)
- [ ] `006-overview.md` final-target line extended + scorecard updated
- [ ] ADR README index gains ADR-014 row
- [ ] Findings.md records spec-009 number + planning surprises
- [ ] `/learn` capture (or explicit "no new pattern")
- Two-Phase Testing N/A for this planning slice; noted in commit body.

## Cross-References

- ADR-014 (load-bearing for all 5 implementation slices)
- ADR-013 (`etsy.listing` mirror — backfill source)
- ADR-010 (MTO/Dropship route invariant — production mode derivation)
- Spec 010 plan.md (consumes the model from this spec — populates fields via Excel)
- Spec 011 plan.md (consumes `x_channel_applicability_ids` + writes `product.channel.status`)
