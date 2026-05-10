# P4-01-C — Gearment state machine + quote wizard + form button (D5)

**Slice ID**: P4-01-C
**Sub-phase of**: P4-01 (per `p4-01-plan.md` §3 Sub-phase C)
**Branch**: `feature/006-master-plan-coding`
**Depends on**: P4-01-B ✓ (adapter contract correct, `confirm()` implemented)
**Phase 1 author**: planner agent (Sonnet) 2026-05-10
**Estimated**: ~635 LOC including tests

---

## 1. Decisions

### E1 — Coexist `x_gearment_status` and `x_gearment_outbound_state` (E1.b)

Keep both. `x_gearment_status` reflects Gearment-side fulfillment (webhook-driven, pending/accepted/in_production/shipped/failed). `x_gearment_outbound_state` reflects Odoo-side push lifecycle (operator-driven, draft/quoted/operator_review/confirmed/cancelled). No migration; new field added alongside.

### E2 — Quote fields on `sale.order` (E2.a)

`x_gearment_quote_total` Float, `x_gearment_quote_currency` Char, `x_gearment_quote_expires_at` Datetime, `x_gearment_quote_breakdown_json` Text. All readonly. Persisting on order means the operator can close + re-open the wizard without re-fetching while still valid.

### E3 — State guard against double-click (E3.a)

Wizard `action_confirm` checks `state == 'operator_review'` BEFORE adapter call; raises `UserError` if not. Combined with Gearment's idempotency (Idempotency-Key SHA-256 from P4-01-B), second click finds `state='confirmed'` and raises a clean error.

### E4 — Expired quote raises (E4.a)

If `x_gearment_quote_expires_at < now()` when `action_confirm` fires, raise `UserError("Quote expired — fetch a new one")`. Operator clicks "Get Quote" again. Auto-refresh would risk silent price change without operator review.

### E5 — Form button visibility (E5.b)

Visible when `sales_channel == 'etsy'` AND `x_gearment_outbound_ref` is empty AND at least one product has `x_gearment_sku` set. Last condition is gated server-side in `action_get_gearment_quote` (cheap-to-check); view condition uses the simpler two-clause test.

---

## 2. File-by-file change list

| File | Type | Scope | LOC |
|---|---|---|---|
| `models/sale_order.py` (mhf) | EDIT | +`x_gearment_outbound_state` Selection (5 keys, default=draft, tracking=True) +4 quote fields +`_advance_gearment_state(target)` helper +`action_get_gearment_quote()` +`action_open_gearment_quote_wizard()` | +120 |
| `wizards/gearment_quote_wizard.py` | NEW | TransientModel `gearment.quote.wizard`; M2O order_id + 4 readonly quote mirrors; `action_confirm` (FR-017 11th confirmation) + `action_cancel` | 100 |
| `wizards/__init__.py` | NEW | `from . import gearment_quote_wizard` | 1 |
| `views/gearment_quote_wizard_views.xml` | NEW | Form view: order info, quote breakdown table, expires-at countdown, Confirm/Cancel buttons | 50 |
| `views/sale_order_views.xml` (mhf) | EDIT | +"Sync to Gearment" button (group_ba_shipping; visibility per E5.b) +"Gearment" notebook tab showing state + quote breakdown + smart link to gearment.api.log | +60 |
| `security/ir.model.access.csv` | EDIT | +2 rows for `gearment.quote.wizard` (ba_shipping read/write/create=1; manager same) | +2 |
| `__manifest__.py` | EDIT | Bump 19.0.1.0.16 → 19.0.1.0.17; add wizards/__init__.py + new view files | +3 |
| `tests/test_p4_01_c_state_machine_db.py` | NEW (RED) | Phase 1 DB: 6 tests pinning new field + Selection values + readonly + tracking + transient wizard | 80 |
| `tests/test_p4_01_c_state_machine_orm.py` | NEW (RED) | Phase 2 ORM: 9 tests covering state transitions + idempotency + quote write-through + expired guard + wizard FR-017 gate + double-click race + cancel-clears-ref + form button visibility | 200 |
| `tests/__init__.py` | EDIT | Register 2 new test modules | +2 |

---

## 3. Slice tasks (for tasks.md)

