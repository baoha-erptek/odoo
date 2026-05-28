# Implementation Plan: P1-IMG-DASH-COL

**Slice**: P1-IMG-DASH-COL (Family A — Spec 003 extension, owner directive UI visual)
**Branch**: `feature/006-master-plan-coding`
**Depends on**: P1-IMG-LINE-WIDGET ✓ (landed 2026-05-07 commit `9f7d3d3e99d`)
**LOC budget**: ~30-50 (aggregate field + view column + tests)
**Author**: planner agent (Phase 1 dispatch 2026-05-07)

---

## Slice Overview

Add aggregate `image_128` column to Operations Dashboard list (`sale.order` rows) in `multichannel_hub_core/views/operations_dashboard_views.xml`. The column displays a clickable image thumbnail that opens full-size via stock Odoo 19 `widget="image"` modal. Aggregates the first non-empty product image from the order's line items. This is a visual-only extension of P1-IMG-LINE-WIDGET (which solved image display at the line level); the dashboard slice surfaces that image at the order summary level. Spec 003 US1 extension — users need order-level visual context before drilling into lines.

---

## Key Decisions

### (a) Aggregate field strategy

**Decision**: Computed Binary field on `sale.order` (non-stored) returning the first line's `product_image_thumb` (cascade fallback to second line, etc., if first line has no image).

**Rationale**:
- Dashboard list is `sale.order` rows, not lines. Need aggregation at the order level.
- P1-IMG-LINE-WIDGET already solved line-level compute; reuse that work rather than re-deriving from product template.
- Non-stored avoids DB column cost; dashboard list computes lazily only for visible rows.
- Many orders have single-line simple orders; fallback to second/third line handles bundles gracefully.

**Alternative considered (Option B)**: Pure XML reading `order_line[0].product_image_thumb` via one2many traversal.
- **Rejected**: Odoo 19 list views cannot reliably traverse one2many fields in a single aggregate column. The `widget="image"` would read from the first line at DOM time, but fallback logic (if first line has no image) requires ORM compute logic, not XML.

**Alternative considered (Option C)**: Read `product_id.image_128` on the main product (if `sale.order` has a main product reference).
- **Rejected**: Sale.order does not have a canonical product_id field; that belongs to the line item structure. Would require a new field to track "primary product" (scope creep).

**Chosen: Option A (compute field)** — simplest, leverages existing line-level compute, two-liner fallback loop.

### (b) Compute body & fallback chain

**Decision**: Synchronous loop through `order_line_ids` in sequence; return first non-empty `product_image_thumb`.

Pseudocode:
```python
@api.depends('order_line_ids.product_image_thumb')
def _compute_order_image_128(self):
    for order in self:
        thumb = False
        for line in order.order_line_ids:
            if line.product_image_thumb:
                thumb = line.product_image_thumb
                break
        order.order_image_128 = thumb
```

