# P0-18b2c — Topic dispatch + sale.order.fulfillment writes from Gearment webhooks

**Branch**: `feature/006-master-plan-coding`
**Created**: 2026-05-02
**Slice size**: ~250 LOC + 18 tests
**Parent**: closes P0-18b2 (final sub-slice). Builds on b2a discovery + b2b verify.

## Topic→handler map

| body['type'] | Action |
|---|---|
| `order_completed` | Lookup order by `body.order.reference == sale.order.name`; on match write fulfillment.tracking_number / tracking_url / tracking_state='shipped' / shipping_date=today |
| `order_cancelled` | production_blocked=True + block_reason; if pipeline `gearment_pod/confirmed` rollback to `quoted` via `_write_pipeline_state(state, change_type='rollback')`; chatter alert |
| `tracking_order_updated` | Refresh tracking_number/url; **don't** flip tracking_state (keeps already-shipped intact) |
| `order_on_hold` | production_blocked=True + block_reason; chatter; no rollback |
| `shipping_address_verified` / `shipping_address_unverified` / `product_out_of_stock` / `variant_created` / `variant_updated` | Chatter post if order found; NO field writes |
| anything else | `(False, 'unknown_topic:<x>')` |

## Files

| File | Action |
|---|---|
| `multichannel_hub_fulfillment/services/gearment_webhook_dispatcher.py` | NEW — `GearmentWebhookDispatcher(env).dispatch(topic, body) → (handled, summary)`; one method per handler; pure(-ish), no @api decorators |
| `multichannel_hub_fulfillment/services/__init__.py` | register |
| `multichannel_hub_fulfillment/controllers/gearment_webhook.py` | call dispatcher when verified=True; populate new audit fields |
| `multichannel_hub_fulfillment/models/gearment_api_log.py` | +3 fields (`business_handled` Boolean, `business_summary` Char, populate existing `sale_order_id` Many2one); +UNIQUE partial index in init() |
| `multichannel_hub_core/models/sale_order_fulfillment.py` | +1 field (`tracking_url` Char); +'tracking_url' to `_BUS_TRIGGER_FIELDS` |
| `multichannel_hub_fulfillment/tests/test_webhook_dispatcher_db.py` | NEW — Phase-1 (5 tests) |
| `multichannel_hub_fulfillment/tests/test_webhook_dispatcher_orm.py` | NEW — Phase-2 dispatcher unit + HttpCase E2E (13 tests) |
| `multichannel_hub_fulfillment/tests/__init__.py` | register |
| `multichannel_hub_fulfillment/__manifest__.py` | 19.0.1.0.8 → 19.0.1.0.9 |
| `multichannel_hub_core/__manifest__.py` | 19.0.1.0.9 → 19.0.1.0.10 |

## UNIQUE partial index (TOCTOU fix from b2b security review)

Append to `gearment_api_log.init()`:

```python
self.env.cr.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS gearment_api_log_nonce_ts_unique
    ON gearment_api_log (nonce_value, request_timestamp)
    WHERE nonce_value IS NOT NULL AND nonce_value <> ''
      AND request_timestamp IS NOT NULL AND request_timestamp > 0
""")
```

