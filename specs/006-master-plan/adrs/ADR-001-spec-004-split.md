# ADR-001: Split Spec 004 into 004a / 004b / 004c

- **Status**: Proposed (awaiting owner sign-off)
- **Date**: 2026-04-10
- **Deciders**: Owner, architect, BA lead
- **Supersedes**: Spec 004 monolithic structure (79 tasks)
- **Related**: [MASTER_PLAN.md §4](../MASTER_PLAN.md), [devils-advocate.md §3.3](../agent-reports/devils-advocate.md)

## Context

Spec 004 ("Fulfillment routing, production assignment, partner integration") currently contains **79 tasks** covering four unrelated-but-intertwined concerns:

1. **Tracking import** from GKE Logistics Excel (+ carrier auto-detection for USPS/UniUni/YunExpress)
2. **External partner fulfillment** via Gearment v3 API (OAuth, rate limiting, HMAC webhooks, draft->quote->confirm state machine)
3. **Internal production queue** + return/refund workflow
4. **Google Drive sync** for tracking/design files

All three agent-review lenses flagged this as too large:

- **BA consultant**: "Restructure around business value — tracking import is the daily pain point and should ship first; Gearment is a Phase 4 investment"
- **Technical architect**: "Gearment adapter alone is ~5 weeks of work (auth + HMAC + state machine + rate limiter + webhook + error recovery + sandbox tests + production hardening). Bundling it with Excel import forces sequential delivery."
- **Devil's advocate**: "79 tasks in one spec is a project, not a release. Every week one of the three integrations will block the others. Never ships."

**Key observation**: The three integrations have different external-dependency risk profiles:

- **Tracking import**: Only external dependency is GKE Excel format stability (mitigatable via schema fingerprinting). Low risk, high daily value.
- **Gearment v3**: Unverified — nobody has confirmed sandbox exists, HMAC format, rate-limit scope, or state-machine idempotency. High risk, needs a spike.
- **Returns/refunds**: Mostly internal workflow; only light Gearment/Etsy touchpoints. Medium risk.

Bundling them means the whole spec stalls whenever one is blocked.

## Decision

Split Spec 004 into three separate specs that can be delivered independently:

### Spec 004a: Tracking Import + Carrier Detection (Phase 2, MVP)

**Scope**:
- `tracking.import.log`, `tracking.import.line` models
- `tracking_importer.py` service (parses GKE Excel)
- `carrier_detector.py` service (regex/prefix match for USPS, UniUni, YunExpress)
- `shipping.carrier` model (unified — see [ADR-005](ADR-005-carrier-unification.md))
- Tracking import wizard with schema fingerprinting (hard-fail on unknown column layout)
- Process Dashboard (unified VN+US production view) — BA request #14
- Tracking fields on `sale.order` (or on `sale.order.fulfillment` delegation mixin — see [ADR-007](ADR-007-fulfillment-delegation-mixin.md))

**Dependencies**: Phase 0 (Spec 002 complete, observability in place), Phase 1 (Spec 003 dashboards + delegation mixin)

**Out of scope for 004a**: Any partner API work, returns/refunds, Google Drive.

### Spec 004b: Gearment Partner Adapter (Phase 4, post-MVP)

**Scope**:
- `fulfillment.partner` model
- `partner.sync.log` model
- `partner_sync.py` base adapter (Protocol) + `gearment_adapter.py`
- Gearment OAuth/auth flow, HMAC webhook controller
- Draft -> quote -> confirm state machine with idempotency and recovery for intermediate failures
- Rate limiter utility (shared — see Phase 1 extract)
- Webhook handler with idempotency key deduplication

**Dependencies**: Phase 0 Gearment sandbox spike (3-day POC verifying auth, rate limits, HMAC, draft/quote/confirm semantics) **must pass** before any 004b task starts.

**Prerequisite spike tasks** (Phase 0, not part of 004b count):
- Obtain Gearment sandbox credentials
- Hit `/auth`, `/orders/draft`, `/orders/quote`, `/orders/confirm`, `/orders/cancel` with a real test order
- Document rate-limit scope (per-key vs per-IP), HMAC format (algorithm, header, signed fields), webhook retry policy (count, backoff, ordering), quote TTL, cancel semantics
- Decision gate: if any of these are "TBD", 004b is frozen until documented.

### Spec 004c: Returns, Refunds, Order Tickets (Phase 4)

**Scope**:
- `order.return` model
- `etsy.order.ticket` model (minimal custom replace/refund ticketing — see [ADR-004](ADR-004-enterprise-alternatives.md); replaces the implicit "use helpdesk" assumption)
- BA approval workflow (mail.activity-based)
- Return wizard (`return_wizard.py`)
- Refund accounting touchpoints (minimal, just state machine — accounting entries are out of scope)

**Dependencies**: Spec 003 (chatter + activity infrastructure), Spec 004a (tracking fields exist)

**Out of scope for 004c**: Google Drive sync (permanently deferred — master plan §3), chargebacks, customer service messaging.

## Consequences

### Positive
- **004a ships fast**: Tracking import is the highest-value-per-effort work on the roadmap. With Spec 003 delegation mixin in place, 004a is a clean incremental delivery. Closes BA's biggest daily pain.
- **004b is honestly scoped**: Forces the Gearment sandbox spike to land before committing calendar time, protecting against a 3-week rabbit hole.
- **Parallel-ready**: Once 004a ships, 004b and 004c can run in parallel with two devs.
- **Clearer review checkpoints**: Each sub-spec has its own exit criteria and doesn't block the others.
- **Better estimates**: Each sub-spec gets its own task breakdown; no more "79 tasks" hand-wave.

### Negative
- **Three sets of spec-kit artifacts** to maintain (spec.md, plan.md, research.md, data-model.md, tasks.md × 3). More overhead.
- **Some shared plumbing** (rate limiter, webhook base, shipping.carrier model) must be authored in 004a or extracted to the core module before 004b lands — adds a coordination point.
- **Renaming/renumbering existing spec 004** may confuse contributors who already referenced "004" in commits or branches. Mitigate with a clear pointer in `specs/004-fulfillment-routing/README.md` redirecting to the three new specs.

### Neutral
- Total scope does not decrease — the work still exists. This is a sequencing and delivery decision, not a scope cut.

## Alternatives considered

1. **Keep monolithic 004** — rejected. DA's argument is compelling: the spec will stall repeatedly because of cross-integration blockers, and the 79-task estimate is a guess because the internal dependencies aren't modeled.
2. **Split into two specs (Gearment + everything else)** — rejected. Bundles tracking import with returns/refunds, which have completely different delivery timelines and user value. Tracking import is MVP; returns are Phase 4.
3. **Split by model rather than concern** — rejected. Produces awkward boundaries (e.g. "partner.sync.log" belongs with its consumer).

## Implementation notes

- Rename the existing `specs/004-fulfillment-routing/` directory or leave it in place as a historical record, and create `specs/004a-tracking-import/`, `specs/004b-gearment-partner/`, `specs/004c-returns-refunds/`. Prefer the latter (non-destructive) for git history clarity.
- Each new sub-spec should cite this ADR in its spec.md preamble.
- The shared `fulfillment.partner` adapter base Protocol and rate limiter utility should land in `multichannel_hub_core` per [ADR-003](ADR-003-module-decomposition.md) before 004b starts coding.
