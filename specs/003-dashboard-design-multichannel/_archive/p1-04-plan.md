# P1-04 Tactical Plan — Address-Change Approval Workflow

**Slice**: P1-04 (Spec 003 US4, safety-critical)
**Branch**: `feature/006-master-plan-coding`
**Created**: 2026-04-28
**Source**: planner agent output 2026-04-28 + verifications by orchestrator (groups not yet defined; mhc `sale.order` minimally extended)

---

## 1. Slice scope

### IN scope (this slice)

| Task | Notes |
|---|---|
| T021 (partial) | Only `has_pending_address_change` Boolean (compute, store=True) + `address_change_request_ids` O2M inverse on `sale.order`. Other US1 fields (`sales_channel`, `channel_order_ref`, `x_pipeline_id`, `x_pipeline_state_id`) deferred to P1-01. |
| T022 (partial) | Only C-SO-001 (address-change lock with `approve_address_change` context bypass). C-SO-002 (pipeline policy) deferred to P1-01. |
| T051 | `etsy.address.change.request` model with `mail.thread` + `mail.activity.mixin` per data-model.md §5 |
| T052 | C-AC-001 (no requests on shipped/done/cancel), C-AC-002 (one outstanding per order), C-AC-003 (rejection_reason required when rejected) |
| T053 | `action_approve` (atomic `sale.order` write with bypass context, set state, close activity, post chatter) |
| T054 | `action_reject` (require rejection_reason, post @mention chatter to requester) |
| T055 | Auto-`mail.activity` on create to `group_ba_lead`, type "To Do", deadline +24h |
| T056 | Folded into T022 — same constraint, with bypass detection |
| T057 | `views/etsy_address_change_request_views.xml` form + list + Activity inbox visibility |
| T058 | ACL: create marketing+ba; write (state) ba_lead only; delete system |
| T059 | `sale.order` form readonly destination fields when `has_pending_address_change=True` + banner |
| T060 | "Request address change" button (visible to MP when no pending) |
| T062 | Phase-2 ORM lifecycle test: request → approve, request → reject, server-side write blocked, atomic apply, attempted-double-request rejection |

### SKIPPED (deferred)

| Task | Why | Defer to |
|---|---|---|
| T021 (other 4 fields) | `sales_channel`, `channel_order_ref`, `x_pipeline_id`, `x_pipeline_state_id` are Order Dashboard / Process Dashboard fields | P1-01 |
| T022 C-SO-002 | Pipeline transition policy depends on `x_pipeline_id` | P1-01 |
| T061 | Tracking Dashboard bulk-shipped action (T035) does not exist yet — that's P1-03 | P1-03 |

Note in commit body: T061 deferred; caller will add the address-change skip when T035 lands.

---

## 2. Decisions D1–D5

### D1 — Module home for `etsy.address.change.request` → `etsy_integration`

`etsy.`-prefixed names are barred from `multichannel_hub_core` per its CLAUDE.md (P0-16a finding 2026-04-28). All P1-04 code (model + field + constraint + groups + views + tests) lands in `etsy_integration`. mhc is untouched in this slice.

### D2 — All P1-04 fields live in etsy_integration's `sale.order` extension, NOT in mhc

Originally the planner suggested putting `has_pending_address_change` in `multichannel_hub_core/models/sale_order.py`. Rejected: the `@api.depends('address_change_request_ids.state')` compute references an etsy model — registry build would fail because mhc cannot import etsy_integration. Cleanest fix: keep both the field and its compute in `etsy_integration/models/sale_order.py` (file already exists, currently minimal). When channel-agnostic address-change becomes a thing, we'll lift it via a future ADR; not premature work for this slice.

### D3 — BA approver groups defined in `etsy_integration/security/etsy_security.xml`

Verified via grep: `group_ba_lead`, `group_ba_user`, `group_marketing_user` do not exist anywhere in the tree. Create them fresh in the existing `etsy_integration/security/etsy_security.xml` (alongside existing Etsy groups). When P1-01 introduces channel-agnostic UX we can promote them to mhc; for now they live with their only consumers. **Group XML must be loaded BEFORE `ir.model.access.csv`** (manifest data list ordering — same gotcha as P0-17).

### D4 — `sale.order` form modifications in `etsy_integration/views/sale_order_views.xml`

That file already extends the form for Etsy-specific fields; readonly attrs + banner + "Request address change" button go alongside.

### D5 — T061 deferred; T062 mocks the bulk action context

T062 will assert `has_pending_address_change=True` on the order; the bulk-shipped exclusion test is restated as a unit-level "given an order with pending request, the manager-level bulk method (yet to be written) must check this flag" — captured as a docstring TODO in T062, real integration test added in P1-03.

---

## 3. File touch list (commit order)

All paths are relative to `custom_addons/etsy_integration/` unless noted.

