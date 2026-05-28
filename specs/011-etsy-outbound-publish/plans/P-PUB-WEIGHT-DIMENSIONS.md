# P-PUB-WEIGHT-DIMENSIONS — Implementation Plan

**Authored**: 2026-05-28 (planner agent dispatch, orchestrator wrote file)
**Slice**: P-PUB-WEIGHT-DIMENSIONS (Tracker row 339, MP006)
**Branch**: `feature/006-master-plan-coding`
**Estimated LOC**: ~110

---

## 1. Module Placement Decision

**Decision**: Add `weight_unit_pref` and `dimensions_unit_pref` to `etsy.shop` via **etsy_integration** module (extend existing model). Reuse standard `product.template.weight` (no custom field). Helper logic in `services/etsy_listing_publisher.py`.

**Rationale**:
- Weight + dimension preference are Etsy-specific shop settings (like `default_who_made`).
- `product.template.weight` is standard Odoo — already shipped, no custom field needed. Cite ADR-014 §3 Standard-Odoo-First.
- Channel-agnostic product fields (e.g., list_price, weight, dimensions) stay on `product.template`; channel-specific mapping (shop preference for unit system) stays on `etsy.shop`.
- If future publishers (Amazon, Website) need dimension payloads, they define their own shop fields or share via a mhc config parameter; deferring to that case.

**Standard-Odoo-First check**: `product.template.weight` ships in Odoo 19 CE `product` addon (Float, base unit kg per `weight_uom_name` Char field). No custom weight field needed.

---

## 2. File List

| File | Type | Change |
|------|------|--------|
| `custom_addons/etsy_integration/models/etsy_shop.py` | Edit | Add 2 Selection fields: `weight_unit_pref` ('oz'/'g'), `dimensions_unit_pref` ('cm'/'in'), both `groups='base.group_system'` |
| `custom_addons/etsy_integration/services/etsy_listing_publisher.py` | Edit | Add static `_collect_weight_and_dimensions(tmpl, shop) -> dict` + plug into `_build_create_draft_payload` |
| `custom_addons/etsy_integration/views/etsy_shop_views.xml` | Edit | Add 2 fields to shop form under new group "Etsy Publisher Unit Preferences" (system-group) |
| `custom_addons/etsy_integration/tests/test_phase1_pub_weight_dimensions_db.py` | New | Phase 1 DB schema tests |
| `custom_addons/etsy_integration/tests/test_phase2_pub_weight_dimensions_orm.py` | New | Phase 2 ORM tests (>=8 cases) |
| `custom_addons/etsy_integration/tests/__init__.py` | Edit | Register both test files |
| `custom_addons/etsy_integration/__manifest__.py` | Edit | Bump `19.0.2.22.0` -> `19.0.2.23.0`; no new XML to add to data list (shop fields ORM-only; views file already in data list) |

**No migration file**: Both shop fields are new columns with ORM defaults. Existing shops: see Risk #3.

---

## 3. Model Changes

### etsy_shop.py — append after `default_is_supply` field, before any `_sql_constraints`

```python
weight_unit_pref = fields.Selection(
    selection=[('oz', 'oz'), ('g', 'g')],
    string='Weight Unit Preference',
    default='oz',
    help='Unit system for Etsy listings: oz (ounces) or g (grams). '
         'Odoo stores weight in kg; conversion applied on publish.',
    groups='base.group_system',
)
dimensions_unit_pref = fields.Selection(
    selection=[('cm', 'cm'), ('in', 'in')],
    string='Dimensions Unit Preference',
    default='cm',
    help='Unit system for item_length/width/height on Etsy listings: cm or in.',
    groups='base.group_system',
)
```

---

## 4. Service Method (etsy_listing_publisher.py)

**New static method** placed after `_collect_property_values`:

```python
@staticmethod
def _collect_weight_and_dimensions(tmpl, shop):
    """Build Etsy weight + dimension keys for createListing payload.

    Converts tmpl.weight (kg) to shop's unit preference (oz/g).
    For Rect-family templates with a Size attribute value like 'R30X18'
    or '30X18', extracts width/height. Mug-family Size values like
    '11 oz' do not match the rect pattern and produce no dimension keys.

    Returns: dict with keys item_weight, item_weight_unit, and optionally
    item_length, item_width, item_dimensions_unit. Empty dict when
    weight<=0 AND no parseable Size value.

    Weight<=0 omits weight keys (Etsy accepts absence).
    Dimension parse failures log WARNING + omit the dimension block.
    """
    result = {}

    # -- Weight conversion --
    weight_kg = tmpl.sudo().weight or 0.0
    if weight_kg > 0:
        unit_pref = shop.sudo().weight_unit_pref or 'oz'
        if unit_pref == 'oz':
            weight_val = round(weight_kg * 35.274, 2)
        else:  # 'g'
            weight_val = round(weight_kg * 1000.0, 2)
        result['item_weight'] = weight_val
        result['item_weight_unit'] = unit_pref

    # -- Dimensions from Size attribute on template --
    try:
        size_value_name = ''
        for line in tmpl.sudo().attribute_line_ids:
            if line.attribute_id.name == 'Size' and line.value_ids:
                size_value_name = line.value_ids[0].name or ''
                break

        if size_value_name:
            rect_match = re.match(
                r'^[Rr]?\s*(\d+)\s*[xX×]\s*(\d+)',
                size_value_name,
            )
            if rect_match:
                length = int(rect_match.group(1))
                width = int(rect_match.group(2))
                dim_unit = shop.sudo().dimensions_unit_pref or 'cm'
                result['item_length'] = length
                result['item_width'] = width
                result['item_dimensions_unit'] = dim_unit
    except Exception as exc:  # noqa: BLE001 - parse failure resilience
        _logger.warning(
            "Failed to extract dimensions for product.template id=%s: %s",
            tmpl.id, exc,
        )

    return result
```

