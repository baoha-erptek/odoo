# P0-18b2a — Gearment webhook discovery controller

**Branch**: `feature/006-master-plan-coding`
**Created**: 2026-05-02
**Slice size**: ~80-120 LOC + 11 tests
**Parent**: split out of P0-18b2 (b2 was blocked on URL/secret; URL now `https://odoo.hatafax.com/gearment/webhook`, 3 V3 webhooks registered, payload schema captured via simulator)

## Goal

Land minimal log-only controller. Capture inbound headers + body to `gearment.api.log` so we can inspect the real signature header + algorithm in next deploy. NO HMAC verify, NO topic routing.

## Out of scope (deferred)

- P0-18b2b: HMAC verify + signature algorithm detection
- P0-18b2c: topic→handler dispatch + sale.order lookup + tracking write to fulfillment

## Files

| File | Action |
|---|---|
| `models/gearment_api_log.py` | Extend: 5 new fields + `inbound_webhook` source |
| `controllers/__init__.py` | Create |
| `controllers/gearment_webhook.py` | Create |
| `__init__.py` | Add `from . import controllers` |
| `__manifest__.py` | Bump 19.0.1.0.6 → 19.0.1.0.7 |
| `tests/test_webhook_discovery_db.py` | Create (Phase 1) |
| `tests/test_webhook_discovery_orm.py` | Create (Phase 2 ORM + HttpCase) |
| `tests/__init__.py` | Register both |

## New fields on `gearment.api.log`

- `direction` Selection [outbound, inbound] (nullable for backward compat)
- `request_headers` Text (JSON dict, Authorization scrubbed)
- `request_body` Text (capped at 4 KB)
- `signature_header_seen` Char (heuristic: first header with "signature" in lower-cased name)
- `topic_seen` Char (extracted from body's `event`/`topic` key OR from header)
- `source` Selection: add `('inbound_webhook', 'Inbound Webhook')`

## Controller contract

```python
@http.route('/gearment/webhook', type='http', auth='public', csrf=False,
            methods=['POST'], save_session=False)
```

`type='http'` (not `'json'`) because Gearment may send malformed or non-JSON
payloads during simulator probes; `type='json'` would 400 with `-32700` before
our handler runs. Discovery mode must accept anything, log it, and return 200.

- Accept any payload; tolerate malformed JSON
- Filter `Authorization`, `Cookie`, headers matching `*secret*` from `request_headers` log
- Truncate body at 4096 chars
- `request.env['gearment.api.log'].sudo().create({...})` — public route has no env.user, sudo justified inline
- Always return `{"status": "ok"}` 200; on internal exception, log warning + still return 200 (retry-loop avoidance)

## Risks

1. Public POST = DoS surface. Mitigation: 4 KB body cap + Odoo workers handle backpressure. Rate limiting deferred (nginx layer or P0-18b2b).
2. Authorization-header leak. Mitigation: explicit lower-case header filter list before write.
3. URL collision with existing routes. Mitigation: `/gearment/webhook` is unique (`grep -r '/gearment/' controllers/` confirmed no prior).
4. Test HttpCase needs `auth='public'`, may pollute test session. Mitigation: `save_session=False` set.

## Phase 1 tests (DB)

1. `test_gearment_api_log_columns_added` — direction/request_headers/request_body/signature_header_seen/topic_seen exist
2. `test_direction_nullable` — backward compat with P0-18b1 outbound rows
3. `test_source_selection_inbound_webhook` — selection extended
4. `test_existing_outbound_rows_unchanged` — old rows still queryable

## Phase 2 tests (ORM + HttpCase)

5. `test_create_inbound_log_with_all_fields` — write+read trip
6. `test_existing_outbound_log_still_works` — no-direction create still works
7. `test_webhook_post_returns_200` — basic HTTP smoke
8. `test_webhook_creates_log_record` — POST → log row
9. `test_webhook_logs_signature_header_if_present` — heuristic capture
10. `test_webhook_authorization_header_not_logged` — defense
11. `test_webhook_malformed_json_logged_as_raw` — discovery resilience
12. `test_webhook_detects_event_topic` — body['event'] → topic_seen

## Exit criteria

- [ ] 11 tests pass; ruff clean
- [ ] Module installs `-u multichannel_hub_fulfillment --stop-after-init` exit 0
- [ ] No `_logger.info` / `print` in controller
- [ ] code-reviewer + security-reviewer pass (no CRITICAL/HIGH)
- [ ] tracker P0-18b2 row split into a/b/c; P0-18b2a marked `done`
- [ ] tasks.md + research.md updated with payload schema

## Phase 7 (post-commit, ops)

```bash
rsync -avz custom_addons/multichannel_hub_fulfillment/ \
  ubuntu@129.150.63.207:/odoo/esty19/custom_addons/multichannel_hub_fulfillment/
ssh ubuntu@129.150.63.207 'docker exec esty19_odoo odoo -d demo_esty \
  -u multichannel_hub_fulfillment --stop-after-init && docker restart esty19_odoo'
curl -X POST https://odoo.hatafax.com/gearment/webhook \
  -H "Content-Type: application/json" -d '{"order":{"gearment_id":"TEST"}}'
```

Then re-fire Gearment dashboard simulator at full URL, inspect captured headers.
