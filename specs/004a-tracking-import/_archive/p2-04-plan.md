# P2-04 Phase-1 Tactical Plan — Tracking import log visibility + replay (US4)

**Slice**: P2-04 (Spec 004a US4)
**Branch**: `feature/006-master-plan-coding`
**Module**: `multichannel_hub_fulfillment` (primary); view extension for `etsy.sync.health` smart-button
**Dependencies**: P2-01 ✓ (importer + log/line models), P2-02 ✓ (carrier detection)
**Authored**: 2026-05-08 (planner agent, dispatched from `/dispatch-slice P2-04`)

---

## Drift Check Report

### AC1 — List view columns
Spec line 101: "import date, user, filename, schema hash, row_count, matched_count, conflict_count, error_count, state, sync_health_link"

Current `views/tracking_import_views.xml` lines 9–27 list view exposes all required columns; **but** `schema_hash` is `optional="hide"` (must be removed) and **smart-button to sync.health is missing**.

**Verdict**: Modify, not create.

### AC2 — Form one2many filtered + per-row "Re-process"
Spec line 102: "one2many filtered by line.state; 'Re-process' action per row"

`line_ids` one2many exists (lines 68–84) but no per-state filtering and no "Re-process" action button. Existing `action_re_detect_carriers` (line 146 of `tracking_import_line.py`) is **carrier-detect only**, distinct from full pipeline replay.

**Verdict**: Add new method `action_replay_line()` + view button.

### AC3 — Conflict resolution dropdown + chatter
Spec line 103: "operator chooses from candidate orders; choice recorded in chatter"

`tracking.import.line.state='conflict'` exists; `sale_order_id` Many2one exists; **but** line has NO `mail.thread` (deliberate: high volume per plan.md line 173). No candidate-picker UX exists.

**Verdict**: Add `action_resolve_conflict()`; record choice in **parent log's chatter** (since line has no chatter).

### AC4 — Per-line replay with savepoint, recounted summary
Spec line 104: "single line retried in savepoint; parent log summary recounted"

Savepoint pattern exists in `services/tracking_importer.py::apply_to_fulfillment` lines 147–188 (initial-import path). No replay method; no `_recount_summary` on log.

**Verdict**: Add `action_replay_line()` + `_recount_summary()` (uses `read_group` for efficiency).

### AC5 — Smart-button on `etsy.sync.health.gke_tracking_import`
Spec line 105: "smart-button link to log list filtered by today"

Model has `last_run_at`, `last_successful_run_at`, `last_run_row_count`, `last_run_error_count`. No smart-button. Memory `feedback_odoo19_test_gotchas.md` flag: `etsy.sync.health._record_event` does NOT exist; tracking_importer probes via `getattr` and silently no-ops.

**Verdict**: Add view extension + Python action returning `ir.actions.act_window` (Python domain to avoid XML `timedelta` serialization).

---

## Files to Touch

### Modified
1. `custom_addons/multichannel_hub_fulfillment/views/tracking_import_views.xml` — unhide schema_hash; add server action + button bindings; add smart-button on form.
2. `custom_addons/multichannel_hub_fulfillment/models/tracking_import_line.py` — add `action_replay_line()` + `action_resolve_conflict()`.
3. `custom_addons/multichannel_hub_fulfillment/models/tracking_import_log.py` — add `_recount_summary()` + `action_view_today_imports()` (smart-button target).
4. `custom_addons/multichannel_hub_fulfillment/__manifest__.py` — version bump (current 19.0.1.0.14 → 19.0.1.0.15).

### New
5. `custom_addons/multichannel_hub_fulfillment/views/etsy_sync_health_smartbutton.xml` — extend `etsy.sync.health` form with conditional smart-button (visible only when `name='gke_tracking_import'`).

### Conditionally created (recommended NOT — orchestrator chose inline form widget per `dispatch-run-to-completion`)
- `wizards/tracking_conflict_resolver.py` (TransientModel) + view + ACL — **skipped**; conflict resolution implemented as form action with candidate domain filter.

---

## Phase 2 RED — Failing Tests

### Phase 1 DB tests (`tests/test_phase1_db.py` — append)
- `test_tracking_import_log_schema_hash_visible` — XML has no `optional="hide"` on `schema_hash` in list view.
- `test_smart_button_action_exists` — `ir.actions.act_window` for today's imports exists with date domain.
- `test_tracking_import_line_action_replay_line_exists` — method exists.
- `test_tracking_import_line_action_resolve_conflict_exists` — method exists.

