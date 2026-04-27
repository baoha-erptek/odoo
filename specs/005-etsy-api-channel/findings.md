# Findings — Spec 005 Etsy API Channel

Per `.claude/plans/006-implementation-playbook.md` Phase 7. Surprises, blockers, and deferred decisions discovered during implementation. Each entry stands on its own; do not delete entries — supersede them with new ones.

---

## 2026-04-27 — P0-15 EtsyApiClient sandbox landed

**Slice scope (final, post-execution)**:
- `services/etsy_api_client.py`: `EtsyApiClient(shop)` constructor, `_session()` two-header auth (`Authorization: Bearer`, `x-api-key`), `_request()` with rate limiting + 429 retry + 401 single-shot refresh, `ping()` against `/users/me`. Module-level constants: `ETSY_API_BASE_URL = 'https://openapi.etsy.com/v3/application'`, `_RATE_LIMIT_QPS = 8`, `_MAX_RETRY_AFTER_SECONDS = 60`, `_PROACTIVE_REFRESH_WINDOW_SECONDS = 60`.
- 19 mocked tests in `tests/test_etsy_api_client.py` (TransactionCase, post_install): init validation × 4, session headers × 2, ping × 4, rate-limit × 4, 401-refresh × 5.
- Memory `feedback_odoo19_test_gotchas.md` will gain a #24 once committed: `BaseCase._assertRaises` calls `issubclass(exception, AccessError)`, which fails on tuple — never pass a tuple of expected exceptions to `with self.assertRaises(...)` in Odoo tests.

**Q-resolved (architect's W2 advisory; outcomes)**:
- **Q3 (rate limiter)**: per-instance `TokenBucket(rate=8, period=1.0)`. Imported from `multichannel_hub_core.utils.rate_limiter` — the architect's "long-term home" was reached early in P0-18a. **Phase 1 refactor task removed from backlog** (the per-shop bucket lives in core; if multi-shop fairness becomes an issue, that's a P1 ticket on top of the existing core utility).
- **Q5 (module home)**: lands in `etsy_integration` per the advisory. Re-home to `etsy_channel_api` deferred to ADR-003 Phase 1 (P1-XX), with the API surface intentionally narrow (`shop` + `ping()`) so the move is mechanical.

**Surprises (all resolved before commit)**:

1. **Credential-loader path off-by-one**. Initial GREEN computed the credentials file path via `dirname(__file__)` chained 3 times then `'..', '..', 'secrets', 'credentials.json'`, which resolved to `other_projects/secrets/credentials.json` — outside the project. Code-reviewer caught it as CRITICAL (would 401 in production). Fix: hardcode `CREDENTIALS_PATH = '/opt/odoo/secrets/credentials.json'` to match what `controllers/etsy_oauth._read_credentials` already does (it reads from `ir.config_parameter` with the same string as the default). Convention now: in-container path is the source of truth; the Python computation is fragile when the file lives outside the addon. **If we ever need a portable computed path, derive from `env['ir.config_parameter']` like the controller does — but the service layer here doesn't take `env`, so the constant is fine.**

2. **`BaseCase._assertRaises` does not accept tuples** (Odoo test gotcha). The RED test had `with self.assertRaises((ValueError, FileNotFoundError)):`, which crashed inside Odoo's overridden `_assertRaises`: `if issubclass(exception, AccessError)` — `issubclass` requires a class as first arg, not a tuple. Fix: my impl wraps `FileNotFoundError → ValueError` so the test only needs `ValueError`. Single-class `assertRaises(ValueError)` works fine. Saved to memory as gotcha #24.

3. **Tz-naive datetime comparison** (security-reviewer MEDIUM). First GREEN used `datetime.now()` to compute the proactive-refresh threshold. Odoo Datetime fields read as **naive UTC**, so on a non-UTC host this would skew. Fix: switched to `datetime.utcnow()` for both the threshold and the `expires_at` write inside `_refresh_token`. Now matches Odoo's storage convention regardless of host TZ.

