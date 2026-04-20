# ADR-008: API-First Pivot — Skip Email Parsing for New Orders

- **Status**: Accepted
- **Date**: 2026-04-13
- **Sign-off**: 2026-04-13 (owner)
- **Deciders**: Owner, architect, BA lead
- **Affects**: MASTER_PLAN §4 phased roadmap, Spec 001 (email parser lifecycle), Spec 002 (historical-only scope), Spec 003 (unchanged), Spec 004a (unchanged), Spec 005 (priority lifted)
- **Related**: [ADR-002](ADR-002-drop-dual-sync-mode.md), [ADR-003](ADR-003-module-decomposition.md), [MASTER_PLAN.md](../MASTER_PLAN.md)

## Context

The 2026-04-13 master-plan sign-off accepted ADR-002, which made `api_only` the default for new `etsy.shop` records but kept the existing 19 shops on `email_only` pending per-shop cutover. Spec 005 (Etsy API v3) was deferred to Phase 3, with scope review running in parallel during Phases 0–2.

Owner revised this on 2026-04-13: **for new orders, the Etsy API is the intended ingestion path; email parsing is not a long-term capability we want to extend, maintain, or build new features on top of**. The existing email code continues to run for legacy / historical shops but is frozen for feature work.

The direct consequences:

1. The email parser becomes a **legacy capability** with a known retirement arc, not a co-equal ingestion mode.
2. Spec 005 moves from Phase 3 (post-MVP) to **Phase 0 (dev/sandbox) + Phase 1 (production cutover)**. It is now on the critical path for new-order value.
3. Etsy app scope review changes from a "parallel, nice-to-have-early" task to a **critical-path external dependency**. Production cutover cannot happen until scopes are granted.
4. Gmail polling cron for `sync_mode='api_only'` shops switches to the shadow-logging behaviour described in ADR-002 §4.6 (30-day observation, then filter removal).
5. Any new parser work (new shop onboarding, template variations, new receipt fields) is now **rejected by default**; fixes are allowed for production-breaking bugs only.

## Decision

### 1. API is the primary ingestion path going forward

- **All new shops** onboard with `sync_mode='api_only'` from day one. No email route is configured. If the Etsy app lacks scopes at the time a new shop is added, onboarding is **blocked** (not degraded to email).
- **Existing 19 shops** follow the ADR-002 cutover procedure, but with elevated priority: cutover work begins as soon as Etsy scopes are approved and the Spec 005 P1 stories (US1, US2, US3, US5, US8) are in production. Target: all 19 shops flipped to `api_only` within 8 weeks of scope approval.
- **Historical orders** (17,659 rows currently in the DB) stay on their existing records; Spec 002 cleans them in place. No re-ingestion from the API.

### 2. Spec 005 priority reset

- Spec 005 status changes from **DEFERRED to Phase 3** to **ACTIVE — Phase 0 (dev/sandbox) + Phase 1 (production cutover after scope approval)**.
- Phase 0 work on Spec 005 (before scopes approved): OAuth2 PKCE scaffolding, client library (`EtsyApiClient`), rate limiter, `EtsyOrderSyncer` against a developer-personal-token shop, `etsy.api.log`, test harness with VCR-style fixtures recorded from the dev shop. No production shops touched.
- Phase 1 work on Spec 005 (after scopes approved): production OAuth flow, pilot shop cutover with `sync_audit_mode=True` for 1–2 weeks per ADR-002 §4, then per-shop flip to `api_only`.
- US4 (webhooks) remains P2 per ADR-002. US6 (listing management) remains P2. US7 (conversations) remains deferred.

### 3. Email parser enters maintenance mode

