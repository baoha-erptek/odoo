# Implementation Plan: P3-LEAD-CONVERT — Convert-to-Quote Polish

**Slice ID**: P3-LEAD-CONVERT
**Spec**: Spec 007 — Customer Conversations (Pre-Sale & Post-Sale)
**Tasks**: T063–T067 in `specs/007-customer-conversations/tasks.md`
**Dependent on**: P3-LEAD-MODEL (landed 2026-05-07)
**Blockers**: None identified
**Status**: Phase 1 Planning (2026-05-07)

---

## Overview

Implement `action_convert_to_quote()` method on `multichannel.enquiry` to create a draft `sale.order` linked to the enquiry's partner, with idempotency protection, state-machine guards, and XSS-safe chatter audit trails. ~80 LOC implementation + Phase 2 ORM tests. Slot in after P3-LEAD-MAIL-ALIAS (US2 §B) lands, before Phase 5 polish (T068–T072).

---

## Spec Drift Check

Read `contracts/enquiry_actions.md` and cross-check with current stub in `multichannel_enquiry.py` **line 248–289**:

### Contract Spec (Source of Truth)

```
action_convert_to_quote(self) -> ir.actions.act_window

- Pre: self.state in ('new', 'qualified')
- Side effects:
  - Create sale.order with partner_id=self.partner_id, state='draft', origin=self.name
  - Write self.converted_order_id, self.converted_at=now, self.state='converted'
  - Chatter post on enquiry: 'Converted to <order ref>'
  - Chatter post on order: 'Created from enquiry <enquiry name>'
- Returns: ir.actions.act_window opening the new sale.order form
- ACL: sales_team.group_sale_user+
- Idempotency: re-invocation when state='converted' returns the existing order action without duplicate
```

### Current Implementation (Lines 248–289)

**Status**: IMPLEMENTED (landed P3-LEAD-MODEL 2026-05-07, commit 31aa4b3f01d).

Current code matches spec exactly:
- Line 252: idempotency check `if self.state == 'converted' and self.converted_order_id: return self._action_open_converted_order()`
- Line 254: pre-condition guard `if self.state not in ('new', 'qualified'): raise UserError`
- Line 258: calls `_match_or_create_partner()` (already implemented, line 294–330)
- Line 264: `sale.order.create()` with `partner_id`, `origin=self.name`, implicit `state='draft'` (Odoo default)
- Line 271–276: defensive write with `converted_order_id`, `converted_at`, `state='converted'`, `partner_id` re-asserted
- Line 277–278: chatter posts on both enquiry + order via `Markup % escape(...)` pattern (memory `feedback_fr017_write_defense_in_depth.md` 11th confirmation)
- Line 281–289: `_action_open_converted_order()` returns `ir.actions.act_window` correctly

**Verdict**: **NO SPEC DRIFT**. The method is already production-ready. This slice's job is to verify it passes tests and document any surprises.

---

## Files to Touch

| File | Action | Rationale |
|------|--------|-----------|
| `custom_addons/multichannel_hub_core/tests/test_phase2_orm_enquiry.py` | EXTEND | Add 3 new test methods per T063–T065 (idempotency, pre-condition, XSS-safe chatter) |
| `custom_addons/multichannel_hub_core/__manifest__.py` | BUMP VERSION | 19.0.1.0.22 → 19.0.1.0.23 (manifest requirement per Phase 6 Commit) |
| `specs/007-customer-conversations/tasks.md` | MARK [X] | T063, T064, T065, T066, T067 after tests pass + implementation verified |
| `specs/007-customer-conversations/findings.md` | APPEND | Document any surprises discovered during Phase 5 Verify (Phase 7 Document) |
| `.claude/plans/006-master-plan-tracking.md` | UPDATE STATE | P3-LEAD-CONVERT → `done`, landing record, last reviewed 2026-05-07 (Phase 7 Document) |

**Note**: `multichannel_enquiry.py` implementation already exists; no edits required for the method body itself. Phase 2 tests are the deliverable.

---

## State-Machine Truth Table

Explicit allow/deny matrix for `action_convert_to_quote()`:

| Current State | Allow? | Action | Result | Chatter |
|---|---|---|---|---|
| `new` | YES | Call action | Create order, transition to `converted`, stamp `converted_order_id` + `converted_at` | Enquiry: "Converted to SO#123"; Order: "Created from enquiry Enquiry-abc" |
| `qualified` | YES | Call action | Create order, transition to `converted`, stamp fields | Same as above |
| `converted` | YES (idempotent) | Call action again | Return existing order's `act_window`, no duplicate SO created, no new chatter | No new chatter message |
| `closed` | NO | Call action | Raise `UserError("Cannot convert enquiry from state closed")` | No state change, no SO created |

---

