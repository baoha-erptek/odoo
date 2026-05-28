# P-PUB-VARIANT-PROPERTIES — Implementation Plan

**Authored**: 2026-05-27 (planner agent dispatch, orchestrator wrote file)
**Slice**: P-PUB-VARIANT-PROPERTIES (Tracker row 338, MP006)
**Branch**: `feature/006-master-plan-coding`
**Estimated LOC**: ~150

---

## 1. Module Placement Decision

**Decision**: Add `x_etsy_property_id` and `x_publish_as_property` to `product.attribute` via **etsy_integration** module (new model file).

**Rationale**:
- Both fields are Etsy-specific in current scope (property_id is an Etsy attribute taxonomy ID; x_publish_as_property gates Etsy publish only).
- `multichannel_hub_core` extends `product.attribute.value` (for SKU grammar) but does NOT extend `product.attribute` itself.
- Channel-specific taxonomy mappings stay in the channel module; channel-agnostic data (roles, groups) stays in mhc.
- If future publishers (Amazon, Website) need similar property_id mapping, define abstract base in mhc and subclass per channel. Defer until needed.

**Standard-Odoo-First check**: `grep -rn` in `addons/product/` — no existing fields cover this. Custom fields confirmed required.

---

## 2. File List

| File | Type | Change |
|------|------|--------|
| `custom_addons/etsy_integration/models/product_attribute.py` | New | Inherit `product.attribute`, add 2 new fields |
| `custom_addons/etsy_integration/models/__init__.py` | Edit | Add `from . import product_attribute` |
| `custom_addons/etsy_integration/views/product_attribute_views.xml` | New | Inherit attribute form, expose 2 fields, system-group restricted |
| `custom_addons/etsy_integration/services/etsy_listing_publisher.py` | Edit | New static `_collect_property_values(variant)` + 1-line plug into `push_inventory` |
| `custom_addons/etsy_integration/tests/test_phase1_pub_variant_properties_db.py` | New | Phase 1 DB schema tests |
| `custom_addons/etsy_integration/tests/test_phase2_pub_variant_properties_orm.py` | New | Phase 2 ORM tests (≥6 cases) |
| `custom_addons/etsy_integration/tests/__init__.py` | Edit | Register both test files (memory note: tdd-guide forgets) |
| `custom_addons/etsy_integration/__manifest__.py` | Edit | Bump `19.0.2.21.0` → `19.0.2.22.0`; add view + seed XML to data list |
| `custom_addons/etsy_integration/data/etsy_attribute_defaults.xml` | New | Seed `x_publish_as_property=True` defaults for known attribute records |

**No migration file**: Both fields are new columns; ORM-level default=True handles new rows. Existing rows: see Risk #4.

---

## 3. Model File Details

```python
# product_attribute.py
from odoo import models, fields

class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    x_etsy_property_id = fields.Char(
        string="Etsy Property ID",
        help="Etsy attribute taxonomy ID for this axis. Stored as Char to avoid "
             "XML-RPC int32 overflow on large Etsy IDs. Discover via "
             "GET /v3/application/seller-taxonomy/nodes/{taxonomy_id}/properties.",
    )
    x_publish_as_property = fields.Boolean(
        string="Publish as Etsy property",
        default=True,
        help="If True, this attribute axis is sent in Etsy push_inventory "
             "products[].property_values[]. Disable for SKU-only axes like Family.",
    )
```

No methods, no constraints — fallback to attribute name with WARNING log handles missing property_id.

---

## 4. Service Method (etsy_listing_publisher.py)

**New static method** placed after `_collect_materials`:

```python
@staticmethod
def _collect_property_values(variant):
    """Build Etsy products[].property_values[] for a single variant.

    Walks variant.product_template_attribute_value_ids (per-variant M2M).
    For each axis flagged x_publish_as_property=True:
        - property_id: int(x_etsy_property_id) when numeric, else the string
        - values: [attribute_value.name]

    Returns [] when M2M is empty (dynamic-variant trap: variant has no
    selected combination until purchase) — Etsy accepts empty per
    existing line 247 baseline today.

    Logs WARNING and falls back to attribute name when x_etsy_property_id
    is empty.
    """
    properties = []
    seen_axis_ids = set()
    for ptav in variant.product_template_attribute_value_ids:
        axis = ptav.attribute_id
        if not axis.x_publish_as_property or axis.id in seen_axis_ids:
            continue
        seen_axis_ids.add(axis.id)
        prop_id_raw = axis.x_etsy_property_id
        if not prop_id_raw:
            _logger.warning(
                "product.attribute id=%s name=%r missing x_etsy_property_id; "
                "falling back to attribute name",
                axis.id, axis.name,
            )
            prop_id = axis.name
        else:
            prop_id = int(prop_id_raw) if prop_id_raw.isdigit() else prop_id_raw
        properties.append({
            'property_id': prop_id,
            'values': [ptav.product_attribute_value_id.name],
        })
    return properties
```

