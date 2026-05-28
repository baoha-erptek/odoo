# Implementation Plan: P3-LEAD-DEDUPE (etsy.message.dedupe Model)

**Slice ID**: `P3-LEAD-DEDUPE` | **Branch**: `feature/006-master-plan-coding` | **Phase**: Master Plan 006 — Phase 1 (Plan)
**Date**: 2026-05-07 | **Scope**: Tasks T003–T010 from `specs/007-customer-conversations/tasks.md`

## Executive Summary

Implement `etsy.message.dedupe` — a high-volume audit ledger that deduplicates buyer messages across Etsy API and email-parser channels, buffers messages when their target order hasn't ingested yet, and implements retention. **Foundational** slice blocking both Family C (post-sale, US1) and Family D (pre-sale, US2). 10 fields, no chatter (per `etsy.api.log` precedent). Raw SQL in `init()` mirrors UNIQUE per `project_sql_constraints_drift.md`.

**Target**: ~150 LOC implementation + ~200 LOC tests.

---

## Affected Files

### **Phase 2 (RED) — Test Files First**
```
NEW  custom_addons/etsy_integration/tests/test_phase1_db_message_dedupe.py (T003)
NEW  custom_addons/etsy_integration/tests/test_phase2_orm_message_dedupe.py (T004, T010)
```

### **Phase 3 (GREEN) — Implementation**
```
NEW  custom_addons/etsy_integration/models/etsy_message_dedupe.py (T005)
EDIT custom_addons/etsy_integration/models/__init__.py (T006)
EDIT custom_addons/etsy_integration/security/ir.model.access.csv (T007)
EDIT custom_addons/etsy_integration/models/etsy_api_log.py (T008)
EDIT custom_addons/etsy_integration/data/ir_cron_data.xml (T009)
EDIT custom_addons/etsy_integration/__manifest__.py (version bump)
```

---

## Schema Snapshot (from data-model.md §2)

### Table: `etsy_message_dedupe`

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `etsy_shop_id` | Many2one → `etsy.shop` | required, ondelete='cascade', index | Shop's mailbox |
| `etsy_message_id` | Char(255) | required, indexed, part of UNIQUE | Real API ID or synthesized for email |
| `body_sha256_prefix` | Char(16) | indexed | First 16 hex of SHA-256(body) — API/email collision reconcile |
| `channel` | Selection | required `[('api','API'),('email','Email')]` | Which channel posted first |
| `posted_at` | Datetime | required | Buyer-side timestamp UTC |
| `target_sale_order_id` | Many2one → `sale.order` | ondelete='set null' | Null if pre-sale or buffered |
| `target_enquiry_id` | Many2one → `multichannel.enquiry` | ondelete='set null' | Null if post-sale or buffered |
| `pending_target_receipt_id` | Char(255) | indexed | Receipt ID when message arrived before order |
| `state` | Selection | required, default `'posted'`, `[('posted','Posted'),('buffered','Buffered'),('orphaned','Orphaned')]` | Lifecycle |
| `payload_excerpt` | Char(256) | — | First 256 chars of body (audit only) |

### Constraints

- **UNIQUE `(etsy_shop_id, etsy_message_id)`**: `_sql_constraints` + `init()` raw SQL mirror.
- **Partial index `idx_emd_pending`** ON `(etsy_shop_id, pending_target_receipt_id)` WHERE `state='buffered'` — via `init()`.
- **C-EMD-001 XOR**: `@api.constrains` enforces:
  - `state='posted'`: exactly one of `target_sale_order_id` / `target_enquiry_id` / `pending_target_receipt_id` set
  - `state='buffered'`: only `pending_target_receipt_id` set

---

## init() Raw-SQL Block (per drift template)

Canonical reference: `multichannel_hub_core/models/design_file.py` `init()`.