## Chatter Copy (Plain Business View, Memory Application)

Chatter text per `feedback_end_user_docs_plain_view.md` (no REQ codes, operator-friendly, escaped via `Markup(escape(...))`):

### Enquiry Chatter (Line 277)

```python
self.message_post(body=_("Converted to %s") % order.name)
```

**Actual output example**: `"Converted to SO0012345"` or `"Converted to [SO] Sale Order 00012345"`

Current implementation is plain and correct. No Markup/escape needed here because `order.name` is a field from our own model (no user-supplied input).

### Order Chatter (Line 278)

```python
order.message_post(body=_("Created from enquiry %s") % self.name)
```

**Actual output example**: `"Created from enquiry Enquiry from buyer@example.com · 2026-05-06"`

Current implementation is plain and correct. `self.name` is computed from our own `partner_email` + `create_date`, not user-supplied.

**Twist**: Memory `feedback_fr017_write_defense_in_depth.md` 11th confirmation documents defensive use of `Markup(escape(...))` when interpolating operator-supplied input (e.g., notes from a wizard, subject lines from a form). This action receives NO user input at action-call time — all fields are pre-set on the enquiry. No escape needed beyond standard Odoo sanitization.

**Verdict**: Current chatter is safe and business-appropriate. No changes needed.

---

## Test Cases (Phase 2 ORM)

Write tests **before** implementation per TDD. The implementation is already in the code, so tests verify the existing behavior. Tests must be comprehensive (T063–T065 coverage):

### Test 1: Happy Path from `state='new'` (T063)

```python
def test_convert_from_new_creates_order_and_flips_state(self):
    """Test action_convert_to_quote() from 'new' state creates draft SO + transitions enquiry."""

    # Setup
    enq = self._create_enquiry(
        state='new',
        partner_id=self.partner.id,
    )
    original_name = enq.name

    # Execute
    action = enq.action_convert_to_quote()

    # Verify return is act_window action
    self.assertEqual(action['type'], 'ir.actions.act_window')
    self.assertEqual(action['res_model'], 'sale.order')

    # Verify enquiry state transition
    self.assertEqual(enq.state, 'converted')
    self.assertIsNotNone(enq.converted_at)
    self.assertIsNotNone(enq.converted_order_id)

    # Verify order created with correct fields
    order = enq.converted_order_id
    self.assertEqual(order.state, 'draft')
    self.assertEqual(order.partner_id.id, self.partner.id)
    self.assertEqual(order.origin, original_name)

    # Verify chatter posted on both records
    enq_messages = enq.message_ids.filtered(lambda m: m.body and m.body.strip())
    self.assertTrue(enq_messages)
    self.assertTrue(any('Converted' in msg.body for msg in enq_messages))

    order_messages = order.message_ids.filtered(lambda m: m.body and m.body.strip())
    self.assertTrue(order_messages)
    self.assertTrue(any('Created from enquiry' in msg.body for msg in order_messages))
```

### Test 2: Happy Path from `state='qualified'` (Extension beyond T063)

```python
def test_convert_from_qualified_creates_order_and_flips_state(self):
    """Test action_convert_to_quote() from 'qualified' state also works."""

    enq = self._create_enquiry(
        state='qualified',
        partner_id=self.partner.id,
    )

    action = enq.action_convert_to_quote()

    # Same assertions as T063
    self.assertEqual(enq.state, 'converted')
    self.assertIsNotNone(enq.converted_order_id)
    # ... rest of assertions from T063
```

### Test 3: Idempotency from `state='converted'` (T064)

```python
def test_convert_idempotency_from_converted_state(self):
    """Test re-invocation when state='converted' returns existing order without duplicate."""

    # Setup: create enquiry and convert once
    enq = self._create_enquiry(
        state='new',
        partner_id=self.partner.id,
    )
    first_action = enq.action_convert_to_quote()
    first_order_id = enq.converted_order_id.id

    # Count chatter messages after first convert
    first_msg_count = len(enq.message_ids)

    # Re-invoke action (idempotency test)
    second_action = enq.action_convert_to_quote()

    # Verify same order is returned
    self.assertEqual(second_action['res_id'], first_order_id)
    self.assertEqual(enq.converted_order_id.id, first_order_id)

    # Verify no duplicate sale.order created
    all_orders = self.env['sale.order'].search([
        ('origin', '=', enq.name),
        ('partner_id', '=', self.partner.id),
    ])
    self.assertEqual(len(all_orders), 1, "Only one SO should exist")

    # Verify no new chatter message posted on second invocation
    second_msg_count = len(enq.message_ids)
    self.assertEqual(first_msg_count, second_msg_count,
                     "No new chatter message should be posted on idempotent re-call")
```

### Test 4: Pre-condition from `state='closed'` Raises UserError (T065)

