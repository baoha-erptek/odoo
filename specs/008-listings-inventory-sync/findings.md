# Findings — Spec 008 (Listings & Inventory Sync)

## P-LIST-SPEC (planning slice) — 2026-05-16

- **ADR number collision (resolved).** MP006 tracker row P-LIST-SPEC and the roadmap plan reference "ADR-012" for the listing-model decision. `specs/006-master-plan/adrs/ADR-012-gdrive-failover.md` already exists. Decision recorded as **ADR-013** instead. Tracker prose is stale only on the number; design intent unchanged. No tracker-row rewrite of historical text — corrected forward in the ADR + this finding.
- **ADR README index is stale (pre-existing, not introduced here).** `specs/006-master-plan/adrs/README.md` index table lists only ADR-001–007, though ADR-008–012 exist on disk. Added the ADR-013 row to keep this slice's deliverable discoverable; did NOT backfill 008–012 (surgical-changes: not this slice's mess). Flagging for a future doc-hygiene pass.
- **Owner open-question resolution.** Architect surfaced 3 open questions; owner answered via Telegram (allowlisted DM `1013317517`) "go with architect recommendations". Recorded in ADR-013 §"Owner-confirmed open questions": (a) unmatched SKU → leave unlinked + flag, no auto-create; (b) listing deactivation deferred; (c) multi-variant vs single product → closest-SKU link only.
- **Pure-doc slice.** No code/tests; Two-Phase Testing N/A for P-LIST-SPEC. Implementation slices (P-LIST-PULL, P-LIST-INV-PULL) carry the testing burden; tasks.md encodes the RED/GREEN/Review/Verify/Land phases.
- **Reused codebase invariant.** `_sql_constraints` is never deployed across this codebase's addons (8+ confirmations, `project_sql_constraints_drift`). data-model.md + tasks.md pre-emptively require UNIQUE constraints to be mirrored in `init()` raw SQL with a `pg_constraint IF NOT EXISTS` pre-check, so the implementation slices do not rediscover this.

## P-LIST-PULL (Slice 1) — 2026-05-16

- **Odoo 19 makes `_sql_constraints` inert.** Module load logs `Model
  attribute '_sql_constraints' is no longer supported, please define
  model.Constraint on the model.` The list no longer creates the DB
  constraint — only the `init()` raw-SQL `pg_constraint IF NOT EXISTS`
  mirror does. This *vindicates* the project's mirror-in-init invariant
  (`project_sql_constraints_drift`): in Odoo 19 it is mandatory, not
  belt-and-braces. C-LIST-001 verified enforced (Phase-1 dup-insert →
  IntegrityError) via the init() mirror alone.
- **Odoo 19 `res.users.groups_id` → `group_ids`.** RED Phase-2 test used
  `groups_id` (Odoo ≤18) → `ValueError: Invalid field 'groups_id'`.
  Fixed to `group_ids`. New gotcha for the odoo19 memory.
- **Slice-vs-spec layering (expected, not drift).** data-model.md §1
  lists variant-derived computed fields (`variant_count`,
  `unlinked_variant_count`, `drift_status`) + `product_ids`. Those need
  `etsy.listing.product` (Slice 2). Slice 1 implements the US1 metadata
  subset only; `quantity` is the plain listing-level integer Etsy
  returns, NOT a sum over children. data-model.md describes the Spec-008
  end-state; P-LIST-PULL is the metadata cut. P-LIST-INV-PULL adds the
  rest. No data-model edit needed.
- **Error-path audit durability — reconsidered, not fresh-cursored.**
  code-reviewer flagged (MEDIUM) error-path audit durability. First
  applied the Defect-05 fresh-cursor+commit pattern, but it (a) hit the
  cross-transaction FK test trap (shop created in the uncommitted test
  txn invisible to the fresh cursor) and (b) is unnecessary here:
  `_cron_sync_listings` **swallows** the per-shop exception (no re-raise
  → no Odoo job-runner rollback), so the same-cursor row persists on the
  cron's normal commit. Defect-05's fresh-cursor durability applied to a
  *controller returning 400 that rolls back* — not a swallowing cron.
  Reverted to same-cursor; test now exercises the production entrypoint
  (`_cron_sync_listings`, swallows) and asserts the error audit row
  persists. Simplicity-first per behavioral-guardrails.
- **Cron XML placement deviation from tasks.md T005.** tasks.md T005
  said new file `data/ir_cron_etsy_listing_sync.xml`; instead appended
  the record to the existing `data/ir_cron_data.xml` (house convention —
  all 6 prior crons live there; avoids a manifest data-list edit;
  matches `noupdate="1"` behavior of sibling crons). Surgical; recorded
  here per the run-to-completion contract.
- code-reviewer: 0 CRITICAL, 1 HIGH (`datetime.utcfromtimestamp`
  deprecation) — fixed with naive-UTC `datetime.fromtimestamp(...,
  tz=utc).replace(tzinfo=None)` (reviewer's tz-aware suggestion would
  break Odoo Datetime writes — Odoo Datetime fields reject tz-aware).
  security-reviewer: APPROVED, 0 CRITICAL/HIGH, 1 LOW (optional ir.rule,
  deferred — non-sensitive metadata). 13 P-LIST-PULL tests + full 512
  `etsy_integration` suite green; `-u etsy_integration` exit 0.

## E2E surfacing (live)

_(none yet — implementation not started)_
