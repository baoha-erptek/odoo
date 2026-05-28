# P3-LEAD-MODEL — Phase 1 Plan

**Slice**: P3-LEAD-MODEL (US2 §A, tasks T035–T050)
**Depends on**: P3-LEAD-DEDUPE ✓
**Branch**: `feature/006-master-plan-coding`
**Spec**: 007-customer-conversations · **ADR**: ADR-011 (lightweight `multichannel.enquiry`, no `crm` dep)
**Authored**: 2026-05-07

---

## 1. Slice summary

Land the full `multichannel.enquiry` model on `multichannel_hub_core` by extending the P3-LEAD-DEDUPE stub via classical `_inherit`. Adds 13 fields, 4-state machine, `action_qualify` / `action_close(reason)` / `action_convert_to_quote` / `_match_or_create_partner` helper, close-wizard TransientModel, full views (form/list/kanban/search) + Operations menu, ACL rows for 3 groups × 2 models. ~250 LOC. Unblocks Family D manual workflow before alias inbound (P3-LEAD-MAIL-ALIAS).

**Out of scope** (explicit):
- `_message_new` mail.alias hook — P3-LEAD-MAIL-ALIAS.
- `action_convert_to_quote` polish (idempotency, partner heuristics) — P3-LEAD-CONVERT.
- `EtsyConversationPoller._route_message` integration — P3-LEAD-API-ROUTING.
- `etsy.message.dedupe` cross-write from this slice — already in P3-LEAD-DEDUPE.

`action_convert_to_quote` IS implemented here (basic happy path) because the form button needs it; polish lives in P3-LEAD-CONVERT.

---

## 2. File manifest

| Path | Action | One-liner |
|---|---|---|
| `multichannel_hub_core/models/multichannel_enquiry.py` | EXTEND | Replace 22-LOC stub with full model: 13 fields + state machine + actions + `_compute_name` + `init()` mirror. Keep `_name` only — promote `_inherit` from absent to `['mail.thread', 'mail.activity.mixin']`. |
| `multichannel_hub_core/wizards/__init__.py` | CREATE | New package init importing `multichannel_enquiry_close_wizard`. |
| `multichannel_hub_core/wizards/multichannel_enquiry_close_wizard.py` | CREATE | TransientModel with `enquiry_id` M2o + `reason` Selection + `notes` Text + `action_close()`. |
| `multichannel_hub_core/__init__.py` | MODIFY | Add `from . import wizards`. |
| `multichannel_hub_core/views/multichannel_enquiry_views.xml` | CREATE | Form (header buttons + chatter + body fields), list (state decoration), kanban (group-by state, no `<groupby>` element — use search default), search (filters by state/source/assigned_user_id), action, menu under Operations. |
| `multichannel_hub_core/wizards/multichannel_enquiry_close_wizard_views.xml` | CREATE | Wizard form + `act_window` action. |
| `multichannel_hub_core/data/multichannel_enquiry_seed.xml` | CREATE | i18n placeholder for close-reason labels (no records — `.po` covers strings). Optionally omit if T047 produces no data; declare omission in commit body. |
| `multichannel_hub_core/security/ir.model.access.csv` | MODIFY | Append 6 rows (3 enquiry + 3 close-wizard). |
| `multichannel_hub_core/__manifest__.py` | MODIFY | Add 3 XML files to `data` list; bump version 19.0.1.0.21 → 19.0.1.0.22. |
| `multichannel_hub_core/tests/test_phase1_db_enquiry.py` | CREATE | T035 — 5 introspection tests. |
| `multichannel_hub_core/tests/test_phase2_orm_enquiry.py` | CREATE | T036 + T049 — state machine, constrains, ACL, close wizard. |

Total: 8 created, 4 modified.

---

## 3. Field map

Model: `multichannel.enquiry` (extends stub at `multichannel_hub_core/models/multichannel_enquiry.py`).

