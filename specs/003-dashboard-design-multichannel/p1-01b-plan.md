# P1-01b Tactical Plan

**Slice**: P1-01b — Operations Dashboard refactor `sale.order` → `sale.order.line` (Owner directive D6, 2026-05-10)
**Branch**: `feature/006-master-plan-coding`
**Module**: `multichannel_hub_core`
**Author**: planner agent (Sonnet) → orchestrator-written
**Date**: 2026-05-10

## Spec drift check (verbatim quotes)

Field verification against actual code (Read in Phase 0):

1. **`multichannel_hub_core/models/sale_order_line.py`** currently has:
   - `design_file_ids` (One2many to 'design.file')
   - `product_image_thumb` (Binary computed from `product_id.product_tmpl_id.image_128`)
   - `design_status` (Selection: none/rejected/pending/approved/approved-pending-route)

2. **`etsy_integration/models/sale_order.py`** has Etsy-flavored equivalents:
   - `etsy_gift_message` (Text)
   - `etsy_shipping_service` (Char)
   - `etsy_processing_time` (Char)
   - `etsy_discount_code` (Char)

3. **`multichannel_hub_core/models/sale_order.py`** currently has:
   - `sales_channel`, `channel_order_ref` (identity)
   - `qty_total`, `is_duplicate_buyer`, `is_overdue_approval` (decoration drivers)
   - `order_image_128` (existing line widget heritage)

4. **`multichannel_hub_core/models/sale_order_fulfillment.py`** has (P1-LBL just landed 2026-05-10):
   - `order_id` (reverse pointer)
   - `tracking_number`, `tracking_url`, `shipping_date`, `shipping_carrier_id`
   - `label_status_id` (Many2one to `label.status.option`, P1-LBL)
   - `mp_note`, `pic_user_id`, `pd_pic_user_id`, `order_priority`, `production_blocked`

5. **P1-05 _inherits delegation (ADR-007)**: `sale.order._inherits = {'sale.order.fulfillment': 'fulfillment_id'}` means dashboard reads `order.label_status_id` directly (Odoo delegates transparently). Confirmed by current dashboard XML at `views/operations_dashboard_views.xml:50` (`<field name="label_status_id"/>` without `order_id.` prefix).

**Drift flags**:

- **T-01b-01** (8 line Char fields): No drift. None of `image_url`/`option_label`/`color`/`size`/`side`/`face_mask_size`/`design_link_front`/`design_link_back` collide with existing line fields in mhc.
- **T-01b-02** (4 order fields): **Adjacent etsy_* equivalents exist but no name collision** since etsy fields use `etsy_` prefix. New mhc fields stand alone. See DECISION 1 for the coexist-vs-replace policy.
- **T-01b-04** (related shadows): No drift. Per P1-05 _inherits delegation, `order_id.label_status_id` resolves through `fulfillment_id` automatically — but **the related path on the line should be `related='order_id.label_status_id'`** (not `order_id.fulfillment_id.label_status_id`); Odoo's _inherits transparency removes the intermediate hop. Phase 1 DB test `test_related_fulfillment_fields_resolve` will catch this if wrong.

## Architectural decisions

### DECISION 1 — Channel-agnostic field location: coexist (defer cleanup)

For `design_link_front`/`design_link_back` and `gift_message`/`processing_time`/`discount_code`/`shipping_service_label`:

- **Chosen**: **Coexist with the etsy_* fields**. Create new mhc fields; etsy_integration writes both (dual-write); dashboard reads only mhc. Defer etsy_ deprecation to a follow-up slice (P1-LBL-MIGRATE-style).
- **Rejected**: Replace + migrate — too disruptive for a dashboard refactor; etsy_integration is the largest module and a field rename ripples into ingest, parser, tests.
- **Rationale**: Per memory `feedback_channel_agnostic_groups_in_mhc.md`, mhc is the canonical home for channel-agnostic data; per `feedback_dispatch_run_to_completion.md`, decisive picks beat options. Coexist preserves backward-compat during operator UAT; cleanup is a separate slice.