**Plug into `push_inventory`** (current line ~247 replace `'property_values': []`):

```python
'property_values': self._collect_property_values(variant),
```

`self` is the static-method-bearing class — confirm whether `EtsyListingPublisher.push_inventory` is staticmethod or instance method in current code. If static, call via `EtsyListingPublisher._collect_property_values(variant)`.

---

## 5. View File

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
  <record id="product_attribute_form_etsy_extension" model="ir.ui.view">
    <field name="name">product.attribute.form.etsy</field>
    <field name="model">product.attribute</field>
    <field name="inherit_id" ref="product.product_attribute_view_form"/>
    <field name="arch" type="xml">
      <xpath expr="//sheet" position="inside">
        <group string="Etsy Publisher Settings" groups="base.group_system">
          <field name="x_publish_as_property"/>
          <field name="x_etsy_property_id"
                 invisible="not x_publish_as_property"/>
        </group>
      </xpath>
    </field>
  </record>
</odoo>
```

**Note**: Use Odoo 19 attribute syntax `invisible="not x_publish_as_property"` (NOT legacy `attrs={...}`). Verify inherit_id ref against actual addons/product XML id.

---

## 6. Seed Data

`custom_addons/etsy_integration/data/etsy_attribute_defaults.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
  <!-- Seed publish defaults for known mhc-seeded attributes.
       External IDs come from multichannel_hub_core/data/sku_attribute_seed.xml.
       noupdate=1 so admin edits persist across upgrades. -->
  <record id="multichannel_hub_core.attribute_material" model="product.attribute">
    <field name="x_publish_as_property">True</field>
  </record>
  <!-- Repeat for Color, Size, Shape, Fluid oz, Apparel size as True;
       Family/non-variant axes set to False. Planner: confirm xml-ids by
       reading multichannel_hub_core/data/sku_attribute_seed.xml in Phase 3. -->