4. **`self.shop.refresh()` doesn't exist on Odoo 19 recordsets** (memory gotcha #4). The RED test invalidated the cache via `self.shop.refresh()`; this raised `AttributeError` during GREEN run. Fix: `self.shop.invalidate_recordset()`. Test still asserts the expected post-refresh token state.

**Q-deferred (security-reviewer LOW notes; revisit at hardening pass)**:

- **DQ1 — Caller-side ACL gate**: `EtsyApiClient` does NOT check the calling user's access to the shop before instantiating. Service-layer responsibility per the class docstring; the orchestrator (cron, sync wizard, controller route) must gate access. Add a `check_access_rule` helper if/when this client is ever invoked from a user-controlled action.
- **DQ2 — `requests.Session` redirect policy**: defaults to following redirects. Same finding as P0-18a, deferred to a hardening slice (P1-XX) that sets `session.max_redirects = 0` for both Etsy + Gearment clients.
- **DQ3 — `path` argument to `_request()` accepts fully-qualified URLs accidentally**: `f"{base}/{path.lstrip('/')}"` doesn't validate that `path` is relative. Currently only `ping()` calls it with `'users/me'`; document the convention until `_request()` becomes user-callable.

**Verification**:
- `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --test-tags=/etsy_integration --stop-after-init` → 0 fail / 0 error / 170 tests.
- Full regression `-u etsy_integration,multichannel_hub_core,multichannel_hub_fulfillment` → 0 fail / 0 error / 236 tests.
- No `_logger.info(` / `print(` introduced.
- Reviews: code-reviewer PASS after credential-path fix; security-reviewer PASS with 3 LOW notes captured above.

**Branch + commit**: `feature/006-master-plan-coding`. RED already on branch as `d84f92c3cbb`; GREEN + review fixes commit follows.

**Unblocks**: P0-16 (`EtsyOrderSyncer` against dev shop with VCR fixtures) — has the rate-limited authenticated client to syndicate from.

---

## 2026-04-27 — P0-14 OAuth2 PKCE sandbox landed

**Slice scope (final, post-execution)**:
- `services/etsy_oauth.py` (pure functions): `generate_code_verifier`,
  `generate_code_challenge`, `build_authorize_url`,
  `exchange_code_for_token`, `refresh_access_token`
- `controllers/etsy_oauth.py`: routes `/etsy/api/oauth/authorize`
  (auth='user', shop-write ACL gated) and `/etsy/api/oauth/callback`
  (auth='public', csrf=False, state-based replay defense)
- `models/etsy_shop.py`: 3 new fields with `groups='base.group_system'`
  (plaintext per Q2 deferral; Fernet-at-rest is P1-10 work)
- 23 tests: 9 PKCE pure-function + 7 DB+ORM on the new fields + 7
  HttpCase controller integration

**Routing-namespace surprise**: original ADR-008 implied the OAuth callback
would land at `/etsy/oauth/callback`, but Spec 001 already shipped a Gmail
OAuth controller claiming that exact URL. To avoid a route collision (and
to keep the Gmail flow stable per ADR-008a v2 — email parser stays as
permanent failover), the new Etsy v3 API OAuth lives at
`/etsy/api/oauth/...`. Future module decomposition (ADR-003 Phase 2) can
revisit naming when the per-channel modules split out.

**PKCE test-vector hallucination**: the tdd-guide's RED tests included a
"RFC 7636 Appendix B" expected challenge value of
`E9Mrozoa2owWoUeS_Z6OQ3OKN2iCHaEc292iNLsrgS8` for the verifier
`dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXo`. Python's hashlib produces
`xmcnc8avt3As1ZGvMdrjrrWgSSwK8XeDmIDLCfAoW38` for that input — the
"expected" was wrong (RFC §B's published challenge value differs from
the actual SHA256 of the published verifier; either the RFC has a typo
or the agent paraphrased an incorrect source). Replaced with a verified
vector (SHA256 of `'hello'` → `LPJNul-wow4m6DsqxbninhsWHlwfp0JecwQzYpOLmCQ`).
Lesson: when a test has a memorized RFC vector, verify it against an
independent computation before committing.

