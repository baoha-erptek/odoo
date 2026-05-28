# P2-05 Phase-1 Tactical Plan — `shipping.carrier` admin UX + extended seed (US5)

**Slice**: P2-05 (Spec 004a US5)
**Branch**: `feature/006-master-plan-coding`
**Module**: `multichannel_hub_core` (model + ACL + view + seed XML)
**Dependencies**: P2-02 ✓
**Authored**: 2026-05-09 (planner agent + orchestrator review)

---

## Spec Drift Check

Verified against `multichannel_hub_core/models/shipping_carrier.py`,
`security/ir.model.access.csv`, `data/shipping_carrier_data.xml`,
`views/shipping_carrier_views.xml`, and
`multichannel_hub_fulfillment/services/carrier_detector.py`.

| AS | Spec text | Code today | Action |
|---|---|---|---|
| AS1 | Form requires `name` + `code` + at-least-one of (`tracking_prefix_regex`, `etsy_carrier_name`) | Constraints exist for name/code/code-unique/regex-safe; **no at-least-one constraint** | Add `@api.constrains('tracking_prefix_regex','etsy_carrier_name')` |
| AS2 | Non-`group_system` user blocked on write/create/unlink | ACL grants `sales_team.group_sale_manager` full R/W/C/U; **no system-only ACL** | Tighten ACL: manager → read-only; add `base.group_system` row; layer with model `write/create/unlink` override (FR-017 14th confirmation) |
| AS3 | Extended seed `noupdate="1"` (admin edits persist across upgrades) | `<odoo noupdate="0">` (line 2 of `shipping_carrier_data.xml`) — **all 8 seed rows are re-written on every upgrade** | Flip to `noupdate="1"` |
| AS4 | `is_active=False` → detector skips; existing references render | `carrier_detector._compiled_cache_for` (line 42) + `_other_carrier()` (line 102) both filter `is_active=True` | No code change; test only |

## Files to Modify / Create

| File | Action |
|---|---|
| `models/shipping_carrier.py` | + `_check_at_least_one_mapping()` constrains; + `write/create/unlink` overrides with `_check_group_system_or_raise()` |
| `data/shipping_carrier_data.xml` | line 2: `noupdate="0"` → `noupdate="1"` |
| `security/ir.model.access.csv` | manager row downgrade `1,1,1,1` → `1,0,0,0`; add `access_shipping_carrier_system` row `1,1,1,1` |
| `views/shipping_carrier_views.xml` | optional: add field `help` text clarifying AS1 (non-functional) |
| `tests/test_phase1_shipping_carrier_p2_05.py` | NEW — 3 DB schema checks (write override exists, noupdate seed, ACL CSV has system row) |
| `tests/test_phase2_shipping_carrier_p2_05.py` | NEW — 12 ORM tests (constraint + ACL + detector + chatter) |
| `tests/test_phase2_shipping_carrier_orm.py` | Existing — may need adjustment if any test uses non-admin user; admin is `group_system` in tests so likely no break |
| `__manifest__.py` | bump version 19.0.1.0.X |

## Risk Callouts

1. **ACL tightening blast radius**: existing tests use `self.env['shipping.carrier'].create({...})` from default admin user. Admin is `base.group_system` in test envs — should not break. Verify by running the full mhc + mhf test suite after the change. If a test uses `self.env(user=non_admin)` for carrier creation, it will need updating to use admin or to expect AccessError.
2. **Constraint ordering**: `_check_at_least_one_mapping()` runs alongside `_check_tracking_prefix_regex_safe()`. Empty regex is treated as "not provided" by AS1, so an empty regex + no etsy_name should fail AS1 (no etsy mapping) before regex-safe ever fires (regex is empty → skipped early-return). Test both error paths separately.
3. **noupdate flip is one-way**: future seed-row additions will REPLACE existing rows on first install only; subsequent upgrades preserve admin edits. Document in commit body. No data migration needed.
4. **Defense-in-depth (FR-017 pattern)**: ACL alone is bypassable via `sudo()` in custom code. Adding model `write/create/unlink` gates is the canonical project pattern (14th confirmation per memory). Detector services already use `sudo()` to read carriers — that's reads, unaffected by write gate.
5. **Extended seed scope**: Spec AS3 says "seed data this spec adds beyond Spec 003's initial set". Current XML already has 8 carriers. We are NOT adding new seed rows in P2-05 — only flipping the `noupdate` flag. Document in commit body that "extended seed" is satisfied by the noupdate flip + the model becoming admin-editable (admins can add new carriers via UI without a code release per US5 acceptance scenario).