**Rationale**:
- Lightweight and deterministic — no cron fallback needed (depends on the line's compute which already has async cron fallback).
- Dashboard render is read-only — no state mutations.
- First non-empty image is the most relevant for the order dashboard (primary product).

### (c) Field name & view integration

**Decision**:
- Field name: `order_image_128` (explicit, avoids collision with product_id.image_128)
- View column: inserted into `operations_dashboard_views.xml` list after `name` (Reference), before `sales_channel` for visual context early in the row
- Widget: `widget="image"` with `optional="show"` (operators can hide if they prefer)
- Read-only: yes (no edit needed)

**Rationale**:
- Early position (after reference) gives visual confirmation of the product *before* channel/date context.
- `optional="show"` follows UX precedent from P1-IMG-LINE-WIDGET.
- Stock `widget="image"` in Odoo 19 renders inline <img> with click-to-zoom modal (no custom JS needed).

### (d) Test strategy split

**Phase 1 DB verification** (field registration + dependency graph):
```python
def test_order_image_128_field_registered(self):
    field = self.env['sale.order']._fields.get('order_image_128')
    self.assertIsNotNone(field)
    self.assertEqual(field.type, 'binary')
    self.assertIsNotNone(field.compute)
    self.assertFalse(field.store)

def test_order_image_128_depends_on_line_images(self):
    so = self.env['sale.order']
    compute_method = getattr(so, so._fields['order_image_128'].compute)
    depends = getattr(compute_method, '_depends', ())
    self.assertIn('product_image_thumb', str(depends))
```

**Phase 2 ORM scenarios** (`TransactionCase`):
1. **Single line with image**: order has 1 line → line has `product_image_thumb` → order's `order_image_128` matches.
2. **Multiple lines; first empty, second populated**: order has 2 lines; line[0].product_image_thumb=False, line[1].product_image_thumb=populated → order's `order_image_128` returns line[1]'s image.
3. **No lines or all empty**: order has lines but all have `product_image_thumb=False` → `order_image_128` returns False.
4. **Order with no lines**: empty order → `order_image_128` returns False.

### (e) FR-017 / sudo / raw-SQL audit

**None required.** Computed aggregate field is read-only. No write logic, no state machine. No raw SQL. No `sudo()`. No new model. No ACL row needed — inherits mhc's `sale.order` ACLs already set by P1-DASH-MERGE.

### (f) Manifest version bump

Manifest current: `19.0.1.0.19` (per P1-IMG-LINE-WIDGET landing).

Bump to: **`19.0.1.0.20`**.

### (g) Risks

| Risk | P | I | Mitigation |
|---|---|---|---|
| Dashboard list with 200+ rows × loop-per-order overhead | M | M | Lazy compute; non-stored field evaluates only on render. If perf issues surface in staging, convert to stored compute + recompute cron. Monitor in Phase 2 large-recordset test if practical. |
| Line order changes → first image changes mid-render | L | L | Immutable after create; line reorder is rare. No domain constraint needed. |
| Image_128 invalidation on product image rewrite | L | L | Inherited from line-level compute. Odoo's image pipeline handles cache invalidation. |

### (h) Exit-criteria checklist (playbook §"Slice exit criteria")

- [ ] Aggregate field `order_image_128` defined in `mhc/models/sale_order.py` with `@api.depends('order_line_ids.product_image_thumb')`
- [ ] View column added to `mhc/views/operations_dashboard_views.xml` with `widget="image"` + `optional="show"`
- [ ] Phase 1 DB tests: field registration + dependency introspection
- [ ] Phase 2 ORM tests: 4 scenarios pass (single line, multiple lines with fallback, empty lines, no lines)
- [ ] `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init` exit 0
- [ ] `--test-tags /multichannel_hub_core:TestOrderImage128` all pass (alt ports 18999/18998 if collision)
- [ ] Manifest mhc bumped to `19.0.1.0.20`
- [ ] Tracker P1-IMG-DASH-COL `state→done` + landed-date + commit ref + test count
- [ ] `/learn` insight captured (or "no new patterns" note)
- [ ] `findings.md` updated if anything surprised us

---

## Files to Modify

| File | Action | Rationale |
|---|---|---|
| `custom_addons/multichannel_hub_core/models/sale_order.py` | Add `order_image_128` Binary computed field with fallback loop | Aggregate compute; foundation module owns order-level fields |
| `custom_addons/multichannel_hub_core/views/operations_dashboard_views.xml` | Add xpath inserting image column after `name` field | View definition for dashboard list; mhc owns the view file |
| `custom_addons/multichannel_hub_core/__manifest__.py` | Version bump `19.0.1.0.19` → `19.0.1.0.20` | Manifest hygiene |
| `custom_addons/multichannel_hub_core/tests/test_order_image_128.py` | NEW — Phase 1 DB + Phase 2 ORM tests | Two-phase testing per playbook; parallels P1-IMG-LINE-WIDGET test structure |

---

## Field & Method Names

**Proposed names** (grep verified):

- **Field**: `order_image_128` — explicit aggregate name; avoids collision with inherited `product_id.image_128`, distinct from line-level `product_image_thumb`
  - Grep: `order_image_128` does not exist in current mhc sale_order.py
- **Compute method**: `_compute_order_image_128` — follows Odoo naming convention
  - Grep: `_compute_order_image_128` does not exist
- **Test class names**:
  - `TestOrderImage128Db` — Phase 1 DB introspection
  - `TestOrderImage128Orm` — Phase 2 ORM behavior
  - Grep: Neither exists in test files

**Collision risk**: Low. Verified via grep that no existing fields or methods use these names in mhc or inherited models.

---

## Test Plan

### Phase 1: Direct Database Verification
File: `custom_addons/multichannel_hub_core/tests/test_order_image_128.py`

**TestOrderImage128Db**:

1. `test_order_image_128_field_registered` — Verify field exists, type is binary, compute method is set, store=False
2. `test_order_image_128_depends_on_line_images` — Verify `@api.depends` via `compute_method._depends` includes `product_image_thumb` (critical per memory `feedback_odoo19_test_gotchas.md` entries 86-87)

### Phase 2: ORM Unit Tests
**TestOrderImage128Orm**:

1. `test_single_line_with_image_returns_thumbnail` — Create order + 1 line with product; product.template.image_128 populated → order.order_image_128 equals line's image
2. `test_multiple_lines_fallback_to_second_when_first_empty` — Create order + 2 lines; line[0] product has no image, line[1] product has image → order.order_image_128 equals line[1]'s image
3. `test_all_lines_empty_returns_false` — Create order + 2 lines; both products have no image → order.order_image_128 is False
4. `test_order_with_no_lines_returns_false` — Create order with no lines → order.order_image_128 is False

**Test utilities** (reuse from `test_product_image_thumb.py`):
- `_PNG_1X1` base64 constant for test images
- Helper: `_make_order_with_lines(product_ids, ...)` — factory to create test orders with parameterized line products

---

## Agent Dispatch Order (9-Phase Loop)

1. **Phase 0 Dispatch**: (you are here) — read tracker, verify branch, dependencies satisfied
2. **Phase 1 Plan**: (this document) — tactical breakdown
3. **Phase 2 RED**: `tdd-guide` agent — write Phase 1 DB + Phase 2 ORM tests; run — must fail
4. **Phase 3 GREEN**: `tdd-guide` agent continuation — implement compute field + view xpath + manifest bump; run tests — must pass
5. **Phase 4 Review**: Parallel agents:
   - `code-reviewer` — code quality, field naming, view position, test structure
   - `security-reviewer` — ACL audit (none needed, inherited), raw SQL check (none), sudo check (none)
   - Block on CRITICAL/HIGH; approve on MEDIUM/LOW
6. **Phase 5 Verify**: Manual:
   - `-u multichannel_hub_core --stop-after-init` exit 0
   - `--test-tags /multichannel_hub_core:TestOrderImage128` all pass with alt ports 18999/18998
   - `ruff check custom_addons/multichannel_hub_core/models/sale_order.py` — no errors
   - Grep for `_logger.info`, `print()` — none in new/modified lines
7. **Phase 6 Commit**: Single conventional commit:
   - `[multichannel_hub_core] feat(P1-IMG-DASH-COL): order-level image aggregate + dashboard column`
   - Body: cite tracker task, test count, landing branch, P1-IMG-LINE-WIDGET dependency
8. **Phase 7 Document**: Update tracker line 181:
   - `state→done`
   - `landed-date: 2026-05-XX`
   - `commit: <sha>`
   - `tests: 6` (2 Phase 1 DB + 4 Phase 2 ORM)
   - Append landing note (parallel to P1-IMG-LINE-WIDGET line 180 structure)
9. **Phase 8 Learn**: Run `/learn` — capture if any surprise pattern discovered; else note "no new patterns, reuses P1-IMG-LINE-WIDGET aggregate design"

---

## Risks & Open Questions

| Risk | Question | Mitigation |
|---|---|---|
| **View xpath target correctness** | Is the exact `<field>` structure in `operations_dashboard_views.xml` line 15–59 stable? | Read the file again at Phase 3 before xpath write; use `expr="//field[@name='name']"` as anchor (immutable reference column). |
| **Line order guarantees** | Does `order_line_ids` iterate in creation order? | Yes, Odoo ORM guarantees order_line_ids inherits the order from the One2many field definition. Falls back gracefully if first line is reordered (just picks a different line's image, acceptable for dashboard context). |
| **Performance in staging UI** | Will dashboard render feel sluggish with 200+ orders × loop per order? | Phase 2 tests should include a large-recordset scenario (create 50-order batch, time the compute). If >200ms, mark as perf debt and convert to stored compute + cron in P1-IMG-PERF-OPT (future). |
| **Multi-company scoping** | Should `order_image_128` inherit company_id filtering from order? | No — the field is read-only and non-stored. The list view's filtering already scopes by company via the dashboard's search view. No change needed. |

---

## Success Criteria Checklist

- [ ] Task tasks.md in specs/ updated (if exists) with new IMG task entry
- [ ] Implementation follows P1-IMG-LINE-WIDGET pattern (non-stored computed Binary, Phase 1 DB introspection via `compute_method._depends`, Phase 2 ORM scenarios)
- [ ] Field registered without errors; view xpath applies cleanly; manifest bumps consistently
- [ ] All Phase 1 DB + Phase 2 ORM tests pass (6 total)
- [ ] Module updates and installs without errors (`-u multichannel_hub_core --stop-after-init`)
- [ ] No security findings (ACL/sudo/raw-SQL audit clean)
- [ ] No debug statements (`_logger.info`, `print()`)
- [ ] Ruff linting passes
- [ ] Tracker line 181 updated with landed state + commit ref
- [ ] `/learn` insight captured in auto-memory
- [ ] `findings.md` entry added if anything surprised us

---

## Deviations from Template & Notes for Executor

1. **Reuses P1-IMG-LINE-WIDGET pattern** — This is a follow-on visual aggregate, not a novel architecture. The compute-on-read + fallback pattern is identical to the line-level field; no new paradigm.

2. **View position**: Place image column early in the dashboard list (after `name`, before `sales_channel`) to give users visual context before channel/status columns. Unlike P1-IMG-LINE-WIDGET's `optional="show"`, consider whether the image should be `optional="hide"` on the dashboard for cleaner default (users who care about images can toggle on). Let code-reviewer weigh in if this differs from spec.

3. **Fallback robustness**: The loop breaks on first non-empty image. If an order has both a bundle (multi-product) and single-product lines, this picks the first line's image. This is acceptable UX for the dashboard — the order form drills down to line-level images if more context needed.

4. **Test fixture reuse**: Import `_PNG_1X1` constant from `test_product_image_thumb.py` rather than duplicating; small file, same module, same test scope.

---

**Plan checksum**: P1-IMG-DASH-COL / mhc 19.0.1.0.20 / mhc model + view / ~20 LOC compute + ~10 LOC view + tests / Phase 1 DB + Phase 2 ORM 4-scenario / no security elevation / perf monitoring deferred to Phase 2 large-recordset test.
