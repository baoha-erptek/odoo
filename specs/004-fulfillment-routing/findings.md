# Findings — Spec 004 Fulfillment Routing

Per `.claude/plans/006-implementation-playbook.md` Phase 7. Surprises, blockers, and deferred decisions discovered during implementation. Each entry stands on its own; do not delete entries — supersede them with new ones.

---

## 2026-04-27 — P0-18a Gearment auth probe landed

**Slice scope (final, post-execution)**:
- New module `multichannel_hub_fulfillment` — empty installable skeleton (manifest, init chain, header-only ACL CSV, README, CLAUDE.md). Depends on `multichannel_hub_core`. Will host Gearment + future fulfillment adapters per ADR-003.
- `multichannel_hub_core/utils/rate_limiter.py` — `TokenBucket` token-bucket limiter (non-blocking, returns bool from `acquire()`, advisory). Lives in core so the future `EtsyApiClient` (P0-15) can reuse it.
- `multichannel_hub_fulfillment/services/gearment_api_client.py` — `GearmentApiClient` with header auth (`X-Gearment-Client-Key` + `X-Gearment-Client-Secret`), `ping()` against `GET /api/v3/catalog?limit=1`, 429-retry policy.

**Q-resolved (from planner / runtime discovery)**:

- **Q1 — Gearment auth shape**. Confirmed from `developers.gearment.com/api.md` (2026-04-27): two HTTP headers required, both `GEARMENT_API_KEY` and `GEARMENT_API_SECRET` needed. The unauthenticated landing page at `api.gearment.com` was misleading (said "API keys in params"); the dev-docs page is authoritative.
- **Q2 — Base URLs**. Production `https://apiv2.gearment.com/integration-handler`; sandbox `https://api.gearmentinc.com/integration-handler`.
- **Q3 — Rate-limiter ownership**. Lives in `multichannel_hub_core/utils/` (not Gearment-specific) so the Etsy client can share it. Constructor takes `(rate, period)` so 100/10s (Gearment) and 5/s (Etsy projection) are both expressible.
- **Q4 — 429 retry semantics**. 1 initial attempt + 3 retries = 4 attempts total. 3 sleeps between attempts. `Retry-After` honored when present (now capped at 60s as defense-in-depth — see surprise #2 below). Fallback: (1, 2, 4) exponential backoff. After all retries exhausted → `RateLimitError(retry_after=last_retry_after)`.
- **Q5 — Rate limiter on the send path**. Advisory-only: when `acquire()` returns False, log a warning and send anyway. Caller decides whether the local limiter should hard-block. This keeps the slice scope tight; Gearment's server-side 429 is the authoritative rate gate.

**Q-deferred to P0-18b**:

- **DQ1 — Webhook signature header name + HMAC algorithm**. Public docs say "include signature header for verification" but do not name the header or algorithm. Discovery plan: register a webhook subscription, log all inbound headers on first POST, then add HMAC verification.
- **DQ2 — `vendor_id` semantics**. v3 webhook payloads use `gearment_id` / `gearment_name` / `vendor_id`. Whether `vendor_id` is per-merchant (constant) or per-storefront (varies) needs confirmation before P4-01a outbound order create.
- **DQ3 — HTTPS scheme assertion on `base_url`**. Security-reviewer flagged plain-HTTP acceptance as LOW. Tests use `http://api.gearment.test`; gating on `https://` would break them. Add the assertion in P0-18b once we switch tests to fixture domains that match the real `https://` scheme, OR keep the LOW open as accepted risk because `.env` is repo-private.
- **DQ4 — Redirect policy on `requests.Session`**. Default behavior follows redirects. Gearment is first-party; LOW risk. P0-18b should set `session.max_redirects = 0` if any handler accepts dynamic upstream URLs.

**Surprises (all resolved before commit)**:

1. **Odoo test runner skips `unittest.TestCase`**. The original tdd-guide RED used `unittest.TestCase`; the runner discovered them at import time but never executed because they weren't auto-tagged with the module name. Symptom: `0 failed, 0 error(s) of 0 tests` while logs showed test files imported. Fix: switch base class to `odoo.tests.common.TransactionCase` (overkill for pure-Python tests, but consistent with the rest of the suite and triggers default tag). Lesson: any pure-Python service test in this repo must extend an Odoo test base class, not raw `unittest.TestCase`.
2. **`mock.patch` paths must include `odoo.addons.<module>` prefix**. Custom addons are imported as `odoo.addons.multichannel_hub_core.utils.rate_limiter`, NOT `multichannel_hub_core.utils.rate_limiter`. Patching the latter raises `AttributeError: module 'multichannel_hub_core' has no attribute 'utils'` because the bare module path doesn't resolve under the addon import system. All `@mock.patch('...')` decorators in test files for custom-addon code must use the `odoo.addons.` prefix. Lesson recorded in memory `feedback_odoo19_test_gotchas.md` as a future #22 entry.
3. **`Retry-After` cap added at review time**. Security-reviewer flagged uncapped `Retry-After` as MEDIUM (a malicious upstream returning `Retry-After: 999999` would block 11.5 days). Added `_MAX_RETRY_AFTER_SECONDS = 60` clamp. Cheap defense-in-depth; tests still green (mocks send `Retry-After: 0` or `1`, both under the cap).

**Verification**:
- `docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_fulfillment,multichannel_hub_core,etsy_integration --test-tags=/multichannel_hub_fulfillment,/multichannel_hub_core,/etsy_integration --stop-after-init` → exit 0, **217 tests, 0 failed, 0 error**.
- Reviews: code-reviewer PASS (no CRITICAL/HIGH), security-reviewer PASS with 2 LOW (HTTPS validation + redirect policy, both deferred to P0-18b).
- No `_logger.info(` / `print(` introduced.
- `GEARMENT_API_BASE_URL` empty in `.env` — non-blocking for this slice (all tests mocked); owner must set before P0-18b.

**Branch + commit**: `feature/006-master-plan-coding`, single commit `[multichannel_hub_fulfillment] feat: gearment auth probe + token-bucket rate limiter (P0-18a)`.

**Unblocks**: P0-18b (live sandbox POC + webhook signature discovery).

---

## P0-18b1 planner notes (2026-04-30)

### Gearment API live verified

- Base URL `https://apiv2.gearment.com/integration-handler` works with owner's
  `.env` `GEARMENT_API_KEY` (16 chars) + `GEARMENT_API_SECRET` (66 chars).
- `GET api/v3/catalog?limit=1` returned `legacy_product_id=2`, print_locations
  `[pocket, right_sleeve, front, back, left_sleeve]`, `product_avatar_url`.
- This is owner's real Gearment account, NOT a separate sandbox. P0-18b1 must
  treat it as live: catalog read OK; draft/quote/confirm via mocks ONLY.

### Slice scope

- IN: `GearmentAdapter` Protocol + concrete impl, `GearmentOrderPayload` dataclass,
  `gearment.api.log` audit model, retention cron, env-gated live catalog probe test
- OUT: webhook signature discovery (P0-18b2 — needs ngrok), live POST draft/confirm
  (P4-01 + owner sign-off), full state machine (P4-01)

### Open questions for P0-18b2

| ID | Question | Probe | Default while waiting |
|---|---|---|---|
| DQ1 | webhook signature header name + HMAC algorithm | inspect first inbound POST after register | assume `X-Webhook-Signature` + HMAC-SHA256 hex of body |
| DQ2 | idempotency: header `Idempotency-Key` honored, OR dedupe on `reference_id` body field, OR neither | live POST draft twice with same key/ref | adapter sends BOTH (belt-and-braces) |
| DQ3 | `vendor_id` semantics in callback payloads | inspect P0-18b2 webhook content | log only; routing logic deferred |
| DQ4 | HTTPS scheme assertion on `base_url` | unit test | tighten to `https://` only — P0-18a LOW item |
| DQ5 | redirect policy on `requests.Session` | review code | set `session.max_redirects=0` — P0-18a LOW item |

### Print-location mapping (preliminary from P0-18a ping)

`design.file.role` → Gearment `print_location.code`:
- `front` → `front` ✓
- `back` → `back` ✓
- `pocket` → `pocket` ✓
- `sleeve` → ambiguous (`left_sleeve` vs `right_sleeve`) — **owner pick** at P4-01;
  P0-18b1 defaults to `front` and emits a warning when role is ambiguous

### Idempotency: dual approach

Belt-and-braces until DQ2 resolves:
1. HTTP header `Idempotency-Key: sha256(external_order_id)` — set on every POST
2. Body field `reference_id = external_order_id` — set in `GearmentOrderPayload.serialize()`

If Gearment honors only one, the other is harmless. If neither, retry strategy
needs P4-01 redesign — flag explicitly in P0-18b2.

### `gearment.api.log` mirror of `etsy.api.log`

Same proven design from Spec 005 P0-17:
- 11 fields, no `mail.thread`
- Composite index in `init()` (drift-template applies)
- Selection `source` 6 values (one more than Etsy's 8 — `health_check` carved out
  vs lumping into `probe`)
- Daily retention cron, ICP-configurable
- ACL: `group_system` full, `group_sale_manager` read

### Live-probe test gating

`test_gearment_adapter_phase1.py::test_catalog_live_probe` runs only when env
`MULTICHANNEL_HUB_FULFILLMENT_LIVE_API=1`. Default CI skip. This avoids both
quota burn and accidental production traffic in tests.

### ADR audit

- ADR-001 (Spec 004 split into 4a/4b/4c): P0-18b1 is firmly Spec 004b territory
  (Gearment partner adapter). No amendment.
- ADR-003 (4-module decomposition): adapter lives in
  `multichannel_hub_fulfillment` (already created P0-18a). No amendment.
- ADR-007 (sale.order.fulfillment delegation): P0-18b1 doesn't touch fulfillment
  model — adapter is upstream of the model. Will integrate in P4-01.

### Suggested commits

1. `[multichannel_hub_fulfillment] docs(P0-18b1): planner Phase 1 spec artifacts (this commit)`
2. `[multichannel_hub_fulfillment] test(P0-18b1): RED gearment_adapter + payload + api_log tests (T080-T082)`
3. `[multichannel_hub_fulfillment] feat(P0-18b1): GREEN GearmentAdapter Protocol + payload + api.log model (T083-T089)`
4. `[multichannel_hub_fulfillment] docs(P0-18b1): tracker done + tasks [X] + findings update`

