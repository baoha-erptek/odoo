# P4-01-D — Gearment UI surfaces (D3 + D4 + D5)

**Slice ID**: P4-01-D
**Sub-phase of**: P4-01 (final sub-phase)
**Branch**: `feature/006-master-plan-coding`
**Depends on**: P4-01-C ✓ (state machine + wizard wired)
**Estimated**: ~190 LOC including tests
**Phase 1 author**: planner agent (Sonnet) 2026-05-10

---

## 1. Decisions

| ID | Choice | Rationale |
|---|---|---|
| DD1 — `sale.order.line` _inherit location | DD1.a: new file `mhf/models/sale_order_line.py` | Separation of concerns: sale_order owns state machine; sale_order_line owns the bulk action method |
| DD2 — D3 progress mechanism | DD2.a: `bus.bus.sendmany` | Real-time UX; small payload (~50 bytes/order); matches plan §3 D3 |
| DD3 — bulk error handling | DD3.c: per-order savepoint + summary | Allows partial success; mirrors P1-DASH-MERGE bulk-mark-shipped pattern |
| DD4 — D5 visibility expression | DD4.b: Odoo 19 native `invisible="…"` | Cleanest; avoids storing a computed `x_show_*` field |
| DD5 — D4 field references | DD5.a: flat names via `_inherits` delegation | Standard Odoo pattern; auto-resolves via P1-05 fulfillment mixin |

---

## 2. File-by-file change list

| File | Type | Scope | LOC |
|---|---|---|---|
| `mhf/models/sale_order_line.py` | NEW (D3) | `_inherit = 'sale.order.line'` + `action_gearment_bulk_sync()`. Dedupes via `mapped('order_id')`; per-order `cr.savepoint`; bus.bus progress; FR-017 12th confirmation `_check_ba_shipping_or_raise()` BEFORE any sudo. | 90 |
| `mhf/models/__init__.py` | EDIT | `from . import sale_order_line` | +1 |
| `mhf/views/sale_order_views.xml` | NEW (D5) | Form view inheritance: "Sync to Gearment" header button (group_ba_shipping, visibility per DD4.b) calling `action_get_gearment_quote`; new "Gearment" notebook tab showing state + quote breakdown JSON + expires-at. | 60 |
| `mhc/views/operations_dashboard_views.xml` | EDIT (D3) | New `ir.actions.server` `action_server_gearment_bulk_sync` binding to `sale.order.line`. State='code' calls `records.action_gearment_bulk_sync()`. | +25 |
| `etsy_integration/views/sale_order_views.xml` | EDIT (D4) | Inside existing Etsy tab, append read-only "Shipping Tracking" group with 5 fields (`tracking_number`, `shipping_carrier_id`, `tracking_state`, `shipping_date`, `tracking_url`). | +20 |
| `mhf/__manifest__.py` | EDIT | Bump 19.0.1.0.17 → 19.0.1.0.18; add `views/sale_order_views.xml` to data list. | +2 |
| `mhf/tests/test_p4_01_d_db.py` | NEW (RED) | Phase 1 view-arch: button + Gearment tab xpath; Etsy-tab Shipping subsection xpath + readonly attr; server action exists with right binding. | 80 |
| `mhf/tests/test_p4_01_d_orm.py` | NEW (RED) | Phase 2 ORM: bulk action dedup + savepoint isolation + FR-017 gate + bus.bus call count. | 110 |
| `mhf/tests/__init__.py` | EDIT | Register new test modules | +2 |

---

## 3. Slice tasks (for tasks.md)

```
- [ ] T4-01-D-01 RED Phase 1 view-arch: D5 button exists with group_ba_shipping + correct visibility expr
- [ ] T4-01-D-02 RED Phase 1 view-arch: D5 Gearment notebook tab + state + breakdown + expires-at fields
- [ ] T4-01-D-03 RED Phase 1 view-arch: D4 Etsy tab Shipping subsection — 5 fields readonly
- [ ] T4-01-D-04 RED Phase 1 view-arch: D3 server action exists + binding_model_id=sale.order.line + binding_view_types='list'
- [ ] T4-01-D-05 RED Phase 2 ORM: bulk action dedupes orders via mapped('order_id')
- [ ] T4-01-D-06 RED Phase 2 ORM: savepoint isolation — one order failure does not roll back others
- [ ] T4-01-D-07 RED Phase 2 ORM: FR-017 12th gate — non-shipping user raises AccessError before any write
- [ ] T4-01-D-08 RED Phase 2 ORM: bus.bus.sendmany called once per unique order
- [ ] T4-01-D-09 GREEN: mhf/models/sale_order_line.py with action_gearment_bulk_sync + helpers
- [ ] T4-01-D-10 GREEN: mhf/views/sale_order_views.xml form button + Gearment notebook tab
- [ ] T4-01-D-11 GREEN: mhc/views/operations_dashboard_views.xml server action + binding
- [ ] T4-01-D-12 GREEN: etsy_integration/views/sale_order_views.xml Shipping subsection
- [ ] T4-01-D-13 GREEN: __init__.py + manifest 19.0.1.0.18 bump + view list
- [ ] T4-01-D-14 code-reviewer + security-reviewer parallel; block on CRITICAL/HIGH
- [ ] T4-01-D-15 Verify: -u mhf + mhc + etsy_integration --stop-after-init exit 0; full test tags green; grep _logger.info/print
- [ ] T4-01-D-16 Tracker P4-01-D → done; P4-01 parent row split→done; findings.md §"P4-01-D" with FR-017 12th confirmation
```

---

## 4. Risks

| Risk | P | I | Mitigation |
|---|---|---|---|
| Bulk-action partial failure UX confusing | M | M | Final summary message names failed orders; chatter on each order records the failure |
| D4 readonly bypass via RPC | L | M | Field-level `readonly=True` in mhc model + ACL on sale.order.fulfillment; UI readonly is sugar |
| D5 button visible on order with no Gearment-eligible lines | M | L | Server-side guard in `action_get_gearment_quote` raises with clear message |
| `bus.bus.sendmany` payload size at 100+ orders | L | L | ~50 bytes/order; 5 KB total at 100 — well within bus design |
| D3 + D4 cross-module wiring breaks | L | M | mhf depends on mhc; mhc.sale.order.line + mhf.sale.order.line both inherit cleanly per Odoo MRO |
| FR-017 12th confirmation mismatch with 11th in wizard | L | M | Helper duplicated into sale_order_line.py (same pattern as P4-01-C wizard); both gate `sudo()` writes |

---

## 5. Phase 2..9 hand-off

1. Phase 2 RED — author 2 test files; verify all fail for the right reasons
2. Phase 3 GREEN — D3 → D4 → D5 in order (D3 establishes the bulk-action method; D4/D5 are independent UI)
3. Phase 4 Review — parallel agents
4. Phase 5 Verify — cross-module install + full test tags
5. Phase 6 Commit — RED + GREEN + docs commits
6. Phase 7 Document — tracker P4-01-D → done; P4-01 parent split → done; findings §"P4-01-D"
7. Phase 8 Learn — FR-017 12th confirmation captured; parallel UI surface dispatching pattern
