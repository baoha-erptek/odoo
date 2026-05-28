# Implementation Plan: P1-IMG-LINE-WIDGET

**Slice**: P1-IMG-LINE-WIDGET (Family A — Spec 003 extension, owner directive 2026-05-06)
**Branch**: `feature/006-master-plan-coding`
**Depends on**: P1-DASH-MERGE ✓
**LOC budget**: ~50 (compute field + view xpath + tests)
**Author**: planner agent (Phase 1 dispatch 2026-05-07)

---

## Slice Overview

Add computed Binary thumbnail field `product_image_thumb` to `sale.order.line` (mhc) returning `product_id.product_tmpl_id.image_128`. Render as inline `widget="image"` column in the order-line list within the Etsy-inherited order form. Spec 003 US1 extension — operators on the unified Operations Dashboard cannot see product images on order lines without leaving Odoo.

---

## Key Decisions

### (a) Compute field placement & storage

**Decision**: Non-stored computed Binary field on `multichannel_hub_core.sale_order_line` with `attachment=False` (in-row).

Rationale:
- ~50 LOC budget rules out a stored field (would need migration + recompute trigger).
- Thumbnails are typically ≤16 KB; in-row Binary is faster than filestore for the read path.
- List view computes lazily — only renders for visible rows.

### (b) Compute body & fallback chain

**Decision**: Synchronous read of `product.image_128` only. **No on-read download.** The "fallback via image_downloader" in the tracker description means the *existing async cron* `cron_download_pending_images` (`etsy_integration/services/image_downloader.py`, runs every 10 min) populates the upstream `product.template.image_1920` from `etsy_image_url`; Odoo's stock image-resize pipeline auto-derives `image_128`; next list-render picks up the populated thumbnail.

Pseudocode:
```python
@api.depends('product_id.product_tmpl_id.image_128')
def _compute_product_image_thumb(self):
    for line in self:
        line.product_image_thumb = line.product_id.product_tmpl_id.image_128 or False
```

**Critical**: compute must NOT call `image_downloader.download_and_store()` — compute is a hot read path. P1-IMG-BACKFILL is the slice that amends the cron predicate to cover any uncovered cases.

### (c) View inheritance — which file?

**Decision**: View column lives in `etsy_integration/views/sale_order_views.xml` (NOT `sale_order_form.xml` — the tracker description has a stale filename; verify by reading the file).

Rationale:
- Compute field lives in mhc (foundation) per the channel-agnostic-in-mhc memory rule.
- The slice description explicitly says "(etsy_integration)" for the view — owner intent is clear.
- Etsy-form-flavored UX belongs in etsy_integration; visible to all order lines on the Etsy-inherited form.

XPath target (verify exact field name during implementation):
```xml
<xpath expr="//field[@name='order_line']//list//field[@name='product_id']" position="after">
  <field name="product_image_thumb" widget="image" readonly="1" optional="show"/>
</xpath>
```

Use `optional="show"` so operators can hide the column if they prefer. **Do NOT** apply `column_invisible` gating to `is_etsy_order` — the column should be visible for all lines on this form (the form itself only renders for Etsy-flavored orders).

### (d) Test strategy split

**Phase 1 DB verification** (no real table column for non-stored computed Binary):
```python
def test_product_image_thumb_field_registered(self):
    field = self.env['sale.order.line']._fields.get('product_image_thumb')
    self.assertIsNotNone(field)
    self.assertEqual(field.type, 'binary')
    self.assertIsNotNone(field.compute)
    self.assertFalse(field.store)
```

**Phase 2 ORM scenarios** (`TransactionCase`):
1. **Happy path**: `product_id` set + `product.template.image_128` populated → `line.product_image_thumb` returns the bytes.
2. **Async-cron-not-yet-run**: `product_id` set + `image_128` empty + `etsy_image_url` populated on the line → returns `False` (not blank-string, not exception).
3. **No product**: `product_id=False` → returns `False`.

