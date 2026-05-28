# P1-03 Tactical Plan — Tracking Dashboard for Shipping Ops

**Slice**: P1-03 (Spec 003 US2, Phase 1)
**Branch**: `feature/006-master-plan-coding`
**Author**: planner agent + main session synthesis
**Date**: 2026-04-29
**Status**: Phase 1 (planning) complete; Phase 2 (RED) next

---

## 1. Slice Goal

Deliver the **Tracking Dashboard** so BA-shipping operators can: (a) see all open fulfillments in one list with channel/carrier/tracking columns, (b) bulk-mark orders shipped while honoring the address-change approval gate from P1-04, (c) emit a `bus.bus` channel for future real-time updates. The dashboard is channel-agnostic and lives in `multichannel_hub_core`; `etsy_ship_notified_at` is the only Etsy-named field and lives in `etsy_integration`.

This slice is the second leg of the email-fallback E2E demo loop (after P1-01 Order Dashboard). Combined with P2-01 (Excel import wizard) it closes the inbound-tracking workflow.

---

## 2. Scope (T032–T039 + T061; T036 deferred)

### IN scope

| Task | Description |
|---|---|
| **T032** | Add missing fields to `sale.order.fulfillment` (mhc): `pd_pic_user_id`, `warehouse_zone`. `etsy_ship_notified_at` lives in **etsy_integration** as a `_inherit='sale.order.fulfillment'` extension (mhc Etsy-name prohibition). |
| **T033** | Verify C-SOF-001 constraint (`block_reason` required when `production_blocked=True`) exists; P1-05 status TBD. |
| **T034** | New `views/tracking_dashboard_views.xml` — list view + 13 columns + filters + action. |
| **T035** | Server action `action_bulk_mark_shipped` — silent-skip pending-address rows + post-action `display_notification` warning. |
| **T037** | `bus.bus` push hook on fulfillment write/create — channel `multichannel_hub.fulfillment_update`. |
| **T038** | Phase-2 test scaffolding (file paths + method names; tdd-guide writes assertions in Phase 2). |
| **T039** | Menu `Operations → Tracking Dashboard`. |
| **T061** | Address-change skip surfacing folded into T035 warning (deferred from P1-04 per tasks.md L119). |

### DEFERRED to P2-01 (Spec 004a US1 / new slice)

- **T036 — Excel export to GKE format**: spec 004a does not pin canonical GKE column order; sample file in `.0temp/` is an Etsy export, not GKE tracking. P2-01 owns the GKE schema definition (FR-001/FR-002 hash-fingerprinted at import). Designing T036 now risks divergence with P2-01. Re-attach T036 to the P2-01 slice (export ↔ import round-trip designed together).

**Owner ACK required** for the T036 deferral — flag in tracker change-log.

### Already on disk from P1-05 / P1-06 (no re-add in T032)

`tracking_number`, `shipping_carrier_id` (M2O→shipping.carrier), `shipping_date`, `label_status`, `tracking_state`, `mp_note` (tracking=True via P1-01a fix), `pd_note` (tracking=True via P1-01a fix), `pic_user_id`, `order_priority`, `production_blocked`, `block_reason`, `fulfillment_status`.

---

## 3. Module-Home Decisions

| Artifact | Module | Justification |
|---|---|---|
| `pd_pic_user_id` Many2one | `multichannel_hub_core` | Channel-agnostic; production team's PIC for any channel |
| `warehouse_zone` Selection (vn/us) | `multichannel_hub_core` | Logical warehouse, channel-agnostic |
| `etsy_ship_notified_at` Datetime | **`etsy_integration`** (sale.order.fulfillment `_inherit` extension) | mhc CLAUDE.md prohibits Etsy-named fields; stamped by Spec 005 EtsyTrackingPusher |
| `tracking_dashboard_views.xml` | `multichannel_hub_core` | Channel-agnostic UI; reused for Amazon/Website later |
| `action_bulk_mark_shipped` server action | `multichannel_hub_core` | Channel-agnostic state transition |
| `bus.bus` channel emit hook | `multichannel_hub_core` | On fulfillment write — model lives in mhc |
| Menu entry | `multichannel_hub_core` `views/menu_views.xml` | Operations menu owned by mhc |

---

