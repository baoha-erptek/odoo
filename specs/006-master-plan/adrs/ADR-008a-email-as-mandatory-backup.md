# ADR-008a: Email Parser as Failover Source Behind a Single Ingestion Pipeline (amends ADR-008)

- **Status**: Accepted
- **Date**: 2026-04-26
- **Sign-off**: 2026-04-26 (owner; recorded via Stage-1 synthesis)
- **Deciders**: Owner, architect (synthesis), BA lead
- **Affects**: ADR-008 §3 and §5 (superseded), ADR-002 sync_mode default, ADR-003 module naming, MASTER_PLAN §4 retirement language, SRS REQ-SYN-00 (resolved)
- **Related**: [ADR-002](ADR-002-drop-dual-sync-mode.md), [ADR-003](ADR-003-module-decomposition.md), [ADR-008](ADR-008-api-first-pivot.md), [`../clarifications/spec-005-roi-memo.md`](../clarifications/spec-005-roi-memo.md)

## Context

ADR-008 (2026-04-13) declared the Etsy API v3 the primary ingestion path and put the email parser into "maintenance mode" with an explicit retirement arc:

- §3: "No new features on the email parser… The parser code moves to `etsy_channel_legacy`… Uninstallability arrives 12 months after the last shop is flipped."
- §5: "Post-cutover, per-shop: Gmail cron still polls for 30 days but writes only to `etsy.api.log`… After 30 days: remove the shop from the Gmail label filter… After all 19 shops are flipped and 30-day shadow periods elapse: disable the Gmail cron at module level."

The 2026-04-26 master-plan red-pen review and devil's advocate post-redpen surfaced two related concerns:

- **N1 (DA)**: API business case unjustified if email is "<1% error" today.
- **C3 (DA)**: The "<1% error" claim has no evidence.

The Owner's clarification — captured in [`../clarifications/spec-005-roi-memo.md`](../clarifications/spec-005-roi-memo.md) — reframed both, then refined the architecture further:

> The case for API is not "email is broken today." It is "email parsing has uncontrolled external dependency on Etsy's HTML email template — every Etsy template change forces emergency manual code updates with no notice and no versioning. API gives us a versioned contract." Therefore email must remain available as a backup source.
>
> **API and email come from the same upstream (etsy.com) and produce the same data. Build one ingestion pipeline; switch the source adapter when needed. The pipeline, columns, and downstream code are unchanged whether the active adapter is API or email.**

This ADR formalises the direction. It supersedes ADR-008 §3 and §5.

## Decision

### 1. One ingestion pipeline, swappable upstream source adapter

Both upstream sources (`EtsyApiAdapter`, `EtsyEmailAdapter`) implement the same interface and produce the same canonical record (proposed: `etsy.order.payload`). Downstream code (`OrderCreator`, `sale.order` writes, dashboards, reporting) is **source-agnostic** — it never branches on which adapter produced the payload.

Concretely:

- A single ingestion service (`EtsyOrderIngestor`) reads from whichever adapter is active for the shop and writes to `sale.order` via the existing path.
- Adapters are responsible for **normalising** their source-specific quirks into the canonical payload. New fields the API exposes that the email cannot (e.g., `listing_id`, real currency, receipt-level timestamps) are filled in by `EtsyApiAdapter` when present and left null by `EtsyEmailAdapter`.
- The pipeline never "merges" two records for the same receipt. Only one source is active per shop at a time.

### 2. Active source per shop, automatic failover

`etsy.shop` carries `active_source` (`api` | `email`) and `active_source_changed_at`. The current configuration is:

| State | When |
|---|---|
| `active_source='api'` | Default once Etsy scopes are granted for the shop and the API adapter has succeeded at least once |
| `active_source='email'` | Default before scopes are granted; auto-set on adapter health failure (see §3); manual fallback via admin |

The `sync_mode` enum from ADR-002 (`email_only` / `api_only` / `dual`) is **superseded** by `active_source` for new logic. Existing data using the old enum maps as: `email_only` → `active_source='email'`, `api_only` → `active_source='api'`. The `dual` value becomes unused and is removed at the next module migration.

### 3. Health-check-driven automatic failover