**Mock pattern caveat** (memory `feedback_odoo19_test_gotchas.md`): if any test needs to mock `image_downloader`, patch the module function via `unittest.mock.patch('odoo.addons.etsy_integration.services.image_downloader.download_and_store')` — do NOT mock on a recordset method (raises `AttributeError: read-only`).

### (e) FR-017 / sudo / raw-SQL audit

**None required.** Computed field is read-only (no write logic, no state machine). No raw SQL. No `sudo()`. No new model → no ACL row needed; inherits mhc's `sale.order.line` ACLs which are already set up by P1-DASH-MERGE.

### (f) Manifest version bump

mhc current: `19.0.1.0.18` (per tracker P1-MTO-SYNC entry).

Bump to: **`19.0.1.0.19`**.

### (g) Risks

| Risk | P | I | Mitigation |
|---|---|---|---|
| List view with 80+ lines renders slowly due to per-row Binary fetch | M | M | Computed fields are lazy. If perf issue surfaces in staging, convert to stored + recompute on cron. Monitor in Phase 2 tests on large recordsets if practical. |
| `image_128` cache invalidation when `product.image_1920` rewritten | L | L | Odoo's image-derive pipeline handles cache invalidation; no action. |
| SSRF via malicious `etsy_image_url` | L | L | Compute does NOT call download. SSRF allowlist in `image_downloader.py` already gates the cron. |

### (h) Exit-criteria checklist (playbook §"Slice exit criteria")

- [ ] Computed field defined in `mhc/models/sale_order_line.py` with `@api.depends('product_id.product_tmpl_id.image_128')`
- [ ] View column added to `etsy_integration/views/sale_order_views.xml` with `widget="image"` + `optional="show"`
- [ ] Phase 1 DB test (field registration introspection)
- [ ] Phase 2 ORM tests: 3 scenarios pass
- [ ] `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core,etsy_integration --stop-after-init` exit 0
- [ ] `--test-tags /multichannel_hub_core:TestProductImageThumb` all pass
- [ ] Manifest mhc bumped to `19.0.1.0.19`
- [ ] Tracker P1-IMG-LINE-WIDGET `state→done` + landed-date + commit ref + test count
- [ ] `/learn` insight captured (or "no new patterns" note)
- [ ] `findings.md` updated if anything surprised us
- [ ] Doc-debt note: amend `specs/003-dashboard-design-multichannel/tasks.md` with formal IMG task entries (currently the slice description in tracker is the only spec)

---

## Files to modify

| File | Action |
|---|---|
| `custom_addons/multichannel_hub_core/models/sale_order_line.py` | Add `product_image_thumb` Binary computed field |
| `custom_addons/multichannel_hub_core/__manifest__.py` | Version bump `19.0.1.0.18` → `19.0.1.0.19` |
| `custom_addons/etsy_integration/views/sale_order_views.xml` | Add xpath for image column on order-line list |
| `custom_addons/multichannel_hub_core/tests/test_product_image_thumb.py` | NEW — Phase 1 DB + Phase 2 ORM tests (3 scenarios) |

---

## Implementation order (for tdd-guide)

1. **RED Phase 1**: Write field-registration introspection test. Run — must fail (`product_image_thumb` not in `_fields`).
2. **RED Phase 2**: Write 3 ORM scenarios. Run — must fail.
3. **GREEN compute**: Implement field on mhc `sale_order_line.py`.
4. **GREEN view**: Add xpath in etsy_integration `sale_order_views.xml`.
5. **GREEN manifest**: Bump version.
6. **Verify RED→GREEN**: Re-run tests; must pass.
7. **Verify install**: `-u multichannel_hub_core,etsy_integration --stop-after-init` exit 0.
8. **Hand off to Phase 4** (parallel code-reviewer + security-reviewer).

---

**Plan checksum**: P1-IMG-LINE-WIDGET / mhc 19.0.1.0.19 / mhc model + etsy_integration view / ~35 LOC compute + ~10 LOC view + tests / Phase 1 DB + Phase 2 ORM 3-scenario / no security elevation / lazy-compute perf risk noted.
