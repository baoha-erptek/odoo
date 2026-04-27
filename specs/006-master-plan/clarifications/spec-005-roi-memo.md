---
title: "Spec 005 ROI Memo — Etsy API as Primary Source, Email as Failover Behind a Single Pipeline"
date: "2026-04-26"
revision: "v2 — incorporates Owner clarification on single-pipeline / swappable-source design"
author: "Owner (recorded by synthesis from 2026-04-26 conversation)"
status: ACCEPTED
resolves:
  - SRS REQ-SYN-00 (formerly BLOCKER)
  - Synthesis B1 (Spec 005 ROI memo)
  - Synthesis B3 (<1% email error claim)
  - Devil's Advocate post-redpen N1
  - Devil's Advocate post-redpen C3
amends:
  - ADR-008 §3 (email parser maintenance mode → failover source)
  - ADR-008 §5 (Gmail cron 30-day shadow then disable → permanent failover behind same pipeline)
  - ADR-002 (sync_mode enum superseded by active_source field — see ADR-008a §2)
related_followups:
  - ADR-008a-email-as-mandatory-backup.md (formal amendment to ADR-008; v2 source-switching design)
  - SRS_Multichannel_Hub_EN.md REQ-SYN-00 status update + REQ-SRC-* family (v2.2)
  - SRS_Multichannel_Hub_VN.md mirror update (v2.2)
---

# Decision

**Etsy API v3 is the primary order-ingestion source. Email parsing remains a permanent failover source. Both feed the same single ingestion pipeline — same canonical record, same downstream code, same dashboards. Switching the source for a shop changes nothing else.**

This supersedes the framing in:
- ADR-008 §3 ("Email parser enters maintenance mode" with retirement arc)
- ADR-008 §5 ("After 30 days: remove the shop from the Gmail label filter" / "disable the Gmail cron at module level")

The earlier ADR-008a draft (morning of 2026-04-26) proposed a dual-write reconciliation contract. **That design is withdrawn**; the current ADR-008a documents the simpler single-pipeline / swappable-source design that the Owner clarified later the same day.

# Rationale (the actual ROI)

The original synthesis assumed the case for API was "email is broken today" (a current-error-rate argument) and the devil's advocate correctly identified that the `<1% error` claim was unsubstantiated. **Both sides framed the question incorrectly.**

The real risk profile is **template fragility under uncontrolled external change**:

| Source | Who controls the contract | What happens when contract changes |
|---|---|---|
| **Etsy email parsing** | Etsy unilaterally — they ship HTML template changes with no notice and no versioning | Manual emergency code edit on every regex/selector that breaks. Affected shops have unpredictable downtime until a developer is available. Shop-by-shop fix or batch fix; no test coverage protects against an unknown future template. |
| **Etsy API v3** | A versioned contract Etsy publishes; deprecations announced with lead time | Code change is scheduled, scoped, and testable against a sandbox. Failure modes (rate limit, 5xx, scope revoked) are documented and have idiomatic recovery patterns. |

Today's email error rate is therefore the wrong metric. The correct metrics are:

- **Mean time to detect** an email-template break (currently: when a customer or BA notices a missing order — no upstream alert).
- **Mean time to recover** from an email-template break (currently: hours-to-days; one-developer dependency).
- **Probability of recurrence per N months** (uncontrolled — Etsy ships at their cadence).

API ingestion converts an *uncontrolled, unscheduled, manual-fix* failure mode into a *contractual, versioned, code-reviewable* one. **That is the ROI**, not "API is faster" or "API has fewer errors today."

# Why email stays as failover (not legacy)

Two reasons, plus a critical insight from Owner that simplifies everything:

1. **API can fail too.** Scope revocation, account suspension, regional outage, or Etsy infrastructure incidents leave us with zero ingestion if email is gone. Today the email path is operational and proven; throwing it away would replace one fragility with a different one.
2. **Scope-grant uncertainty.** ADR-008 §4 lists six scopes. If `transactions_r` is denied or revoked, the API path stops working for ingestion. Email is the only other source of order data we have.
3. **Owner's insight (the design simplification):** API and email come from the same upstream — etsy.com. Both produce records about the same orders, with the same identifiers (`etsy_receipt_id`). **They are not two systems to reconcile. They are two adapters to the same upstream.** Build one pipeline, swap the adapter when needed.

The cost of keeping email running is the existing parser code + Gmail cron + a periodic regex update when Etsy changes a template. The cost of removing it is single point of failure on every Etsy shop's order data. **The trade is not close, and the design carries no extra reconciliation complexity** — switching sources changes the *adapter* in front of the pipeline, not the pipeline itself.

# Architecture (single-pipeline / swappable-source)

```
                  ┌──────────────────────┐
                  │  EtsyApiAdapter      │── normalises ──┐
                  │  (uses Etsy API v3)  │                │
                  └──────────────────────┘                │
                                                          ▼
                                              ┌──────────────────────┐    ┌──────────────────┐
                                              │  etsy.order.payload  │ →  │  EtsyOrderIngestor │ → sale.order, dashboards, …
                                              │  (canonical record)  │    │  (source-agnostic) │
                                              └──────────────────────┘
                                                          ▲
                  ┌──────────────────────┐                │
                  │  EtsyEmailAdapter    │── normalises ──┘
                  │  (uses Gmail parser) │
                  └──────────────────────┘

     active_source per shop ─ controls which adapter is invoked. One at a time.
```

Source selection rules (active_source per shop):