A health-check cron (frequency: 5 min) probes the active adapter:

- **API**: small read against `/v3/application/openapi-ping` or equivalent.
- **Email**: Gmail label query; cron is healthy if it has received ≥1 message in the last N hours (configurable per shop, default 24h) OR if the last poll executed without exception.

On **3 consecutive failures** of the active source, the shop auto-switches to the other source. An alert is raised (severity HIGH). The switch is logged in `etsy.shop.source.change.log` (who/when/from→to/reason="auto-failover"|"manual"|"recovery-probe"). PD/BA does not need to do anything — orders keep flowing through the same pipeline.

A separate **recovery probe** (frequency: hourly when in failover) checks whether the original primary source has recovered. After **6 consecutive successful probes**, an automatic switch back happens unless the shop has `auto_recovery=False` set (used when the failover was triggered by a known event the team is still resolving, e.g., scope revocation pending Etsy support).

### 4. Email parser stays operational forever

- The email parser is **not legacy code** and is not scheduled for retirement. It is the failover source for every shop indefinitely.
- New parser features that are justified by template drift (new regex, new field extractor, new shop-specific format support) are valid maintenance work, not feature creep.
- Test coverage on the email parser cannot be reduced. Email-parser unit and integration tests stay in CI.

### 5. Module renaming

- ADR-003's planned `etsy_channel_legacy` module name is **rejected**. Recommend `etsy_channel_email` to reflect peer status with `etsy_channel_api`.
- This is a documentation change to ADR-003; the technical decomposition (separate module per channel) is unchanged.
- Migration script for the rename should be added to ADR-003's implementation notes.

### 6. Health metric becomes permanent ops infrastructure

- The `parser_template_drift` tile that ADR-008 §6 planted as a temporary cutover safety measure becomes a **permanent ops dashboard** in Spec 002 / Spec 006.
- New permanent tiles fed by the source-change log and health-check cron:
  - `active_source_per_shop` (current state)
  - `auto_failover_count_7d` (alerts on spike)
  - `time_since_last_recovery_probe_success` (catches both API and email going dark)
- Alerts trigger maintenance work (parser fix, scope re-application, etc.) — not cutover acceleration.

### 7. Etsy scope-grant uncertainty handling

- ADR-008 §4's contingency ("if `transactions_w` denied → tracking push blocked, but ingestion still works with `transactions_r`") still holds.
- New: **if `transactions_r` is denied or revoked** for a shop, the shop's `active_source` flips to `email` and `auto_recovery` is set to `False`. Backup keeps shipping orders while the team escalates with Etsy.

## Consequences

### Positive

- **No single point of failure on order ingestion** for the lifetime of the integration. API outages, scope revocations, and account suspensions all have a working fallback.
- **Pipeline / column / report code is unchanged when the source switches.** Operations doesn't need to learn two systems; reports don't need source-conditional logic.
- **Drastically simpler than dual-write reconciliation.** No match window, no field-authority table, no late-arrival upgrade rules. One source active at a time.
- **Owner-controlled manual recovery path** — if API contract changes break us in production, manual `active_source='email'` keeps orders flowing while we patch.
- **Resolves REQ-SYN-00, B1, B3, DA-N1, DA-C3** in one decision.

### Negative

- **Permanent maintenance cost on the email parser**. We carry the regex/template debt forever — but the cost is now budgeted and visible (see §6 health metrics) instead of being pretended away.
- **Auto-failover semantics need careful test coverage.** False-positive failover (e.g., Etsy returns transient 5xx that the cron misreads as outage) flips the shop unnecessarily. Mitigation: 3-consecutive-failure threshold + 6-consecutive-success recovery threshold + manual override.
- **Source-specific fields** (e.g., API-only `listing_id`) are missing from records ingested while in email-failover. Mitigation: nullable fields; downstream UI shows "—" when missing; reports degrade gracefully.
- **Adapter-interface discipline** must hold. Any change to the canonical payload must land in both adapters at the same time, or one source breaks silently.

### Neutral

