# ADR-012: GDrive Failover & Discord as Permanent Manual Escape Hatch

- **Status**: Accepted
- **Date**: 2026-04-26
- **Sign-off**: 2026-04-26 (owner; recorded via Stage-1 synthesis — Owner accepted recommended defaults)
- **Deciders**: Owner, architect (synthesis), PD lead, DevOps (consulted)
- **Affects**: Spec 004a (file lifecycle implementation), Spec 002 / 006 (health dashboard), SRS REQ-FIL-04 (gets concrete content)
- **Related**: [ADR-006-design-file-storage.md](ADR-006-design-file-storage.md), [`../clarifications/gdrive-failover-questions.md`](../clarifications/gdrive-failover-questions.md), [`ADR-008a-email-as-mandatory-backup.md`](ADR-008a-email-as-mandatory-backup.md) (mirrors the "permanent backup" pattern)

## Context

ADR-006 made GDrive the primary store for design files (10 MB cap on `ir.attachment`, GDrive URLs stored on `sale.order` / `design.file`). SRS v2.1 §10 added **REQ-FIL-04**: *"Discord retained as documented fallback. Sunset date signed by Owner."* — but no sunset date, no failover SLA, and no health-check policy.

Two known operational risks:

1. **GDrive OAuth tokens expire** after 6 months of inactivity (raised in prior DA §4.4 and post-redpen N4). If a service-account token expires unnoticed, file uploads silently stop.
2. **Discord is the current production fallback**. It works today but becomes shadow infrastructure once GDrive goes live. Sunset window was never specified.

The Owner accepted the recommended defaults from [`../clarifications/gdrive-failover-questions.md`](../clarifications/gdrive-failover-questions.md) on 2026-04-26 with a note: *"go with your recommendation."* This ADR formalises those defaults.

## Decision

### 1. Use a Google Workspace service account (no OAuth user credential)

- Service account credentials do not expire from inactivity. There is no 6-month idle clock.
- Service account is provisioned in the Owner's Google Workspace tenant with `Drive File` scope (least privilege).
- The service-account JSON key lives in the Odoo server filesystem, mounted via secrets manager (NOT committed to git, NOT in `ir.config_parameter`).
- **If the Workspace tenant does not allow service accounts**, fall back to a dedicated workspace user account (e.g., `etsy-ops@<tenant>`) and apply the proactive-refresh policy in §2 below.

### 2. Token-refresh policy (only relevant if the workspace blocks service accounts)

- Proactive refresh every **30 days** via cron (well within the 6-month idle limit).
- Lazy refresh on first 401 from the API.
- Cron failure is alerted (see §3).

If §1 succeeds (service account provisioned), §2 is moot.

### 3. Failure policy on the GDrive client

When the GDrive client raises an unrecoverable error (auth fails, quota exceeded, service unavailable):

| Action | Behaviour |
|---|---|
| **Alert** | Owner + DevOps via email + Discord channel (severity HIGH) |
| **Queue** | Pending uploads stay in a `design.file.upload.queue` table; cron retries with exponential backoff (1m, 5m, 15m, 1h, 4h capped) |
| **Do NOT auto-fall-back to Discord** | Discord stays as a manual escape hatch; PD/admin operates it consciously, not as silent automation |
| **UI surface** | Pending-uploads count appears as a banner on the Order Dashboard for affected shops; clicking the banner opens the queue list |

**Why no auto-fallback to Discord**: GDrive failures are typically auth/quota/configuration issues that have a clear recovery path (refresh token, raise quota, etc.). Auto-failing-over to Discord risks creating split-source content (some files in GDrive, some in Discord) which is harder to recover from than a temporary upload queue. Manual escape hatch is the safer pattern.

### 4. Discord as permanent manual escape hatch (no sunset)

- Discord stays available **indefinitely** as a manual workflow.
- This mirrors the email-as-permanent-failover pattern from [`ADR-008a`](ADR-008a-email-as-mandatory-backup.md). The reasoning is the same: a working fallback is too valuable to delete on a calendar.
- "Permanent" means: no sunset date, no sunset trigger, no countdown. If the team ever decides Discord is no longer needed, that decision lives in a future ADR with its own context.
- **No dual-write.** GDrive is the primary; Discord is dormant unless PD/admin manually copies a file there during a GDrive incident.
- The `design.file` model has an optional `discord_url` field for files that were placed there during incidents; primary `gdrive_url` is empty in those cases. When the GDrive incident is resolved, the team can backfill (manual UI action: "promote Discord file to GDrive").

