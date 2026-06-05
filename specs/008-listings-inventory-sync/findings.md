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

## P-LIST-INV-PULL (Slice 2) — 2026-05-16

- **Spec-drift: ADR-013 §2 `(company_id, default_code)` SKU-match domain
  is unbuildable.** `etsy.shop` has NO `company_id` field (grep clean);
  the planner asserted "standard Odoo" without verifying the shop side.
  Resolved (owner out, non-destructive, run-to-completion): match by
  `default_code` alone, deterministic first-by-id on duplicates with
  the R-L1 warn-log. Single-company deployment (no multi-company
  anywhere). ADR-013 §2's tuple is the architect's assumption, not
  reality — documented in the model docstring + this finding. Not a
  STOP (no data-destroying ambiguity).
- **Spec-drift: `models/product_product.py` had NO `product.product`
  class** — only `ProductTemplate (_inherit='product.template')`
  despite the filename. Added a new `ProductProduct
  (_inherit='product.product')` class for the `etsy_listing_variant_id`
  FK. Planner's "add to existing ProductProduct class" was wrong (no
  such class existed).
- **Odoo 19 search-view RNG gotchas (2 new):** (1) a non-stored
  computed field (`qty_drift`) CANNOT appear in a `<filter>` domain —
  `ValidationError: Unsearchable field`; removed that filter (the
  drift *reporter service* is the real drift query path, list
  decoration still works on read). (2) `<group expand="0">` is invalid
  in an Odoo 19 `<search>` view RNG (`RELAXNG_ERR_INVALIDATTR` +
  `Element search has extra content: field`); group-by must be a flat
  `<filter context="{'group_by': ...}">`, not wrapped in `<group>`.
  Both → memory.
- code-reviewer: 0 CRITICAL / 0 HIGH; 2 MEDIUM N+1 (per-variant SKU
  search; orphan full-scan) — accepted within the ADR-013 ~5k-variant
  bound, deferred per plan.md R-L2 (docstring note added).
  security-reviewer: 0 CRITICAL; 1 self-downgraded "HIGH"→clarity
  (mark `_sql_constraints` inert — applied). 3 cheap reviewer fixes
  applied (inert comment, concrete audit endpoint, orphan-scan
  docstring); N+1 refactor deferred (not scope creep). 18 slice tests
  + full 530 `etsy_integration` suite green; `-u` exit 0.
- Cron appended to existing `ir_cron_data.xml` (house convention,
  consistent with P-LIST-PULL).

## E2E surfacing (live)

_(none yet — implementation not started)_

---

## P-BUG-ESTY-188 — createListing 400 readiness_state_id bootstrap (2026-06-05)