### DECISION 2 — OPTION/COLOR/SIZE/SIDE/FACE_MASK_SIZE: non-stored compute + manual override

- **Chosen**: `fields.Char(compute='_compute_<name>', inverse='_inverse_<name>', store=False)` reading `product_template_attribute_value_ids` (case-insensitive attribute-name match), with `_<name>_manual` Char sibling preferring manual when set.
- **Rationale**: Operators rarely group/filter by these (visual variant metadata); store=False avoids the `@api.depends` invalidation cascade and write-protect overhead. Inverse + manual sibling mirrors the T023/T074 design-file approval pattern already in mhc.

### DECISION 3 — Related-field shadows: `store=False` for all

- **Chosen**: Every related shadow on `sale.order.line` is `store=False, readonly=True`. No per-shadow indexing.
- **Rationale**: Saved filters traverse via `order_id.<field>` and Odoo executes against the canonical column (`sale_order_fulfillment.production_blocked` etc., already indexed). Storing the shadow doubles the write cost on every order/fulfillment update for zero-read benefit until performance testing proves otherwise. If Phase 5 verify reveals slow filters, add `store=True, index=True` to the specific shadow in a follow-up slice.

### DECISION 4 — Form-fallback redirect: auto-pick `(False, 'form')`

- **Chosen**: `<field name="views" eval="[(ref('operations_dashboard_list_view'), 'list'), (False, 'form')]"/>`.
- **Rationale**: Simplest; lets Odoo auto-generate a default `sale.order.line` form. If operator UAT shows the auto-form is unusable (likely — line forms are sparse), the lightweight follow-up is a thin OWL JS button to jump to `order_id` form via `act_window_open`. Don't pre-build OWL until UAT proves need.

## Files to create

| Path | Purpose | LOC est |
|------|---------|---------|
| `custom_addons/multichannel_hub_core/tests/test_operations_dashboard_line_db.py` | 9 Phase 1 DB tests | ~180 |
| `custom_addons/multichannel_hub_core/tests/test_operations_dashboard_line_orm.py` | 11 Phase 2 ORM tests (9 from spec + 2 added below) | ~280 |
| `custom_addons/multichannel_hub_core/migrations/19.0.1.0.32/post-stamp-new-sale-order-fields.py` | Optional — only if T-01b-02 needs NULL backfill (likely not — Char fields default to empty) | ~40 |

## Files to modify

| Path | Tasks | Nature | LOC est |
|------|-------|--------|---------|
| `custom_addons/multichannel_hub_core/models/sale_order_line.py` | T-01b-01, T-01b-04 | Add 8 Char fields + ~20 related shadows + 5 attribute-compute methods | +120 |
| `custom_addons/multichannel_hub_core/models/sale_order.py` | T-01b-02 | Add 4 Char fields with `tracking=True` | +40 |
| `custom_addons/multichannel_hub_core/views/operations_dashboard_views.xml` | T-01b-03, T-01b-05, T-01b-06, T-01b-07 | Model swap (3 records); 34 Excel cols + 7 BA/PD/MP cols + 3 hidden decoration drivers; rebound search + action + decorations | refactor (~150 net) |
| `custom_addons/multichannel_hub_core/data/operations_dashboard_saved_filters.xml` | T-01b-09 | Rewrite each `model_id` + domain to traverse `order_id.*` | refactor (~10) |
| `custom_addons/multichannel_hub_core/views/menu.xml` | T-01b-10 | Add legacy fallback menu + action; TODO sunset comment | +30 |
| `custom_addons/multichannel_hub_core/__manifest__.py` | T-01b-14 | Bump version to `19.0.1.0.32` | +1 |
| `custom_addons/multichannel_hub_core/CLAUDE.md` or `README.md` | T-01b-15 | Mention P1-01b in Active list | +3 |
| `specs/003-dashboard-design-multichannel/findings.md` | T-01b-15 | Append §P1-01b surprises | +50 |

## Agent dispatch order