### 5. On-call expectation (tiered)

| Failure tier | Definition | Response |
|---|---|---|
| **Auth failure** (single shop, single client) | One token refresh failed; queue is small | Business-hours response (next morning if after-hours) |
| **Quota / rate limit** | API returns 429 / 403 quota-exceeded; affects multiple shops | Business-hours response; auto-retry with backoff in the meantime |
| **Complete outage** | All GDrive calls failing for >10 min; multiple shops affected; queue growing | 24/7 page to Owner + DevOps |

Alerts are routed accordingly. The Order Dashboard banner from §3 stays visible until cleared.

### 6. Permanent ops dashboard tiles

These tiles join the dashboard alongside the source-switching tiles from ADR-008a §6:

- `gdrive_pending_uploads_count` (per shop)
- `gdrive_oldest_pending_age` (alert if >1h)
- `gdrive_token_age_days` (informational; relevant only if §2 applies)
- `discord_manual_uploads_7d` (catches when the team is using Discord — high count = signal that GDrive is unhealthy or PD is bypassing automation)

## Consequences

### Positive

- **No silent upload failures.** Token-expiry detection is structural (service account) or proactive (30-day cron), not "wait for someone to notice."
- **Permanent escape hatch** that the team knows exists and can reach for in a crisis without negotiating with code.
- **Clean separation of failure modes**: GDrive issues are visible (alerts + dashboard banner + queue); Discord is conscious (manual action). No silent split-source content drift.
- **Mirrors the email-as-failover pattern** — the team only has to learn one operational philosophy ("primary + permanent failover, switch consciously, no auto-blending").
- **Resolves H4, DA-N4, E2 §8 decision #18 (D-19), and most of D-22** in one ADR.

### Negative

- **Discord stays as ungoverned content store** in the long term. Files dropped there during incidents can become orphans if no one promotes them. Mitigation: §6 dashboard tile `discord_manual_uploads_7d` plus a periodic reconciliation report (monthly).
- **Manual recovery work after a GDrive incident** — the team has to backfill files into GDrive via the "promote" action. This is acceptable because incidents are rare; if they become frequent, the alerting and `discord_manual_uploads_7d` tile will signal an escalation.
- **Workspace tenant dependency**. If the tenant administrator changes service-account policy, §1 falls back to §2 — that's a tenant-level risk we accept.

### Neutral

- ADR-006's 10 MB `ir.attachment` cap is unchanged.
- File-routing models (`design.file`, `design.file.route`) from REQ-FIL-01..03 are unchanged — they just point at GDrive URLs as before.
- The `design.print.batch` wizard is unaffected.

## Alternatives considered

1. **Auto-failover to Discord** — rejected (see §3 reasoning). Risk of silent split-source content + harder incident recovery.
2. **Discord sunset after 90 days** — rejected. The same template-fragility / API-can-fail-too argument that kept email permanent applies to GDrive too. A working escape hatch is too valuable to schedule for deletion.
3. **Dual-write to GDrive + Discord during overlap** — rejected. Overlap window was a pre-decision artefact; under §4 Discord is permanent so there is no overlap, just primary + manual fallback.
4. **OAuth user credential as primary (instead of service account)** — rejected unless the tenant blocks §1. User credentials carry the 6-month idle clock and tie operational stability to one human's account lifecycle.

## Implementation notes

Spec 004a tasks (added to its `tasks.md` after this ADR):

- Implement GDrive client with service-account auth (priority 1) — `services/gdrive_client.py`
- Implement upload queue (`design.file.upload.queue`) with exponential-backoff retry cron — frequency 1 min when queue non-empty
- Wire alerts to email + Discord channel; severity HIGH
- Add Order Dashboard banner widget for pending-uploads count
- Add the four dashboard tiles from §6 to Spec 002 / 006 health module
- Implement "promote Discord file to GDrive" action on `design.file` form view
- Document operations runbook page: "GDrive incident — what to check, how to use Discord, how to backfill"
- (If §1 fails) Implement 30-day token-refresh cron + cron-failure alert

Operational follow-through:

- Owner / DevOps to provision the service account this week
- Define on-call rotation per §5 (tiered)
- Add `gdrive_oldest_pending_age` to the weekly review cadence ADR-008 already established

## Revision history

- **2026-04-26**: Initial authoring. Accepted same day with Owner-recommended defaults from clarification pack v1.