```python
def init(self):
    """Mirror UNIQUE constraint + create partial index per project_sql_constraints_drift.md (5th confirmation likely)."""
    cr = self.env.cr
    cr.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'etsy_message_dedupe_uniq_emd_shop_message_id'
            ) THEN
                ALTER TABLE etsy_message_dedupe
                    ADD CONSTRAINT etsy_message_dedupe_uniq_emd_shop_message_id
                    UNIQUE (etsy_shop_id, etsy_message_id);
            END IF;
        END $$
    """)
    cr.execute("""
        CREATE INDEX IF NOT EXISTS idx_emd_pending
        ON etsy_message_dedupe (etsy_shop_id, pending_target_receipt_id)
        WHERE state = 'buffered'
    """)
```

NOTE: Constraint name follows Odoo's `<table>_<sql_constraint_name>` convention so `_sql_constraints` and `init()` mirror produce the same `pg_constraint` row.

---

## Test Plan

### Phase 1 DB tests (T003) — `test_phase1_db_message_dedupe.py`

| Test method | Assertion |
|---|---|
| `test_table_exists` | `information_schema.tables` has `etsy_message_dedupe` |
| `test_columns_exist_and_types` | All 10 fields present with correct types |
| `test_unique_constraint_enforced` | Two direct `INSERT`s with same `(shop_id, msg_id)` → `IntegrityError` (PG 23505) |
| `test_partial_index_idx_emd_pending_exists` | `pg_indexes.indexdef` contains `WHERE state = 'buffered'` |
| `test_foreign_keys` | FK ondelete CASCADE on shop, SET NULL on order/enquiry |