| Order | File | Action | Tasks | Notes |
|---|---|---|---|---|
| 1 | `security/etsy_security.xml` | modify | T058 prereq | Add three groups (ba_lead, ba_user, marketing_user) before any ACL refs them |
| 2 | `models/sale_order.py` | modify | T021p, T022 | Add `has_pending_address_change` Boolean + `address_change_request_ids` O2M inverse + C-SO-001 with bypass |
| 3 | `models/etsy_address_change_request.py` | new | T051–T055 | Model + constraints + actions + auto-activity |
| 4 | `models/__init__.py` | modify | T051 | Import new model |
| 5 | `views/etsy_address_change_request_views.xml` | new | T057 | Form + list + Activity inbox |
| 6 | `views/sale_order_views.xml` | modify | T059, T060 | Readonly attrs + banner + button |
| 7 | `security/ir.model.access.csv` | modify | T058 | ACL rows for new model |
| 8 | `__manifest__.py` | modify | wiring | Add new view file to `data` list (security xml stays first) |
| 9 | `tests/test_address_change_workflow.py` | new | T062 | Phase 2 ORM tests |
| 10 | `tests/test_address_change_db.py` | new | Phase-1 verification | Phase 1 DB tests (table, columns, index) |
| 11 | `tests/__init__.py` | modify | wiring | Import new test files |

No migration script needed — `has_pending_address_change` is computed/stored and Odoo populates it on first compute pass; no data backfill required since no order can have a pending request at install time.

---

## 4. Agent dispatch

| Phase | Agent | Tier | Task |
|---|---|---|---|
| 2 (RED) | `tdd-guide` | Sonnet | Write Phase 1 + Phase 2 failing tests covering all 13 in-scope tasks. Must fail for the right reason (model missing / method missing / constraint missing). |
| 3 (GREEN) | inline (Sonnet executor) | Sonnet | Implement files 1–8 in commit order. Mark `[X]` in tasks.md as each completes. |
| 4 (Review) | `code-reviewer` + `security-reviewer` | Sonnet (parallel) | Single message, two Agent calls. Security focus: ACL gates, bypass-context only set by `action_approve`, no PII leak in chatter, no raw SQL. Code focus: `tracking=True` coverage, `_description`, `ondelete`, idempotency of approve. |

No Opus escalation expected — no novel architecture, no cross-spec ADR change.

---

## 5. Top risks

1. **R1 — Group-before-ACL ordering**: `ir.model.access.csv` row referencing `group_ba_user` fails install if `etsy_security.xml` loads after it. Manifest `data` list must list the security XML first. Same lesson from P0-17. Mitigation: explicit assertion in Phase 2 DB test (`env.ref('etsy_integration.group_ba_lead')` succeeds post-install).
2. **R2 — Bypass context leaks via inheritance**: If `action_approve` calls `self.order_id.write(new_values)` and `sale.order.write` is overridden by another module that does not propagate context, the constraint may fire. Mitigation: invoke `sale.order.with_context(approve_address_change=True).write(values)` explicitly; test asserts the context is honored even when called via mail-thread message_post side-effects.
3. **R3 — `mail.activity` recipient resolution**: posting an activity to a group requires the group to have at least one member; in tests we must add `env.user` to `group_ba_lead` via `setUp`. Failing to do so produces a confusing "no recipient" error rather than a clear assertion. Mitigation: explicit fixture step in test base class.

---

## 6. Slice exit criteria (machine-checkable)

- [ ] All 13 in-scope task IDs marked `[X]` in `specs/003-dashboard-design-multichannel/tasks.md`. T061 marked `[~]` deferred with comment.
- [ ] `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init` exits 0
- [ ] `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /etsy_integration --stop-after-init` exits 0; ≥80% line coverage on the two new test files
- [ ] All three groups resolvable via `env.ref()` post-install
- [ ] C-SO-001 fires on direct `sale.order.write({'street': ...})` when `has_pending_address_change=True`; passes when `with_context(approve_address_change=True)`
- [ ] C-AC-001/002/003 each have a dedicated test that asserts the UserError
- [ ] `action_approve` closes the related `mail.activity` and posts a chatter delta with old→new values
- [ ] `action_reject` requires `rejection_reason` and posts `@requested_by` mention
- [ ] `ruff check custom_addons/etsy_integration/models/etsy_address_change_request.py` clean
- [ ] `grep -rE "_logger\.info\(|^[[:space:]]*print\(" custom_addons/etsy_integration/models/etsy_address_change_request.py` empty
- [ ] Tracker `006-master-plan-tracking.md` P1-04 row state→`done`, last reviewed 2026-04-28
- [ ] `findings.md` entry appended (or explicit "no new patterns" note)
- [ ] Full regression across all three custom modules green

---

## 7. Open questions for user (none blocking)

1. Group naming — `group_ba_lead` vs `group_etsy_ba_lead`? The latter is consistent with our "etsy-named code in etsy_integration" convention. Defaulting to `group_ba_lead` per spec, but flag if rename preferred before P1-01 inherits these.
2. Activity deadline +24h — server TZ. (Default; flag if user-TZ preferred.)

Both default-resolved; proceed unless objected.

---

## 8. Next phase

Phase 2 (RED) — spawn `tdd-guide` agent with this plan + spec/data-model excerpts. Tests must FAIL for the right reason before any implementation lands.
