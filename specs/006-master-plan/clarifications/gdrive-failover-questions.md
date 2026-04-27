---
title: "Clarification Pack — GDrive Failover + Discord Sunset (REQ-FIL-04)"
date: "2026-04-26"
audience: "Owner + PD lead (primary), DevOps (consulted)"
purpose: "Collect the answers needed to write ADR-012 (GDrive failover + Discord retirement). E2 §8 decision #18 + DA post-redpen N4."
resolves_blockers:
  - Synthesis H4 (GDrive failover / Discord sunset undocumented)
  - DA post-redpen N4 (Discord fallback + OAuth expiry)
  - E2 §8 decision #18 (Discord fallback duration)
how_to_use: |
  Read the Context section. Answer Q1–Q7 (mark + initials + date).
  Hand to architect to write `../adrs/ADR-012-gdrive-failover.md`.
estimated_session: "30 min Owner + PD (+ 15 min DevOps if available)"
---

# Context (read first)

The file lifecycle requirements (REQ-FIL-01..03) move design files to GDrive as the primary store. SRS v2.1 added **REQ-FIL-04**: *"Discord retained as documented fallback. Sunset date signed by Owner."* — but no sunset date, no failover SLA, and no health-check policy were specified.

Two known operational risks:
1. **GDrive OAuth tokens expire** after 6 months of inactivity (raised in prior DA §4.4 and post-redpen N4). If a service-account token expires unnoticed, file uploads silently stop.
2. **Discord is the current production fallback** (memory note: Discord is doc-as-fallback). It works today but becomes shadow infrastructure once GDrive goes live. How long does it stay alive?

Without answers, Spec 004a cannot write the GDrive client retry logic, the health-check cron, or the Discord sunset migration. Operations cannot estimate the on-call expectation for design-file failures.

---

# Section A — GDrive token health (3 questions)

## Q1. What kind of GDrive credential are we using?

| Option | Credential |
|---|---|
| **A** | Service account (recommended; no user consent needed; tokens don't expire from inactivity) |
| **B** | OAuth user credential (Owner's personal Google account; expires after 6 months idle) |
| **C** | OAuth user credential (a dedicated workspace account, e.g., `etsy-ops@…`) |
| **D** | Don't know yet — to be decided in setup |

**Owner / DevOps answer:** ____________  
**Initials + date:** ____________

> *If A is feasible, Q2 and Q3 become moot.* Most G Suite / Workspace tenants allow service accounts; check first.

---

## Q2. (only if Q1 = B or C) — How often should we proactively refresh the token?

| Option | Cadence |
|---|---|
| **A** | Every 30 days (well within the 6-month idle limit) |
| **B** | Every 90 days |
| **C** | Only when the token is about to expire (lazy refresh) |
| **D** | Cron-based health check pings the API daily; refresh on first 401 |

**Owner / DevOps answer:** ____________  
**Initials + date:** ____________

---

## Q3. What should happen when token refresh fails?

| Option | Behaviour |
|---|---|
| **A** | Alert Owner + DevOps via email + Discord; queue all uploads to retry; do NOT auto-fall-back to Discord |
| **B** | Alert + auto-fall-back to Discord for new uploads until token is restored |
| **C** | Alert + halt design-file uploads; PD acknowledges via UI; file lifecycle is paused per shop until manual unlock |
| **D** | Other — describe |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

---

# Section B — Discord sunset (3 questions)

## Q4. How long does Discord stay as the production fallback after GDrive go-live?

| Option | Duration |
|---|---|
| **A** | **30 days** — short overlap; cutover completes quickly |
| **B** | **90 days** — one quarter of soak; matches typical cutover-monitoring windows |
| **C** | **6 months** — full template-drift cycle observed before sunset |
| **D** | **Permanent** — Discord stays as a manual escape hatch forever (mirrors the email-as-mandatory-backup decision in `../adrs/ADR-008a-email-as-mandatory-backup.md`) |
| **E** | Other — pick a date or trigger condition |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

> *Recommend B or D depending on how often Discord has actually saved the day historically. If it's been used in the last 90 days, choose D — there's no good argument for removing a working fallback.*

---

## Q5. During the overlap period (whatever Q4 chose), should design files be written to BOTH GDrive AND Discord?

| Option | Behaviour |
|---|---|
| **A** | Yes — dual-write for the entire overlap period (matches reconciliation-as-observability pattern from ADR-008a) |
| **B** | No — primary writes to GDrive only; Discord is dormant unless GDrive fails (manual or automated trigger) |
| **C** | Hybrid — dual-write for first 30 days, then GDrive-only with Discord on standby |
| **D** | Other |

**Owner / PD answer:** ____________  
**Initials + date:** ____________

---

## Q6. Who decides when the Discord sunset actually fires (if Q4 ≠ D)?

| Option | Authority |
|---|---|
| **A** | Auto-sunset on the date — calendar-based |
| **B** | Owner signs off manually after the period expires (date-based prompt, not auto) |
| **C** | Sunset only after N consecutive days with zero Discord-fallback activations (event-based) |
| **D** | Other |

**Owner answer:** ____________  
**Initials + date:** ____________

---

# Section C — Operational expectations (1 question)

## Q7. What's the on-call expectation for design-file failures?

| Option | Coverage |
|---|---|
| **A** | Business hours only — failures outside 9–18 wait until next morning; queue grows |
| **B** | Extended hours (9–22 daily) |
| **C** | 24/7 — page Owner / DevOps on any GDrive auth failure |
| **D** | Tiered — auth failures = business hours; complete outage = 24/7 |

**Owner / DevOps answer:** ____________  
**Initials + date:** ____________

> *Drives the alert routing in ADR-012 §3 and the staffing line in the operations runbook.*

---

# What happens after this is answered

1. Architect (or `/sc:design`) writes **ADR-012** with: credential type (Q1), refresh cadence (Q2), failure policy (Q3), Discord sunset window (Q4), dual-write policy (Q5), sunset trigger (Q6), on-call (Q7).
2. SRS v2.2 §10 REQ-FIL-04 expanded with the answers + link to ADR-012. Add new REQ-OPS-* IDs if on-call expectations need formal acceptance criteria.
3. E2 v1.2 §7.8 footnote updated with the sunset window in plain Vietnamese.
4. Spec 004a task list adds:
   - GDrive client with retry + health-check cron (Q1–Q3)
   - Dual-write logic for the overlap (Q5)
   - Sunset trigger code (Q6) — manual flag in admin settings if Q6=B
   - Alert wiring (Q3 + Q7)
5. Operations runbook gets a new "design-file failure" page with the alert routing.

---

# Open questions NOT in this pack (deferred)

- File-size cap enforcement (10 MB per ADR-006) — already decided; not relisted here.
- Backup of the GDrive folder itself (versioning / off-site copy) — separate Phase-2 decision.
- Per-shop GDrive folder vs. shared root — Spec 003 / Spec 004a design decision; doesn't need ADR.