| Rule | Behaviour |
|---|---|
| **Default once API scopes are granted** | `active_source='api'` and the adapter has succeeded at least once |
| **Default before scopes are granted** | `active_source='email'` |
| **Auto-failover trigger** | 3 consecutive health-check failures on the active source → switch to the other source. Alert raised. |
| **Recovery probe** | When in failover, an hourly probe checks whether the original primary source recovered. After 6 consecutive successful probes → switch back automatically (unless `auto_recovery=False` for that shop). |
| **Manual override** | Admin can set `active_source` directly and set `auto_recovery=False` to pin the override (used when the failover is intentional pending a known fix). |
| **Field shape** | Both adapters output the same canonical `etsy.order.payload`. Source-specific fields (e.g., API-only `listing_id`) are nullable; downstream UI shows "—" when absent. |

**No dual-write. No reconciliation. No field-authority table.** One source active at a time per shop. Switching sources is invisible to operations, reports, and downstream code — only the upstream adapter changes.

# Operational consequences (simplified)

| Item | ADR-008 said | New direction (ADR-008a v2) |
|---|---|---|
| Gmail cron | Shadow-log for 30 days, then remove shop from filter | **Runs forever as the email-adapter implementation.** Polls only when the shop's `active_source='email'`. |
| Email parser code lifecycle | Move to `etsy_channel_legacy`; uninstallable 12 months after last cutover | **First-class module renamed to `etsy_channel_email` for parity with `etsy_channel_api`.** |
| New parser features | "Rejected by default" | **Allowed when justified by template drift.** New regex / new field extractor / new shop format support are valid maintenance work. |
| Test coverage on parser | Implicitly frozen | **Must be maintained.** Email-parser tests stay in CI. |
| Cutover semantics | One-way flip per shop from `email_only` → `api_only` | **`active_source` field replaces `sync_mode` enum.** Switch is bidirectional and automatic on health failure. |
| Onboarding new shop | API-only from day one (blocked if scopes missing) | **Onboards on whichever source is healthy. If scopes missing, defaults to email; auto-switches to API on first successful probe.** |
| `parser_template_drift` health metric | Temporary cutover safety tile | **Permanent ops dashboard** alongside `active_source_per_shop` and `auto_failover_count_7d`. |

# Source-switching contract (NEW; replaces the rejected reconciliation contract)

These rules belong in Spec 005 and become new SRS REQs `REQ-SRC-01..04`:

| Rule | Default | Configurable? |
|---|---|---|
| **Health-check frequency** on active source | 5 min | Yes, per-shop |
| **Failure threshold** to trigger auto-failover | 3 consecutive failures | Yes, per-shop |
| **Recovery-probe frequency** when in failover | 1 hour | Yes, per-shop |
| **Recovery threshold** to switch back | 6 consecutive successes | Yes, per-shop |
| **Auto-recovery enabled** | True | Yes, per-shop (False pins manual overrides) |
| **Source-specific field policy** | Nullable; downstream renders "—" when missing | Not applicable |

# Impact on existing artifacts

These edits are required (downstream of this memo):

- **ADR-008** — superseded §3 + §5 by `ADR-008a-email-as-mandatory-backup.md` (this is done).
- **ADR-002** — `sync_mode` enum is superseded by `active_source`. Annotate ADR-002 with a pointer to ADR-008a §2.
- **ADR-003** — the planned `etsy_channel_legacy` module name is revised to `etsy_channel_email`.
- **MASTER_PLAN.md §4** — remove "uninstallability arrives 12 months after last shop flipped" language; remove sunset milestones.
- **SRS_Multichannel_Hub_EN.md §3** — REQ-SYN-00 changes from `BLOCKER` to `RESOLVED`; add new requirement family `REQ-SRC-01..04` for source-switching rules.
- **SRS_Multichannel_Hub_VN.md** — mirror.
- **E2_Quy_trinh_san_xuat.md §2.1 #2** — remove "<1% lỗi"; replace with template-drift framing + "đường ống không đổi khi đổi nguồn."
- **Spec 005 plan + tasks** — drop reconciliation tasks; add adapter-interface tasks + health-check cron + recovery-probe cron + source-change log.

# Open questions still pending Owner answer (operational only — not blocking Phase 0)

This memo resolves the *direction*. Three operational details remain:

1. **Health-check failure threshold** — proposed 3 consecutive failures. Confirm or adjust.
2. **Recovery-probe success threshold** — proposed 6 consecutive successes (~6 hours of healthy probes before auto-switching back). Confirm or adjust.
3. **Backup-maintenance budget** — what's the standing capacity allocated to email-parser fixes per quarter? Used to size on-call expectation for template-drift incidents.

These are NOT blockers for Phase 0 — Spec 005 sandbox work can start while the operational details are being finalized.

# Status

- **REQ-SYN-00** → **RESOLVED** (replaces BLOCKER status)
- **Synthesis B1** → **CLOSED** (this memo + ADR-008a v2 are the deliverables)
- **Synthesis B3** → **DISSOLVED** (the question was malformed; <1% historic error rate is not the relevant metric)
- **DA post-redpen N1** → **CLOSED** with a different answer than the DA proposed
- **DA post-redpen C3** → **WITHDRAWN** (the unsubstantiated claim is no longer load-bearing)

---

*Recorded 2026-04-26. Author: Owner (recorded via synthesis conversation, refined same-day on architecture). Acknowledge by sign-off in `decision-log.md` D-13.*
