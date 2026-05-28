# P0-18b2b — Gearment webhook HMAC verify + replay defenses

**Branch**: `feature/006-master-plan-coding`
**Created**: 2026-05-02
**Slice size**: ~120 LOC + 12 tests
**Parent**: P0-18b2a discovery probe captured Gearment headers + cracked HMAC scheme via OpenAPI yaml. Now we verify.

## HMAC contract (cracked + verified)

```
secret         = os.environ['GEARMENT_API_SECRET']
algorithm      = HMAC-SHA256
url_path       = "/gearment/webhook"
signing_string = url_path + nonce + timestamp + base64url(body)   # NO separators
encoding       = base64-URLsafe with '=' padding
header         = X-Connect-Signature
compare        = hmac.compare_digest (constant-time)
```

Aux headers: `X-Connect-Client-Key` (= `GEARMENT_API_KEY`), `X-Connect-Timestamp` (unix), `X-Connect-Nonce`.

## Goal

1. Verify signature; 401 on mismatch
2. Replay window: reject if `timestamp` outside `[now-300s, now+60s]` (forward skew tolerance)
3. Nonce dedup: reject if `(nonce, request_timestamp)` seen in last 10 min via `gearment.api.log` table search
4. Origin: reject if `X-Connect-Client-Key != GEARMENT_API_KEY`
5. On verify failure: 401 + audit log + truncate `request_body` to 256 chars (defense)
6. On verify success: 200; `signature_verified=True` row written
7. Update `_detect_topic` to read body's `type` key (not just `event`/`topic`)

## Out of scope (P0-18b2c)

- `sale.order` lookup by `body.order.reference`
- Topic→handler dispatch
- `sale.order.fulfillment` tracking write

## Files

| File | Action |
|---|---|
| `models/gearment_api_log.py` | +4 fields (`nonce_value` Char indexed, `request_timestamp` Integer indexed, `signature_verified` Boolean default False, `verify_failure_reason` Char), 2 indexes via init() |
| `controllers/gearment_webhook.py` | New `_verify_signature(headers, body) → (ok, reason)` helper (module-level, pure); refactor `_record_inbound` to call verify first; on fail → 401 path + truncated body; update `_detect_topic` to check body['type'] first |
| `tests/test_webhook_verify_orm.py` | NEW — 12 HttpCase + helper unit tests |
| `tests/__init__.py` | Register new test module |
| `__manifest__.py` | 19.0.1.0.7 → 19.0.1.0.8 |

## Verify helper signature

```python
def _verify_signature(raw_headers: dict, body_bytes: bytes,
                       env_for_dedup, now_provider=time.time) -> tuple[bool, str]:
    """Return (is_valid, failure_reason). reason='' on success."""
```

`now_provider` injected so tests don't need `freezegun` (not in requirements). `env_for_dedup` is `request.env` for nonce search; tests can pass any env.

## Failure reason codes

| Reason | When |
|---|---|
| `missing_signature_header` | no `X-Connect-Signature` |
| `missing_timestamp_header` | no `X-Connect-Timestamp` |
| `missing_nonce_header` | no `X-Connect-Nonce` |
| `missing_client_key_header` | no `X-Connect-Client-Key` |
| `client_key_mismatch` | client key != `GEARMENT_API_KEY` env var |
| `timestamp_invalid` | not int-parseable |
| `timestamp_outside_window` | < now-300 or > now+60 |
| `nonce_replay` | same nonce within last 10 min |
| `signature_mismatch` | HMAC mismatch (constant-time compared) |

## Test list (Phase 2 — `tests/test_webhook_verify_orm.py`)

Use `HttpCase` for end-to-end HTTP tests; `TransactionCase` for pure helper tests.