| Field | Type | Required | Indexed | Ondelete | Tracking | Default |
|---|---|---|---|---|---|---|
| `name` | Char | Y (required already on stub) | — | — | N | computed `_compute_name`, stored |
| `partner_id` | Many2one(`res.partner`) | N | — | `restrict` | Y | — |
| `partner_email` | Char | N | Y | — | Y | — |
| `subject` | Char | N | — | — | Y | — |
| `source` | Selection | Y | Y | — | Y | — (caller-set) |
| `etsy_shop_id` | Many2one(`etsy.shop`) | N | Y | `restrict` | Y | — |
| `etsy_conversation_id` | Char | N | Y | — | Y | — |
| `state` | Selection | Y | — | — | Y | `'new'` |
| `assigned_user_id` | Many2one(`res.users`) | N | — | `set null` | Y | — |
| `converted_order_id` | Many2one(`sale.order`) | N | — | `set null` | Y | — |
| `converted_at` | Datetime | N (readonly) | — | — | Y | — |
| `closed_reason` | Selection | N | — | — | Y | — |
| `notes` | Text | N | — | — | N | — |
| `active` | Boolean | N | — | — | N | `True` |

**Selections**:
- `source`: `[('etsy_api','Etsy API'), ('email_alias','Email Alias'), ('manual','Manual')]`
- `state`: `[('new','New'), ('qualified','Qualified'), ('converted','Converted'), ('closed','Closed')]`
- `closed_reason`: `[('no_response','No Response'), ('not_interested','Not Interested'), ('spam','Spam'), ('duplicate','Duplicate'), ('other','Other')]`

**Compute**:
- `_compute_name(self)` — `@api.depends('partner_email', 'create_date')`. Format: `f"Enquiry from {partner_email or 'unknown'} · {create_date.strftime('%Y-%m-%d')}"`. Stored, recomputed on email change.

**Constraints (declarative)**:
- `_sql_constraints` is NOT used for the partial UNIQUE — Odoo's declarative form does not support partial WHERE. Declare it in `init()` only (drift-template canonical pattern from `etsy_message_dedupe.py`). The plain UNIQUE on `etsy_message_id` mirror **does not apply** here; `multichannel.enquiry` has no plain UNIQUE.

**Indexes (`init()` raw SQL with `pg_constraint IF NOT EXISTS` pre-check pattern)**:
- `idx_mhe_etsy_conv` — partial UNIQUE on `(etsy_shop_id, etsy_conversation_id) WHERE etsy_conversation_id IS NOT NULL`.
- `idx_mhe_partner_email_state` — composite non-unique on `(partner_email, state)`.

`init()` skeleton (cite drift template line ranges from `etsy_message_dedupe.py`):
```python
def init(self):
    super().init()
    # Mirror declarative constraints in raw SQL because Odoo's
    # _sql_constraints does not deploy partial UNIQUE indexes.
    # Drift template (5th confirmation): pg_constraint pre-check, NOT
    # EXCEPTION clause. PG raises 42P07 (duplicate_table) on re-run.
    self.env.cr.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE schemaname='public' AND indexname='idx_mhe_etsy_conv'
            ) THEN
                CREATE UNIQUE INDEX idx_mhe_etsy_conv
                ON multichannel_enquiry (etsy_shop_id, etsy_conversation_id)
                WHERE etsy_conversation_id IS NOT NULL;
            END IF;
        END $$;
    """)
    # idx_mhe_partner_email_state — non-unique composite, plain CREATE INDEX IF NOT EXISTS
    self.env.cr.execute("""
        CREATE INDEX IF NOT EXISTS idx_mhe_partner_email_state
        ON multichannel_enquiry (partner_email, state);
    """)
```

---

## 4. State machine