## 4. Field Delta (T032 checklist)

| Field | Type | Already on disk? | Action |
|---|---|---|---|
| `tracking_number` | Char(index, tracking=True) | ✓ P1-05 (line 11 of `sale_order_fulfillment.py`) | Verify |
| `shipping_carrier_id` | M2O(shipping.carrier, index, tracking=True) | ✓ P1-06 | Verify |
| `shipping_date` | Date(tracking=True) | ✓ P1-05 | Verify |
| `label_status` | Selection(tracking=True) | ✓ P1-05 | Verify |
| `tracking_state` | Selection(tracking=True) | ✓ P1-05 | Verify |
| `mp_note` | Text(tracking=True) | ✓ P1-05 + P1-01a fix | Verify |
| `pd_note` | Text(tracking=True) | ✓ P1-05 + P1-01a fix | Verify |
| `pic_user_id` | M2O(res.users, index, tracking=True) | ✓ P1-05 | Verify |
| `order_priority` | Selection(tracking=True) | ✓ P1-05 | Verify |
| `production_blocked` | Boolean(tracking=True) | ✓ P1-05 | Verify |
| `block_reason` | Text(tracking=True) | ✓ P1-05 | Verify |
| `pd_pic_user_id` | M2O(res.users, index, tracking=True) | ✗ | **ADD** (mhc) |
| `warehouse_zone` | Selection [('vn','VN'),('us','US')](tracking=True) | ✗ | **ADD** (mhc) |
| `etsy_ship_notified_at` | Datetime | ✗ | **ADD** (etsy_integration `_inherit`) |

Verification step in Phase 2: read current `multichannel_hub_core/models/sale_order_fulfillment.py` first; confirm field list before tdd-guide writes RED tests.

---

## 5. Address-Change Exclusion Design (T035 + T061)

**Spec FR-017**: rows with `has_pending_address_change=True` are *excluded from the batch with an on-screen warning listing the skipped order references*.

**Decision**: silent-skip + post-action warning notification (NOT pre-flight UserError).

**Rationale**: spec wording "excluded…with warning" implies graceful skip not hard-fail. BA daily flow: select 20 rows, action processes 18, warning lists 2 to revisit. UserError would force manual deselection — friction.

**Implementation sketch**:

```python
def action_bulk_mark_shipped(self):
    """T035 + T061 — silent-skip pending-address rows + warning notification."""
    excluded = self.filtered('has_pending_address_change')
    to_process = self - excluded
    to_process.write({
        'shipping_date': fields.Date.context_today(self),
        'tracking_state': 'shipped',
    })
    if not excluded:
        return True
    excluded_refs = ', '.join(excluded.order_id.mapped('name'))
    return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'title': _('Shipped %(processed)d order(s); skipped %(skipped)d',
                       processed=len(to_process), skipped=len(excluded)),
            'message': _('Skipped (pending address-change approval): %s', excluded_refs),
            'type': 'warning',
            'sticky': True,
        },
    }
```

**ACL gate**: action runs as RPC, so an explicit `has_group` check at method entry blocks salesman-tier users (consistent with P1-04 RPC-gate pattern from security-reviewer P1-04 finding). Group: `multichannel_hub_core.group_production_team` OR `base.group_system`.

---

## 6. bus.bus Channel (T037)

| Aspect | Value |
|---|---|
| Channel name | `multichannel_hub.fulfillment_update` |
| Emitted from | `sale.order.fulfillment.write()` override + `@api.model_create_multi` create override |
| Payload | `{fulfillment_id, order_id, order_name, tracking_number, tracking_state, label_status, updated_by, updated_at}` |
| Web client subscription | **OUT of scope** — declared only; UI subscription lands later |

**Implementation note**: use `self.env['bus.bus']._sendone(channel, 'fulfillment_update', payload)` per Odoo 19 bus API. Verify signature in Phase 2 (`bus.bus._sendone` vs `_sendmany` — Odoo 19 may have deprecated one).

---

## 7. Tracking Dashboard List View (T034)

**13 columns** per spec US2 acceptance §1:

1. order_id.partner_id.name (Buyer)
2. order_id.x_etsy_shop_id.name OR sales_channel-aware shop label (Shop)
3. order_id.sales_channel (Channel — badge decoration)
4. tracking_number (indexed search)
5. shipping_carrier_id.name (Carrier)
6. shipping_date
7. label_status (badge)
8. tracking_state (badge — merged column per FR-008)
9. order_id.has_pending_address_change (boolean icon)
10. order_id.is_overdue_approval (overdue marker — from P1-01a)
11. warehouse_zone
12. order_id.order_priority (badge)
13. pd_note (truncated)

**Filters**: sales_channel, label_status, warehouse_zone, has_pending_address_change, tracking_number search.
**Default sort**: `shipping_date DESC NULLS LAST`.
**Pagination**: server-side, limit=80.

**Action**: `multichannel_hub_core.action_tracking_dashboard` (`ir.actions.act_window` on `sale.order.fulfillment`).

---

## 8. ACL Plan

Existing P1-05 ACL on `sale.order.fulfillment` covers:
- `sales_team.group_sale_salesman` — read
- `multichannel_hub_core.group_production_team` (P1-02a) — read+write
- `base.group_system` — full

No ACL row changes in P1-03. RPC gate on `action_bulk_mark_shipped` at method entry (P1-04 pattern).

---

## 9. Test Plan

### Phase 1 (DB) — `multichannel_hub_core/tests/test_tracking_dashboard_db.py`

1. `test_pd_pic_user_id_column_exists` — query `information_schema.columns` for `pd_pic_user_id_id`, type `integer`.
2. `test_warehouse_zone_column_exists` — column `warehouse_zone`, type `varchar`, NULL allowed (no default override).
3. `test_etsy_ship_notified_at_column_exists` — column `etsy_ship_notified_at`, type `timestamp without time zone`. (Extension lives in etsy_integration; verify post-install of both modules.)
4. `test_tracking_number_btree_index_exists` — pg_indexes lookup for index on `tracking_number` (already from P1-05; regression guard).
5. `test_c_sof_001_constraint_present` — `_constraint_methods` includes `_check_block_reason_required_when_blocked`.

### Phase 2 (ORM) — `multichannel_hub_core/tests/test_tracking_dashboard.py`

1. `test_bulk_mark_shipped_excludes_pending_address` — 2 fulfillments; one parent has approved address-change request, other has pending; bulk action only writes to non-pending; pending row state unchanged.
2. `test_bulk_mark_shipped_warning_notification_payload` — selection has 1 pending; assert return dict `tag='display_notification'`, `params.type='warning'`, `params.message` includes order name.
3. `test_bulk_mark_shipped_no_pending_returns_true` — clean selection; method returns `True`, no notification dict.
4. `test_bulk_mark_shipped_rpc_gate_blocks_salesman` — salesman user calls action, raises `AccessError`.
5. `test_search_by_tracking_number_uses_index` — search by tracking_number, assert returns recordset; performance not asserted (E2E sprint owns).
6. `test_bus_push_emitted_on_write` — patch `env['bus.bus']._sendone`; trigger write on tracking_state; assert called once with channel name + payload includes fulfillment_id.
7. `test_bus_push_emitted_on_create` — `@api.model_create_multi` path; assert one bus event per record.
8. `test_warehouse_zone_filter_works` — search by `[('warehouse_zone','=','vn')]`.

### etsy_integration Phase 2 — extend existing `test_sale_order_fulfillment.py`

9. `test_etsy_ship_notified_at_writable_via_inherit` — etsy_integration extension surfaces field on the same recordset; write succeeds.

**Coverage target**: ≥80% on new methods + view file (action code).

---

## 10. File Touch List (commit order)

1. `multichannel_hub_core/models/sale_order_fulfillment.py` — add `pd_pic_user_id`, `warehouse_zone`; add `action_bulk_mark_shipped`; add `write()` + `create()` overrides for bus push.
2. `multichannel_hub_core/views/tracking_dashboard_views.xml` — NEW (list view + action + server action XML).
3. `multichannel_hub_core/views/menu_views.xml` — add Operations → Tracking Dashboard menu (Operations menu already created in P1-01a).
4. `multichannel_hub_core/__manifest__.py` — register new view file.
5. `multichannel_hub_core/security/ir.model.access.csv` — verify (no change expected).
6. `multichannel_hub_core/tests/test_tracking_dashboard_db.py` — NEW.
7. `multichannel_hub_core/tests/test_tracking_dashboard.py` — NEW.
8. `multichannel_hub_core/tests/__init__.py` — register new test files.
9. `etsy_integration/models/sale_order_fulfillment.py` — NEW or extend (`_inherit='sale.order.fulfillment'`) — add `etsy_ship_notified_at`.
10. `etsy_integration/__manifest__.py` — wire model file.