1. **Phase 2 RED** — `tdd-guide` agent (Sonnet, single message): write both test files (`test_operations_dashboard_line_db.py` + `test_operations_dashboard_line_orm.py`) as failing stubs. All 18-20 tests fail because fields/views don't yet exist. Commit as `test(P1-01b): RED — failing tests for line dashboard refactor`.
2. **Phase 3 GREEN** — orchestrator-driven implementation in this exact sequence:
   1. T-01b-01 (line fields + computes) → verify file syntax via `python3 -m py_compile`
   2. T-01b-02 (order fields)
   3. T-01b-04 (related shadows)
   4. T-01b-03 (list view refactor)
   5. T-01b-05 (search view refactor)
   6. T-01b-06 (action refactor)
   7. T-01b-07 (decorations rebind)
   8. T-01b-08 (bulk-ship server action)
   9. T-01b-09 (saved filters)
   10. T-01b-10 (legacy menu)
   11. T-01b-11 (ICP marker — defer if dashboard works without it)
   12. T-01b-14 (manifest bump + clean install verify)
   13. Run module update: `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init` → exit 0
   14. Run test tags: `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /multichannel_hub_core --stop-after-init` → all 18-20 PASS
   15. Commit as `feat(P1-01b): GREEN — sale.order.line dashboard with 34 Excel columns`
3. **Phase 4 Review** — PARALLEL (single message, two `Agent` calls):
   - `code-reviewer` agent: ORM patterns, field ordering, compute correctness, no `_logger.info`/`print()`, related-field readonly
   - `security-reviewer` agent: ACL coverage (no new model so likely just verify existing rows still hold), no new sudo(), bulk-action FR-017 9th confirmation, no XSS in dashboard string fields (Char auto-escapes)
   - Block on CRITICAL/HIGH; fix in-line; commit each fix as `fix(P1-01b): <what reviewer flagged>`.
4. **Phase 5 Verify** — `ruff check custom_addons/multichannel_hub_core/` (if available); grep for `_logger.info`/`print(`; final clean install.
5. **Phase 6 Commit** — already done per checkpoint above.
6. **Phase 7 Document** — flip T-01b-01..15 to `[X]` in tasks.md; update tracker P1-01b row to `done` with summary; append §P1-01b to findings.md if surprises emerged. Commit as `docs(P1-01b): mark slice done`.
7. **Phase 8 Learn** — run `/learn` to capture patterns (related-field shadows over _inherits, attribute-label compute pattern, Excel column-order test contract).
8. **Phase 9 Land** — accumulate on `feature/006-master-plan-coding`; merge after W7 E2E sprint.

## Risks

| ID | Risk | Probability | Impact | Mitigation |
|----|------|-------------|--------|------------|
| R1 | R-2026-05-10 — operator muscle-memory breakage | Medium | Medium | T-01b-10 legacy menu; one-sprint sunset comment; rollback = revert P1-01b commit |
| R2 | Related-field via _inherits delegation fails (need explicit `fulfillment_id.` hop) | Low | High | Phase 1 DB test `test_related_fulfillment_fields_resolve` catches; ADR-007 corrected 2026-04-27 |
| R3 | Excel column count grows (owner adds 35th col) | Low | Medium | Phase 1 DB test `test_excel_column_count_matches` parses arch + asserts 34 — fails fast on drift |
| R4 | Form-view fallback unusable | Medium | Low | Auto-pick `(False, 'form')` first; OWL jump-to-order button as P1-01b-FU if UAT fails |
| R5 | Saved-filter bookmarks invalidated for users | Low | Low | Old bookmarks become stale (non-fatal); Odoo silently re-resolves; communicate in release notes |
| R6 | etsy_* dual-write drift (etsy code writes etsy_*, mhc dashboard reads mhc field; legacy data only on etsy_*) | Medium | Medium | DECISION 1 coexist policy; legacy reconciliation deferred to follow-up slice; Phase 1 DB test could optionally check that ingest writes both — defer to ingest-side slice |

## Exit-criteria check