**Source**: Jira ESTY-188 sub-step 6.11b ("Lỗi Bug ko publish listing lên
Etsy được"); owner reproduced on staging JaHandmadeArt 2026-06-03.

**Root cause confirmed**: Planner hypothesis #1 (out of 3 candidates) was
correct. The staging shop JaHandmadeArt (`etsy_api_shop_id=60752333`) had
NULL `default_readiness_state_id` because the field was added in
`19.0.2.15.0` but never bootstrapped on shops created before that release.
`etsy_listing_publisher.py:237-238` includes the key only when truthy, so
the createListing payload omitted it → Etsy 400 "A readiness_state_id is
required for physical listings". Personalization regression (candidate #2)
and new-2026-mandatory-field (candidate #3) were not the cause.

**Fix shape** (commit `297fc717b04`, manifest 19.0.2.33.0):

- New `migrations/_19_0_2_33_0/` Python package with `post_migrate(cr, env)`
  function callable directly by tests; new `migrations/19.0.2.33.0/post-migrate.py`
  Odoo discovery shim that constructs `Environment` and delegates.
- Per-shop GET `/shops/{etsy_api_shop_id}/readiness-state-definitions` →
  first definition id → write as Char (Etsy ids overflow XML-RPC int32).
- Filter `active_source='api'` AND empty field; skip rows missing
  `etsy_api_shop_id`; per-shop `except Exception` swallow with WARNING.
- `demo_data.xml` pins both demo shops to `1406133708616` for fresh
  installs (existing demo records untouched due to `noupdate="1"`).

**New gotchas captured for memory**:

1. Odoo 19 recordset has **no `.refresh()` method**. Use
   `.invalidate_recordset()` to flush cached field values after a sibling
   process wrote them (the original tdd-guide draft used `shop.refresh()`
   and ERRORed with AttributeError).
2. **Mocking `EtsyApiClient.get` is insufficient** when the test code
   exercises a path that instantiates the client — `EtsyApiClient.__init__`
   raises `"client_id missing from credentials"` for a test-fixture shop
   before `.get()` is ever reached. Patch the whole class
   (`patch('...EtsyApiClient') as MockClient`) and set
   `MockClient.return_value.get.return_value = ...`.
3. **Odoo migration dirs with dots** (`19.0.2.33.0`) are not valid Python
   identifiers — Phase 2 tests that want to call the migrate function
   directly cannot do `from ...migrations.19.0.2.33.0 import ...`. Pair the
   standard Odoo discovery file with an underscore-prefixed sibling package
   (`migrations/_19_0_2_33_0/__init__.py`) where the actual logic lives.
   Add a no-op `migrations/__init__.py` so the dir becomes a package.

**Open follow-ups** (not blockers):

- T6 staging publish dry-run on JaHandmadeArt owner-gated — confirm the
  bootstrap migration ran and the next createListing returns 201.
- Existing demo records on existing DBs do NOT pick up the new
  `default_readiness_state_id` value (noupdate=1). Operator workaround:
  manual chatter-fix or set `active_source='api'` and re-run the
  migration. Documented; not promoted to a separate slice.

### Phase 9 deploy (2026-06-05) — hypothesis #1 RULED OUT, slice flipped back to `doing`

**Deploy path** (per `reference_staging_ssh_deploy.md`):

1. `rsync -avz custom_addons/etsy_integration/ → /odoo/esty19/custom_addons/etsy_integration/` (no `--delete`). Sent 23.5 kB, 1.32 MB total. All P-BUG-ESTY-188 files landed (`migrations/__init__.py`, `migrations/_19_0_2_33_0/__init__.py`, `migrations/19.0.2.33.0/post-migrate.py`, both test files, demo_data.xml, manifest 19.0.2.33.0).
2. `sudo docker exec esty19_odoo odoo -d esty_odoo19 -u etsy_integration --stop-after-init` — Module loaded in 1.53s / 1144 queries; `Running migration [19.0.2.33.0>] post-migrate`; Registry loaded in 6.241s; exit 0.
3. `sudo docker restart esty19_odoo`; healthy.

**Expected harmless WARNING captured**: `Invalid version for upgrade script '/mnt/extra-addons/etsy_integration/migrations/_19_0_2_33_0'`. Confirms the split-package design works as intended — Odoo's discovery scans the migrations dir, finds the underscored mirror, can't parse it as a version, and skips it. The dotted `19.0.2.33.0/` IS picked up and executed. Future migrations with this pattern will emit the same WARNING; do NOT promote to ERROR.

**Pre-migration baseline psql** on `esty_odoo19.etsy_shop`:

```
 id |     name      | etsy_api_shop_id | active_source | default_readiness_state_id
----+---------------+------------------+---------------+----------------------------
  1 | Julien        |                  | email         |
  2 | Carina        |                  | email         |
  3 | Viktor        |                  | email         |
  4 | Sven          |                  | email         |
 10 | JaHandmadeArt | 60752333         | api           | 1406133708616
```

**Hypothesis #1 (readiness_state_id NULL) is FALSE** on staging. JaHandmadeArt already has the field populated with the JaHandmadeArt-known value (`1406133708616`); the migration was idempotent and bootstrapped 0 shops. The 4 email-only shops were correctly skipped by the `active_source='api'` filter.

**Implication**: the createListing 400 owner reproduced on 2026-06-03 is NOT caused by hypothesis #1. The publisher payload at `etsy_listing_publisher.py:237-238` WAS including `readiness_state_id=1406133708616` in the request. Etsy rejected for a different reason.

**Pivot decision**: the slice is flipped `done → doing` because the *root cause* is still unknown. The defensive code already shipped (`19.0.2.33.0`) is HARMLESS and stays — it's correct prevention for any future shop where the field WOULD be NULL, just not the fix for this specific 400. Re-target investigation to candidate #2 or #3.

**Candidate #2** (personalization-fields regression):
- Memory `reference_etsy_createlisting_2025_readiness.md` item (2): 4 inline personalization fields deprecated in 2026; createListing 400s "Use the dedicated personalization endpoints instead". Gated OFF in commit `643370c9837`. Follow-up `R-PUB-PERSONALIZATION-ENDPOINTS` re-implementation deferred.
- **Verify on staging HEAD**: `git -C /odoo/esty19 log --oneline | grep 643370c9837` AND grep `etsy_listing_publisher.py` for `personalization_is_personalizable / personalization_instructions / personalization_char_count_max / personalization_property_id` — if any of those four keys are still in the createListing payload, that's the bug.
- If staging is on an older build than the gating commit, the cheapest fix is to deploy the current `feature/006-master-plan-coding` HEAD (which includes the gating).

**Candidate #3** (new 2026 mandatory field):
- Etsy has been adding required fields with little notice (e.g. `readiness_state_id` was the same kind of change in 19.0.2.15.0). The 2026 personalization migration explicitly says "Use the dedicated personalization endpoints instead" but other endpoints may have new requirements.
- **The authoritative answer is the 400 response body**, per `feedback_capture_response_body_before_blackbox_probe.md` (5-variant probe cap before vendor escalation, capture body FIRST).

**Capture command for next session** (run while owner reproduces the publish):

```bash
# Terminal A — follow Odoo logs for the next createListing call:
ssh -i secrets/ssh-key-2023-02-24.key ubuntu@129.150.63.207 \
  'sudo docker logs -f --tail 0 esty19_odoo 2>&1 | grep -A 8 -i "createListing\|/v3/application/shops.*listings\|400 Client Error\|HTTPError"'

# Terminal B (owner) — click "Publish to Etsy" in the Odoo web UI against
# JaHandmadeArt with the same product that 400'd on 2026-06-03.

# The 400 response body will appear in the captured tail because
# EtsyApiClient._request raises HTTPError which logs the body before the
# RPC layer scrubs it.
```

If the body is not visible in the basic Odoo log, alternative is querying `etsy.api.log` directly via psql (per `P-UAT-FIX-API-LOG-HTTP-STATUS`):

```bash
ssh ... 'sudo docker exec esty19_odoo psql postgresql://odoo:odoo@db/esty_odoo19 -c "SELECT id, source, http_status, error_message, payload_excerpt FROM etsy_api_log WHERE http_status = 400 ORDER BY id DESC LIMIT 5;"'
```

**Fresh-session resume checklist** (paste into the next session's first prompt):

1. Read this Phase 9 deploy section + `p-bug-esty-188-plan.md` (especially the "Pivot 2026-06-05" header that will be added next).
2. Confirm tracker P-BUG-ESTY-188 is `doing` with the pivot note.
3. Capture the 400 body on staging using one of the two commands above.
4. Match the body to candidate #2 (personalization keys present) or candidate #3 (new mandatory field name in the error message).
5. Plan + RED + GREEN under a new commit on `feature/006-master-plan-coding`, manifest bump `19.0.2.33.0 → 19.0.2.34.0`.
6. Flip tracker back to `done` only after staging createListing actually returns 201.