Partial: outbound rows with empty nonce can coexist. Concurrent webhook inserts with same `(nonce, ts)` → second raises `psycopg2.IntegrityError` → controller catches, returns 401 + `verify_failure_reason='nonce_replay_db'` (distinct from b2b's search-based `nonce_replay`).

## Dispatcher contract

```python
class GearmentWebhookDispatcher:
    def __init__(self, env): self.env = env
    def dispatch(self, topic: str, body: dict) -> tuple[bool, str]:
        """Returns (handled, summary). Never re-raises — soft-fail + log on
        any internal exception so the controller stays at 200/401 cleanly.
        """
```

All ORM access through `sudo()` with inline justification (controller is `auth='public'`, no env.user with write perms).

For fulfillment writes, pass `with_context(bypass_address_change_check=True)`. Documented policy: webhook is **inbound system data**, not an interactive operator action; FR-017's address-change-pending block is meant to stop human RPC writes during owner-pending-decision, not to drop tracking arrivals from upstream. If a human raised an address change AFTER Gearment shipped, the operator must resolve the conflict — that's not a reason to drop tracking. Security reviewer must explicitly approve.

`markupsafe.escape()` on `body['order']['status']` and `body['type']` before chatter posts (defense vs stored-XSS in Odoo chatter UI).

## Idempotency strategy

1. b2b nonce dedup (search) handles same-nonce replay within 10min.
2. New UNIQUE partial index handles concurrent same-nonce inserts (race).
3. Field-level: writing same tracking_number twice is a no-op write (still emits one bus event — accepted; UI dedups by row).
4. If Gearment ever fires same-event-different-nonce within 10min → handler runs, but writes are last-value-wins on identical fields. Acceptable; no double-effect.

## Phase-2 test list (13 tests)

### Dispatcher unit (TransactionCase)

1. `test_order_completed_writes_tracking` — full happy path: pre-create SO+fulfillment, dispatch, assert tracking_number/url/state/shipping_date set
2. `test_order_completed_no_match_returns_order_not_found` — reference doesn't match → `(False, 'order_not_found')`, no writes
3. `test_order_cancelled_blocks_and_rolls_back_pipeline` — pre-seed pipeline `gearment_pod/confirmed`, dispatch, assert production_blocked + pipeline back to `quoted` + chatter
4. `test_tracking_order_updated_keeps_existing_state` — pre-shipped row, dispatch update, assert state still `shipped` but number changed
5. `test_order_on_hold_blocks_no_rollback` — pre-seed in `gearment_pod/confirmed`, dispatch, assert production_blocked, pipeline still `confirmed`
6. `test_log_only_topics_post_chatter_only` — `shipping_address_verified` payload, assert chatter post + no field writes
7. `test_unknown_topic_returns_unhandled` — `body['type']='weird_event'` → `(False, 'unknown_topic:weird_event')`
8. `test_handler_exception_soft_fails_no_reraise` — patch handler to raise, dispatch returns `(False, 'handler_error:RuntimeError:...')`, no exception propagates
9. `test_xss_in_status_escaped_in_chatter` — `body.order.status = "<script>alert(1)</script>"` → chatter contains `&lt;script&gt;`

### HttpCase E2E (signed POST)

10. `test_e2e_valid_sig_dispatches` — full webhook with valid sig + matching order → 200, audit row `business_handled=True`, `business_summary` starts `order_completed`, fulfillment updated
11. `test_e2e_valid_sig_unknown_order_returns_200` — valid sig, unknown reference → 200 (no Gearment retry storm), audit row `business_handled=False`, `business_summary='order_not_found'`
12. `test_e2e_invalid_sig_skips_dispatch` — bogus sig → 401, fulfillment unchanged, audit row `business_handled=False`

### Phase-1 DB (5 tests in `test_webhook_dispatcher_db.py`)

13. `test_business_fields_present` — info_schema check for `business_handled` + `business_summary` columns
14. `test_tracking_url_column_present` — sale_order_fulfillment table
15. `test_unique_partial_index_exists` — pg_indexes lookup for `gearment_api_log_nonce_ts_unique`
16. `test_unique_constraint_blocks_duplicate` — direct `create()` of two rows w/ same `(nonce, ts)` → second raises IntegrityError
17. `test_null_nonce_allows_multiple` — outbound rows w/ `nonce_value=False` can repeat freely

## Risks

1. **`bypass_address_change_check=True` policy** — explicit override of FR-017. Justify in code comment + commit body. Security reviewer must sign off.
2. **Sudo() scope leak** — sudo'd recordset returned to caller could be misused. Keep all sudo'd values inside the dispatcher; do not return to controller.
3. **Pipeline rollback may fail** if order isn't in `gearment_pod/confirmed`. Wrap in try/except, log WARNING, don't block fulfillment write.
4. **Chatter `markupsafe.escape`** must wrap user-input strings. Test 9 catches XSS.
5. **bus.bus events on replay** — same-tracking second write still emits bus event. Acceptable cost.
6. **IntegrityError from new UNIQUE** must be caught at controller (savepoint rollback) — Odoo's default would 500 the request. Controller change: catch IntegrityError around `_record_inbound`, recover, return 401 nonce_replay_db.

## Phase 7 (post-commit, ops)

```bash
rsync mhf + mhc to staging
sudo docker exec esty19_odoo odoo -d demo_esty -u multichannel_hub_core,multichannel_hub_fulfillment --stop-after-init
sudo docker restart esty19_odoo

# Self-signed probe with reference matching a real demo order on staging
python3 -c "..." → POST /gearment/webhook → 200
psql: SELECT tracking_number, tracking_state, tracking_url, shipping_date FROM sale_order_fulfillment WHERE id=...; → updated
psql: SELECT business_handled, business_summary, sale_order_id FROM gearment_api_log ORDER BY id DESC LIMIT 1; → True / order_completed:tracking_set:USPS / order id

# Owner re-fires Gearment dashboard simulator with reference matching a real demo
# order → confirms end-to-end with real Gearment HMAC.
```

## Exit criteria

- [ ] 18 tests pass; cross-module regression clean (mhc + mhf + etsy_integration)
- [ ] code-reviewer PASS; security-reviewer PASS (incl. explicit nod to bypass_address_change_check policy)
- [ ] Module installs `-u multichannel_hub_core,multichannel_hub_fulfillment` exit 0
- [ ] No `_logger.info` / `print` in changed files
- [ ] tracker P0-18b2c → done; P0-18b2 row marked complete (all sub-slices closed)
- [ ] tasks.md T122-T130 [X]
- [ ] Staging probe: self-signed POST with real demo order ref → fulfillment row updated; row visible in tracking dashboard