- No new features on the email parser. "New feature" = new field extraction, new template support, new shop format handling, new cron logic.
- **Allowed** on the parser: production-breaking bug fixes (regex failing on a specific shop's current template), security fixes, logging changes needed for cutover observability.
- **Not allowed**: extending parser coverage to new Etsy email templates, adding new extracted fields, adding new anti-detection or retry logic beyond the current state.
- The parser code moves to `etsy_channel_legacy` module per ADR-003 as soon as the 4-module decomposition ships (before Phase 1 code per the master plan). Moving to the legacy module does **not** mark it uninstallable — it continues to run for shops still on `email_only`. Uninstallability arrives 12 months after the last shop is flipped (per ADR-002 §5).

### 4. Etsy scope review is the critical-path external dependency

- Submission window: **this week** (no slippage). Owner task.
- Scopes requested: `transactions_r`, `transactions_w`, `listings_r`, `listings_w`, `shops_r`, `email_r`. `conversations_r` is requested with a stated willingness to be deferred.
- Weekly status ping on the review ticket; if >4 weeks with no response, owner escalates via Etsy developer support.
- **Contingency if scopes denied or materially reduced**: the pivot holds for new shops on whatever scopes are granted. Features gated on missing scopes go to a separate rejected-scopes backlog. `transactions_w` denial blocks tracking push (US3) only; ingestion (US2) still works with `transactions_r` alone.

### 5. Gmail cron shadow-logging activation

- Pre-cutover, per-shop: Gmail cron still parses and writes (existing behaviour).
- Post-cutover, per-shop: Gmail cron still polls for 30 days but writes only to `etsy.api.log` (source='post_cutover_shadow') — no `sale.order` writes. This is the safety net described in ADR-002 §4.6.
- After 30 days: remove the shop from the Gmail label filter. The cron stops seeing that shop's mail entirely.
- After all 19 shops are flipped and 30-day shadow periods elapse: disable the Gmail cron at module level. The `EmailParser` service remains importable (for tests) but is no longer scheduled.

### 6. Roadmap impact (summary; full restatement lives in MASTER_PLAN §4)

| Phase | Pre-pivot | Post-pivot |
|---|---|---|
| 0 | Spec 002 migration + observability + Gearment POC + scope review submission | Same, **plus** Spec 005 sandbox scaffolding (OAuth, client, order syncer against dev shop) |
| 1 | Spec 003 three dashboards + approval workflows | Same, **plus** Spec 005 production cutover begins as soon as scopes approved (overlaps with dashboard work) |
| 2 | Spec 004a GKE tracking import | Same, **plus** completion of remaining shop cutovers to `api_only` |
| 3 | Spec 005 full rollout | **Removed.** Rolled into Phases 0–2. Freed capacity moves to Phase 4 earlier. |
| 4 | Spec 004b Gearment + 004c returns + 006 pricing audit | Same, starts ~4 weeks earlier than pre-pivot estimate |
| 5 | 007 inventory, 008+ catalog/scan/Amazon/website | Same |

### 7. Amazon and Website channels

- Confirmed by owner the same day: Amazon integration remains **architecture-planning only** until Etsy full-flow production (Phase 1 cutover complete for all 19 shops). Spec 010 (Amazon) and Spec 011 (Website) stay in Phase 5.
- Phase 1 Spec 003 must still deliver channel-agnostic abstractions (`sales_channel`, `channel_order_ref`, the delegation mixin, unified carrier) — unchanged requirement, no new scope.

## Consequences

### Positive

- **One path forward**. The team stops hedging between two ingestion modes. Parser work ends; API work begins.
- **Cleaner data model**. New orders carry `buyer_email`, `listing_id`, receipt-level timestamps, and real currency from the API — data the parser cannot produce. This raises the ceiling for dedup, reporting, and pricing audit (Spec 006).
- **Earlier tracking push**. US3 (push tracking to Etsy) was the single most-requested capability from Marketing. Moving Spec 005 forward surfaces this in Phase 1 instead of month 7+.
- **Gearment spike stays where it was** (Phase 0). No cross-dependency introduced by this pivot.
- **Spec 003's channel abstractions get validated against a real second writer** (API syncer) during Phase 1, not retrofit years later.

### Negative

- **Critical-path external dependency**. If Etsy takes 8+ weeks for scope review, Phase 1 cutover slips by the same amount. Dashboards can still ship on schedule (they don't depend on scopes), but the "API-first" promise to the team materialises later.
- **Developer tokens have limits**. Phase 0 sandbox work on Spec 005 uses the owner's personal Etsy dev token, which can only access the owner's shop. Integration-test coverage across the 19 shops' quirks is impossible until production scopes arrive. Mitigation: record real API responses from 2–3 representative shops via dev-token calls (read-only on shops where the owner is a collaborator), replay in CI.
- **Cost of parser-freeze visible early**. Any shop whose email template changes during Phase 0/1 (before its cutover) cannot be fixed by the parser — that's a "feature" change now. Such shops must be prioritised for early cutover. Mitigation: maintain a "parser-at-risk" watch list in `etsy.sync.health`.
- **Team-size estimate unchanged**. The master plan's 2-dev / 12–18-month timeline remains the realistic baseline; this pivot does not accelerate the total effort, only reorders it.

### Neutral

- ADR-002 remains in force unchanged. `sync_mode` values, default, cutover procedure, 30-day shadow window — all unchanged.
- ADR-003 (module decomposition) timing unchanged — still "before Phase 1 code".
- Spec 002's scope unchanged — still the authoritative cleanup of the 17K historical rows.

## Alternatives considered

1. **Keep Spec 005 in Phase 3, proceed with email-forever** — rejected. Parser has failed 423 times already on the current corpus; continuing to extend it is paying interest on a debt with no principal reduction.
2. **Disable email parser immediately, API-only from day one on all shops** — rejected. Blocks on Etsy scope review (3–8 weeks) and on Spec 005 P1 stories completing (another 6–8 weeks). Creates a full ingestion outage during that window. The ADR-002 cutover procedure is the correct bridge.
3. **Keep dual paths but mark API as "preferred"** — rejected. That's ADR-002's pre-pivot state; it failed to create the decisive prioritisation the team needed. Pivot requires a clear hierarchy: API is primary, email is legacy.
4. **Wait for scope approval before starting any Spec 005 code** — rejected. Owner has a dev shop; OAuth scaffolding and client code can be built against it without consuming production scopes. Starting now saves 3–8 weeks of calendar.

## Implementation notes

Immediate file edits (this PR):

- `specs/006-master-plan/MASTER_PLAN.md` §4 (roadmap) — move Spec 005 from Phase 3 into Phase 0 (sandbox) + Phase 1 (cutover).
- `specs/006-master-plan/MASTER_PLAN.md` §6 (decisions) — append row 10: "API-first pivot; Spec 005 Phase 0 + Phase 1".
- `specs/006-master-plan/MASTER_PLAN.md` §7 (next steps) — elevate Etsy scope submission to Wave A highest-priority.
- `specs/005-etsy-api-channel/spec.md` — replace the Phase-3 deferral banner with an ACTIVE banner pointing here.
- `specs/005-etsy-api-channel/plan.md` — split implementation into Phase 0 (sandbox) and Phase 1 (production cutover) blocks; add dev-token test-harness task.
- `specs/001-etsy-order-migration/` — add a `STATUS-MAINTENANCE.md` note freezing feature work (separate follow-up, not blocking).
- `.claude/plans/006-master-plan-tracking.md` — execution tracker with Etsy scope submission as Task 1.

Operational follow-through:

- Record a "parser-at-risk" tile on the health dashboard (Spec 002 scope is already building this; add a `parser_template_drift` metric fed by current parser failure counts).
- Add a weekly 30-minute review slot for Etsy scope ticket status until approved.
- Owner submits scope review with all scopes in the list above **this week**; success criterion is a confirmed ticket ID from Etsy.

## Revision history

- **2026-04-13**: Initial authoring. Accepted same day.