**Plug into `_build_create_draft_payload`** after materials block (current line 167 — right before `return payload`). Note: payload builder shadows args with `s = tmpl.sudo()` and `sh = shop.sudo()` locals; reuse them:

```python
# Spec 011 P-PUB-WEIGHT-DIMENSIONS - weight + dimensions
payload.update(self._collect_weight_and_dimensions(s, sh))
```

Helper takes already-sudo'd inputs (matches `_collect_materials(s)` convention).

---

## 5. View File

`custom_addons/etsy_integration/views/etsy_shop_views.xml` — add new inherited view (or extend existing inherited form):

```xml
<record id="etsy_shop_form_weight_dimensions" model="ir.ui.view">
  <field name="name">etsy.shop.form.weight.dimensions</field>
  <field name="model">etsy.shop</field>
  <field name="inherit_id" ref="etsy_integration.view_etsy_shop_form"/>
  <field name="arch" type="xml">
    <xpath expr="//page[@name='publisher_defaults']" position="inside">
      <group string="Etsy Publisher Unit Preferences" groups="base.group_system">
        <field name="weight_unit_pref"/>
        <field name="dimensions_unit_pref"/>
      </group>
    </xpath>
  </field>
</record>
```

Verify exact `inherit_id` ref and xpath anchor in Phase 3 (read current `etsy_shop_views.xml` first; "Publisher Defaults" group was landed by P-PUB-CLIENT T004).

---

## 6. Phase 1 DB Tests

`test_phase1_pub_weight_dimensions_db.py`:

1. `test_weight_unit_pref_column_exists` — `information_schema.columns`: column on `etsy_shop`, type `character varying`.
2. `test_dimensions_unit_pref_column_exists` — same for `dimensions_unit_pref`.
3. `test_weight_unit_pref_default_oz` — minimal `etsy.shop` ORM create; assert default `'oz'`.
4. `test_dimensions_unit_pref_default_cm` — minimal ORM create; assert default `'cm'`.

---

## 7. Phase 2 ORM Tests (>=8)

`test_phase2_pub_weight_dimensions_orm.py` (TransactionCase):

1. **test_weight_kg_to_oz_conversion** — tmpl.weight=0.35, shop pref 'oz' → `{'item_weight': round(0.35*35.274, 2), 'item_weight_unit': 'oz'}` (= 12.35).
2. **test_weight_kg_to_g_conversion** — tmpl.weight=0.5, shop pref 'g' → `{'item_weight': 500.0, 'item_weight_unit': 'g'}`.
3. **test_weight_zero_omitted** — tmpl.weight=0 → returned dict has NO `item_weight`/`item_weight_unit` keys.
4. **test_weight_negative_omitted** — tmpl.weight=-0.1 → same; no crash, no weight keys.
5. **test_dimensions_rect_pattern_R30X18** — Size value `R30X18`, shop dim 'cm' → `{'item_length': 30, 'item_width': 18, 'item_dimensions_unit': 'cm'}`.
6. **test_dimensions_inch_unit_no_leading_R** — Size value `12X18`, shop dim 'in' → `{'item_length': 12, 'item_width': 18, 'item_dimensions_unit': 'in'}`.
7. **test_no_size_axis_dimensions_omitted** — template w/o Size attribute line, weight=0.25 oz pref → only weight keys present.
8. **test_size_value_non_rect_pattern_omits_dimensions** — Size value `11 oz` (Mug family) → only weight keys; no dimension keys.
9. **test_payload_integration_create_draft** — full call to `_build_create_draft_payload(...)` returns payload containing both weight + dimension keys for a Rect-family template with weight set.
10. **test_sibling_keys_preserved** — regression: `materials` / `tags` / `property_values` keys still present alongside new weight/dimension keys.

**Fixture reuse**: mirror `test_phase2_pub_variant_properties_orm.py` (sibling, landed 2026-05-27, commit `9ce4e93df1d`). Create Size attribute axis if not already in test DB; create attribute value `R30X18` ad-hoc per test.

---