```python
def test_convert_from_closed_raises_user_error(self):
    """Test action_convert_to_quote() from 'closed' state raises UserError."""

    enq = self._create_enquiry(
        state='closed',
        closed_reason='spam',
    )

    with self.assertRaises(UserError):
        enq.action_convert_to_quote()

    # Verify no order created
    self.assertFalse(enq.converted_order_id)
    self.assertFalse(enq.converted_at)
```

### Test 5: `_match_or_create_partner()` called when `partner_id` empty

```python
def test_convert_calls_match_or_create_partner_when_empty(self):
    """Test action_convert_to_quote() calls _match_or_create_partner() if partner_id is False."""

    # Create enquiry with NO partner_id, but with partner_email
    enq = self._create_enquiry(
        state='new',
        partner_id=None,
        partner_email='newbuyer@example.com',
    )

    action = enq.action_convert_to_quote()

    # Verify partner was created/matched
    self.assertIsNotNone(enq.partner_id)
    self.assertEqual(enq.partner_id.email_normalized, 'newbuyer@example.com')

    # Verify order was created with the matched/created partner
    order = enq.converted_order_id
    self.assertEqual(order.partner_id.id, enq.partner_id.id)
```

### Test 6: FR-017 12th Confirmation — State-Machine Guard Mirrors in write()

```python
def test_state_machine_guard_blocks_direct_write_to_converted_when_closed(self):
    """Test FR-017: direct write({'state': 'converted'}) from 'closed' is blocked.

    Memory `feedback_fr017_write_defense_in_depth.md` 12th confirmation:
    action_convert_to_quote() guards via write() override in the model.
    Verify the guard mirrors all state-machine constraints.
    """

    enq = self._create_enquiry(state='closed', closed_reason='spam')

    # Direct write attempt (bypassing action) should fail
    with self.assertRaises(ValidationError):
        enq.write({'state': 'converted'})

    # Enquiry should remain in 'closed' state
    enq.invalidate_recordset()
    self.assertEqual(enq.state, 'closed')
```

### Test 7: XSS Regression — Chatter Escape (if user-supplied input existed)

```python
def test_chatter_xss_safe_when_partner_email_contains_html(self):
    """Test chatter body is escaped if partner_email (tracked field) contains HTML.

    Memory `feedback_fr017_write_defense_in_depth.md`: Markup(escape(...)) pattern.
    While action_convert_to_quote() chatter does NOT interpolate partner_email,
    verify that if the field is updated elsewhere, the mail.message tracking
    does not render raw HTML.
    """

    enq = self._create_enquiry(
        state='new',
        partner_email='<script>alert("xss")</script>@example.com',
        partner_id=self.partner.id,
    )

    # Convert the enquiry
    action = enq.action_convert_to_quote()

    # Verify chatter body on the order is safe (no script tags)
    order = enq.converted_order_id
    order_messages = order.message_ids.filtered(lambda m: m.body and m.body.strip())
    for msg in order_messages:
        self.assertNotIn('<script>', msg.body,
                         "Chatter body must escape HTML")
```

---

## Agent Dispatch Order

Orchestrator will execute Phases 2–9 after this plan lands:

1. **Phase 2 (RED)** — `tdd-guide` agent:
   - Write failing tests in `test_phase2_orm_enquiry.py`
   - Run `odoo --test-tags /multichannel_hub_core:TestEnquiryConvert --stop-after-init`
   - Verify tests fail with the right reason (implementation exists, but tests assert new behavior)

2. **Phase 3 (GREEN)** — Orchestrator direct:
   - Slice is too small (~80 LOC already in place) for sub-agent
   - Verify tests now pass
   - Implementation already in file; just verify test alignment

3. **Phase 4 (Review)** — Parallel agents (single message, two `Agent` calls):
   - `code-reviewer` — verify test quality, ORM patterns, readability
   - `security-reviewer` — verify ACL gates, chatter escape safety, no `sudo()` without comment
   - Block on CRITICAL/HIGH; address MEDIUM advisories per memory pattern

4. **Phase 5 (Verify)**:
   - `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init`
   - `docker exec namco_odoo19 odoo -d namco_odoo19 --test-tags /multichannel_hub_core:TestEnquiryConvert --stop-after-init`
   - `ruff check custom_addons/multichannel_hub_core/` (check for debug statements)
   - Grep: `grep -rE "_logger\.info\(|^[[:space:]]*print\(" custom_addons/multichannel_hub_core/tests/test_phase2_orm_enquiry.py`

5. **Phase 6 (Commit)**:
   - One conventional commit: `[multichannel_hub_core] test(p3-lead-convert): add convert-to-quote ORM tests`
   - Body cites T063–T067; notes that implementation already landed in P3-LEAD-MODEL; lists any deviations from contract

