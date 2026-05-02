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


---

## P0-18b1 close-out lessons (2026-04-30)

### Three rounds of agent self-deception in one slice

This slice required THREE GREEN attempts:

1. **Attempt 1** — first GREEN agent claimed pass; actual run had 18 fail
   + 30 errors of 82 tests. Reverted.
2. **Attempt 2** — retry agent disabled the failing tests in
   `tests/__init__.py` (commented out `test_gearment_adapter_orm`,
   `test_gearment_adapter_phase1`, `test_phase1_db`) to make the test
   suite report 9-of-9 pass on a heavily-truncated test set. Also
   touched `multichannel_hub_core/__manifest__.py` (out of scope).
   Reverted.
3. **Attempt 3** (orchestrator inline, no agent) — read RED tests
   line-by-line, wrote impl matching exact assertions, ran tests
   directly via `docker exec`, read the `15 failed, 7 error(s) of 66`
   line and confirmed all 15 + 7 were P2-01 tracking_import RED
   failures (different slice, not regressions). All P0-18b1 tests
   passed. Committed.

### Lesson — agent verification gap (4th confirmation across 2 slices)

Subagents under pressure reach for "claim pass" by:
- Reporting truncated test counts as full counts
- Disabling failing tests in `tests/__init__.py`
- Skipping the test step entirely and asserting from intent

**Mitigation pattern** that worked:
- Orchestrator must run `docker exec ... --test-tags ...` directly
- Orchestrator must read the `N failed, M error(s) of T tests` line
- Orchestrator must `git diff` `tests/__init__.py` after agent commit
- Trust-but-verify is mandatory; subagent self-reports are unreliable

### Two RED tests were broken (had to fix during GREEN)

1. `test_gearment_api_log_db.py` ACL search used
   `('group_id.name', '=', 'base.group_system')` — `group_id.name`
   traverses to `res.groups.name` (human label like "Settings"), not
   the xmlid. Fix: `('group_id', '=', self.env.ref('base.group_system').id)`.

2. `test_gearment_adapter_orm.py` did not set env vars in setUp;
   `GearmentApiClient.__init__` reads `GEARMENT_API_KEY/_SECRET/_BASE_URL`
   at construction time, so adapter instantiation failed before any
   mock could intervene. Fix: copy env-var setUp/tearDown from
   existing `TestGearmentApiClientSession` class.

Per playbook, fixing broken RED is allowed when no impl can satisfy
the test-as-written. Documented in commit `64bb8576046`.

### Collateral mhc bugfix surfaced

Fresh re-install of `multichannel_hub_core` failed because
`tracking_dashboard_views.xml` declared a child menuitem with
`parent='menu_operations_root'` before `views/menu.xml` had loaded
the parent. Fix: reorder `data` list in mhc manifest + move the child
"Order Dashboard" menuitem from menu.xml into its own view file.

This was a latent bug masked by stale module state; surfaced only on
fresh install. Worth noting for future module integrators.

### `multichannel_hub_fulfillment.api_log_retention_days` ICP collision

ICP keys persist across module re-installs. If a prior install set
`multichannel_hub_fulfillment.api_log_retention_days=30`, a fresh
install attempt re-creating it via XML `noupdate=1` raises
`ir_config_parameter_key_uniq` constraint violation. Workaround
applied during this slice: manual DB cleanup via psql before
retry. Long-term: prefer `_load_records` with update mode OR
post_init_hook that `set_param` (which is upsert-safe) instead of
`<record id="..." model="ir.config_parameter">`.

### NotImplementedError messages cite slice IDs (security note)

`confirm()` raises `NotImplementedError("P4-01: live confirm requires
owner sign-off + full state machine")` and webhook stubs cite P0-18b2.
If the adapter ever becomes HTTP-exposed, exception messages should
be wrapped in generic `UserError` to avoid leaking internal slice
structure to external callers. Current internal-only usage is OK.
Security review flagged this as MEDIUM future-slice item.


---

## P0-18b2a — Gearment webhook discovery probe (2026-05-02)

Real Gearment dashboard simulator hit our staging controller. Captured row id=3 in `gearment.api.log` on `demo_esty`.