```
- [ ] T4-01-C-01 RED Phase 1 DB: x_gearment_outbound_state Selection (5 keys, default=draft, tracking=True)
- [ ] T4-01-C-02 RED Phase 1 DB: 4 quote fields exist + readonly contract
- [ ] T4-01-C-03 RED Phase 1 DB: gearment.quote.wizard is TransientModel
- [ ] T4-01-C-04 RED Phase 2 ORM: state transitions (draft→quoted→operator_review→confirmed; quoted→cancelled)
- [ ] T4-01-C-05 RED Phase 2 ORM: _advance_gearment_state idempotency (no-op when already at/past target)
- [ ] T4-01-C-06 RED Phase 2 ORM: action_get_gearment_quote calls adapter, writes quote fields, transitions to 'quoted'
- [ ] T4-01-C-07 RED Phase 2 ORM: action_get_gearment_quote raises if no Gearment-eligible lines (E5.b enforcement)
- [ ] T4-01-C-08 RED Phase 2 ORM: wizard.action_confirm requires state=='operator_review'; raises UserError otherwise (E3 guard)
- [ ] T4-01-C-09 RED Phase 2 ORM: wizard.action_confirm checks _check_ba_shipping_or_raise BEFORE sudo().write() (FR-017 11th confirmation)
- [ ] T4-01-C-10 RED Phase 2 ORM: wizard.action_confirm raises if quote expired (E4)
- [ ] T4-01-C-11 RED Phase 2 ORM: wizard double-click race — second action_confirm finds state='confirmed' and raises
- [ ] T4-01-C-12 RED Phase 2 ORM: wizard.action_cancel transitions to 'cancelled' + clears x_gearment_outbound_ref
- [ ] T4-01-C-13 GREEN: x_gearment_outbound_state + 4 quote fields + _advance_gearment_state helper on mhf sale.order
- [ ] T4-01-C-14 GREEN: action_get_gearment_quote + action_open_gearment_quote_wizard (mhf sale.order)
- [ ] T4-01-C-15 GREEN: gearment.quote.wizard TransientModel + form view; action_confirm + action_cancel
- [ ] T4-01-C-16 GREEN: form button "Sync to Gearment" + Gearment notebook tab on mhf sale_order_views.xml
- [ ] T4-01-C-17 GREEN: ACL CSV row for gearment.quote.wizard + manifest bump 19.0.1.0.17
- [ ] T4-01-C-18 Run code-reviewer + security-reviewer in parallel; block on CRITICAL/HIGH
- [ ] T4-01-C-19 Verify: -u multichannel_hub_fulfillment exit 0; full test tags green; grep _logger.info/print
- [ ] T4-01-C-20 Update tracker P4-01-C row → done; append findings.md §"P4-01-C" with E1-E5 + FR-017 11th confirmation
```

---

## 4. Risks

| Risk | P | I | Mitigation |
|---|---|---|---|
| Double-click race on Confirm | M | M | E3 state guard + Gearment Idempotency-Key (P4-01-B) |
| Wizard cancel leaves stale ref | L | M | action_cancel clears x_gearment_outbound_ref (test T4-01-C-12) |
| Expired-quote race | L | M | E4 server-side check (test T4-01-C-10) |
| Gearment 202 (async accepted) not 200 | L | M | Adapter doesn't parse status_code in body — accepts 200/202 uniformly |
| Quote currency mismatch with order currency | L | L | Stored separately; operator sees both in form |
| Form button visibility breaks on missing SKU | M | M | Server-side gate in action_get_gearment_quote raises UserError |
| FR-017 gate placed wrong (allows non-shipping users) | M | H | Inline comment cites confirmation #11; security-reviewer must verify |

---

## 5. Phase 2..9 hand-off

1. Phase 2 RED — author 2 test files (DB + ORM); verify all fail for the right reasons
2. Phase 3 GREEN — implement model edits + wizard + view; run tests after each cycle
3. Phase 4 Review — parallel code-reviewer + security-reviewer
4. Phase 5 Verify — odoo -u mhf --stop-after-init exit 0; full mhf test tags; cross-module spot check
5. Phase 6 Commit — RED commit + GREEN commit + docs commit
6. Phase 7 Document — tasks.md [X], tracker P4-01-C → done, findings.md §"P4-01-C"
7. Phase 8 Learn — /learn capture (wizard modal lifecycle, state guard pattern, E1 coexistence rationale)
