# Architecture Decision Records (ADRs)

ADRs for the multichannel e-commerce hub. Each ADR captures a single significant architectural decision with context, alternatives considered, and consequences.

## Status key

- **Proposed** — drafted, awaiting owner sign-off
- **Accepted** — approved, implementation underway or pending
- **Superseded** — replaced by a later ADR (see the "Superseded by" link)
- **Deprecated** — no longer relevant

## Index

| # | Title | Status | Affects |
|---|---|---|---|
| [001](ADR-001-spec-004-split.md) | Split Spec 004 into 004a / 004b / 004c | Proposed | Spec 004 |
| [002](ADR-002-drop-dual-sync-mode.md) | Drop dual-mode sync; keep only `email_only` / `api_only` | Proposed | Spec 005 |
| [003](ADR-003-module-decomposition.md) | Decompose `etsy_integration` into four modules | Proposed | Specs 002–005 |
| [004](ADR-004-enterprise-alternatives.md) | Enterprise alternatives — custom minimal implementations | Proposed | Specs 003, 004c |
| [005](ADR-005-carrier-unification.md) | Unified carrier model via `shipping.carrier` | Proposed | Specs 003, 004a, 005 |
| [006](ADR-006-design-file-storage.md) | Design file storage — filestore/URL only, 10 MB cap | Proposed | Specs 003, 004 |
| [007](ADR-007-fulfillment-delegation-mixin.md) | `sale.order.fulfillment` delegation mixin | Proposed | Specs 003, 004 |
| [013](ADR-013-etsy-listing-architecture.md) | Etsy listing model architecture & product mapping | Accepted | Spec 008 |

> Note: ADR-008–012 exist on disk but were never added to this index (pre-existing doc drift, flagged in `specs/008-listings-inventory-sync/findings.md`). ADR-013 added here so Spec 008's load-bearing decision is discoverable.

## How to use

- When starting work on a spec, read the ADRs that affect it (see "Affects" column).
- When changing an architectural decision, **do not edit the ADR** — supersede it by creating a new ADR and marking the old one "Superseded by ADR-NNN".
- When a decision is accepted by the owner, update the status field and add an "Accepted on" date.
- Reference ADRs from spec `plan.md` files when the decision is load-bearing for that spec's implementation.

## Related

- [../MASTER_PLAN.md](../MASTER_PLAN.md) — the master plan that spawned these ADRs
- [../agent-reports/](../agent-reports/) — the three-agent review that surfaced most of these decisions