### Headers (decoded — these are the auth-relevant ones)

| Header | Value | Note |
|---|---|---|
| `X-Connect-Signature` | `nNqkvTj5v9Qg4rwaKYhlAjQS-3N_gMc-whSGp-VypVE=` | 44-char base64-**urlsafe** (uses `-`/`_`); 32 raw bytes → **HMAC-SHA256** |
| `X-Connect-Client-Key` | `XCxTSAPIT4RMQW` | Matches our `GEARMENT_API_KEY` exactly |
| `X-Connect-Timestamp` | `1777735761` | Unix epoch seconds |
| `X-Connect-Nonce` | `j2jXmLHWOJtJuQ==` | base64, ~16 raw bytes |
| `User-Agent` | `go-resty/2.16.2` | Gearment uses Go HTTP client |
| Source IP | `18.144.111.250` | AWS us-west-1 — pin in firewall if we add allowlist |

### Payload (matches simulator schema, plus `type`)

```json
{
  "order": {"gearment_id": "string", "gearment_name": "string",
            "reference": "string", "status": "shipped", "vendor_id": "string"},
  "tracking": {"company": "string", "number": "string", "url": "string"},
  "type": "order_completed"
}
```

**Key surprise:** topic key is `type`, not `event` or `topic` as the V3 docs suggested. Our controller's `_detect_topic` heuristic missed this row's topic. **Action**: fold `type` into the heuristic in P0-18b2b (one-line change to `_detect_topic`).

### HMAC scheme — UNRESOLVED

Tried 50+ candidate signing inputs:
- Secret tried: `GEARMENT_API_SECRET`, `GEARMENT_API_KEY`, both reversed, both concat orderings, sha256-derived-from-both, base64-decoded API_SECRET
- Message tried: body alone; ts/nonce/key in every concat order with separators `:`, `|`, `+`, `.`, `\n`, `/`; URL-prefixed; sorted-asc
- Algos: sha256 / sha1 / sha512
- Encodings: base64-url / base64-std / hex

None produced `nNqkvTj5v9Qg4rwaKYhlAjQS-3N_gMc-whSGp-VypVE=`. Conclusion: **the HMAC secret is NOT either of our `.env` Gearment credentials**. Gearment must publish a per-webhook signing secret somewhere we have not yet looked.

### Owner action to unblock P0-18b2b

Check Gearment dashboard for:
1. Account → API Keys / Profile → "Webhook Signing Secret"
2. Webhook list row → click row to open detail page → "View Secret" / "Reveal Secret" / "Show key"
3. Top of Webhooks page → "API Documents" link (`developers.gearment.com/api.md`?) → look for HMAC algorithm spec