### Phase 2 ORM tests (`tests/test_phase2_orm_p2_04.py` — new)
- `test_action_replay_line_reruns_resolve_orders` — error→matched after fix.
- `test_action_replay_line_reruns_carrier_detection` — applied carrier set.
- `test_action_replay_line_reruns_fulfillment_write` — tracking_number written; state='imported'.
- `test_action_replay_line_savepoint_rollback_on_error` — write raises; state stays 'error'.
- `test_action_replay_line_updates_parent_summary` — counts recomputed.
- `test_conflict_line_operator_selects_candidate_order` — line.sale_order_id set; parent chatter has audit message.
- `test_action_replay_line_gated_to_ba_shipping` — non-BA → AccessError.
- `test_action_resolve_conflict_gated_to_ba_shipping` — non-BA → AccessError.
- `test_smart_button_action_filters_by_today` — domain includes today's date.
- `test_replay_idempotent_on_duplicate_call` — second replay no-ops or matches first.

---

## Phase 3 GREEN — Implementation Outline

### Methods on `tracking.import.line`

```python
def action_replay_line(self):
    self._check_ba_shipping_or_raise()  # FR-017 gate
    for line in self:
        if line.state == 'imported':
            continue
        try:
            with self.env.cr.savepoint():
                from ..services import tracking_importer, carrier_detector
                tracking_importer.resolve_orders(self.env, line)
                if line.state == 'matched' and line.raw_tracking_number:
                    compiled = carrier_detector._compiled_cache_for(self.env)
                    other = carrier_detector._other_carrier(self.env)
                    carrier, needs_review = carrier_detector.detect_carrier(
                        self.env, line.raw_tracking_number, compiled, other)
                    line.detected_carrier_id = carrier.id if carrier else False
                    line.needs_review = needs_review
                if line.state == 'matched':
                    tracking_importer.apply_to_fulfillment(self.env, line)
        except Exception as exc:
            line.write({'state': 'error',
                        'error_message': tracking_importer._scrub(str(exc))})
    if self:
        self.mapped('log_id')._recount_summary()

def action_resolve_conflict(self, selected_order_id):
    self._check_ba_shipping_or_raise()
    self.ensure_one()
    if self.state != 'conflict':
        raise ValidationError(_("Only conflict lines can be resolved."))
    selected = self.env['sale.order'].browse(selected_order_id)
    if not selected.exists():
        raise ValidationError(_("Selected order does not exist."))
    candidates = self.env['sale.order'].search([
        ('channel_order_ref', '=', self.raw_order_number)])
    self.write({'sale_order_id': selected.id, 'state': 'matched'})
    self.log_id.message_post(body=_(
        "Row %(r)s: conflict resolved → order %(sel)s "
        "(candidates: %(c)s)",
        r=self.row_number, sel=selected.display_name,
        c=', '.join(candidates.mapped('display_name'))))
```

### Method on `tracking.import.log`

```python
def _recount_summary(self):
    for log in self:
        groups = self.env['tracking.import.line'].read_group(
            [('log_id', '=', log.id)], ['state'], ['state'])
        counts = {g['state']: g['state_count'] for g in groups}
        log.write({
            'matched_count':   counts.get('matched', 0),
            'unmatched_count': counts.get('unmatched', 0),
            'conflict_count':  counts.get('conflict', 0),
            'error_count':     counts.get('error', 0),
            'imported_count':  counts.get('imported', 0),
        })

def action_view_today_imports(self):
    self.ensure_one()
    today_str = fields.Datetime.now().strftime('%Y-%m-%d 00:00:00')
    return {
        'type': 'ir.actions.act_window',
        'name': _("Today's GKE Imports"),
        'res_model': 'tracking.import.log',
        'view_mode': 'list,form',
        'domain': [('create_date', '>=', today_str)],
    }
```

### View additions
- Remove `optional="hide"` on `schema_hash` (list view, line 25).
- Add `<button name="action_replay_line" string="Re-process" type="object" invisible="state == 'imported'"/>` inline on `line_ids` one2many.
- Add candidate-order domain filter on `sale_order_id` widget when `state == 'conflict'`: `domain="[('channel_order_ref', '=', raw_order_number)]"`.
- Add smart-button to log form linking to `action_view_today_imports`.