6. **Phase 7 (Document)**:
   - Mark `[X]` T063–T067 in `tasks.md`
   - Update tracker P3-LEAD-CONVERT → `done`, landing record, `last reviewed` 2026-05-07
   - Append to `findings.md` if any surprises (test gotchas, assertion brittleness, etc.)

7. **Phase 8 (Learn)**:
   - Run `/learn` to capture any reusable patterns (idempotency pattern, chatter audit-trail pattern, Markup escape, etc.)
   - Threshold: at least one explicit insight

8. **Phase 9 (Land)**:
   - Commit lands on `feature/006-master-plan-coding`
   - Merge to `main` deferred until W7 E2E sprint passes (per playbook)

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Implementation already exists; tests fail due to behavior mismatch | Medium | High | Orchestrator must read the stub carefully before writing tests. Compare against `contracts/enquiry_actions.md` line-by-line. |
| Idempotency test assertion on message count is brittle (tracking might add extra rows) | Low | Medium | Filter messages by `body` content, not just count. Assert specific strings present/absent. |
| `partner_id` is False AND `partner_email` is False — what then? | Low | Low | Contract silent; code raises "Cannot convert: enquiry has no partner and no email to create one from." Acceptable — test for this edge case. |
| Chatter `Markup(escape(...))` pattern conflicts with `_()` translation wrapper | Low | Medium | Code currently uses `_("Converted to %s") % order.name` (plain string, no Markup). If translation needs escaping, consult memory `feedback_end_user_docs_plain_view.md`. No action needed for this slice. |
| State-machine guard in `write()` override already exists; test may verify existing logic, not new | Low | Low | This is expected — P3-LEAD-MODEL implemented the guard. This slice verifies it works in the convert context. |
| Test isolation: `created_at` timestamp may differ between runs, causing `name` compute to differ | Low | Low | Use `assertRegex()` or parse the date, don't hardcode expected name. Already shown in Test 1. |

---

## Exit Criteria Checklist

All required before slice is marked `done`:

- [ ] Phase 2 tests (T063–T067) written and failing for correct reasons (KeyError on unimplemented method, etc.)
- [ ] Phase 3 tests pass (implementation already in code; tests verify existing behavior)
- [ ] Phase 4 code-reviewer + security-reviewer parallel pass; no CRITICAL/HIGH issues
- [ ] Phase 5 verify: `odoo -u multichannel_hub_core --stop-after-init` exit 0
- [ ] Phase 5 verify: `--test-tags /multichannel_hub_core:TestEnquiryConvert` all green
- [ ] Phase 5 verify: `ruff check` clean; no `_logger.info()` or `print()` in test code
- [ ] Tracker P3-LEAD-CONVERT `state` → `done`, `last reviewed` 2026-05-07
- [ ] `tasks.md` tasks T063–T067 marked `[X]`
- [ ] `findings.md` appended with surprises (or explicit "no new patterns" note)
- [ ] `/learn` executed; memory entry created (if applicable)
- [ ] Manifest version bumped: 19.0.1.0.22 → 19.0.1.0.23

---

## Acceptable Shortcuts Review

Per playbook §"Acceptable shortcuts", this slice is ~80 LOC + tests (non-trivial; meets thresholds). **NO phases can be skipped**:

- **Phase 1 Plan** — This document; cannot skip.
- **Phase 2 RED** — TDD mandatory; tests first.
- **Phase 3 GREEN** — Small but required; verify tests pass.
- **Phase 4 Review** — Security-sensitive (chatter escape, ACL); parallel review required.
- **Phase 5 Verify** — Module install + full test run + ruff; non-negotiable.
- **Phase 6 Commit** — Git hygiene; conventional format required.
- **Phase 7 Document** — Tracker + tasks.md + findings.md; audit trail required.
- **Phase 8 Learn** — `/learn` execution; memory capture required.

All 9 phases must execute.

---

## Blockers

**NONE IDENTIFIED**. Slice is unblocked and ready for Phase 2 (RED) dispatch.

---

## Notes

- Slice is a "verification + test-coverage" slice, not greenfield implementation. Method `action_convert_to_quote()` already exists and is production-ready per P3-LEAD-MODEL landing (2026-05-07, commit 31aa4b3f01d).
- Test-first discipline applies anyway — verify the behavior is as spec'd by writing tests.
- Memory applications: `feedback_fr017_write_defense_in_depth.md` (12th confirmation candidate on state-machine guard mirroring); `feedback_odoo19_test_gotchas.md` (entries 74–75 on `assertRaises` tuple + `message_post` defaults); `feedback_end_user_docs_plain_view.md` (plain business language in chatter copy).
- Cross-slice: T062 (poller-extension) depends on this slice being done (enquiry model fully operational).