| Criterion (per playbook) | Satisfied by |
|--------------------------|--------------|
| Every slice task `[X]` in tasks.md | Phase 7 Document checks T-01b-01..15 |
| Tests pass; coverage ≥80% changed lines | Phase 5 Verify runs test tags + (optional) `--cov` |
| Module installs cleanly (`-u <module> --stop-after-init` exit 0) | Phase 3 GREEN step 13; Phase 5 Verify re-runs |
| ACLs / sudo() / raw SQL audited | Phase 4 Review (security-reviewer); no new model so no new ACL row needed; no sudo planned; no raw SQL planned |
| Tracker `state` updated; blockers documented | Phase 7 Document — set `state: done`, append summary line |
| `/learn` insight captured | Phase 8 Learn |
| `findings.md` updated if surprises | Phase 7 Document — append §P1-01b if any of R1-R6 fired |

## Out of scope (defer)

- **Per-line bulk Push-to-Gearment** → P4-01 step (b)
- **Excel-export round-trip of line view** → P2-01 (GKE schema slice)
- **Historical etsy_design_link reconciliation** → follow-up `P1-DESIGNLINK-MIGRATE` slice (post-UAT)
- **Etsy field deprecation cleanup** (DECISION 1 deferred half) → same follow-up
- **Process Dashboard / Design kanban** → US3 (separate slice)
- **OWL jump-to-order button** → P1-01b-FU if UAT proves need

## Test plan summary

### Phase 1 DB tests (9, ~180 LOC)

`test_operations_dashboard_line_db.py`:

1. `test_view_model_is_sale_order_line` — list view model swap
2. `test_action_res_model_is_sale_order_line` — action res_model swap
3. `test_search_view_model_is_sale_order_line` — search view model swap
4. `test_bulk_shipped_binding_model_is_sale_order_line` — server action binding
5. `test_legacy_menu_present` — legacy fallback menu + action exist
6. `test_new_line_fields_columns_exist` — pg_columns for 8 new line fields
7. `test_new_order_fields_columns_exist` — pg_columns for 4 new order fields
8. `test_excel_column_count_matches` — list arch parsed via lxml: 34 Excel cols + ≤7 BA/PD/MP + ≤3 invisible decoration drivers
9. `test_excel_column_order_matches` — 34 Excel cols in exact `.xlsx` row-1 order

### Phase 2 ORM tests (11, ~280 LOC)

`test_operations_dashboard_line_orm.py`:

1. `test_attribute_compute_derives_option_label` — line.option_label reads `product_template_attribute_value_ids` matching attribute name "Option" (case-insensitive)
2. `test_attribute_compute_falls_back_to_manual_entry` — manual write to `option_label_manual` overrides compute
3. `test_related_address_fields_resolve` — `partner_shipping_name`/`street`/`zip` mirror `order_id.partner_shipping_id.*`
4. `test_related_order_fields_resolve` — `gift_message`/`discount_code` mirror `order_id.*`
5. `test_related_fulfillment_fields_resolve` — `label_status_id`/`pic_user_id`/`production_blocked` mirror via _inherits delegation (path: `order_id.<field>`, NOT `order_id.fulfillment_id.<field>`)
6. `test_related_decoration_flags_resolve` — `qty_total`/`is_duplicate_buyer`/`order_priority`/`sales_channel` mirror `order_id.*`
7. `test_bulk_shipped_action_dedupes_orders` — 5 lines across 2 orders → action calls `action_bulk_mark_shipped` on 2 orders, not 5 lines (mock + call-count assert)
8. `test_bulk_shipped_action_skips_lines_without_fulfillment` — line on order without fulfillment_id → silent skip, no AccessError
9. `test_bulk_shipped_action_preserves_fr017_gate` — non-production user → silent skip (FR-017 9th confirmation)
10. `test_saved_filters_rebound_to_line_model` — every `ir.filters` row in saved-filters XML has `model_id == 'sale.order.line'`
11. `test_legacy_menu_action_targets_sale_order` — legacy menu's act_window opens `sale.order` (fallback during UAT)

**Coverage target**: ≥80% on changed lines per playbook.

---

**Status**: Phase 1 plan complete. Ready for Phase 2 RED dispatch (`tdd-guide` agent).
