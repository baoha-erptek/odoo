# Findings — Spec 005 Etsy API Channel

Per `.claude/plans/006-implementation-playbook.md` Phase 7. Surprises, blockers, and deferred decisions discovered during implementation. Each entry stands on its own; do not delete entries — supersede them with new ones.

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

Tick or annotate per question, then proceed with implementation:

- [ ] Q1 — One-per-test cassettes, quarterly refresh via `ETSY_DEV_TOKEN_REFRESH=1`. Refresh cadence ok? Y / N / change to: ___
- [ ] Q2 — `ir.config_parameter` + `group_system` for sandbox; encryption deferred to P1-XX. Acceptable? Y / N
- [ ] Q3 — Per-client token bucket for sandbox; shared bucket as Phase 1 refactor task. Acceptable? Y / N
- [ ] Q4 — Boolean `etsy.shop.sync_audit_mode`; read-only path in syncer. Acceptable? Y / N
- [ ] Q5 — Land in `etsy_integration`, re-home to `etsy_channel` during ADR-003 Phase 1. Acceptable? Y / N
- [ ] Author ADR-009 (VCR policy) and ADR-010 (audit mode) before sandbox coding starts? Y / N

---