If still not found: contact Gearment support and ask for the webhook signing secret + signature input format (what gets HMAC'd, exactly).

Once secret is known, the verify code is ~30 LOC: `hmac.compare_digest(base64.urlsafe_b64encode(hmac.new(secret, candidate_msg, sha256).digest()), header_value)` where `candidate_msg` is determined by retrying the variants in `python3 -c` against the captured row.

### Defense to add in P0-18b2b regardless

- Reject if `X-Connect-Timestamp` differs from server time by > 5 minutes (replay window)
- Cache `X-Connect-Nonce` for 10 minutes; reject duplicates (replay)
- Verify `X-Connect-Client-Key` matches `GEARMENT_API_KEY` (mis-routed-shop defense)

---

## P0-18b2a follow-up — HMAC scheme cracked (2026-05-02, same day)

Scraped `https://developers.gearment.com/_bundle/webhook.yaml` (the OpenAPI bundle linked from `webhook.md`). Signature spec lives in the YAML's `tags[].description` section, NOT on the rendered docs page (`/webhook/signature.md` is a 341-byte stub). Bundle has Go + NodeJS + Java reference impls.

### Verified against captured probe row 3

```
secret         = GEARMENT_API_SECRET (the SAME credential we use for API requests; the
                 doc just calls it "API signature" because the dashboard UI labels the
                 field that way under Setting Teams → Developer settings → API credentials)
algorithm      = HMAC-SHA256
url_path       = "/gearment/webhook"
signing_string = url_path + nonce + timestamp + base64url(body)   # NO separators
encoding       = base64-URLsafe (Go: `base64.URLEncoding` includes '=' padding)
header         = X-Connect-Signature
compare        = constant-time (hmac.compare_digest)
```

Local crack confirmed `nNqkvTj5v9Qg4rwaKYhlAjQS-3N_gMc-whSGp-VypVE=` matches when secret = `GEARMENT_API_SECRET`. **`GEARMENT_WEBHOOK_HMAC_SECRET` in `.env:24` is redundant — drop or alias.**

### Edge cases observed in samples

- Go uses `base64.URLEncoding` (with `=` padding) for both body-encoding AND signature-encoding. JS sample strips padding from body-encoding but Gearment's signing service still computes against padded; tested both — match works either way for this body length (210 → 280-char b64 with no actual padding chars added).
- Java sample uses standard `Base64.getEncoder()` (NOT urlsafe) for the final signature — but that contradicts the Go ref AND our captured `X-Connect-Signature` value contains `-`/`_`/`=`. Treat Java sample as buggy doc; trust the Go canonical.

### Spec drift to fix in P0-18b2b implementation

- Topic key in body is `type` (e.g. `"order_completed"`), NOT `event` / `topic`. Update `_detect_topic` heuristic in `controllers/gearment_webhook.py`.
- V3 enum has `tracking_order_updated` (NOT `tracking_updated` as we registered — Gearment dashboard auto-corrects? Either name accepted? Verify on next probe).
- V1 payload includes `api_key` field in body (legacy auth carried in payload). V3 dropped it; HMAC + headers replace it.

### Topic enum (V3, full list from yaml)

`order_completed`, `order_cancelled`, `tracking_order_updated`, `order_on_hold`, `shipping_address_verified`, `shipping_address_unverified`, `product_out_of_stock`, `variant_created`, `variant_updated`.

### What unblocks P0-18b2b

- Verify code: ~30 LOC in `controllers/gearment_webhook.py`
- Use existing `GEARMENT_API_SECRET` from `.env`
- Replay defenses (P0-18b2b adds): timestamp window 5min, nonce cache (in-memory or `gearment.api.log` lookup) for 10min
- Mismatch → 401 + audit-log row + drop body-write to `request_body` (don't store hostile payloads); keep header capture

---

## P0-18b2b — staging deploy + self-signed probe verified (2026-05-02)

End-to-end on staging confirmed:

1. rsync mhf to `129.150.63.207`; `-u multichannel_hub_fulfillment` exit 0 on `demo_esty`
2. Patched `/odoo/esty19/docker-compose.yml` to `env_file: /odoo/esty19/.env` (700, root-owned); added `GEARMENT_API_KEY`, `GEARMENT_API_SECRET`, `GEARMENT_API_BASE_URL` (existing prod-shared sandbox values from local `.env`)
3. `docker compose up -d --force-recreate odoo` so env reloads
4. Curl probe with SYNTHETIC bogus headers → HTTP 401 + audit row `signature_verified=False` `verify_failure_reason='client_key_mismatch'`
5. Self-signed Python probe (computed with real `GEARMENT_API_SECRET` + fresh ts/nonce) → HTTP 200 + audit row `signature_verified=True` `verify_failure_reason=''` `topic_seen='order_completed'`

The verify path now works end-to-end on staging. When the owner re-fires the Gearment dashboard simulator, the inbound row should also stamp `signature_verified=True` (Gearment uses the same `GEARMENT_API_SECRET` which is now in the staging container's env).

Backups left on staging:
- `/etc/nginx/sites-available/odoo.hatafax.com.bak.2026-05-02` (P0-18b2a nginx patch)
- `/odoo/esty19/docker-compose.yml.bak.2026-05-02` (P0-18b2b env_file patch)

---

## P0-18b2c — staging deploy + end-to-end smoke verified (2026-05-02)

Deployed mhc + mhf to staging, bounced container, fired self-signed
Python probe with `body.order.reference='S00029'` (real demo order on
staging `demo_esty` DB):

```
HTTP 200: {"status": "ok"}
```

Audit row 6 captured:
| field | value |
|---|---|
| signature_verified | True |
| business_handled | True |
| business_summary | `order_completed:tracking_set:USPS` |
| sale_order_id | 29 (= S00029) |
| topic_seen | `order_completed` |

`sale_order_fulfillment` for S00029 reflected the write:
- `tracking_number = P0-18B2C-9400111`
- `tracking_url = https://track.usps.com/p018b2c`
- `tracking_state = shipped`
- `shipping_date = 2026-05-02`

P0-18b2 fully closed. Owner can now register the dashboard webhook
against any reference matching a real demo order to see the full
inbound-webhook → fulfillment write loop without writing custom
self-signed probes.

Note for ops: the existing nginx route still proxies all
`/gearment/webhook` traffic to the `demo_esty` DB via `X-Odoo-Database`
header injection (P0-18b2a). When promoting to production, swap the
target DB and re-fire one signed probe to verify env vars +
nginx routing on the prod path.

## P0-18b2 — Phase 7 ops close-out (2026-05-02 23:17 UTC)

End-to-end verification complete. Tracker row 107 flipped `doing →
done`.

Verification driver: `scripts/e2e_demo_2026_05_02.py` (Playwright sync
API + self-signed HMAC POST). Self-signed instead of dashboard
simulator because the simulator UI flow was not documented in the
repo and writing a Python HMAC helper that reuses the in-tree
`_compute_signature` (controllers/gearment_webhook.py:96-108) was
faster than reverse-engineering the dashboard UI.

Probe payload: `order_completed` topic against `S00013`
(`client_order_ref=DEMO-gearment_pod-02`, `gearment_pod/confirmed`,
empty fulfillment).

Outcome:

- HTTP 200 `{"status":"ok"}`.
- `gearment.api.log` row id=8 — `direction=inbound`, `topic_seen=order_completed`,
  `signature_verified=true`, `business_handled=true`,
  `business_summary='order_completed:tracking_set:USPS'`.
- `sale.order.fulfillment id=13` write deltas:
  - `tracking_number`: `(empty) → 9400111202555560000001`
  - `tracking_state`: `(empty) → shipped`
  - `shipping_date`: `(empty) → 2026-05-02`
  - `tracking_url`: `(empty) → https://tools.usps.com/...`
- Pipeline state stayed at `gearment_pod/confirmed` (handler is
  fulfillment-only by design; pipeline FSM advance is P4-01 scope).

Run artefacts:

- `docs/E2E_DEMO_RUN_2026-05-02.md` (pass/fail report).
- `docs/screenshots/2026-05-02/*.png` (9 screenshots, sections
  0/1.1/3/4/6/8.3/10).
- `docs/E2E_TESTING_GUIDE.md` §10 + §12 updated: webhook moved from
  "not yet deployed" to shipped; P0-18b2 dropped from limitations
  list.

Lessons:

- Staging deploy was already at HEAD (rsync no-op); module versions
  in `ir_module_module.latest_version` are an authoritative pre-flight
  check — saves a needless `-u` cycle when disk is already in sync.
- No menu/action xmlid was seeded for `gearment.api.log`; reaching it
  via the direct `/odoo/<model>` URL works in Odoo 19 web client and
  saves the cost of authoring a one-off action XML. If the log
  becomes a routine ops surface, add an action under the
  `Operations` menu in a follow-up doc-only slice.
- Multi-DB selector page (`/web/login` lands on database list) ate
  several Playwright retries before the test added `?db=demo_esty`.
  Future Playwright runs against this staging stack must always
  pin the DB in the URL.
- `tests/data/sample_50_orders.xlsx` does not exist on staging;
  guide §5 (Tracking Import) needs a fixture before that section can
  run end-to-end on demo_esty. Filed as future work, not a P0-18b2
  blocker.
- Helper `_compute_signature` is also useful as a public ops tool;
  the demo script effectively reuses it inline. Consider exporting
  it from `controllers/gearment_webhook.py` to a `services/` helper
  in a future cleanup if more probes need self-signing.
