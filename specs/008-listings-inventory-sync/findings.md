# Findings — Spec 008 (Listings & Inventory Sync)

## P-LIST-SPEC (planning slice) — 2026-05-16

- **ADR number collision (resolved).** MP006 tracker row P-LIST-SPEC and the roadmap plan reference "ADR-012" for the listing-model decision. `specs/006-master-plan/adrs/ADR-012-gdrive-failover.md` already exists. Decision recorded as **ADR-013** instead. Tracker prose is stale only on the number; design intent unchanged. No tracker-row rewrite of historical text — corrected forward in the ADR + this finding.
- **ADR README index is stale (pre-existing, not introduced here).** `specs/006-master-plan/adrs/README.md` index table lists only ADR-001–007, though ADR-008–012 exist on disk. Added the ADR-013 row to keep this slice's deliverable discoverable; did NOT backfill 008–012 (surgical-changes: not this slice's mess). Flagging for a future doc-hygiene pass.
- **Owner open-question resolution.** Architect surfaced 3 open questions; owner answered via Telegram (allowlisted DM `1013317517`) "go with architect recommendations". Recorded in ADR-013 §"Owner-confirmed open questions": (a) unmatched SKU → leave unlinked + flag, no auto-create; (b) listing deactivation deferred; (c) multi-variant vs single product → closest-SKU link only.
- **Pure-doc slice.** No code/tests; Two-Phase Testing N/A for P-LIST-SPEC. Implementation slices (P-LIST-PULL, P-LIST-INV-PULL) carry the testing burden; tasks.md encodes the RED/GREEN/Review/Verify/Land phases.
- **Reused codebase invariant.** `_sql_constraints` is never deployed across this codebase's addons (8+ confirmations, `project_sql_constraints_drift`). data-model.md + tasks.md pre-emptively require UNIQUE constraints to be mirrored in `init()` raw SQL with a `pg_constraint IF NOT EXISTS` pre-check, so the implementation slices do not rediscover this.

## E2E surfacing (live)

_(none yet — implementation not started)_