**Fail-for-right-reason**: Each test fails before model lands (table doesn't exist → all tests RED).

### Phase 2 ORM tests (T004 + T010) — `test_phase2_orm_message_dedupe.py`

| Test method | Assertion |
|---|---|
| `test_create_basic_posted_record` | Create with all fields → succeeds |
| `test_xor_constraint_posted_zero_targets` | `state='posted'`, no targets → `ValidationError` |
| `test_xor_constraint_posted_two_targets` | `state='posted'`, 2 targets → `ValidationError` |
| `test_xor_constraint_buffered_only_pending` | `state='buffered'` + `pending_target_receipt_id` only → succeeds |
| `test_xor_constraint_buffered_with_order` | `state='buffered'` + `target_sale_order_id` → `ValidationError` |
| `test_acl_api_log_reader_read_only` | `group_etsy_api_log_reader` create → `AccessError`; search → succeeds |
| `test_acl_base_group_system_full` | `base.group_system` create+write+unlink → all succeed |
| `test_payload_excerpt_truncation` | Create with 300-char body → stored as exactly 256 |
| `test_retention_cron_posted_old_deleted` | `posted_at = now-31d, state='posted'` → unlinked |
| `test_retention_cron_posted_recent_kept` | `posted_at = now-15d, state='posted'` → kept |
| `test_retention_cron_orphaned_kept_indefinitely` | `posted_at = now-31d, state='orphaned'` → kept |
| `test_retention_cron_buffered_aged_to_orphaned` | `posted_at = now-8d, state='buffered'` → flipped to `orphaned` |

### Test runner command (per memory `feedback_odoo19_test_gotchas.md`):

```bash
docker exec namco_odoo19 odoo -d namco_odoo19 \
  --test-tags /etsy_integration:TestPhase1DbMessageDedupe \
  --stop-after-init --http-port 18999 --gevent-port 18998 -u etsy_integration

docker exec namco_odoo19 odoo -d namco_odoo19 \
  --test-tags /etsy_integration:TestPhase2OrmMessageDedupe \
  --stop-after-init --http-port 18999 --gevent-port 18998 -u etsy_integration
```

---

## Open Questions (resolved)

1. **`payload_excerpt` truncation: `create()` only?** YES. Body is immutable post-creation; no `write()` override needed.
2. **Retention cron killswitch (FR-035 pattern)?** NO. This is hygiene, not a feature toggle. Disabling causes audit bloat. Ops disables `ir.cron` record directly if needed.
3. **Orphaned row alert via `multichannel.sync.health`?** Defer — flip state only; BA review via admin UI filter. Follow-up slice.
4. **Body SHA256 collision strategy?** Defer to `P1-MSG-API-PULL` T032 (cross-channel dedupe test). Current slice just stores prefix.
5. **Partial-index predicate verification**: `data-model.md §2` line 92 states `WHERE state='buffered'` literally. Confirmed.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| `_sql_constraints` UNIQUE silently fails to deploy | `init()` raw SQL mirror with `pg_constraint IF NOT EXISTS` pre-check |
| C-EMD-001 XOR not enforced | Phase 2 ORM test catches; runs before GREEN |
| Cron deletes orphaned by mistake | Explicit Phase 2 test asserts orphaned kept |
| ACL prevents legitimate writes | Phase 2 test verifies `base.group_system` full access |
| Cron runs as wrong user | Use `model._cron_dedupe_retention()` (no user context); cron model_id binding makes it run as superuser |

---

## Agent Dispatch Order (Phases 2–4)

### Phase 2 (RED): `tdd-guide`
- Inputs: this plan + `data-model.md §2` + `email_fallback.md` + `etsy_conversation_poller.md`
- Outputs: T003 file + T004 file (T010 tests appended to T004 file per tasks.md note)
- Success: tests RED before any model code lands

### Phase 3 (GREEN): direct coding (orchestrator inline)
- Inputs: RED test files + this plan's schema/init()
- Outputs: T005 model + T006 import + T007 ACL + T008 Selection extension + T009 cron + manifest bump
- Success: all RED tests turn GREEN

### Phase 4 (Review): `code-reviewer` + `security-reviewer` **in parallel** (single message, two Agent calls)
- **code-reviewer focus**:
  - `init()` raw SQL comment quality + drift-template adherence
  - XOR constraint logic clarity
  - Cron retention 3-state logic correctness
  - Field ordering / Odoo convention
- **security-reviewer focus**:
  - ACL matrix completeness (no privilege escalation)
  - `sudo()` usage (should be NONE here; if any, justified inline)
  - Raw SQL parameter binding (no string concat)
  - C-EMD-001 enforced at write level not just `@api.constrains` (FR-017 9th confirmation candidate — evaluate if state machine downstream)

---

## Exit Criteria (machine-checkable)

- [ ] T003–T010 all `[X]` in `specs/007-customer-conversations/tasks.md`
- [ ] Phase 1 DB tests pass
- [ ] Phase 2 ORM tests pass (12 cases)
- [ ] Coverage ≥80% on changed lines
- [ ] `odoo -u etsy_integration --stop-after-init` exit 0
- [ ] No `_logger.info(` / `print(` introduced
- [ ] ACL row count: 2 new (reader R, system full)
- [ ] Tracker `P3-LEAD-DEDUPE` state→done with landing record
- [ ] `/learn` capture or "no new patterns" note
- [ ] `findings.md` updated if drift template hits 5th confirmation

---

## Deliverables Summary

| Item | Path | Est LOC |
|---|---|---|
| Model + `init()` + constraints + cron method | `models/etsy_message_dedupe.py` | ~120 |
| Model registration | `models/__init__.py` | +1 |
| ACL rows | `security/ir.model.access.csv` | +2 |
| `etsy.api.log` Selection extension | `models/etsy_api_log.py` | +2 |
| Cron XML | `data/ir_cron_data.xml` | +15 |
| Manifest version bump | `__manifest__.py` | +1 |
| Phase 1 DB tests | `tests/test_phase1_db_message_dedupe.py` | ~80 |
| Phase 2 ORM tests | `tests/test_phase2_orm_message_dedupe.py` | ~150 |
| **Total** | — | **~371 LOC** |

---

**Plan author**: planner agent (Sonnet) | **Phase 1 complete**. Hand off to `tdd-guide` for Phase 2 RED.