1. `test_helper_signing_string_format` — pure unit on `_compute_signature`; uses captured-probe values + GEARMENT_API_SECRET; expect digest = `nNqkvTj5v9Qg4rwaKYhlAjQS-3N_gMc-whSGp-VypVE=`
2. `test_valid_signature_accepted` — HttpCase; mock `time.time()` to row 3 timestamp; mock `os.environ` so secret matches; POST with computed sig → 200, `signature_verified=True`, `verify_failure_reason=''`
3. `test_invalid_signature_rejected_401` — flip 1 char of sig → 401, `signature_verified=False`, reason `signature_mismatch`
4. `test_missing_signature_header_rejected_401`
5. `test_missing_timestamp_header_rejected_401`
6. `test_missing_nonce_header_rejected_401`
7. `test_missing_client_key_header_rejected_401`
8. `test_wrong_client_key_rejected_401` — reason `client_key_mismatch`
9. `test_expired_timestamp_rejected_401` — ts = mocked-now - 600
10. `test_future_timestamp_rejected_401` — ts = mocked-now + 120 (skew > 60s)
11. `test_duplicate_nonce_rejected_401` — fire same valid request twice, second returns 401 reason `nonce_replay`
12. `test_topic_extracted_from_body_type_key` — body `{"type":"order_completed"}` → `topic_seen='order_completed'`
13. `test_failure_drops_request_body_to_256` — invalid sig → audit row's `request_body` length ≤ 256

## Risks

1. **`request.httprequest.path` vs `full_path`** — Go ref uses `r.URL.Path` (no query). Use `request.httprequest.path`. Test asserts no query-string contamination.
2. **Body bytes integrity** — must HMAC against EXACT bytes Gearment sent. `get_data(cache=True)` is Werkzeug default; Odoo's request layer does not mutate. Verify by calling `get_data()` twice in handler — should be cached.
3. **Env-var read at call time vs init time** — read at call so secret rotation works without restart. Tests use `mock.patch.dict(os.environ, {...})`.
4. **Time mocking** — pass `now_provider` callable into helper. Production caller passes `time.time`. Tests pass `lambda: 1777735761` for deterministic windows.
5. **Nonce dedup race** — two requests with same nonce arrive concurrently. Solution: rely on append-only `gearment.api.log` row creation as the natural lock — both rows write, the first ALSO won; second's search SEES the first by the time it runs (savepoint isolation in Odoo). Acceptable for discovery + audit; full transactional uniqueness deferred until P0-18b2c handlers.
6. **`gearment.api.log` row created BEFORE verify pass/fail decided** — current pattern is "verify first, then log". To meet defense (don't store full hostile body) write a single row at the END of `_record_inbound` with `signature_verified` already known. Simpler than 2-phase.

## Phase 7 (post-commit, ops)

```bash
rsync -avz custom_addons/multichannel_hub_fulfillment/ \
  ubuntu@129.150.63.207:/odoo/esty19/custom_addons/multichannel_hub_fulfillment/
ssh -i secrets/ssh-key-2023-02-24.key ubuntu@129.150.63.207 \
  'sudo docker exec esty19_odoo odoo -d demo_esty -u multichannel_hub_fulfillment \
   --stop-after-init --http-port=8888 --workers=0 --max-cron-threads=0'
ssh ... 'sudo docker restart esty19_odoo'
# Re-fire dashboard simulator → verify gearment.api.log row 4+ has
# signature_verified=true and verify_failure_reason='' and topic_seen='order_completed'
```

## Exit criteria

- [ ] 13 tests pass; cross-module regression clean (mhc + mhf + etsy_integration)
- [ ] code-reviewer + security-reviewer both PASS (no CRITICAL/HIGH)
- [ ] Module installs `-u multichannel_hub_fulfillment` exit 0
- [ ] No `_logger.info` / `print` in changed files
- [ ] tracker P0-18b2b → done; P0-18b2c row updated to "blocked → unblocked"
- [ ] tasks.md T112-T120 [X]
- [ ] Staging probe: real dashboard simulator hit logs `signature_verified=true`