| From → To | new | qualified | converted | closed |
|---|---|---|---|---|
| **new** | — | ✅ `action_qualify` | ✅ `action_convert_to_quote` | ✅ `action_close(reason)` |
| **qualified** | ❌ | — | ✅ `action_convert_to_quote` | ✅ `action_close(reason)` |
| **converted** | ❌ | ❌ | — | ❌ |
| **closed** | ❌ | ❌ | ❌ | — |

**Rules**:
- Backwards forbidden (data-model.md §1).
- `converted` and `closed` are terminal.
- Transition to `closed` requires non-null `closed_reason`.

**Guard placement (FR-017 10+ confirmations — MUST mirror in BOTH)**:
1. `@api.constrains('state', 'closed_reason')` — catches direct `write({'state': ...})` from any path.
2. `write()` override — re-runs the same predicate when `'state' in vals` to surface a friendlier error and short-circuit before constrains. Required because constrains fires post-write; `write()` lets us reject before the DB row mutates.

Both must agree. Test both paths (direct write + ORM action call).

---

## 5. ACL matrix

Append to `multichannel_hub_core/security/ir.model.access.csv`:

```csv
access_multichannel_enquiry_user,multichannel.enquiry user,model_multichannel_enquiry,sales_team.group_sale_salesman,1,1,1,0
access_multichannel_enquiry_ba_lead,multichannel.enquiry ba lead,model_multichannel_enquiry,multichannel_hub_core.group_ba_lead,1,1,1,1
access_multichannel_enquiry_manager,multichannel.enquiry manager,model_multichannel_enquiry,sales_team.group_sale_manager,1,1,1,1
access_multichannel_enquiry_close_wizard_user,close wizard user,model_multichannel_enquiry_close_wizard,sales_team.group_sale_salesman,1,1,1,0
access_multichannel_enquiry_close_wizard_ba_lead,close wizard ba lead,model_multichannel_enquiry_close_wizard,multichannel_hub_core.group_ba_lead,1,1,1,1
access_multichannel_enquiry_close_wizard_manager,close wizard manager,model_multichannel_enquiry_close_wizard,sales_team.group_sale_manager,1,1,1,1
```

**Group resolution check**:
- `sales_team.group_sale_salesman` — stock Odoo CE (data-model.md §1 ACL row 1 names "group_sale_user" but the canonical XML ID in Odoo 19 CE `sales_team` module is `group_sale_salesman`; "user" is the menu label). Verify with `grep "id=\"group_sale_salesman\"" addons/sales_team/security/sales_team_security.xml` before commit.
- `multichannel_hub_core.group_ba_lead` — promoted from etsy_integration in P1-DASH-MERGE prereq commit. Verify still present.
- `sales_team.group_sale_manager` — stock.

If `group_sale_salesman` mismatch surfaces, switch to `sales_team.group_sale_salesman` in the CSV (data-model spec drift — flag in findings.md).

**Action methods need RPC gates beyond ACL** (FR-017): `action_qualify`, `action_close`, `action_convert_to_quote` each call a private `_check_sale_user_or_raise()` helper that runs `self.env.user.has_group('sales_team.group_sale_salesman')` and raises `UserError` on fail. Pattern from `design_file_route._check_production_team_or_raise()`.

---

## 6. Test plan

### Phase 1 DB tests (`test_phase1_db_enquiry.py`)