## 8. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| 1 | Size attribute value formats in real seed differ from `R30X18` (case, separator) | Medium | Parse failure → dimensions silently omitted | Regex tolerates `[Rr]?` leading + ASCII `x/X` + Unicode `×`. Tests #5, #6, #8 cover. Phase 3 read `multichannel_hub_core/data/sku_attribute_seed.xml` for real Size values. |
| 2 | `product.template.weight` NULL in DB | High | None — `or 0.0` covers; test #3 / #4 verify | Coalesce in helper. |
| 3 | Existing shop rows have NULL `weight_unit_pref` after upgrade | Medium | First read returns NULL → fallback `'oz'` via `or 'oz'` in helper | Inline fallback; no migration script needed. |
| 4 | Etsy 400 if `item_length` sent without `item_dimensions_unit` (or vice versa) | Low | Listing fail | Helper emits all three dimension keys together or none — atomic block. |
| 5 | Size axis named differently (code/namespace not 'Size') | Medium | Axis not detected → dimensions omitted | Tracker text says "Size variant attribute". Phase 3: grep seed for `name="Size"`. |
| 6 | Mug Size values are numeric-only (e.g., `11 oz`) — must NOT produce dimension keys | High by design | If regex too loose, false-positive | Regex requires `\d+` then `[xX×]` then `\d+`; `11 oz` lacks the separator. Test #8 explicit. |
| 7 | Rounding precision drift (0.35 kg * 35.274 = 12.3499... → round(…,2) = 12.35 not 12.4 as tracker hinted) | Low | Test expectation needs care | Tracker said "12.4" loosely; correct value is 12.35. Document in commit body if owner expected 12.4. |
| 8 | `_build_create_draft_payload` signature: positional vs kwargs vs `self` binding | Low | Wire-up break | Phase 3 reads file first; insertion line cited in plan §4. |
| 9 | View xpath target `//group[@string='Publisher Defaults']` may not match (group not present or different string) | Low | XML parse error on install | Phase 3 reads current views file; adjust xpath. |

---

## 9. Agent Dispatch Order (9-Phase Loop)

| Phase | Agent / Actor | Output |
|-------|--------------|--------|
| 0 Dispatch | orchestrator (done) | Tasks created, env verified |
| 1 Plan | planner (done) | This file |
| 2 RED | tdd-guide | Failing Phase 1 + Phase 2 tests; **orchestrator MUST run suite to confirm RED** with `--http-port=8170` (memory 134) |
| 3 GREEN | orchestrator | Implement shop fields + service method + view + manifest bump |
| 4 Review | code-reviewer ∥ security-reviewer (single message, two `Agent` calls) | Block on CRITICAL/HIGH |
| 5 Verify | orchestrator | `-u etsy_integration --stop-after-init`, run test-tags (port 8170), ruff, debug-statement grep |
| 6 Commit | orchestrator | One conventional commit on `feature/006-master-plan-coding` |
| 7 Document | orchestrator | Tracker state→done, findings.md if surprises, decision-log entry |
| 8 Learn | orchestrator + /learn | Capture surprises (rect-pattern nuances, Size axis naming) |
| 9 Land | (deferred to W7 E2E sprint) | Merge to main |

---

## 10. Exit Criteria (machine-checkable)

| Criterion | Verification |
|-----------|-------------|
| Tasks `[X]` in tracker | n/a — tracker row 339 is source of truth (sibling P-PUB-VARIANT-PROPERTIES precedent) |
| Tests pass; >=80% changed-line coverage | `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags etsy_integration --http-port=8170 --stop-after-init` exit 0; new tests appear GREEN |
| Module installs cleanly | `docker exec namco_odoo19 odoo -u etsy_integration --stop-after-init` exit 0 |
| ACLs / sudo / raw SQL | No new model (ACL N/A); helper `sudo()` reads documented; no raw SQL |
| Tracker state updated | Row 339 → `done`, commit SHA in summary cell |
| /learn captured | Auto-memory or explicit "no new patterns" note |
| findings.md updated on surprise | Append under P-PUB-WEIGHT-DIMENSIONS section |

---

## 11. Manifest Bump

`__manifest__.py`:
- `'version': '19.0.2.22.0'` → `'version': '19.0.2.23.0'`
- No new `data` entries (shop fields ORM-only; existing `views/etsy_shop_views.xml` already in data list).

---

## 12. Surprises to Watch For

- Real Size attribute value format in `sku_attribute_seed.xml` (case, separator, leading char).
- `_build_create_draft_payload` parameter names and `self`/staticmethod binding.
- "Publisher Defaults" xpath anchor existence in current `etsy_shop_views.xml`.
- Rounding of 0.35 kg → 12.35 oz vs tracker's loosely-stated 12.4. Test asserts the mathematically correct value.

---

## 13. FR-017 & Security Notes

- FR-017: N/A this slice (no new `action_*` methods; helper is read-only).
- BA gate: lives upstream in `etsy_publish_wizard._check_ba_or_raise()` (already shipped P-PUB-PUBLISH T024).
- Helper uses `sudo()` for cross-ACL reads of template/shop attributes; commented inline.
- New shop fields `groups='base.group_system'` to prevent BA from remapping units.