---

## 11. Risks + Mitigations

| ID | Risk | Mitigation |
|---|---|---|
| **R1** | Cross-module `@api.depends` on etsy_integration field (`has_pending_address_change` lives on sale.order in etsy_integration) — Tracking Dashboard list view *reads* it on parent order via M2O traversal; OK for views, not OK for stored compute. **Mitigation**: keep view-only access via `order_id.has_pending_address_change`; do NOT add stored compute on fulfillment that reads parent field cross-module. Verify in RED. |
| **R2** | `bus.bus._sendone` signature change in Odoo 19. **Mitigation**: locate existing usage in `addons/bus/` for canonical signature; mock in tests with patched method. If signature differs from older Odoo, adjust + note in findings.md. |
| **R3** | `display_notification` action dict format. **Mitigation**: Odoo 19 uses `'tag': 'display_notification'`; verify `params.type` accepts `warning` (not `danger`). Existing 18.x examples in `addons/account` confirm format. |
| **R4** | Server-action XML binding via `binding_model_id` — bulk action visibility in list view "Action" dropdown depends on Odoo 19 syntax. **Mitigation**: model after existing P1-04 server actions or `addons/sale/views/sale_views.xml` patterns. |
| **R5** | `etsy_ship_notified_at` on etsy_integration extension — module load order. **Mitigation**: etsy_integration depends on multichannel_hub_core (per P1-05 manifest); inheritance order is correct by construction. Verify via `-u` install. |
| **R6** | Bus emit on every write triggers chatter+tracking churn for routine field edits. **Mitigation**: gate emit to writes that touch tracking_number, tracking_state, label_status, shipping_date (the dashboard-relevant fields); skip emit for unrelated edits. Document in `_bus_relevant_fields` frozenset. |

---

## 12. Slice Exit Criteria (machine-checkable)

- [ ] All in-scope tasks (T032/T033/T034/T035/T037/T038/T039/T061) marked `[X]` in `tasks.md`
- [ ] T036 explicitly marked `[~]` deferred-to-P2-01 with cross-reference comment
- [ ] `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core,etsy_integration --stop-after-init` exits 0
- [ ] `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /multichannel_hub_core --stop-after-init` exits 0
- [ ] All 9 new tests pass (5 Phase-1 DB + 8 Phase-2 ORM + 1 cross-module)
- [ ] All 405 prior tests still green (no regressions)
- [ ] `ruff check custom_addons/multichannel_hub_core custom_addons/etsy_integration` clean
- [ ] No `_logger.info(` / `print(` introduced
- [ ] Address-change exclusion test green (P1-04 integration verified)
- [ ] bus.bus emit asserted via mock; no live bus.bus required for tests
- [ ] Tracker `006-master-plan-tracking.md` P1-03 row → `done` with change-log entry
- [ ] `findings.md` entry appended (T036 deferral + any Odoo 19 bus API surprises)
- [ ] `/learn` insight captured (or "no new patterns" note)
- [ ] T036 deferral acknowledged by owner in tracker change-log

---

## 13. Open Questions (escalated to owner)

1. **T036 deferral to P2-01** — confirm OK to defer Excel export until Spec 004a defines canonical GKE schema. Without that pin, P1-03's export format risks divergence. Acceptable?
2. **Bus emit gate fields** — proposed gate set: `{tracking_number, tracking_state, label_status, shipping_date}`. Add `production_blocked` / `block_reason`? (Default: yes — operators want production-block visibility live.)
3. **Address-change exclusion warning UX** — `sticky: True` notification (operator must dismiss) vs auto-fade after 5s. Default: sticky.

---

## 14. Next Phase

Phase 2 (RED) — spawn `tdd-guide` with this plan + spec excerpts. Tests must FAIL for the right reason before any implementation lands.
