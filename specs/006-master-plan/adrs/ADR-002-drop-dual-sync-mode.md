# ADR-002: Drop Dual-Mode Sync; Keep Only `email_only` / `api_only`

- **Status**: Proposed (awaiting owner sign-off)
- **Date**: 2026-04-10
- **Deciders**: Owner, architect, BA lead
- **Affects**: Spec 005 (Etsy API v3 channel integration)
- **Related**: [MASTER_PLAN.md §3](../MASTER_PLAN.md), [tech-architect.md §4](../agent-reports/tech-architect.md), [devils-advocate.md §1.3](../agent-reports/devils-advocate.md)

## Context

Spec 005 currently proposes a per-shop `sync_mode` field on `etsy.shop` with three values:

- `email_only` — legacy Gmail-based regex parser (Spec 001 behavior)
- `api_only` — new Etsy API v3 pull
- `dual` — both active simultaneously, producing orders from whichever arrives first, with the other branch updating the existing record

The stated rationale for `dual` is gradual migration safety: "run both until we're confident the API matches email-parsed data."

Two of the three agent-review lenses flagged `dual` as dangerous:

- **Technical architect**: "Dual is a trap. Two sources writing to the same `sale.order` without row locking = last-write-wins. Email's 43-regex parser has already failed 423 times; partial data overwrites complete API data."
- **Devil's advocate**: "Race conditions are unmanaged. Email arrives 12s before API sync. Two orders created. Tracking arrives via GKE, then API rewrites from stale Etsy cache. Silent data corruption. **No documented reconciliation logic.**"

The BA lens concurs indirectly: "Defer Spec 005 entirely past MVP and ship the dashboards first." If Spec 005 is deferred, the premise of `dual` (gradual migration on live data) becomes moot anyway.

### Specific failure modes dual introduces

1. **Dedup collision**: Email parser extracts `receipt_id` via regex → fails on 2.4% of emails today → creates `etsy_order_{malformed_id}`. API creates canonical `etsy_order_{real_id}`. Two orders for one receipt.
2. **Field stomping**: API webhook arrives during email poll. Both call `write()` on the same order. Odoo ORM doesn't lock rows for write. Last-write-wins. Fulfillment state silently corrupted.
3. **Flip-flopping tracking**: GKE Excel import writes tracking. Next API sync reads Etsy's cached `tracking_code` field (which may be stale because Etsy hasn't seen the upload yet) and overwrites. Cycles forever.
4. **Conflicting totals**: Email parser says `$42.50`. API says `$41.97` (Etsy fee recalculation). Which wins? If the email was already invoiced, does the API re-invoice the delta?
5. **No conflict-resolution policy** documented anywhere.

## Decision

1. **`sync_mode` has exactly two values**: `email_only` and `api_only`.
2. Per-shop, the switch is **one-way**: once flipped to `api_only`, it cannot return to `email_only` without explicit admin override.
3. For the transitional period (one shop at a time, during validation), a **separate one-off field** `sync_audit_mode = Boolean` is added. When `True` on a shop that is still `email_only`, the API client runs **read-only** and writes comparison results to `etsy.api.log` (source='audit'). No writes to `sale.order`. This is a 1-week validation tool, not a permanent state.
4. **Cutover procedure** per shop:
   1. Enable `sync_audit_mode = True` on the shop (shop is still `email_only`, email parser is live)
   2. Run for 1-2 weeks; audit log shows per-receipt diffs between email-parsed and API-fetched data
   3. BA lead reviews the audit log. Target: >= 99.5% field match on critical fields (`amount_total`, `line_items`, `shipping_address`)
   4. If threshold met, set `sync_mode = 'api_only'` and `sync_audit_mode = False` atomically
   5. From that moment, email ingestion for this shop stops; API becomes the source of truth
   6. For 30 days post-cutover, the email cron continues polling but **only logs** received emails for this shop (no parsing, no writes) — a safety net to prove nothing was missed. After 30 days, remove the shop from the Gmail filter entirely.
5. **After all shops are flipped**: the email parser code is marked deprecated in Spec 005 phase 3, moved to `etsy_channel_legacy` (uninstallable module, see [ADR-003](ADR-003-module-decomposition.md)), and deleted 12 months later.

## Consequences

### Positive
- **Eliminates race conditions** — each shop has exactly one writer at any time.
- **Forces a clean cutover decision** per shop, backed by real audit data.
- **Removes "dual mode maintenance forever"** risk — the parser has a real retirement timeline.
- **Simplifies Spec 005's order syncer code** — no merge/reconcile logic for conflicting sources.
- **Matches the devil's advocate's minimum mitigation** (synthetic lock column not needed because there's only one writer).

### Negative
- **Cutover is less "gradual"**: the switch is a single moment per shop, not a gradient. Mitigated by the 1-2 week audit period before flipping.
- **Operators must consciously decide** when to flip each shop. Requires process discipline. Mitigated by a one-pager runbook in each shop's record.
- **If an API sync fails catastrophically post-flip**, there's no email fallback to cover orders received during the outage. Mitigated by (a) the 30-day email shadow-logging safety net and (b) the Etsy app's standard retry mechanism.

### Neutral
- Spec 005's `etsy.shop` model still has a `sync_mode` field — just with fewer values.

## Alternatives considered

1. **Keep `dual` with explicit conflict resolution policy** — rejected. Defining a policy that handles all the failure modes above is non-trivial and adds test surface. Net effort to add the policy is greater than the effort of one-shop-at-a-time migration.
2. **Drop `sync_mode` entirely, force immediate global switch** — rejected. Too risky with 19 shops; one bad API integration could take down all ingestion.
3. **`dual` with row locking via `SELECT ... FOR UPDATE`** — rejected. Doesn't solve the dedup-key mismatch problem (email's broken regex would still create shadow records); only solves field stomping.
4. **Background reconcile job that reviews dual conflicts** — rejected. Adds a whole reconciliation subsystem for a temporary problem. YAGNI.

## Implementation notes

- Update `specs/005-etsy-api-channel/spec.md` to remove `dual` from `sync_mode` enum and add the `sync_audit_mode` Boolean field.
- Update `specs/005-etsy-api-channel/data-model.md` to match.
- Update Spec 005 US8 ("Sync mode selection") wording: "Per-shop switch between `email_only` and `api_only` with optional 1-week audit period."
- Update Spec 005's `etsy_order_syncer.py` contract to always be a single writer; no merge logic.
- Add a new Spec 005 user story (or amend US2): "Sync audit mode — API client runs read-only, logs field diffs to `etsy.api.log`, no writes to sale.order."
- The 30-day email shadow-logging safety net is an implementation detail, not a new user story; document it in `plan.md` under cutover procedure.