1. `test_table_exists` — `SELECT 1 FROM information_schema.tables WHERE table_name='multichannel_enquiry'`.
2. `test_columns_match_spec` — query `information_schema.columns`; assert each field name + udt_name matches data-model §1.
3. `test_partial_unique_index_exists` — `SELECT indexdef FROM pg_indexes WHERE indexname='idx_mhe_etsy_conv'`. **PG normalizes WHERE clause** — assert the returned `indexdef` contains `WHERE (etsy_conversation_id IS NOT NULL)` (case insensitive); do NOT assert exact byte match.
4. `test_composite_index_exists` — `SELECT indexdef FROM pg_indexes WHERE indexname='idx_mhe_partner_email_state'`; assert columns `(partner_email, state)` appear.
5. `test_fk_ondelete_specs` — query `information_schema.referential_constraints` JOIN `key_column_usage` (per memory gotcha #74 — `referential_constraints` lacks table/column names); assert `partner_id` is `RESTRICT`, `etsy_shop_id` is `RESTRICT`, `assigned_user_id`/`converted_order_id` are `SET NULL`.

### Phase 2 ORM tests (`test_phase2_orm_enquiry.py`)

Class `TestEnquiryPhase2`:

1. `test_default_state_new` — create with no `state` → `state == 'new'`.
2. `test_compute_name_format` — set `partner_email='alice@example.com'`; assert `name` matches `re.compile(r"Enquiry from alice@example\.com · \d{4}-\d{2}-\d{2}")`.
3. `test_qualify_advances_state` — `enq.action_qualify()` → `state == 'qualified'`; assert chatter message body contains `'Qualified by'` (don't assert via `mail.tracking.value` — known broken per Bug-2026-05-03).
4. `test_qualify_from_non_new_raises` — `state='qualified'`, call `action_qualify()` → `UserError`.
5. `test_close_requires_reason` — `enq.action_close(reason='')` → `UserError` or `ValidationError`. Then `enq.action_close(reason='spam')` → `state='closed'`, `closed_reason='spam'`.
6. `test_convert_creates_draft_order` — `enq.action_convert_to_quote()` returns `act_window`; new `sale.order.state=='draft'`, `partner_id` matches, `origin == enq.name`. Enquiry: `state='converted'`, `converted_at` set, `converted_order_id` set.
7. `test_backwards_transition_blocked_via_write` — direct `enq.write({'state': 'new'})` from `qualified` → `ValidationError`. Tests `@api.constrains` path.
8. `test_backwards_transition_blocked_via_action` — no `action_unqualify` exists; ensure no public method allows it. (Sanity test.)
9. `test_terminal_states_immutable` — from `closed`, `enq.write({'state': 'new'})` → `ValidationError`. Same from `converted`.
10. `test_match_partner_existing` — create `res.partner(email='bob@example.com', is_etsy_customer=True)`; new enquiry with `partner_email='Bob@Example.com'` (case differs); call `_match_or_create_partner()`; assert `partner_id == bob` (email_normalize round-trip).
11. `test_match_partner_creates_when_absent` — new enquiry with novel email; call helper; new `res.partner` exists with `is_etsy_customer=True`.
12. `test_match_partner_blank_email` — `partner_email=''` (empty string per Char default); call helper → no exception, `partner_id` stays null. Assert no junk partner created.
13. `test_acl_salesman_can_create` — `with_user(salesman_user)` create + write; succeed. `salesman_user.unlink()` raises `AccessError` (no unlink right).
14. `test_acl_ba_lead_can_unlink` — `ba_lead_user.unlink()` succeeds.
15. `test_action_qualify_rpc_gated_for_no_group` — user without `group_sale_salesman` calls `action_qualify` → `UserError` (RPC gate beyond ACL).
16. `test_partial_unique_enforced` — same `(etsy_shop_id, etsy_conversation_id='X')` twice → second raises `IntegrityError`. With `etsy_conversation_id=None`, two rows allowed (partial WHERE).
17. `test_dedupe_target_enquiry_fk_intact` — create `etsy.message.dedupe(target_enquiry_id=enq.id, ...)`; unlink enquiry → dedupe row's `target_enquiry_id` becomes null (ondelete='set null' from P3-LEAD-DEDUPE side, NOT this slice's responsibility — sanity test only).

Class `TestEnquiryCloseWizard` (T049):

18. `test_wizard_close_flow` — create enq, instantiate wizard with `enquiry_id=enq.id, reason='spam', notes='dup of #123'`; `wizard.action_close()`; assert enq `state='closed'`, `closed_reason='spam'`, chatter message exists with body containing `'dup of #123'`.

### Test-side gotchas to honor

- Use `cr.savepoint()` for negative-path tests instead of `cr.commit()` (forbidden in `TransactionCase`).
- `mock.patch.object(record, ...)` raises read-only on Odoo Models — patch `type(record)` if mocking is needed. The above tests don't mock; flag for any future test additions.
- For ACL probes: `self.env['multichannel.enquiry'].with_user(salesman_user).create({...})`. Do not assert via `assertRaises((AccessError, IntegrityError))` tuple — Odoo's `_assertRaises` issubclass check breaks; use savepoint + manual try/except (memory gotcha #74).
- `mail.tracking.value` rows are NOT being persisted DB-wide (Bug-2026-05-03). All tracking assertions go via `enq.message_ids` (count + body content), not `mail.tracking.value`.
- Tests creating enquiries must satisfy ALL invariants — when triggering the partial-UNIQUE case, both `etsy_shop_id` AND `etsy_conversation_id` must be set; when not testing that constraint, leave `etsy_conversation_id=None` to avoid collision.

---

## 7. Risks

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| 1 | Partial UNIQUE introspection drift — PG-normalized form differs from declared form | High | Test 3 asserts via `LIKE '%IS NOT NULL%'` substring, not byte-equal. |
| 2 | State guard in `@api.constrains` only — direct RPC `write({'state':'new'})` still runs the field write, then constrains fires; but UX is worse (post-write rollback). FR-017 pattern requires `write()` override too. | High | Implement BOTH; tests #7 and #9 exercise the `write()` path explicitly. |
| 3 | Action methods callable via RPC by users with READ-only ACL but not the action's intent group | High | Add `_check_sale_user_or_raise()` to each action; test #15 covers it. |
| 4 | `_match_or_create_partner` with blank email creates junk partner | Med | Helper guard: `if not self.partner_email: return False` before search/create; test #12. |
| 5 | Chatter XSS via user-controlled `closed_reason` Selection labels reflected back into `message_post(body=...)` | Low | Selection values are server-controlled; safe. But the close-wizard `notes` Text IS user-controlled — wrap with `markupsafe.Markup(escape(notes))` before `message_post`. Pattern from `etsy.address.change.request.action_approve`. |
| 6 | `multichannel.enquiry` stub already exists with `name=fields.Char(default='Enquiry')` — extending replaces the default with `_compute_name` stored compute. Migration risk if any rows exist. | Low | No production rows possible (stub landed 2026-05-07 same day). Add idempotent fallback in `_compute_name`: `if not partner_email: return 'Enquiry'`. |
| 7 | P3-LEAD-DEDUPE's `etsy.message.dedupe.target_enquiry_id` FK depends on `multichannel.enquiry` table existing; extending via `_inherit` keeps the table intact. | Low | Verify via test #17. Manifest order: mhc loads before etsy_integration. |
| 8 | `group_sale_user` vs `group_sale_salesman` XML-ID confusion | Med | Verify exact XML ID before CSV write; spec says "group_sale_user" but Odoo 19 ships `group_sale_salesman`. If mismatch, fix CSV + flag findings.md. |
| 9 | Kanban `group-by state` — Odoo 19 RNG forbids `<groupby>` in some kanban modes; use `<kanban default_group_by="state">` attribute instead. | Med | Use attribute form; smoke-test via `-u` install. |
| 10 | `action_convert_to_quote` partial implementation here (basic happy path) — P3-LEAD-CONVERT polish must not break existing tests | Low | Document the basic path's behavior in the docstring; P3-LEAD-CONVERT extends, does not rewrite. |

---

## 8. Manifest bump

`multichannel_hub_core/__manifest__.py`:

```python
'version': '19.0.1.0.22',  # was 19.0.1.0.21 (P3-LEAD-DEDUPE stub bump)
'data': [
    # ... existing entries ...
    'security/ir.model.access.csv',  # already listed; ensure entry present
    'views/multichannel_enquiry_views.xml',           # NEW
    'wizards/multichannel_enquiry_close_wizard_views.xml',  # NEW
    'data/multichannel_enquiry_seed.xml',             # NEW (or omit if empty per §2)
],
```

If `multichannel_enquiry_seed.xml` is empty (i18n via `.po` only), drop it from `data` and document in commit body. Don't ship empty XML.

---

## 9. Agent dispatch order for downstream phases

| Phase | Agent | Inputs | Output |
|---|---|---|---|
| 2 (RED) | `tdd-guide` | This plan + data-model.md §1 + contracts/enquiry_actions.md + memory gotchas | T035 + T036 + T049 test files; all RED with fail-for-right-reason |
| 3 (GREEN) | Orchestrator inline (not agent) | RED tests + this plan | T037 model + T038 guard + T039–T041 actions + T042 wizard + T043 init + T044 ACL + T045/T046/T047 views + T048 manifest |
| 4 (REVIEW) | `code-reviewer` + `security-reviewer` (parallel, single message) | Diff vs `feature/006-master-plan-coding` HEAD | Verdicts; CRITICAL/HIGH must be fixed pre-commit |
| 5 (VERIFY) | Orchestrator inline | — | `odoo -d <db> -u multichannel_hub_core --stop-after-init` exit 0; `--test-tags /multichannel_hub_core:TestEnquiryPhase1,TestEnquiryPhase2`; ruff if available; grep for `_logger.info` / `print(` |
| 6 (COMMIT) | Orchestrator inline | — | Conventional commit `[multichannel_hub_core] feat(P3-LEAD-MODEL): ...` citing T035–T050 |
| 7 (DOCUMENT) | Orchestrator inline | — | tasks.md `[X]` for T035–T050; tracker row state=done with commit hash + test counts + review verdicts; findings.md if surprises |
| 8 (LEARN) | `/learn` skill | — | Auto-memory entries for any new gotcha or "no new patterns" note |
| 9 (LAND) | — | — | Stays on feature branch; merge to main is W7 E2E sprint task |

**No architect agent** — ADR-011 (2026-05-07) authorizes the design; data-model.md §1 + contracts/enquiry_actions.md are sufficient detail. Spawning architect would be churn.

---

## 10. Exit-criteria checklist (from playbook §"Slice exit criteria")

- [ ] Every slice task `[X]` in `specs/007-customer-conversations/tasks.md` (T035–T050).
- [ ] Tests pass; coverage ≥80% on changed lines. **Evidence**: full mhc suite green ≤1 pre-existing failure (`TestHistoricalSeedT078.test_seed_skips_empty_urls` from P1-MTO-DEPS — unrelated). Expected new test count: 18 (5 Phase 1 + 13 Phase 2).
- [ ] Module installs cleanly: `odoo -d <db> -u multichannel_hub_core --stop-after-init` exit 0; manifest 19.0.1.0.22.
- [ ] ACLs defined (6 new rows); `init()` raw SQL has drift-template comment + `pg_constraint`/`pg_indexes` pre-check; any `sudo()` has inline rationale (none expected — actions run as user).
- [ ] Tracker `state=done`, blockers documented (none expected).
- [ ] `/learn` insight captured (or "no new patterns — pure pattern reuse from etsy_message_dedupe + design_file" note).
- [ ] `findings.md` updated for any surprise (XML ID mismatch on `group_sale_user`, kanban RNG quirk, blank-email partner-match edge case, `mail.tracking.value` flakiness reconfirmation, etc.).

**Estimated LOC**: ~250 (model 130, wizard 40, views XML 60, ACL CSV 6 lines, manifest 3 lines, tests 200+).
**Estimated time**: 4–6h orchestrator inline including reviews.