## Phase 2 — RED Tests (T2-05-01..T2-05-15)

Exposed in `tasks.md` block. Two new test files:
- `test_phase1_shipping_carrier_p2_05.py` — 3 DB-level checks
- `test_phase2_shipping_carrier_p2_05.py` — 12 ORM tests

## Phase 3 — GREEN Skeleton

```python
# shipping_carrier.py — additions

@api.constrains('tracking_prefix_regex', 'etsy_carrier_name')
def _check_at_least_one_mapping(self):
    """US5 AS1: every carrier must declare at least one detection mapping —
    a tracking-number regex (used by P2-02 detector) or an Etsy carrier
    name (used by future Spec 005 tracking push). A carrier with neither
    is unreachable from any auto-routing path and likely a data-entry error.
    """
    for record in self:
        regex = (record.tracking_prefix_regex or '').strip()
        etsy = record.etsy_carrier_name
        if not regex and not etsy:
            raise ValidationError(_(
                "Shipping carrier %(name)s must have at least one of: "
                "Tracking Prefix Regex or Etsy Carrier Name.",
                name=record.name or record.code or '?',
            ))

def _check_group_system_or_raise(self):
    """US5 AS2: master-carrier data is admin-only. Sales managers can
    READ via ACL but cannot mutate — protects the seed-driven detector
    pipeline from accidental misconfig by non-admin users.
    Defense-in-depth above the CSV ACL (FR-017 pattern, 14th confirmation).
    """
    if not self.env.user.has_group('base.group_system'):
        raise AccessError(_(
            "Only system administrators can edit shipping carriers."))

@api.model_create_multi
def create(self, vals_list):
    self._check_group_system_or_raise()
    return super().create(vals_list)

def write(self, vals):
    self._check_group_system_or_raise()
    return super().write(vals)

def unlink(self):
    self._check_group_system_or_raise()
    return super().unlink()
```

```csv
# ir.model.access.csv — diff
- access_shipping_carrier_manager,shipping.carrier manager,model_shipping_carrier,sales_team.group_sale_manager,1,1,1,1
+ access_shipping_carrier_manager,shipping.carrier manager,model_shipping_carrier,sales_team.group_sale_manager,1,0,0,0
+ access_shipping_carrier_system,shipping.carrier system,model_shipping_carrier,base.group_system,1,1,1,1
```

```xml
<!-- shipping_carrier_data.xml line 2 -->
- <odoo noupdate="0">
+ <odoo noupdate="1">
```

## Agent Dispatch Order

1. **Phase 2 (RED)**: `tdd-guide` — write Phase 1 + Phase 2 failing tests; verify FAIL for the right reasons
2. **Phase 3 (GREEN)**: orchestrator inline (small surface, well-specified)
3. **Phase 4 (Review)**: `code-reviewer` + `security-reviewer` parallel
4. **Phase 5–8 (Verify/Commit/Document/Learn)**: orchestrator inline

## Exit Criteria → Tasks

| Exit criterion | Task |
|---|---|
| All T2-05-* `[X]` | T2-05-29 |
| Tests pass + coverage ≥80% on changed | T2-05-23 + T2-05-24 |
| Module installs clean | T2-05-22 |
| ACL tightened for new gating | T2-05-21 (review) |
| Tracker `state=done` | T2-05-31 |
| `/learn` captured | T2-05-33 |
| `findings.md` updated | T2-05-32 |