- ADR-002's per-shop cutover procedure description is partially obsoleted by §2 (the `active_source` field replaces the `sync_mode` enum), but the migration mechanics ADR-002 §4 described are unchanged in spirit.
- ADR-003's decomposition principle is unchanged — the only edit is the module-name rename.
- ADR-008's §1 (API is primary), §2 (Spec 005 priority + Phase 0/1 split), §4 (scope review on critical path), §6 roadmap moves, and §7 (Amazon/Website timing) all remain in force.
- Spec 002's historical-orders cleanup is unaffected.
- Scope-review submission urgency is unaffected — it's still on the critical path; the only change is what happens after scopes arrive (and what happens if they don't).

## Alternatives considered

1. **Edit ADR-008 in place** — rejected. ADR convention here is immutable Accepted decisions. Amendments live as new ADRs that supersede specific clauses.
2. **Dual-write reconciliation contract** (the original 2026-04-26 morning version of this ADR, with match window, late-arrival upgrade/ignore, field authority on conflict, drift SLA) — rejected by Owner same day. The dual-write design solved a problem that does not exist: API and email are the same upstream, so running both in parallel for "drift detection" produces no signal that a single-source failover-with-recovery-probe doesn't already produce. Dual-write also added permanent code complexity (dedup logic, conflict resolution, field authority overrides) that the simpler design avoids.
3. **Sunset email after a longer window (24 months instead of 12)** — rejected. The argument for sunset was "API is enough"; the rebuttal is "API has the same uncontrolled-external-change risk as email but in a different shape (scope revocation, account suspension, contract breaks)." A longer window doesn't address that.
4. **Email backup but only behind a feature flag (off by default)** — rejected. A backup that is off by default is not a backup.

## Implementation notes

Immediate file edits (separate from this ADR — captured here so they aren't lost):

- `MASTER_PLAN.md` §4 — strip retirement language; mark single-pipeline source-switching as the steady-state model.
- `SRS_Multichannel_Hub_EN.md` §3 REQ-SYN-00 — flip to RESOLVED, link this ADR + the ROI memo.
- `SRS_Multichannel_Hub_EN.md` — add new `REQ-SRC-01..04` covering: canonical payload contract, active-source field, health-check + auto-failover, recovery probe.
- `SRS_Multichannel_Hub_VN.md` — mirror.
- `E2_Quy_trinh_san_xuat.md` §2.1 #2 — remove "<1% lỗi"; replace with the template-drift framing + "đường ống không đổi khi đổi nguồn."
- `specs/005-etsy-api-channel/plan.md` — drop reconciliation tasks; add adapter-interface tasks + health-check cron + recovery-probe cron + source-change log.
- `specs/005-etsy-api-channel/tasks.md` — regenerate via `/speckit-tasks` after the plan update lands.
- `specs/006-master-plan/adrs/ADR-002-drop-dual-sync-mode.md` — annotate that ADR-008a §2 supersedes the `sync_mode` enum (replaced by `active_source`).
- `specs/006-master-plan/adrs/ADR-003-module-decomposition.md` — annotate that `etsy_channel_legacy` is renamed to `etsy_channel_email`.
- Health dashboard (Spec 002 / 006) — add `active_source_per_shop`, `auto_failover_count_7d`, `time_since_last_recovery_probe_success`, `parser_template_drift` as permanent tiles.

Operational follow-through:

- Define the on-call rotation expectation for source-failover incidents (Owner + Tech Lead).
- Capacity-check the Gmail cron for permanent multi-shop operation alongside API.
- Document the manual override workflow (admin sets `active_source` directly + sets `auto_recovery=False` for sticky overrides).

## Revision history

- **2026-04-26 (morning)**: Initial authoring with dual-write reconciliation contract (§5 had match window, late-arrival upgrade/ignore, field authority on conflict, drift SLA).
- **2026-04-26 (afternoon)**: Owner clarification — API and email are the same upstream and produce the same data; build one pipeline with a swappable adapter; no dual-write, no reconciliation. §3 reworded ("swappable source" instead of "peer ingestion path"). §5 replaced (source-switching contract instead of reconciliation contract). §2 added (active_source supersedes sync_mode). New §3 (health-check-driven failover + recovery probe). Alternative #2 added documenting the rejected dual-write design. **This is the version of record.**