</odoo>
```

The exact list of XML-ids must be verified in Phase 3 by reading the seed file before committing.

---

## 7. Phase 1 DB Tests

`test_phase1_pub_variant_properties_db.py`

1. `test_x_etsy_property_id_column_exists` — `information_schema.columns`: name + data_type IN (`character varying`, `text`)
2. `test_x_publish_as_property_column_exists` — boolean type
3. `test_x_publish_as_property_default_true_on_new_row` — INSERT minimal row, SELECT, assert True
4. (Optional) `test_no_unique_constraint_on_etsy_property_id` — duplicates allowed (multiple axes can share the same Etsy property_id technically, though uncommon)

Skip if Phase 2 ORM covers schema implicitly. Keep at least #1 + #2 for type assertion (catches typo / wrong field type drift).

---

## 8. Phase 2 ORM Tests (≥6)

`test_phase2_pub_variant_properties_orm.py` — `TransactionCase`:

1. **test_two_axes_publish_both** — template w/ Material+Color, variant has explicit ptav for both, both axes `x_publish_as_property=True`, both have x_etsy_property_id → 2 dicts in output, correct property_id (int) + values.

2. **test_axis_publish_false_excluded** — Material(True) + Family(False) → only Material in output.

3. **test_missing_property_id_warns_and_falls_back_to_name** — Material has no x_etsy_property_id → output uses attribute name as property_id; `with self.assertLogs(level='WARNING') as cm:` confirms warning logged. Per memory 148: filter level on `_logger.info` is WARNING; use logger.warning() which we do.

4. **test_dynamic_variant_empty_m2m_returns_empty** — variant.product_template_attribute_value_ids is empty (dynamic-variant trap, memory 150) → method returns `[]`. No crash.

5. **test_property_id_numeric_string_cast_to_int** — x_etsy_property_id='12345' → int(12345) in output; non-numeric ('abc') passes as string.

6. **test_push_inventory_embeds_property_values_per_offering** — full call with mocked EtsyApiClient; assert each products[] entry has non-default property_values (regression: ensures the `[]` literal replacement actually wired through).

7. (Bonus) **test_preserves_materials_and_tags_alongside_property_values** — sibling-slice regression check.

**Fixture reuse**: model after `test_phase2_pub_materials_payload_orm.py` (the P-PUB-MATERIALS test file just landed today, commit 80ae8a43a).

---

## 9. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| 1 | Dynamic-variant `product_template_attribute_value_ids` empty (memory 150) | High in test env (Material seed is `create_variant='dynamic'`) | Returns [] silently | Test #4 explicit. Use Color or Size (non-dynamic) in test #1 fixture, or force-create combination. Plan: read sku_attribute_seed.xml for create_variant values per attr before authoring test #1. |
| 2 | Etsy int32 overflow on property_id (memory 144) | Medium | API 500 | Char field type + isdigit() cast. JSON API tolerates large ints when serialized natively. |
| 3 | Etsy rejects empty `property_values: []` array | Low (today's code sends []) | Listing fail | Empty-array is current production behavior at line 247; not a regression. If discovered to be a bug separately, omit-key fix is one extra dict comprehension. |
| 4 | Seed `noupdate=1` does not backfill pre-existing attribute rows | Medium | Pre-deploy attrs default to True (Odoo default), Family axis stays True incorrectly | Manual admin step + a post-install migration script. Add to plan as Phase 7 doc note. ALTERNATIVELY: drop `noupdate=1` for first ship, then re-enable. Recommend: ship without noupdate, document upgrade ordering. |
| 5 | `EtsyListingPublisher.push_inventory` may be staticmethod (not bound) | Low | Call site `self._collect_property_values(variant)` fails | Verify method binding in Phase 3 before code edit. Use `EtsyListingPublisher._collect_property_values(variant)` (class-direct) if staticmethod. |
| 6 | View inherit_id `product.product_attribute_view_form` xml id wrong | Low | XML parse error on install | Verify in Phase 3 via `grep -rn "product_attribute_view_form\|product_attribute_form" addons/product/views/`. |

---

## 10. Agent Dispatch Order (9-Phase Loop)

| Phase | Agent / Actor | Output |
|-------|--------------|--------|
| 0 Dispatch | orchestrator (done) | Tasks created, env verified |
| 1 Plan | planner (done) | This file |
| 2 RED | tdd-guide | Failing Phase 1 + Phase 2 tests; **orchestrator MUST run suite to confirm RED** (memory: tdd-guide skips suite run) |
| 3 GREEN | orchestrator | Implement model + service + view + seed + manifest |
| 4 Review | code-reviewer ∥ security-reviewer (SINGLE message, two Agent calls) | Block on CRITICAL/HIGH |
| 5 Verify | orchestrator | `odoo -u etsy_integration --stop-after-init`, run test-tags (port 8170 per memory 134), ruff, debug-statement grep |
| 6 Commit | orchestrator | One conventional commit on feature/006-master-plan-coding |
| 7 Document | orchestrator | Tracker state→done, findings.md if surprises, decision-log entry |
| 8 Learn | orchestrator + /learn | Capture surprises (e.g., property_values empty-array behavior, dynamic-variant trap re-confirmation) |
| 9 Land | (deferred to W7 E2E sprint) | Merge to main |

---

## 11. Exit Criteria (machine-checkable)

| Criterion | Verification |
|-----------|-------------|
| Each tasks.md slice task `[X]` | n/a — tracker row is source of truth (sibling P-PUB-MATERIALS precedent) |
| Tests pass; ≥80% changed-line coverage | `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags etsy_integration --stop-after-init` exit 0; new tests appear in GREEN |
| Module installs cleanly | `docker exec namco_odoo19 odoo -u etsy_integration --stop-after-init` exit 0 |
| ACLs for new model | N/A — extending existing `product.attribute`; view groups=base.group_system |
| sudo() documented | N/A — no new sudo |
| Raw SQL commented | N/A — no new raw SQL |
| Tracker state updated | `.claude/plans/006-master-plan-tracking.md` row 338 → `done`, commit SHA in summary cell |
| /learn captured | Auto-memory entry or "no new patterns" note |
| findings.md updated if surprise | Append under P-PUB-VARIANT-PROPERTIES section |

---

## 12. Manifest Bump

`__manifest__.py`:
- `'version': '19.0.2.21.0'` → `'version': '19.0.2.22.0'` (single minor bump, no schema breakage)
- Add to `'data'` list (after security, before wizards):
  - `'data/etsy_attribute_defaults.xml'`
  - `'views/product_attribute_views.xml'`

Verify exact ordering vs existing manifest data list at Phase 3.

---

## 13. Surprises to Watch For

- Etsy API behavior on `property_values: []` (current baseline — does it actually ship today, or is the field silently dropped server-side?).
- `product_template_attribute_value_ids` M2M shape in test fixtures (Material is dynamic-variant per memory 150; pick Color or force-create combos).
- View xml inherit_id name in Odoo 19 product module.
- Whether `push_inventory` is staticmethod or instance method.

All four go into `findings.md` as discoveries during Phase 3/5.