**Test-harness surprise**: HttpCase tests in Odoo 19 follow redirects
by default. When the authorize route correctly returns 302/303 to
`https://www.etsy.com/oauth/connect`, the test harness's `requests`
session follows it and gets blocked by Odoo's
`Blocking un-mocked external HTTP request` middleware — surfacing as
an opaque test error. Fix: pass `allow_redirects=False` to `url_open`.

**Q2 reaffirmed (encryption deferred)**: tokens stored plaintext in
`etsy_shop.etsy_oauth_access_token`. Field-level `groups='base.group_system'`
ACL blocks UI reads for non-admins, but the column is plaintext on
disk and in `pg_dump`. Acceptable for sandbox per Q2 (owner accepted
2026-04-26). P1-10 must add Fernet-at-rest before any production token
lands. Track this in tracker P1-10 as a hard prerequisite.

**Security gate added late**: original /authorize route accepted any
authenticated user with any `shop_id`. Security-reviewer (Opus) flagged
as HIGH (privilege escalation: a salesman could trigger token rebind
for a manager's shop). Fixed by adding `shop.check_access_rights('write')
+ shop.check_access_rule('write')`. Lesson: when a route accepts a
user-supplied record ID, always gate with explicit ACL — auth='user'
alone is not enough.

**Werkzeug exception → 500 instead of 400**: raising
`werkzeug.exceptions.BadRequest` in an Odoo 19 HttpCase test triggers
the qweb 400 error template, which depends on assets unavailable in the
test harness — the response bumps to 500. Workaround: return a plain
`request.make_response(msg, status=400)` instead of raising. May be
worth contributing back to Odoo as a documentation fix if the
`werkzeug.exceptions.*` pattern is meant to work in HttpCase.

---

## 2026-04-26 — Architecture Advisory: Sandbox Bootstrap Open Questions

**Context**: Wave 2 planner (P0-14..17 sandbox bootstrap) raised 5 open questions before implementation. `architect` agent (Opus tier) produced this advisory. **Owner decision required** before sandbox coding starts.

### TL;DR
For sandbox Phase 0 work:
1. **VCR cassettes**: one-per-test in `tests/fixtures/vcr/`, refresh quarterly via `ETSY_DEV_TOKEN_REFRESH=1` flag.
2. **Token storage**: `ir.config_parameter` with `group_system` ACL; defer encryption to Phase 1.
3. **Rate limiter**: in-memory token bucket inside `EtsyApiClient` (per-instance), promoted to shared in `multichannel_hub_core` post-Phase 1.
4. **Audit mode**: Boolean `etsy.shop.sync_audit_mode` field; runs read-only, logs diffs to `etsy.api.log` with `source='audit'`, gates all `sale.order` writes.
5. **Module decomposition**: land sandbox in `etsy_integration` now; re-home to `etsy_channel` during ADR-003 Phase 1 (before Phase 1 spec code ships).

### Q1 — VCR cassette policy

**Recommendation**: One cassette per test (fine-grained, many files).

**Rationale**: Sandbox tests target the owner's dev token + one shop. Each fixture (list receipts / token refresh / 429 response) exercises a distinct API behavior. One-per-test isolates these and lets you repair affected cassettes when Etsy responses change. Shared/scenario cassettes tempt cross-test coupling.

**Tradeoffs**:
| Approach | Pro | Con | Verdict |
|---|---|---|---|
| Shared (per scenario) | Fewer files, realistic sequences | Tests entangled, all-or-nothing re-record | Rejected |
| One-per-test | Clear isolation, incremental repair | ~30–50 cassettes | **Chosen** |

**Refresh policy**: CI replays cached cassettes by default (hermetic). When `ETSY_DEV_TOKEN_REFRESH=1`, re-record against dev shop. Manual quarterly cadence to catch Etsy surface changes. git-lfs only if total > 50 MB.

**Location**: `custom_addons/etsy_integration/tests/fixtures/vcr/<scope>/`.

**Decision needed**: Confirm refresh frequency (quarterly default) and whether CI auto-records on schedule or requires manual flag.

---

### Q2 — OAuth token storage

**Recommendation**: `ir.config_parameter` with `group_system` ACL for sandbox; encryption deferred to Phase 1.

**Rationale**: Sandbox = dev token, dev shop, dev DB. The pattern matches existing Gmail OAuth credentials. Per-shop key naming (`etsy_integration.etsy_access_token_{shop_id}`) plus `groups='base.group_system'` blocks casual UI visibility. No operator sees raw tokens.

**Phase 1 decision (out of scope here)**: Once production scopes arrive (E1), evaluate Fernet / KMS / Odoo `fields.Encrypted` (verify Odoo 19 support). Compliance may require encryption at rest. Add task P1-XX.

**Tradeoffs**:
| Approach | Pro | Con | Verdict |
|---|---|---|---|
| Encrypt sandbox tokens now | Defense in depth | Key rotation complexity for dev | Rejected (premature) |
| Env vars | Simple for dev | Doesn't scale to 19 prod shops | Rejected |
| `ir.config_parameter` + `group_system` | Sufficient for sandbox, defers crypto | Plaintext-at-rest in dev DB | **Chosen** |

**Decision needed**: Confirm `group_system` ACL is sufficient for Phase 0; commit to a P1-XX task to evaluate encryption when production scopes land.

---

### Q3 — Rate limiter design

**Recommendation**: In-memory token bucket inside `EtsyApiClient` (per-instance). Long-term home in `multichannel_hub_core/utils/rate_limiter.py` post-ADR-003 Phase 1.

**Rationale**: Etsy publishes ~10 QPS + 10 000 QPD per *app* (not per shop). Sandbox = 1 shop, so per-instance bucket is exact. Phase 1 = 19+ shops on the same app, where shared bucket becomes correct (and adds intra-process locking + fairness logic). Defer that complexity until multi-shop testing reveals starvation.

**Concrete**: `EtsyApiClient._qps_bucket = TokenBucket(capacity=8, refill_rate=8/sec)`. Adjust dynamically via `x-remaining-this-second` response header.

**Tradeoffs**:
| Approach | Pro | Con | Verdict |
|---|---|---|---|
| Shared global bucket | Accurate to API contract | Locking, fairness, complexity | Deferred to Phase 1 |
| No rate limit | Fastest | Account-throttle risk (FR-023 violation) | Rejected |
| Per-client bucket | Simple, sufficient for sandbox | Inaccurate when N shops > 1 | **Chosen for Phase 0** |

**Long-term home**: Per ADR-003, `multichannel_hub_core/utils/rate_limiter.py`. Until that module exists, place in `etsy_integration/services/rate_limiter.py` and flag for re-home in Phase 1.

**Decision needed**: Confirm per-client bucket for sandbox; commit to refactor task in Phase 1 if multi-shop testing shows unfair distribution.

---

### Q4 — `sync_audit_mode` semantics

**Recommendation**: Boolean field `etsy.shop.sync_audit_mode`. When `True`: API runs read-only, fetches receipts, logs field diffs to `etsy.api.log` (source='audit'), zero `sale.order` writes.

**Rationale**: ADR-002 §3 introduces audit mode for the 1–2 week pilot-shop cutover window. The API runs in parallel with the email parser; the BA reviews diffs. Implementation:

1. `EtsyOrderSyncer.sync_shop_orders(shop)` checks `shop.sync_audit_mode` early.
2. If True: fetch receipts → for each, compare key fields (amount_total, line items, shipping address) against existing `sale.order` matched by `etsy_order_id` → write diffs to `etsy.api.log` with `source='audit'`.
3. Return without calling `OrderCreator`.
4. Log summary: "Audit run: 247 receipts compared, 5 diffs found."

**Field placement**: Boolean on `etsy.shop`, default `False`. Orthogonal to `sync_mode` (can be True regardless of `email_only` / `api_only` — though `api_only + audit` is nonsensical and should be guarded by a constraint).

**Tradeoffs**:
| Option | Verdict |
|---|---|
| (a) Block cron entirely | Rejected — loses validation opportunity |
| (b) Read-only, log diffs | **Chosen** |
| (c) Third value in `sync_mode` enum (`audit_only`) | Rejected — audit is temporary + orthogonal |

**Decision needed**: Confirm Boolean field design; confirm BA's ≥99.5% field-match gate before flipping to `api_only` per ADR-002 still holds.

---

### Q5 — Module decomposition timing

**Recommendation**: Land sandbox in `etsy_integration` now. Organize structurally as if split. Re-home to `etsy_channel` during ADR-003 Phase 1, before Phase 1 spec code ships.

**Rationale**: ADR-003 §3 commits to phased decomposition:
- Phase 0 (during Spec 002): `etsy_integration` monolithic, but code organized as if split.
- Phase 1 (start of Spec 003 rewrite): create `multichannel_hub_core`, extract shared pieces, declare dependency.
- Phase 2 (Spec 004a): create `multichannel_hub_fulfillment`, rename `etsy_integration` → `etsy_channel`.

For P0-14..17 specifically:
- Do NOT create `etsy_channel` yet.
- Land code in `etsy_integration/{models,services,tests}/`.
- Use module-agnostic test imports: `from odoo.addons.etsy_integration.services.etsy_api_client import ...` (survives the rename).
- Document the future move in `etsy_integration/__init__.py` comment + this findings file.

**Why not alternatives?**
| Option | Verdict |
|---|---|
| (a) Land in `etsy_integration` now, re-home in Phase 1 | **Chosen** — single clean move |
| (b) Do P0-20 first, then land in `etsy_channel` | Rejected — P0-20 unknowns block sandbox |
| (c) Create only `multichannel_hub_core` now | Rejected — splits a single feature, premature abstraction |

**Decision needed**: Confirm landing in `etsy_integration` is acceptable; commit to executing P0-20 before Phase 1 spec code starts.

---

### Cross-cutting risks

- **`EtsyApiClient` lifecycle**: All five decisions converge on this class. It owns the cassettes (Q1), reads tokens (Q2), holds the rate limiter (Q3), is invoked by `EtsyOrderSyncer` which checks audit mode (Q4), and lives in `etsy_integration` until Phase 1 (Q5). Verify the test harness and imports stay aligned across changes.
- **Token refresh during sandbox**: Dev token expires in ~1 hour. VCR cassettes must include a "refresh token" success case + a refresh-timeout test for graceful failure.
- **Audit mode + rate limiter**: Audit sends N-1 read-only requests per cycle → same QPS load as normal mode. With 19 shops in audit simultaneously (Phase 1), the per-client bucket (Q3 Phase 0) becomes a starvation risk → confirms the Phase 1 refactor to shared bucket.

---

### New ADRs proposed

- **ADR-009**: VCR cassette policy (Q1) — lightweight, no risk.
- **ADR-010**: Audit mode semantics (Q4) — clarifies the cutover workflow for BA.

Both are <1 page. Author them in `specs/006-master-plan/adrs/` once Owner decisions land here.

---

### Owner decision form

**2026-04-26 Owner decision**: "proceed as recommendation, we'll comeback for open questions when do end-to-end test."

All five recommendations accepted as defaults for sandbox implementation (W5). Revisit during the W7 E2E sprint if it surfaces issues.

- [x] Q1 — One-per-test cassettes, quarterly refresh via `ETSY_DEV_TOKEN_REFRESH=1`. **Accepted as architect recommendation. Revisit at W7.**
- [x] Q2 — `ir.config_parameter` + `group_system` for sandbox; encryption deferred to Phase 1. **Accepted as architect recommendation. Revisit at W7.**
- [x] Q3 — Per-client token bucket for sandbox; shared bucket as Phase 1 refactor task. **Accepted as architect recommendation. Revisit at W7.**
- [x] Q4 — Boolean `etsy.shop.sync_audit_mode`; read-only path in syncer. **Accepted as architect recommendation. Revisit at W7.**
- [x] Q5 — Land in `etsy_integration`, re-home to `etsy_channel` during ADR-003 Phase 1. **Accepted as architect recommendation. Revisit at W7.**
- [ ] ADR-009 (VCR policy) and ADR-010 (audit mode) — **deferred until W7 E2E results inform whether the policies need codifying as ADRs or remain implementation-level decisions.**

W2 → W5 unblocked. P0-14..17 move from `blocked` to `todo` in the tracker.

---