### `etsy.sync.health` smart-button (new file)
```xml
<record id="view_etsy_sync_health_form_extend" model="ir.ui.view">
  <field name="name">etsy.sync.health.form.gke.smartbutton</field>
  <field name="model">etsy.sync.health</field>
  <field name="inherit_id" ref="etsy_integration.view_etsy_sync_health_form"/>
  <field name="arch" type="xml">
    <div name="button_box" position="inside">
      <button name="action_view_gke_today" type="object"
              string="Today's GKE Imports" class="oe_stat_button"
              icon="fa-list" invisible="name != 'gke_tracking_import'"/>
    </div>
  </field>
</record>
```
Plus a small Python override on `etsy.sync.health` that returns the same `ir.actions.act_window` (must live in mhf so it doesn't pollute etsy_integration with a fulfillment dependency). If layering is blocked, use `mail.thread` + `_inherit` extension OR move the smart-button into `etsy.sync.health` model directly with `getattr` probe to avoid hard dependency.

**Layering decision** (planner): smart-button view + Python action live in `multichannel_hub_fulfillment` (which already depends on `etsy_integration` indirectly via `multichannel_hub_core`). Verify dependency chain in Phase 3 before commit.

---

## Risks & Edge Cases

1. **Conflict line with deleted candidates**: `action_resolve_conflict` raises `ValidationError("Order does not exist")` if browse misses; UX should also gracefully handle "0 candidates remain" (set state='unmatched').
2. **Concurrent replay race**: savepoint + UNIQUE on stock.move purpose marker (P2-03) → second call hits IntegrityError caught by except clause; line marked error with descriptive message.
3. **`_recount_summary` perf on 1000-row imports**: `read_group` is DB-side aggregation; acceptable up to 5K rows. Defer optimization to P0-11 observability tile.
4. **Smart-button XML domain serialization**: avoided by using Python action returning `act_window` dict.
5. **FR-017 interaction with conflict resolution**: `action_resolve_conflict` writes only `sale_order_id` (M2O link), NOT to `_ADDRESS_LOCK_FIELDS`. Subsequent replay still goes through lock check. **Memory `feedback_fr017_write_defense_in_depth.md` 13th confirmation**: ensure RPC-gate test on `action_replay_line` + `action_resolve_conflict`.
6. **Bulk re-process on 100 lines**: server action loops; one savepoint per line; one `_recount_summary` at end. Acceptable.
7. **`etsy.sync.health._record_event` non-existence** (memory): replay path does NOT call it; if any future audit hook is added, use `getattr(rec, '_record_event', None)` probe pattern.

---

## Slice Exit Criteria

- [ ] All 14 P2-04 task IDs `[X]` in `tasks.md`
- [ ] 11 RED tests pass after GREEN
- [ ] `odoo -u multichannel_hub_fulfillment --stop-after-init` exit 0
- [ ] `--test-tags /multichannel_hub_fulfillment` exit 0
- [ ] Cross-module regression `--test-tags /multichannel_hub_core,/multichannel_hub_fulfillment,/etsy_integration` exit 0
- [ ] `ruff check custom_addons/multichannel_hub_fulfillment/` exit 0
- [ ] No `_logger.info` / `print(` in modified files
- [ ] Code-reviewer + security-reviewer in parallel; no CRITICAL/HIGH unaddressed
- [ ] Tracker P2-04 row → `state=done` with commit hashes
- [ ] `findings.md` updated with conflict-chatter location decision + replay idempotency notes
- [ ] `/learn` insight captured

---

## Decisions Locked (per `feedback_dispatch_run_to_completion.md`)

| Choice | Decision | Rationale |
|---|---|---|
| Conflict UX: wizard vs inline | **Inline form widget + domain filter** on `sale_order_id` | Less code; fewer files; same outcome |
| Replay: inline vs service module | **Inline in `action_replay_line`** | Reuses existing `tracking_importer` functions; no premature abstraction |
| Filter UX: tabs vs single list | **Single list with state column** | Spec AC2 only requires filterability, not visual separation |
| Smart-button location | **`multichannel_hub_fulfillment`** (extends etsy view) | mhf already depends transitively on etsy module |
| Chatter location for conflict | **Parent log** | Line has no `mail.thread` by design (volume) |
