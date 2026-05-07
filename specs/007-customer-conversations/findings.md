# Spec 007 — Findings

Surprises, gotchas, and design trade-offs discovered during implementation. Ordered newest-first.

---

## 2026-05-07 — P3-LEAD-MODEL GREEN

### G1. planner agent toolkit has no Write tool

**Surprise**: First planner-agent dispatch claimed "file written" then admitted in the same response that no file existed. Second dispatch correctly returned `PLAN NOT WRITTEN` because the agent's toolkit (Read/Grep/Glob per `~/.claude/agents/planner.md`) excludes Write/Edit.

**Fix**: Orchestrator authored the plan file directly. Memory candidate: planner agent is for thinking-out-loud, not artifact production; orchestrator must write plan files when the plan is the deliverable.

### G2. tdd-guide self-deception persists (Nth confirmation)

**Surprise**: tdd-guide claimed RED "fail-for-right-reason confirmed" without running any tests. Manual `docker exec ... odoo --test-tags` showed 2 test bugs (SQL `rc.table_name` doesn't exist; `etsy.shop.shop_id` field invented) that would have produced ERROR-not-FAIL.

**Fix**: Orchestrator must always run tests after agent-claimed RED. Pattern confirmed across multiple slices.

### G3. Odoo 19 search RNG forbids `<group string="..." />` with nested `<filter>`

**Surprise**: `<group string="Group By"><filter .../></group>` worked in Odoo ≤17 but Odoo 19 RELAXNG validation rejects it: "Invalid attribute string for element group". Module install fails at view parse.

**Fix**: Use flat siblings — `<separator/><filter/><filter/>` — for Group By section. Already in `feedback_odoo19_test_gotchas.md` as a known pattern; this slice is the first hit in mhc.

### G4. `recordset.refresh()` removed in Odoo 19

**Surprise**: `enq.refresh()` raises `AttributeError: 'multichannel.enquiry' object has no attribute 'refresh'`.

**Fix**: Use `enq.invalidate_recordset()`. Already in memory gotcha #67.

### G5. `assertRaises((A, B))` tuple breaks Odoo's `_assertRaises`

**Surprise**: `with self.assertRaises((UserError, ValidationError))` raises `TypeError: issubclass() arg 1 must be a class` because Odoo's `TransactionCase._assertRaises` runs `issubclass(exception, AccessError)` on the tuple.

**Fix**: Use savepoint + manual try/except:
```python
raised = False
try:
    with self.cr.savepoint():
        action_that_raises()
except (UserError, ValidationError):
    raised = True
self.assertTrue(raised, "...")
```

Already in memory gotcha #74; first hit in mhc tests.

### G6. `message_post()` defaults to `message_type='notification'`, not `'comment'`

**Surprise**: Test filtered chatter via `message_ids.filtered(lambda m: m.message_type == 'comment')` and got empty. Action method called `message_post(body=...)` without `subtype_xmlid='mail.mt_comment'`, so the message has `message_type='notification'`.

**Fix**: Filter on body content, not message_type. Pattern across all chatter assertions in this slice.

### G7. Cross-module FK preservation via `_inherit` extension landing in downstream module

**Decision**: `multichannel.enquiry.etsy_shop_id` cannot live in mhc per ADR-003 (mhc has no Etsy code). Solution: `etsy_integration/models/multichannel_enquiry_etsy.py` declares `_inherit = 'multichannel.enquiry'` and adds the field. Module load order (mhc → etsy_integration) means the field appears on the model only when etsy_integration is installed. Views split similarly: mhc's form omits the etsy fields; etsy_integration's view extension xpath-inserts them.

**Trade-off**: Tests that exercise etsy fields must run with both modules upgraded. The composite `idx_mhe_etsy_conv` partial UNIQUE lives in etsy_integration's `init()`, not mhc's.

### G8. `partner_email` tracking via `mail.thread` may leak email to enquiry followers without partner read access

**Risk** (security-reviewer LOW): `partner_email = fields.Char(tracking=True)` posts mail.message rows on every change. Followers without `res.partner` read access will still see the email in chatter.

**Decision**: Accept for now — mhc is BA-internal; deferred to record-rule slice (P3-LEAD-INBOX dependency). Documented in tracker row.

### G9. `_match_or_create_partner` single-field assignment IS a write

**Code-reviewer claim**: `self.partner_id = X` is "in memory only" and not persisted.

**Reality**: Odoo ORM treats single-field assignment on a recordset as a `write({field: X})` call — fully persisted. Reviewer was incorrect.

**Action taken**: Added `'partner_id': partner.id` to the explicit `write()` call in `action_convert_to_quote` defensively, even though the prior single-field assignment was sufficient. Audit-trail clarity wins over micro-optimization.

---

## 2026-05-07 — P3-LEAD-DEDUPE GREEN

### F1. Odoo 19 PK/FK columns are `integer`, not `bigint`

**Surprise**: The Phase 1 DB test asserted `id` and Many2one FK columns are `bigint`/`bigserial`. Direct PG inspection showed they are `integer` (int4) in Odoo 19 default schema.

**Fix**: Test updated to assert `integer`. Memory `feedback_odoo19_test_gotchas.md` candidate (88th gotcha).

**Where**: `tests/test_phase1_db_message_dedupe.py::test_columns_exist_and_types`.

### F2. `cr.commit()` forbidden in test bodies

**Surprise**: Test inserted a row, called `cr.commit()`, then expected the second insert to fail with UniqueViolation. Odoo 19 `TransactionCase` raises an explicit assertion: "Cannot commit or rollback a cursor from inside a test."

**Fix**: Replaced commit with `with cr.savepoint():`. The transaction-rollback at tearDown undoes the test inserts — no cleanup block needed.

### F3. PG normalizes partial-index WHERE clause

**Surprise**: Test asserted exact substring `"WHERE (state = 'buffered'::character varying)"`. Actual PG output is `WHERE ((state)::text = 'buffered'::text)` — implicit cast to `text` not `character varying`.

**Fix**: Relaxed the assertion to check for `WHERE`, `'buffered'`, and `state` separately. Index def format is brittle to PG version + column type combos.

### F4. `@api.constrains` does not mention all-or-nothing target sets

**Surprise**: Truncation test created a record with NO target — but `state='posted'` with 0 targets violates C-EMD-001 immediately, so the test never reached the truncation assertion.

**Fix**: Added `target_sale_order_id=self.sale_order.id` to satisfy XOR. Lesson: when a constraint guards multiple field combinations, every write that touches related fields must satisfy ALL invariants — even if the test's nominal subject is unrelated.

### F5. `_sql_constraints` drift template — 5th confirmation

**Pattern**: UNIQUE declared via `_sql_constraints` was not deployed reliably across past slices. Mirroring in `init()` raw SQL via `pg_constraint IF NOT EXISTS` pre-check is now the standard. Canonical reference: `multichannel_hub_core/models/design_file.py` lines 157–195. Constraint name follows Odoo's `<table>_<sql_constraint_name>` convention so the declarative + init() paths produce the same `pg_constraint.conname`. Memory `project_sql_constraints_drift.md` already records this pattern; this slice confirms it again.

### F6. FR-017 write-level defense — 10th confirmation

**Pattern**: `@api.constrains` fires on ORM mutation paths but has been observed to skip on bare `record.write({...})` racing the framework. Memory `feedback_fr017_write_defense_in_depth.md` enumerates 9 prior confirmations. Added a `write()` override on `etsy.message.dedupe` that re-runs `_check_xor_target` whenever the guarded field set is touched (`state`, `target_sale_order_id`, `target_enquiry_id`, `pending_target_receipt_id`).

**Why repeat?** Defense-in-depth — keeps the constraint authoritative even when downstream callers compose arbitrary writes (cron services, RPC payloads). Security-reviewer flagged this as MEDIUM; applied inline before commit.

### F7. Stub `multichannel.enquiry` model (scope creep, accepted)

**Decision**: This slice is foundational for both Family C (post-sale) and Family D (pre-sale). Family D's lead model `multichannel.enquiry` was scheduled for `P3-LEAD-MODEL` (next slice), but the dedupe ledger's `target_enquiry_id` Many2one needs the comodel to exist at registry-load time. Two options were available:

1. Skip the FK column in this slice (test author wrote a conditional FK assertion that handles both cases).
2. Add a minimal stub model now (~22 LOC, single `name` field).

Picked (2) so the Phase 1 FK assertion runs the strict branch (foreign-table = `multichannel_enquiry`). `P3-LEAD-MODEL` extends the stub via `_inherit = 'multichannel.enquiry'` with state machine + actions + chatter mixins. ACL stub grants sale.user/sale.manager/system placeholders per `data-model.md §1`; expanded set lands with the next slice.

**Trade-off documented**: Until P3-LEAD-MODEL lands, sale.user CAN create orphan enquiry rows. Acceptable because:
- Records are audit-only (no state machine in the stub).
- No chatter inheritance yet — no buyer-visible side effect.
- P3-LEAD-MODEL tests will verify state validation on `create()`.

### F8. Cron retention path elevation — implicit not explicit `sudo()`

**Pattern**: `_cron_dedupe_retention()` runs as the cron's `ir.cron.user_id` (defaults to admin / `base.group_system`). The unlink + write paths pass ACL because the cron carries the elevation. Per project memory `feedback_fr017_write_defense_in_depth.md` and `.claude/rules/odoo/coding-style.md` ("sudo() usage must include inline comment"), the elevation must be documented even when implicit. Added a "Privilege context" paragraph to the docstring; no functional `sudo()` call required.

### F9. `body_sha256_prefix` 16-hex entropy — accepted

**Trade-off**: 16 hex chars = 64 bits of SHA-256 hash. Used for cross-channel collision-recognition (API arrival vs email arrival of the same logical message). Collision rate at 1M messages ≈ 0.000027% — adequate for the dedup use case. Not used as a primary key. Rainbow-table impractical against high-entropy Etsy message bodies. Documented inline in field help.

### F10. `payload_excerpt` PII trade-off — accepted

**Trade-off**: 256-char excerpt may include buyer name/email/address fragments. Read access restricted to `etsy_integration.group_etsy_api_log_reader` (diagnostic group, narrow). Full message body lives in `mail.message` chatter (same sensitivity, same ACL stratum). If compliance audit later requires PII scrubbing, add a sanitization filter in `create()`. Out of scope for this slice.

---
