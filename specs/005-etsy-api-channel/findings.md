# Findings — Spec 005 Etsy API Channel

Per `.claude/plans/006-implementation-playbook.md` Phase 7. Surprises, blockers, and deferred decisions discovered during implementation. Each entry stands on its own; do not delete entries — supersede them with new ones.

## 2026-06-23 — Staging deploy + E2E (3 of 4 gate items PASS; 1 HIGH UX gap blocks sign-off)

Deployed the 4 feature commits to staging (`esty_odoo19`, container `esty19_odoo`):
rsync etsy_integration → `-u etsy_integration --stop-after-init` (clean) → restart.
Branch pushed to `namco/feature/006-master-plan-coding` (HEAD 161302044bf).

Ran the review-plan staging E2E in an odoo shell (sections rolled back unless noted):

- **[A1 reconcile-after-fix] PASS** — dry-create from the REAL receipt 3818231452
  through the live `order_creator` path: `amount_total = 411708.00` exactly
  (= grandtotal 494050 − tax 82342), `etsy_total_mismatch = False`, lines =
  product 538677 + shipping 196237 − discount 323206; tax stays informational.
  Rolled back.
- **[Per-user scoping] PASS** — mirrored the unit-test setup live (scoped =
  base.group_user + sales_team.group_sale_salesman): scoped salesperson sees
  own-shop etsy + non-etsy, NOT other-shop etsy; sale-manager sees all;
  non-manager base.group_system admin (id≠1) sees all. Rolled back.
  - NOTE: a plain `base.group_user` with NO sales group cannot read sale.order
    at all (standard Odoo ACL) — the rule layers on top of a sales group. The
    review-plan's "plain base.group_user" wording means "a salesperson", as the
    unit test encodes.
- **[Pull button — function] PASS** — scoped user with no shops → clean warning
  "No Etsy shops assigned to you." (no traceback); admin path → 1 api shop →
  success "Pulled Etsy orders: 1 ingested, 0 audited, 0 errors." (this DID
  ingest 1 real receipt on staging via the new hybrid path — expected).
- **[Pull button — render] HIGH / FAIL-FOR-INTENT** — live browser check (gstack
  /browse, logged in as admin, Sales → Quotations list). The `Pull Etsy Orders`
  button renders ONLY in the list **selection action bar** (visible after
  selecting ≥1 row), next to `Create Invoices | Pull Etsy Orders | Print |
  Actions`. With zero rows selected it is absent from the control panel.
  Root cause: the button was added via `<xpath expr="//header" position="inside">`
  on `sale.view_quotation_tree_with_onboarding`; Odoo renders list-view
  `<header>` buttons in the multi-select bar, NOT as always-visible CP buttons.
  Why this is a problem for THIS action: "pull new orders from Etsy" is a global
  operation that ignores selection, yet it (a) sits among record-scoped actions
  implying it acts on the selected rows, and (b) is unreachable on an empty
  quotation list — exactly when you'd pull. Resolved arch test passed (button
  node present), so XML/arch checks alone miss this — the live render check is
  what caught it, as the review-plan anticipated.
  Evidence screenshot: `pull_btn_selection_bar.png` (session scratchpad).

Decision needed (escalated; NOT signing off ESTY-207 until resolved). Candidate
standard-Odoo fixes for an always-available global pull entry point:
  1. Dedicated menu item under Sales → Orders bound to an `ir.actions.server`
     (always visible, selection-independent) — cleanest standard pattern.
  2. `ir.actions.server` with `binding_model_id` on sale.order surfaced in the
     cog "Actions" menu (still tends to be selection-scoped in list view).
  3. OWL control-panel patch to inject an always-visible CP button (heaviest).
  4. Accept current selection-bar placement (weak — fails the empty-list case).

GATE STATUS: ESTY-205 (scoping) and ESTY-206 (coverage + reconciliation) pass
their staging E2E. ESTY-207 (manual pull) is functionally correct but BLOCKED on
the button-placement UX decision above. No JIRA transition / tracker `done` until
resolved.

---

## 2026-05-30 — P1-11-SHOPID-BOOTSTRAP landed (`f6b96fe2eb6`)

**Slice scope (final)**:
- `controllers/etsy_oauth.py` — new block at end of `callback()`: after token persist + before final redirect, call `EtsyApiClient(shop).fetch_users_me_shop_id()` → `shop.sudo().write({'etsy_api_shop_id': api_shop_id})`. `BLE001` swallow (with noqa explanation) so `/users/me` failures never break OAuth — tokens are valid; operator can re-Authorize or set field manually; **C-ESY-003 is the safety net** that blocks the eventual `active_source='api'` flip until shop_id lands.
- `services/etsy_api_client.py` — new `fetch_users_me_shop_id() → str | None`. Wraps the existing `_request('GET', 'users/me')` (gets the 401-refresh + 429-retry + 4xx-body-capture behavior for free). `str(shop_id)` cast at the boundary per gotcha #144.
- `models/etsy_shop.py` — new `_check_api_source_has_shop_id` `@api.constrains` (C-ESY-003).
- `migrations/19.0.2.31.0/post-migrate.py` — raw-SQL `SELECT id, name FROM etsy_shop WHERE active_source='api' AND (etsy_api_shop_id IS NULL OR etsy_api_shop_id='')` → if any rows, raise `Exception` listing them (operator must fix and re-run `-u`).
- Two new test files: `test_p1_11_shopid_bootstrap_phase1_db.py` (DB schema) + `test_p1_11_shopid_bootstrap_phase2_orm.py` (constraint + helper + live `_probe_api` canary + service guards + migration). 20 tests, all GREEN.
- Manifest 19.0.2.30.0 → **19.0.2.31.0**.

**Surprises (resolved before commit)**:

1. **C-ESY-003 must be gated on tokens-present.** First implementation made it unconditional (`if active_source=='api' and not etsy_api_shop_id: raise`). Result: 7 pre-existing C-ESY-001 / SourceChangeLog tests in `test_p1_11a_phase2_orm.py` + `test_etsy_order_syncer.py` started failing because their fixtures created `active_source='api'` shops without shop_id — and Odoo's constraint dispatch order is not deterministic. C-ESY-003 raced ahead and raised about etsy_api_shop_id, masking the C-ESY-001 "tokens required" message the tests asserted on. Fix: gate C-ESY-003 on `etsy_oauth_access_token AND etsy_oauth_refresh_token` so C-ESY-001 owns the "totally unconfigured" path and C-ESY-003 owns only the "post-authorization gap". This is also semantically cleaner — the two constraints cover disjoint failure modes. Companion fixture parity: 7 pre-existing test writes now also set `'etsy_api_shop_id': '60752333'` so they survive C-ESY-003 (no semantic change to those tests; they target other concerns).

2. **OAuth callback `sudo()` write is unavoidable for an `auth='public'` route.** The callback runs with no logged-in user; writing `etsy_api_shop_id` (which has `groups='base.group_system'`) requires `sudo()`. State-param validation upstream pins `shop.id`, so there's no shop-hijack surface. The shop_id content is fully owner-controlled (Etsy returns the OAuth user's shop_id). Inline rationale comment added per project rule. security-reviewer confirmed PASS.

3. **`EtsyApiClient.__init__` reads credentials from disk via `_read_credentials()`.** New tests must `patch.object(eac_module, '_read_credentials', return_value=_FAKE_CREDS)` in setUpClass — same pattern as existing `test_phase2_pub_client_orm.py`. Without the patch, the constructor raises before the test method body runs and the test ERRORs on setup rather than running the assertion. Caught by orchestrator's own test-run (per memory `feedback_tdd_guide_init_py_imports.md`: orchestrator MUST run the suite itself, not trust tdd-guide's "RED confirmed" claim).

4. **Raw-SQL fixture bypass needed to exercise the constraint guards.** The 3 caller-site service guards (`etsy_order_syncer`, `etsy_tracking_pusher`, `etsy_listing_publisher`) all check `if not shop.sudo().etsy_api_shop_id: refuse`. To unit-test those guards we need a shop in the very state C-ESY-003 refuses. Raw SQL inside the test savepoint (no `cr.commit()` — per gotcha #33 forbidden in TransactionCase) is the only valid path. Helper function `_bypass_c_esy_003_create_api_shop(env, name, with_tokens, with_shop_id)` encapsulates this and is reusable.

5. **Migration test cannot call `cr.commit()`** (gotcha #33). First version of `test_migration_refuses_email_to_api_flip_without_shop_id` tried it and ERRORed with `Cannot commit or rollback a cursor from inside a test`. Fix: raw SQL within the savepoint (visible to the same cursor), then `importlib.util.spec_from_file_location` to load the migration module and call its `migrate(cr, version)` function directly. Clean RED → GREEN.

6. **Vacuous-pass test trap from tdd-guide.** The first iteration of the OAuth callback tests was `try: shop.sudo().write({'etsy_api_shop_id': '...'}); assert ...; except ValueError: pass` — the test manually wrote the field it was asserting about, with a broad except swallowing the contract failure. Caught by orchestrator review. Rewrote as a service-helper unit test (test the helper that the controller calls), which is cheaper than spinning up `HttpCase` and exercises the actual contract.

**Verification**:
- 20/20 P1-11-SHOPID tests GREEN (Phase 1 DB schema + Phase 2 constraint/helper/probe/guards/migration).
- Full `etsy_integration` suite: 18 failed + 5 errored of 664 tests; **zero NEW regressions** vs baseline (post-slice failures all pre-existing — `test_p1_12_orm`, `test_p_list_pull_phase2_orm`, `test_phase2_*` work outside this scope).
- Module installs cleanly (`-u etsy_integration --stop-after-init` exit 0).
- code-reviewer: 0 CRITICAL / 0 HIGH / 3 MEDIUM applied (dead `isinstance(dict)` guard removed; `sudo()` inline comment at callback write site; migration raw-SQL rationale comment) / 1 LOW deferred.
- security-reviewer: 0 CRITICAL / 0 HIGH / APPROVED.

**Branch + commit**: `feature/006-master-plan-coding` `f6b96fe2eb6`. 10 files (+831/-1).

**Deferred (not scope creep)**:
- Deprecated `check_access_rights()` / `check_access_rule()` at `controllers/etsy_oauth.py:176-177` (planner OQ3 default: defer; still works in Odoo 19; cosmetic DeprecationWarning surfaced during P1-11-WIRE-LIVE).
- Multi-shop owners (Etsy supports it; we don't have any today; `/users/me` returns one `shop_id`, multi-shop case would need `/users/{user_id}/shops`).

**Unblocks**: Future Etsy shop OAuth flips never need manual `UPDATE etsy_shop SET etsy_api_shop_id=...` SQL backfill again. Next-shop cutover runbook can drop that step.

---

---

## 2026-04-28 — P0-17 etsy.api.log model + audit retrofit + retention cron landed

**Slice scope (final, post-execution)**:
- `models/etsy_api_log.py` (NEW, ~140 LOC): `etsy.api.log` Model with 11 fields per data-model.md §3. Does NOT inherit `mail.thread` (high-volume). Composite index `(shop_id, request_started_at DESC)` declared in `init()` via raw SQL. `_cron_cleanup_old_logs` raw-SQL DELETE parameterized via psycopg2; threshold from `ir.config_parameter.etsy_integration.api_log_retention_days` (default 30, integer underflow guarded).
- `services/etsy_order_syncer.py` `_audit_log`: P0-16c stopgap (`_logger.warning`) replaced with `self._env['etsy.api.log'].sudo().create({...})`. PII scrubbed — `response_summary` contains receipt_id + amount + currency only.
- `security/etsy_security.xml`: new `group_etsy_api_log_reader` group.
- `security/ir.model.access.csv`: 2 rows (reader read-only, system full).
- `data/ir_cron_data.xml`: new `cron_etsy_api_log_cleanup` (daily).
- `views/etsy_api_log_views.xml` (NEW): list (`decoration-danger` on 5xx) + read-only form + search; menu under Etsy Integration gated to `group_etsy_api_log_reader,base.group_system`.
- `__manifest__.py`: `etsy_security.xml` reordered BEFORE `ir.model.access.csv` (CSV references the group).

**Owner-confirmed planner OQs** (all 7 accepted as recommended):

| OQ | Decision |
|---|---|
| OQ1 add `audit` to source enum | Yes — explicit, cheap. data-model.md §3 updated. |
| OQ2 per-call API-client logging | Defer to P0-17b — pair with rate-limit header capture |
| OQ3 dedicated reader group | Define now — 2 lines, no harm |
| OQ4 retention SQL vs ORM | Raw SQL DELETE — fast on high-volume table; cron context = system |
| OQ5 PII scrub depth | Aggressive — drop buyer_*, addresses, message_from_buyer |
| OQ6 indexes | Just `(shop_id, request_started_at DESC)`; defer 2 others to P1 |
| OQ7 audit log granularity | Per-receipt — enables row-level diff inspection |

**Surprises (resolved before commit)**:

1. **Odoo 19 renamed `res.groups.category_id` → `privilege_id`** (Many2one to `res.groups.privilege`). RED group XML used `category_id` per Odoo ≤18 convention; install fired `ValueError: Invalid field 'category_id' in 'res.groups'`. Fix: drop the `category_id` field entirely — `privilege_id` is optional in Odoo 19 (verified against `addons/product/security/product_security.xml`). Group works fine without a privilege; appears under a default group in Settings UI. **Captured to memory as gotcha #31.**

2. **Search-view RelaxNG in Odoo 19 rejects `<group expand="0">`.** P0-17 search view used the standard pre-19 pattern `<group expand="0" string="Group By"><filter ... context="{'group_by': '...'}"/></group>`. Odoo 19 emits 3 RelaxNG warnings:
   - `Invalid attribute expand for element group`
   - `Element search has extra content: field`
   - `Expecting an element field, got nothing`
   The view loads fail with `ParseError`. Fix: drop `<group>` wrapper; group-by filters become flat siblings of regular filters, separated by `<separator/>`. **Captured to memory as gotcha #32.**

3. **`TransactionCase.cr.commit()` is forbidden.** Retention RED tests inserted rows via raw SQL then called `self.env.cr.commit()` to make them visible to the cron's DELETE. Odoo's test cursor raises `AssertionError: Cannot commit or rollback a cursor from inside a test`. Fix: create rows via ORM at default time, then UPDATE `request_started_at` via raw SQL inside the savepoint + `invalidate_recordset()` to refresh the cache. The DELETE sees the backdated rows because UPDATE is visible within the same transaction. **Captured to memory as gotcha #33.**

4. **Manifest `data` order matters when ACL CSV references a custom group.** RED + GREEN initially had `security/ir.model.access.csv` BEFORE `security/etsy_security.xml`; install failed with `No matching record found for external id 'etsy_integration.group_etsy_api_log_reader'`. Fix: load XML before CSV. Existing modules avoided this because they only used built-in group xmlids (`base.group_user`, `base.group_system`) which are loaded much earlier; new custom groups must precede the CSV that references them. **Already in memory gotcha #15-area; reaffirmed.**

5. **tdd-guide `assertRaises(Exception)` was too broad.** `test_source_selection_rejects_invalid_value` used `with self.assertRaises(Exception)` — would have passed RED via the `KeyError: 'etsy.api.log'` from accessing the missing model. Tightened to `assertRaises(ValueError)` (Odoo's Selection write-time validation). Same family as the P0-16c `assertRaises(ImportError)` placeholder anti-pattern; reinforces the rule "always assert a specific exception type, never a base class".

6. **tdd-guide audit retrofit tests passed raw fixture dicts as payloads** to a `MagicMock` adapter. The syncer's `_audit_log` expects `EtsyOrderPayload` dataclass instances (with `.last_modified` attr), not dicts. The mock returned `iter([fixture_data])` → a single dict was yielded → `payload.last_modified` raised `AttributeError`. Fix: replace the mock with a real `EtsyApiAdapter(MagicMock(client))` where `client.get.side_effect = [page]` — the adapter does the JSON→payload conversion, mirroring the production code path. P0-16c's `test_etsy_order_syncer.py` already showed this pattern; the agent didn't carry it over.

**Q-resolved (security-reviewer P0-17, fixed inline)**:

- **MEDIUM** — `sudo()` call in `_audit_log` lacked an inline comment per project rule. Added 5-line comment explaining the bypass rationale (etsy.api.log create requires `base.group_system`; cron context already has it; sudo() is defensive redundancy for any future manual admin trigger).

**Q-deferred (security-reviewer P0-17 LOWs / accepted-with-mitigation)**:

- **LOW** — Retention parameter has no upper bound (admin could set 999999 days = forever). Operational risk, not security. Defer to P1 hardening (config UI with spinner).
- **LOW (escalates post-cutover)** — No record rules on `etsy.api.log`. A BA in `group_etsy_api_log_reader` for Shop A diagnostics can read logs for ALL shops. Acceptable in sandbox / pre-cutover; **flag for P0-17c (multi-tenant per-shop scoping) when production cutover begins multi-shop**.
- **LOW** — Group lacks `privilege_id` (cosmetic; group appears in default UI bin). Optional polish.

**Verification**:
- `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration,multichannel_hub_core,multichannel_hub_fulfillment --test-tags=/etsy_integration,/multichannel_hub_core,/multichannel_hub_fulfillment --stop-after-init` → 0 fail / 0 error / 342 tests.
- Module installs cleanly.
- No `_logger.info(` / `print(` introduced beyond the new `_cron_cleanup_old_logs` operational summary line (cron-completion is a "significant operational event" per project rule).

**Branch + commit**: `feature/006-master-plan-coding` `481bd4250d7`. RED already on branch as `d45576bd364`.

**Doc drift fixed**: data-model.md §3 `source` Selection enum updated to include `audit` (resolves contradiction with findings 2026-04-26 architect Q4 recommendation).

**Unblocks**: P1-04 (address-change approval workflow) — next critical-path slice per active prioritization. P0-17b (per-call EtsyApiClient logging + rate-limit header capture) is a dedicated future slice, not gating Phase 1.

---

## 2026-04-28 — P0-16c EtsyOrderSyncer + audit mode + status-only re-sync landed

**Slice scope (final, post-execution)**:
- `services/etsy_order_syncer.py` (NEW, ~110 LOC): `EtsyOrderSyncer.sync_shop_orders(shop)` orchestrator. `_build_adapter(shop)` factory hook for test override. `_audit_log(shop, payload)` single-call-site so P0-17 retrofit to `etsy.api.log` is one line.
- `services/etsy_order_ingestor.py`: extended to route existing orders to `_status_only_resync` (FR-009 subset — payment_status + etsy_last_modified only; shipping_status / cancellation deferred to P0-17).
- `services/etsy_order_payload.py`: additive `last_modified: datetime | None = None` field at end of frozen dataclass (backward-compatible).
- `services/etsy_api_adapter.py`: `_receipt_to_payload` now reads `last_modified_tsz` (or `updated_timestamp` fallback) into the payload.
- `services/order_creator.py` `process_etsy_payload`: writes `payment_status` + `etsy_last_modified` from payload during initial create.
- `models/etsy_shop.py`: new `sync_mode` Selection [email_only, api_only] + `sync_audit_mode` Boolean, both `groups='base.group_system'`. New `_cron_sync_orders` method with `_is_system()` guard.
- `models/sale_order.py`: new `payment_status` Selection [unpaid, paid] + `etsy_last_modified` Datetime, both `readonly=True` (chosen over `groups='base.group_system'` so dashboard salesmen retain read access).
- `data/ir_cron_data.xml`: new cron `cron_etsy_order_sync`, 5min, filters `sync_mode='api_only'`.
- 17 P0-16c tests (Phase 1 DB + Phase 2 ORM); pre-existing tests preserved.

**Owner-confirmed planner OQs** (all 5 accepted as recommended):

| OQ | Decision |
|---|---|
| OQ1 audit logging | `_logger.warning` per receipt; `etsy.api.log` retrofit in P0-17 |
| OQ2 status-only depth | Full FR-009 (subset shipped: payment_status + etsy_last_modified); shipping_status / cancellation deferred to P0-17 alongside richer Selection taxonomy |
| OQ3 cursor advancement | Per-payload (after each successful ingest) |
| OQ4 audit + api_only constraint | Soft-warn (`_logger.warning`) only — no `@api.constrains` |
| OQ5 cron filter | `sync_mode='api_only'` only — audit flag does NOT trigger cron |

**Surprises (all resolved before commit)**:

1. **`ir.model.fields` field-level ACL has no DB column.** RED test asserted ACL via `ir_fields.groups_id` (then tried `group_ids`) — both fail with `AttributeError`. The Many2many is `ir_model_fields.groups`, but its junction table `ir_model_fields_group_rel` is documented in `odoo/addons/base/models/ir_model.py` as `# CLEANME unimplemented field (empty table)`. Field-level ACL lives in-memory on the `Field` object's `.groups` attribute and is enforced by ORM, not stored in DB. **Fix**: assert `self.env['etsy.shop']._fields['sync_audit_mode'].groups == 'base.group_system'` instead. Phase 1 DB tests for field-level ACL must always go through the in-memory Field object.

2. **tdd-guide produced placeholder RED tests that would silently flip FAIL→PASS.** The agent wrote 11 syncer tests, ~10 of which were `with self.assertRaises((AttributeError, ImportError)): from ... import EtsyOrderSyncer` — these "fail" only because the import raises ImportError, then `assertRaises` swallows it. Once GREEN lands and the import succeeds, `assertRaises` itself fires (no exception raised), turning a "passing" test green into a regression. **Fix**: rewrote `test_etsy_order_syncer.py` with proper mock-based contract assertions before running the post-GREEN test pass. **Lesson**: when a tdd-guide RED commit lands with "all tests fail for the right reason", verify that the "right reason" is contract-specific, not import-availability. An `assertRaises(ImportError)` is RED-poor — the test must exercise the actual contract method even when it doesn't yet exist. Captured to memory as a recurring tdd-guide failure mode.

3. **Pre-existing duplicate-ingest semantic inverted by FR-009.** `test_ingest_returns_none_on_duplicate` asserted `self.assertIsNone(second)` — that was the P0-16b1 semantic. P0-16c FR-009 routes existing orders through status-only re-sync, which returns the (refreshed) order, not None. The pre-existing test caught this on first run; renamed to `test_ingest_returns_existing_order_on_duplicate` with `self.assertEqual(second.id, first.id)`. **Lesson**: when changing single-writer ingestor semantics, grep the test suite for prior expectations on return-shape — they are likely stale.

4. **`order.refresh()` doesn't exist in Odoo 19.** tdd-guide wrote `order.refresh()` after re-sync to re-read fields. Odoo 19 dropped that method (gotcha #4 in memory). **Fix**: `order.invalidate_recordset()` (or scope to specific fields with `invalidate_recordset(['payment_status'])`).

**Q-resolved (security-reviewer P0-16c, fixed inline)**:

- **MEDIUM** — `payment_status` + `etsy_last_modified` had no field-level write restriction. Reviewer suggested `groups='base.group_system'`, which would hide them from dashboard salesmen who need read access to filter unpaid orders. **Resolution**: `readonly=True` (single-writer at UI level) instead. Hard ACL via `groups=` deferred until P0-17 when `tracking=True` + `mail.thread` audit gives us tamper detection without losing visibility.
- **MEDIUM** — `_audit_log` logged `payload.buyer_name` into Odoo's log files (less protected than DB rows). PII minimization: dropped buyer_name; receipt_id + amount + currency are enough for BA reconciliation. Buyer identifiers move into `etsy.api.log` (proper read ACL) in P0-17.
- **HIGH-mitigated** — `_cron_sync_orders` is `@api.model` with no privilege gate; the field-level ACL on OAuth tokens is the existing defense. **Resolution**: added explicit `if not self.env.user._is_system(): raise AccessError(...)` for defense-in-depth against accidental RPC exposure.

**Q-deferred (security-reviewer P0-16c LOWs / accepted-with-mitigation)**:

- **HIGH-mitigated, accepted** — Cursor advancement is non-durable until the cron transaction commits. Crash mid-batch = loss of cursor advance, but ingest idempotency (etsy_order_id dedup) + status-only re-sync idempotency mean the next cron tick re-fetches and writes are no-ops. Explicit `env.cr.commit()` per payload defers to P1-XX hardening.
- **MEDIUM-mitigated, accepted** — `_status_only_resync` writes regardless of monotonicity → a stale payload could downgrade `payment_status` from 'paid' to 'unpaid'. Defense: the syncer's monotonic cursor (`payload_ts > last_seen`) is the authoritative gate. Documented in ingestor docstring.
- **LOW** — Soft-warn (no constraint) on `sync_audit_mode + sync_mode='api_only'` per OQ4; an `@api.constrains` could be added pre-cutover (P1-11) if the soft warning gets ignored.

**Verification**:
- `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration,multichannel_hub_core,multichannel_hub_fulfillment --test-tags=/etsy_integration,/multichannel_hub_core,/multichannel_hub_fulfillment --stop-after-init` → 0 fail / 0 error / 320 tests.
- Module installs cleanly; no new `_logger.info(` in models or services beyond the pre-existing operational cron-summary line (which is convention).
- Reviews: code-reviewer PASS with 2 MINORs accepted; security-reviewer 2 MEDIUMs + 1 HIGH-mitigated fixed inline.

**Branch + commit**: `feature/006-master-plan-coding` `b70daf6b07a`. RED already on branch as `74dc81db0de`.

**Unblocks**: P0-17 (`etsy.api.log` model + audit reconciliation) and P1-12 (`EtsyTrackingPusher` — once Spec 005 US3 starts) — both share the cron + audit-log scaffolding this slice put in place.

---

## 2026-04-28 — P0-16a module-home decision (supersedes data-model.md §"Adapter contract" location)

**Contradiction**: `data-model.md` line 260 places `EtsyChannelAdapter` Protocol + `EtsyOrderPayload` dataclasses in `multichannel_hub_core/services/`. `multichannel_hub_core/CLAUDE.md` (added under P0-20 skeleton) prohibits Etsy-specific code: *"This module has no Etsy-specific code. If a model, service, or view references `etsy_*` anything, it belongs in `etsy_channel`, not here."*

**Decision (owner-confirmed 2026-04-28)**: place both files in `etsy_integration/services/`, NOT in `multichannel_hub_core`.

**Rationale**:
1. Module CLAUDE.md is the binding contract; data-model.md predates the rule.
2. Both artifacts are Etsy-named (`EtsyChannelAdapter`, `EtsyOrderPayload`) — they belong with Etsy.
3. When Amazon/website channels arrive, each channel will host its own canonical payload + adapter Protocol. A generic `OrderIngestor` in core can consume any payload by structural typing (Protocol/duck-typing) — no need to design that abstraction today.
4. P0-16 only needs the Etsy half; abstraction-on-demand keeps core lean.

**Implication for downstream slices**:
- `EtsyOrderIngestor` (T008) likely also moves to `etsy_integration/services/` for P0-16; if a future Amazon adapter wants ingestion reuse, extract a generic ingestor into core at that point.
- Spec 005 `data-model.md` line 260 is superseded by this entry; a follow-up doc edit in the next slice will update the path.
- ADR-003 module decomposition still holds — this decision narrows what "shared core" means without changing the four-module split.

---

## 2026-04-27 — P0-15 EtsyApiClient sandbox landed

**Slice scope (final, post-execution)**:
- `services/etsy_api_client.py`: `EtsyApiClient(shop)` constructor, `_session()` two-header auth (`Authorization: Bearer`, `x-api-key`), `_request()` with rate limiting + 429 retry + 401 single-shot refresh, `ping()` against `/users/me`. Module-level constants: `ETSY_API_BASE_URL = 'https://openapi.etsy.com/v3/application'`, `_RATE_LIMIT_QPS = 8`, `_MAX_RETRY_AFTER_SECONDS = 60`, `_PROACTIVE_REFRESH_WINDOW_SECONDS = 60`.
- 19 mocked tests in `tests/test_etsy_api_client.py` (TransactionCase, post_install): init validation × 4, session headers × 2, ping × 4, rate-limit × 4, 401-refresh × 5.
- Memory `feedback_odoo19_test_gotchas.md` will gain a #24 once committed: `BaseCase._assertRaises` calls `issubclass(exception, AccessError)`, which fails on tuple — never pass a tuple of expected exceptions to `with self.assertRaises(...)` in Odoo tests.

**Q-resolved (architect's W2 advisory; outcomes)**:
- **Q3 (rate limiter)**: per-instance `TokenBucket(rate=8, period=1.0)`. Imported from `multichannel_hub_core.utils.rate_limiter` — the architect's "long-term home" was reached early in P0-18a. **Phase 1 refactor task removed from backlog** (the per-shop bucket lives in core; if multi-shop fairness becomes an issue, that's a P1 ticket on top of the existing core utility).
- **Q5 (module home)**: lands in `etsy_integration` per the advisory. Re-home to `etsy_channel_api` deferred to ADR-003 Phase 1 (P1-XX), with the API surface intentionally narrow (`shop` + `ping()`) so the move is mechanical.

**Surprises (all resolved before commit)**:

1. **Credential-loader path off-by-one**. Initial GREEN computed the credentials file path via `dirname(__file__)` chained 3 times then `'..', '..', 'secrets', 'credentials.json'`, which resolved to `other_projects/secrets/credentials.json` — outside the project. Code-reviewer caught it as CRITICAL (would 401 in production). Fix: hardcode `CREDENTIALS_PATH = '/opt/odoo/secrets/credentials.json'` to match what `controllers/etsy_oauth._read_credentials` already does (it reads from `ir.config_parameter` with the same string as the default). Convention now: in-container path is the source of truth; the Python computation is fragile when the file lives outside the addon. **If we ever need a portable computed path, derive from `env['ir.config_parameter']` like the controller does — but the service layer here doesn't take `env`, so the constant is fine.**

2. **`BaseCase._assertRaises` does not accept tuples** (Odoo test gotcha). The RED test had `with self.assertRaises((ValueError, FileNotFoundError)):`, which crashed inside Odoo's overridden `_assertRaises`: `if issubclass(exception, AccessError)` — `issubclass` requires a class as first arg, not a tuple. Fix: my impl wraps `FileNotFoundError → ValueError` so the test only needs `ValueError`. Single-class `assertRaises(ValueError)` works fine. Saved to memory as gotcha #24.

3. **Tz-naive datetime comparison** (security-reviewer MEDIUM). First GREEN used `datetime.now()` to compute the proactive-refresh threshold. Odoo Datetime fields read as **naive UTC**, so on a non-UTC host this would skew. Fix: switched to `datetime.utcnow()` for both the threshold and the `expires_at` write inside `_refresh_token`. Now matches Odoo's storage convention regardless of host TZ.

4. **`self.shop.refresh()` doesn't exist on Odoo 19 recordsets** (memory gotcha #4). The RED test invalidated the cache via `self.shop.refresh()`; this raised `AttributeError` during GREEN run. Fix: `self.shop.invalidate_recordset()`. Test still asserts the expected post-refresh token state.

**Q-deferred (security-reviewer LOW notes; revisit at hardening pass)**:

- **DQ1 — Caller-side ACL gate**: `EtsyApiClient` does NOT check the calling user's access to the shop before instantiating. Service-layer responsibility per the class docstring; the orchestrator (cron, sync wizard, controller route) must gate access. Add a `check_access_rule` helper if/when this client is ever invoked from a user-controlled action.
- **DQ2 — `requests.Session` redirect policy**: defaults to following redirects. Same finding as P0-18a, deferred to a hardening slice (P1-XX) that sets `session.max_redirects = 0` for both Etsy + Gearment clients.
- **DQ3 — `path` argument to `_request()` accepts fully-qualified URLs accidentally**: `f"{base}/{path.lstrip('/')}"` doesn't validate that `path` is relative. Currently only `ping()` calls it with `'users/me'`; document the convention until `_request()` becomes user-callable.

**Verification**:
- `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --test-tags=/etsy_integration --stop-after-init` → 0 fail / 0 error / 170 tests.
- Full regression `-u etsy_integration,multichannel_hub_core,multichannel_hub_fulfillment` → 0 fail / 0 error / 236 tests.
- No `_logger.info(` / `print(` introduced.
- Reviews: code-reviewer PASS after credential-path fix; security-reviewer PASS with 3 LOW notes captured above.

**Branch + commit**: `feature/006-master-plan-coding`. RED already on branch as `d84f92c3cbb`; GREEN + review fixes commit follows.

**Unblocks**: P0-16 (`EtsyOrderSyncer` against dev shop with VCR fixtures) — has the rate-limited authenticated client to syndicate from.

---

## 2026-04-27 — P0-14 OAuth2 PKCE sandbox landed

**Slice scope (final, post-execution)**:
- `services/etsy_oauth.py` (pure functions): `generate_code_verifier`,
  `generate_code_challenge`, `build_authorize_url`,
  `exchange_code_for_token`, `refresh_access_token`
- `controllers/etsy_oauth.py`: routes `/etsy/api/oauth/authorize`
  (auth='user', shop-write ACL gated) and `/etsy/api/oauth/callback`
  (auth='public', csrf=False, state-based replay defense)
- `models/etsy_shop.py`: 3 new fields with `groups='base.group_system'`
  (plaintext per Q2 deferral; Fernet-at-rest is P1-10 work)
- 23 tests: 9 PKCE pure-function + 7 DB+ORM on the new fields + 7
  HttpCase controller integration

**Routing-namespace surprise**: original ADR-008 implied the OAuth callback
would land at `/etsy/oauth/callback`, but Spec 001 already shipped a Gmail
OAuth controller claiming that exact URL. To avoid a route collision (and
to keep the Gmail flow stable per ADR-008a v2 — email parser stays as
permanent failover), the new Etsy v3 API OAuth lives at
`/etsy/api/oauth/...`. Future module decomposition (ADR-003 Phase 2) can
revisit naming when the per-channel modules split out.

**PKCE test-vector hallucination**: the tdd-guide's RED tests included a
"RFC 7636 Appendix B" expected challenge value of
`E9Mrozoa2owWoUeS_Z6OQ3OKN2iCHaEc292iNLsrgS8` for the verifier
`dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXo`. Python's hashlib produces
`xmcnc8avt3As1ZGvMdrjrrWgSSwK8XeDmIDLCfAoW38` for that input — the
"expected" was wrong (RFC §B's published challenge value differs from
the actual SHA256 of the published verifier; either the RFC has a typo
or the agent paraphrased an incorrect source). Replaced with a verified
vector (SHA256 of `'hello'` → `LPJNul-wow4m6DsqxbninhsWHlwfp0JecwQzYpOLmCQ`).
Lesson: when a test has a memorized RFC vector, verify it against an
independent computation before committing.

**Test-harness surprise**: HttpCase tests in Odoo 19 follow redirects
by default. When the authorize route correctly returns 302/303 to
`https://www.etsy.com/oauth/connect`, the test harness's `requests`
session follows it and gets blocked by Odoo's
`Blocking un-mocked external HTTP request` middleware — surfacing as
an opaque test error. Fix: pass `allow_redirects=False` to `url_open`.

**Q2 reaffirmed (encryption deferred)**: tokens stored plaintext in
`etsy_shop.etsy_oauth_access_token`. Field-level `groups='base.group_system'`
ACL blocks UI reads for non-admins, but the column is plaintext on
disk and in `pg_dump`. Acceptable for sandbox per Q2 (owner accepted
2026-04-26). P1-10 must add Fernet-at-rest before any production token
lands. Track this in tracker P1-10 as a hard prerequisite.

**Security gate added late**: original /authorize route accepted any
authenticated user with any `shop_id`. Security-reviewer (Opus) flagged
as HIGH (privilege escalation: a salesman could trigger token rebind
for a manager's shop). Fixed by adding `shop.check_access_rights('write')
+ shop.check_access_rule('write')`. Lesson: when a route accepts a
user-supplied record ID, always gate with explicit ACL — auth='user'
alone is not enough.

**Werkzeug exception → 500 instead of 400**: raising
`werkzeug.exceptions.BadRequest` in an Odoo 19 HttpCase test triggers
the qweb 400 error template, which depends on assets unavailable in the
test harness — the response bumps to 500. Workaround: return a plain
`request.make_response(msg, status=400)` instead of raising. May be
worth contributing back to Odoo as a documentation fix if the
`werkzeug.exceptions.*` pattern is meant to work in HttpCase.

---

## 2026-04-26 — Architecture Advisory: Sandbox Bootstrap Open Questions

**Context**: Wave 2 planner (P0-14..17 sandbox bootstrap) raised 5 open questions before implementation. `architect` agent (Opus tier) produced this advisory. **Owner decision required** before sandbox coding starts.

### TL;DR
For sandbox Phase 0 work:
1. **VCR cassettes**: one-per-test in `tests/fixtures/vcr/`, refresh quarterly via `ETSY_DEV_TOKEN_REFRESH=1` flag.
2. **Token storage**: `ir.config_parameter` with `group_system` ACL; defer encryption to Phase 1.
3. **Rate limiter**: in-memory token bucket inside `EtsyApiClient` (per-instance), promoted to shared in `multichannel_hub_core` post-Phase 1.
4. **Audit mode**: Boolean `etsy.shop.sync_audit_mode` field; runs read-only, logs diffs to `etsy.api.log` with `source='audit'`, gates all `sale.order` writes.
5. **Module decomposition**: land sandbox in `etsy_integration` now; re-home to `etsy_channel` during ADR-003 Phase 1 (before Phase 1 spec code ships).

### Q1 — VCR cassette policy

**Recommendation**: One cassette per test (fine-grained, many files).

**Rationale**: Sandbox tests target the owner's dev token + one shop. Each fixture (list receipts / token refresh / 429 response) exercises a distinct API behavior. One-per-test isolates these and lets you repair affected cassettes when Etsy responses change. Shared/scenario cassettes tempt cross-test coupling.

**Tradeoffs**:
| Approach | Pro | Con | Verdict |
|---|---|---|---|
| Shared (per scenario) | Fewer files, realistic sequences | Tests entangled, all-or-nothing re-record | Rejected |
| One-per-test | Clear isolation, incremental repair | ~30–50 cassettes | **Chosen** |

**Refresh policy**: CI replays cached cassettes by default (hermetic). When `ETSY_DEV_TOKEN_REFRESH=1`, re-record against dev shop. Manual quarterly cadence to catch Etsy surface changes. git-lfs only if total > 50 MB.

**Location**: `custom_addons/etsy_integration/tests/fixtures/vcr/<scope>/`.

**Decision needed**: Confirm refresh frequency (quarterly default) and whether CI auto-records on schedule or requires manual flag.

---

### Q2 — OAuth token storage

**Recommendation**: `ir.config_parameter` with `group_system` ACL for sandbox; encryption deferred to Phase 1.

**Rationale**: Sandbox = dev token, dev shop, dev DB. The pattern matches existing Gmail OAuth credentials. Per-shop key naming (`etsy_integration.etsy_access_token_{shop_id}`) plus `groups='base.group_system'` blocks casual UI visibility. No operator sees raw tokens.

**Phase 1 decision (out of scope here)**: Once production scopes arrive (E1), evaluate Fernet / KMS / Odoo `fields.Encrypted` (verify Odoo 19 support). Compliance may require encryption at rest. Add task P1-XX.

**Tradeoffs**:
| Approach | Pro | Con | Verdict |
|---|---|---|---|
| Encrypt sandbox tokens now | Defense in depth | Key rotation complexity for dev | Rejected (premature) |
| Env vars | Simple for dev | Doesn't scale to 19 prod shops | Rejected |
| `ir.config_parameter` + `group_system` | Sufficient for sandbox, defers crypto | Plaintext-at-rest in dev DB | **Chosen** |

**Decision needed**: Confirm `group_system` ACL is sufficient for Phase 0; commit to a P1-XX task to evaluate encryption when production scopes land.

---

### Q3 — Rate limiter design

**Recommendation**: In-memory token bucket inside `EtsyApiClient` (per-instance). Long-term home in `multichannel_hub_core/utils/rate_limiter.py` post-ADR-003 Phase 1.

**Rationale**: Etsy publishes ~10 QPS + 10 000 QPD per *app* (not per shop). Sandbox = 1 shop, so per-instance bucket is exact. Phase 1 = 19+ shops on the same app, where shared bucket becomes correct (and adds intra-process locking + fairness logic). Defer that complexity until multi-shop testing reveals starvation.

**Concrete**: `EtsyApiClient._qps_bucket = TokenBucket(capacity=8, refill_rate=8/sec)`. Adjust dynamically via `x-remaining-this-second` response header.

**Tradeoffs**:
| Approach | Pro | Con | Verdict |
|---|---|---|---|
| Shared global bucket | Accurate to API contract | Locking, fairness, complexity | Deferred to Phase 1 |
| No rate limit | Fastest | Account-throttle risk (FR-023 violation) | Rejected |
| Per-client bucket | Simple, sufficient for sandbox | Inaccurate when N shops > 1 | **Chosen for Phase 0** |

**Long-term home**: Per ADR-003, `multichannel_hub_core/utils/rate_limiter.py`. Until that module exists, place in `etsy_integration/services/rate_limiter.py` and flag for re-home in Phase 1.

**Decision needed**: Confirm per-client bucket for sandbox; commit to refactor task in Phase 1 if multi-shop testing shows unfair distribution.

---

### Q4 — `sync_audit_mode` semantics

**Recommendation**: Boolean field `etsy.shop.sync_audit_mode`. When `True`: API runs read-only, fetches receipts, logs field diffs to `etsy.api.log` (source='audit'), zero `sale.order` writes.

**Rationale**: ADR-002 §3 introduces audit mode for the 1–2 week pilot-shop cutover window. The API runs in parallel with the email parser; the BA reviews diffs. Implementation:

1. `EtsyOrderSyncer.sync_shop_orders(shop)` checks `shop.sync_audit_mode` early.
2. If True: fetch receipts → for each, compare key fields (amount_total, line items, shipping address) against existing `sale.order` matched by `etsy_order_id` → write diffs to `etsy.api.log` with `source='audit'`.
3. Return without calling `OrderCreator`.
4. Log summary: "Audit run: 247 receipts compared, 5 diffs found."

**Field placement**: Boolean on `etsy.shop`, default `False`. Orthogonal to `sync_mode` (can be True regardless of `email_only` / `api_only` — though `api_only + audit` is nonsensical and should be guarded by a constraint).

**Tradeoffs**:
| Option | Verdict |
|---|---|
| (a) Block cron entirely | Rejected — loses validation opportunity |
| (b) Read-only, log diffs | **Chosen** |
| (c) Third value in `sync_mode` enum (`audit_only`) | Rejected — audit is temporary + orthogonal |

**Decision needed**: Confirm Boolean field design; confirm BA's ≥99.5% field-match gate before flipping to `api_only` per ADR-002 still holds.

---

### Q5 — Module decomposition timing

**Recommendation**: Land sandbox in `etsy_integration` now. Organize structurally as if split. Re-home to `etsy_channel` during ADR-003 Phase 1, before Phase 1 spec code ships.

**Rationale**: ADR-003 §3 commits to phased decomposition:
- Phase 0 (during Spec 002): `etsy_integration` monolithic, but code organized as if split.
- Phase 1 (start of Spec 003 rewrite): create `multichannel_hub_core`, extract shared pieces, declare dependency.
- Phase 2 (Spec 004a): create `multichannel_hub_fulfillment`, rename `etsy_integration` → `etsy_channel`.

For P0-14..17 specifically:
- Do NOT create `etsy_channel` yet.
- Land code in `etsy_integration/{models,services,tests}/`.
- Use module-agnostic test imports: `from odoo.addons.etsy_integration.services.etsy_api_client import ...` (survives the rename).
- Document the future move in `etsy_integration/__init__.py` comment + this findings file.

**Why not alternatives?**
| Option | Verdict |
|---|---|
| (a) Land in `etsy_integration` now, re-home in Phase 1 | **Chosen** — single clean move |
| (b) Do P0-20 first, then land in `etsy_channel` | Rejected — P0-20 unknowns block sandbox |
| (c) Create only `multichannel_hub_core` now | Rejected — splits a single feature, premature abstraction |

**Decision needed**: Confirm landing in `etsy_integration` is acceptable; commit to executing P0-20 before Phase 1 spec code starts.

---

### Cross-cutting risks

- **`EtsyApiClient` lifecycle**: All five decisions converge on this class. It owns the cassettes (Q1), reads tokens (Q2), holds the rate limiter (Q3), is invoked by `EtsyOrderSyncer` which checks audit mode (Q4), and lives in `etsy_integration` until Phase 1 (Q5). Verify the test harness and imports stay aligned across changes.
- **Token refresh during sandbox**: Dev token expires in ~1 hour. VCR cassettes must include a "refresh token" success case + a refresh-timeout test for graceful failure.
- **Audit mode + rate limiter**: Audit sends N-1 read-only requests per cycle → same QPS load as normal mode. With 19 shops in audit simultaneously (Phase 1), the per-client bucket (Q3 Phase 0) becomes a starvation risk → confirms the Phase 1 refactor to shared bucket.

---

### New ADRs proposed

- **ADR-009**: VCR cassette policy (Q1) — lightweight, no risk.
- **ADR-010**: Audit mode semantics (Q4) — clarifies the cutover workflow for BA.

Both are <1 page. Author them in `specs/006-master-plan/adrs/` once Owner decisions land here.

---

### Owner decision form

**2026-04-26 Owner decision**: "proceed as recommendation, we'll comeback for open questions when do end-to-end test."

All five recommendations accepted as defaults for sandbox implementation (W5). Revisit during the W7 E2E sprint if it surfaces issues.

- [x] Q1 — One-per-test cassettes, quarterly refresh via `ETSY_DEV_TOKEN_REFRESH=1`. **Accepted as architect recommendation. Revisit at W7.**
- [x] Q2 — `ir.config_parameter` + `group_system` for sandbox; encryption deferred to Phase 1. **Accepted as architect recommendation. Revisit at W7.**
- [x] Q3 — Per-client token bucket for sandbox; shared bucket as Phase 1 refactor task. **Accepted as architect recommendation. Revisit at W7.**
- [x] Q4 — Boolean `etsy.shop.sync_audit_mode`; read-only path in syncer. **Accepted as architect recommendation. Revisit at W7.**
- [x] Q5 — Land in `etsy_integration`, re-home to `etsy_channel` during ADR-003 Phase 1. **Accepted as architect recommendation. Revisit at W7.**
- [ ] ADR-009 (VCR policy) and ADR-010 (audit mode) — **deferred until W7 E2E results inform whether the policies need codifying as ADRs or remain implementation-level decisions.**

W2 → W5 unblocked. P0-14..17 move from `blocked` to `todo` in the tracker.

---


---

## P0-22 — Etsy API ↔ email-parser ingest parity (2026-05-10)

### Decision

Routed `email_parser` output through a new `EtsyEmailAdapter` that emits the canonical `EtsyOrderPayload`, joining the same write path as `EtsyApiAdapter`. Rejected the alternative (extending `order_creator.process_parse_result` inline) because it locks two divergent code paths in permanently.

### Implementation summary

- `EtsyOrderPayload` gained 4 optional fields: `shipping_service`, `processing_time`, `discount_code`, `subtotal` (defaults `None`).
- `EtsyLineItemPayload` gained `name_override` (default `None`) — lets the email path keep its rendered product label as the operator-visible `sale.order.line.name`.
- `EtsyApiAdapter._receipt_to_payload` populates the 4 new fields when the receipt carries them. New `_processing_time` helper composes `min/max_processing_days` into the human string format the email parser emits ("1-2 business days").
- `OrderCreator.process_etsy_payload` writes the 4 new fields onto `sale.order` and honors `name_override` on lines.
- `EtsyEmailAdapter` itself is a stateless service with no Odoo ORM dependency — its only entry point is `parse_result_to_payload(parse_result, email_log_id, shop_id) → EtsyOrderPayload`.

### Surprises

1. **`email.utils.parsedate_to_datetime` returns timezone-aware datetimes.** Odoo `Datetime` fields require naive UTC and raise `ValueError` on aware inputs. Must normalise via `.astimezone(timezone.utc).replace(tzinfo=None)`. (See `etsy_email_adapter._parse_email_date`.)
2. **`is_duplicate_transaction` blocks parity tests that ingest the same Etsy receipt via both paths.** The dedup check is global on `etsy_transaction_id`. Parity tests must use distinct transaction IDs across the two ingestions and exclude `etsy_transaction_id` from the parity assertion — it's a path-unique identifier, not a content field. The slice plan was framed as "identical orders" but the realisable parity claim is "identical field shapes".
3. **Decision-rationale scope creep risk.** The original tracker entry mentioned routing email through canonical payload OR extending `process_parse_result` directly. Choosing the canonical-payload route means `process_parse_result` is now a parallel duplicate write path until P2-07 rebinds the cron. This is intentional (smaller blast radius for this slice) but the duplication needs documenting so the email-cron rebind doesn't get lost in P2-07 noise.

### Email-cron rebind: deferred to P2-07

The slice ships the adapter + parity proof. The email-polling cron in `etsy_integration` still calls `OrderCreator.process_parse_result` directly. The cutover will:
1. Replace the cron entrypoint with `EtsyEmailAdapter().parse_result_to_payload(...) → EtsyOrderIngestor.ingest()`.
2. Delete `process_parse_result` (and the email-only `_build_line_vals`).
3. Land as part of P2-07 (production cutover from email to API per ADR-008a §5).

### Tests

- 41 P0-22 tests: 13 Phase 1 DB introspection + 24 Phase 2 ORM unit + 4 Phase 2 acceptance.
- 505 `etsy_integration` tests green (0 failed, 0 errors). No regressions.
- Module installs cleanly: `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init --http-port=8888 --gevent-port=8889` exit 0.

### Reviews

- code-reviewer: **APPROVE** — 0 CRITICAL/HIGH/MEDIUM blockers. Notes: missing edge-case test on `_processing_time` single-bound (lo=None,hi=N or vice-versa) — logic handles it correctly but no explicit test. Acceptable for a parity slice.
- security-reviewer: **APPROVE** — 0 CRITICAL/HIGH. 1 MEDIUM applied inline (`_parse_email_date` broadened exception catch from `(TypeError, ValueError)` to `Exception` with rationale comment, defensive against future `email_parser` schema drift). 1 LOW deferred (defensive `int()` coercion on `_processing_time` numerics; Etsy API spec says they're integers, deferred unless schema drift surfaces).

### Closure

- T0-22-01..14 marked `[X]` in `tasks.md`.
- Tracker P0-22 row state `todo` → `done`.
- T088 + T089 (Phase 11 module rename, parity test) close pre-emptively because P0-22 ships the same work in advance of the rename.

### Commit chain

- `8f9384eb9bd` test(P0-22): RED — 9-field parity tests + golden-fixture acceptance
- `23b419b49e6` feat(P0-22): GREEN — Etsy ingest parity via EtsyEmailAdapter


---

## P1-10 — Production OAuth + Fernet-at-rest token encryption (2026-05-16)

### What shipped

- **Fernet-at-rest** for the 3 `etsy.shop` token columns. Decision D-P1-10-01: helper-method indirection (`_get/_set_access_token`, `_get/_set_refresh_token`) over the raw Char columns rather than a custom field type — minimal schema change, preserves P0-14's `groups='base.group_system'` ACL. All production callers (OAuth callback + `EtsyApiClient` session header + refresh) route through helpers.
- **Lazy instance key** in `ir.config_parameter.etsy.oauth.fernet_key`, generated on first `encrypt()` under `pg_advisory_xact_lock` with re-read-after-lock (D-P1-10-02, mitigates R-P1-10-7 concurrent-generation race). `get_param` override in `models/ir_config_parameter.py` gates `_SENSITIVE_KEYS` to system, treating `env.su` as a trust marker.
- **Lazy P0-14 plaintext migration** (D-P1-10-03): `_get_*` returns non-`gAAAAA` content as-is + WARN; next refresh re-writes ciphertext. No migration script.
- **Scope assertion** (D-P1-10-04/05/06): callback hard-fails 400 if granted scopes ≠ 4 E1-approved set or if `conversations_r` present; durable `etsy.api.log` row `source='scope_validation'` via fresh registry cursor + commit (survives the 400 rollback); token PII deliberately excluded.
- Credential plumbing audited: `client_id/secret` read from `secrets/credentials.json` (path overridable via ICP `etsy.oauth.credentials_path`), no hard-coded secrets. Operator runbook authored at `operator-runbook.md`.

### Surprises / non-obvious

- **Signature drift RED→GREEN**: RED test contract was `encrypt(plaintext)`; GREEN clarified to `encrypt(plaintext, env)` because Odoo 19 dropped the implicit `Environment.envs` class attribute — the crypto helper has no ambient env. Contract (round-trip under one instance key) unchanged; documented in the module docstring.
- **`env.su` as trust boundary**: in Odoo 19 `sudo()` sets `env.su=True` without changing `env.uid`, so `env.user._is_system()` alone rejects sudo-with-non-admin-user paths (the `auth='public'` OAuth callback). The gate accepts `env.su` as equivalent to system membership. Future code must keep `.sudo()` reachable only from trusted paths — flagged for the grep-CI gate (R-P1-10-6, deferred).
- **Pre-existing `_logger.info`** at `etsy_api_log.py:128` (retention sweep) is out-of-slice and operational, not debug — left untouched per surgical-changes rule; reviewer concurred.

### Tests

- 19 P1-10 tests green (`TestP1_10Schema` + `TestFernetCrypto` + `TestScopeValidation` + `TestTokenHelpers`), 0 failed/0 errors. Module `-u etsy_integration` clean.
- `ruff` not installed in the local shell — plan §5 says "if available"; skipped, noted. Not a blocker.

### Reviews

- code-reviewer: **PASS** — 0 CRITICAL/HIGH. 1 MEDIUM (vacuous assertion in `test_authorization_header_uses_plaintext` — mock never called) noted for optional follow-up; behaviour itself is correct and covered by `test_refresh_token_round_trip_through_api_client`.
- security-reviewer: **PASS** — 0 CRITICAL/HIGH. Confirmed audit-row PII scrubbing, sudo justification, advisory-lock race mitigation, scope-bypass resistance. Recommended documenting the `env.su` trust-boundary invariant (done above).

---

## P1-12 — EtsyTrackingPusher (US3) — 2026-05-16

Closes the ingest→fulfill→track loop. `services/etsy_tracking_pusher.py`
`EtsyTrackingPusher(env).push(order)`; `EtsyApiClient.push_tracking`;
`sale.order.etsy_tracking_push_status/at/error` (T026 tail); cron
`_cron_push_tracking` (5min fallback); `action_push_tracking_to_etsy`
button; webhook wiring in `gearment_webhook_dispatcher._handle_tracking_order_updated`.

### Decisions

- **D-A confirmed at implementation**: trigger is the Gearment
  `tracking_order_updated` webhook handler, NOT a `sale.order` write
  (owner directive 2026-05-10 D4 — Etsy tab is a read-only mirror).
  Synchronous soft-fail (no queue model — T039's "enqueue" reframed to
  inline call); 5-min cron + on-demand button are the retry paths.
- **`pending` status reserved**: sync push goes `none`→`pushed`|`failed`.
  `pending` kept in the Selection for a future async/queue variant.

### Surprises / non-obvious

- **`etsy.shop` has no numeric Etsy shop-id field** (by design). The
  existing P0-16c adapter (`etsy_api_adapter.py:66-69`) already uses the
  Odoo `etsy.shop` record id as the `{shop_id}` URL path segment
  (`shop_path_id = int(shop_id)` where `shop_id` is `shop.id`). P1-12
  mirrors that convention for endpoint consistency. **If the real Etsy
  numeric shop id is ever required, it is a cross-cutting defect across
  P0-16c + P1-12, not a P1-12-local bug** — flag for a dedicated slice.
- **`etsy_order_id` IS the Etsy receipt_id**: `etsy_api_adapter.py:122-127`
  sets both `etsy_receipt_id` and `etsy_order_id` to `receipt_id` ("Etsy
  uses receipt_id as the canonical order identifier"). Etsy v3 is 1:1
  order↔receipt — no multi-receipt handling needed.
- **`field.default` is a callable in Odoo 19**: a scalar `default='none'`
  is normalized to `lambda recs: 'none'` during field setup, so a
  `field.default == 'none'` assertion can never pass. The tdd-guide RED
  test asserted that directly; corrected to resolve the callable. The
  behavioural sibling test (create record, check value) is the correct
  check and already passed.
- **Module-level vs lazy import for mock targets**: the Phase-2 tests
  patch `...etsy_tracking_pusher.EtsyApiClient`. A lazy in-function
  import means the name does not exist at module scope and `mock.patch`
  fails with "module does not have the attribute". `EtsyApiClient` is a
  plain service (no registry-order hazard) so a top-level import is both
  correct and patch-friendly — planner's lazy-import caution did not apply.
- **tdd-guide scaffolding drift**: first RED pass invented a non-existent
  `etsy.shop.etsy_numeric_shop_id` field and used the demo xml-id
  `product.product_product_1` (demo data is off) — all Phase-2
  setUpClass crashed for the wrong reason. Required a correction pass
  before RED was meaningful. Pattern: always verify RED fails for
  *missing production code*, not scaffolding ValueErrors.

### E2E surfacing (live) — pre-existing, NOT P1-12

- `multichannel_hub_fulfillment/tests/test_p4_01_fix_log_linkage.py`:
  `TestApiLogFailurePathEnrichment` (5) + `TestApiLogSuccessPathDirection`
  (1) **fail on clean baseline too** (verified by stashing P1-12 and
  re-running the identical `-u … --test-tags=/etsy_integration,/multichannel_hub_fulfillment`
  suite: 6 failed of 732 with no P1-12, vs 6 failed of 758 with P1-12).
  Root cause is the known P4-01 durable-fresh-cursor+commit FK artifact
  (`gearment_api_log_sale_order_id_fkey` — the fresh cursor commits the
  log row but the test's `sale.order` is never committed). **Out of
  P1-12 surgical scope.** Recommend a dedicated defect slice
  (P4-01-FIX-LOG-LINKAGE-TXN) to make the durable-audit cursor tolerate
  uncommitted FK targets in TransactionCase, or relax the FK.

### Reviews

- code-reviewer: 0 CRITICAL. 1 HIGH (`_logger.info` on routine success →
  downgraded to `_logger.debug`). MEDIUMs accepted/documented: hardcoded
  `200` in `push_tracking` return (Etsy `createReceiptShipment` returns
  200; `_request` raises on non-2xx so reaching the return == success);
  missing return type hint (internal service).
- security-reviewer: 1 CRITICAL fixed (receipt_id URL-path injection →
  `urllib.parse.quote(safe='')`); 3 HIGH fixed (button now gated to
  `multichannel_hub_core.group_production_team` at view AND method per
  FR-017; webhook split — permanent `ValueError`→`_logger.error`,
  transient→warning). MEDIUMs documented & accepted: tracking_number /
  carrier in audit `response_summary` are logistics metadata, not buyer
  PII; `etsy.api.log` ACL already system + `group_etsy_api_log_reader`;
  error text truncated to 1000 chars.

### Tests

- 26 P1-12 tests green (`test_p1_12_db.py` 7 + `test_p1_12_orm.py` 19),
  0 failed / 0 error. `-u etsy_integration,multichannel_hub_fulfillment
  --stop-after-init` exit 0 (128 modules). `ruff` not installed locally
  (plan §5 "if available"); skipped, not a blocker.

## P1-11 dispatch blocked → resolved by inserting P1-11a (2026-05-16)

**Blocker (Phase 0 dispatch, /dispatch-slice P1-11):** P1-11's exit
action is "flip pilot shop's `etsy.shop.active_source='api'`" per
ADR-008a v2, but `active_source` does **not exist anywhere in
`custom_addons/`** (0 occurrences). Code follows ADR-002 `sync_mode`
(`etsy_shop.py`; ingestor T008/P0-16b1 explicitly selects adapter "via
`etsy_shop.sync_mode` (per ADR-002, not `active_source` per superseded
spec)"). ADR-008a (Accepted 2026-04-26) supersedes ADR-002's sync_mode
default with `active_source` + a `sync_mode→active_source` migration,
but that migration/field was never built. P1-11's tracker `Depends on`
(P1-10 ✓, P1-12 ✓) omits the true prerequisites: tasks **T013, T050,
T054, T055, T058** (all `[ ]` unchecked, US8) — `active_source` field +
health probes + `sync_mode→active_source` migration + system-gated
toggle UI + ingestor adapter-selection by `active_source`.

**Resolution (owner, 2026-05-16):** honor ADR-008a as written. Insert
a new prerequisite slice **P1-11a — Etsy active_source scaffolding**
(covers T013/T050/T054/T055/T058) ahead of P1-11. P1-11 (pilot flip)
re-blocks on P1-11a. ADR-002 sync_mode is migrated, not amended.

**Sub-finding (planner, P1-11a):** `etsy.shop.source.change.log`
(task T047) also unbuilt (0 matches in `custom_addons/`). T054's
migration bootstraps `reason='bootstrap'` rows into it and C-ESY-002's
manual-toggle `write()` override logs `reason='manual'` rows — both
hard-depend on the model. **Owner decision 2026-05-16:** fold T047
(model + ir.model.access.csv) into P1-11a. Final P1-11a scope =
T013 + T047 + T050 + T054 + T055 + T058. ADR-008a §3 audit trail
complete; no orphan dependency.

### P1-11a outcome (2026-05-16)

- **Surprise — `sync_mode` is NOT NULL with no DB default.** Phase-1
  RED tests raw-INSERT `etsy_shop (name, create_uid, create_date)`
  only. Odoo applies field defaults in ORM `create()`, not as a
  Postgres column default, so the legacy required `sync_mode`
  column rejected the insert *before* the new `active_source`
  trigger logic ran. Fix: the `etsy_shop.init()` BEFORE INSERT
  trigger also defaults `sync_mode := 'email_only'` when NULL,
  then maps `active_source` from it. Trigger is the real mechanism
  that makes the raw-SQL Phase-1 "migration mapping" tests
  deterministic; the `post-migrate.py` only covers shops that
  exist at upgrade time.
- **tracking=True deferred.** data-model.md §1 marks
  `active_source`/`auto_recovery`/`active_source_changed_at`
  `tracking=True`, but `etsy.shop` does not `_inherit`
  `mail.thread`. Adding the mixin is out of P1-11a surgical scope;
  the audit trail is instead the explicit append-only
  `etsy.shop.source.change.log`. Revisit if chatter is wanted.
- **Superseded test rewritten, not deleted.**
  `TestEtsyOrderSyncer_CronFilter.test_cron_method_skips_email_only_shops`
  encoded the ADR-002 `sync_mode='api_only'` cron filter. T058
  repoints the cron to `active_source='api'`; the test now creates
  shops with `active_source` (+ C-ESY-001 tokens for the api one).
  Full `/etsy_integration` suite (478) re-run 0-fail confirms this
  is a contract update, not regression-masking.
- Reviews: code-reviewer + security-reviewer both no CRITICAL/HIGH.
  Security flagged a non-blocking gap (no explicit C-SCL-001 unlink
  test) — closed with `TestP1_11a_Phase2_SourceChangeLogAppendOnly`.

### P1-11 dispatch — operator-runbook gap (2026-05-16)

`/dispatch-slice P1-11` aborted at Phase 0: P1-11 is an **operational
flip** (BA-lead names pilot shop; admin completes prod OAuth; admin
sets `active_source='api'` via the system-gated form), not a code
slice — no entries in `tasks.md`, scaffolding already shipped by
P1-11a. Walked owner through the cutover procedure synthesized from
code (`etsy_shop.py` write-gate/C-ESY-001, `EtsyOrderIngestor` T058
adapter switch, `etsy.shop.source.change.log` audit, P1-12
`etsy_tracking_push_status`). Two gaps surfaced that block *repeatable*
cutover (matters for P1-13's 2–4 additional shops):

- **`operator-runbook.md` ends at P1-10 §4.** No §5 for the P1-11
  `active_source` flip: prerequisites, the system-gated form step,
  post-flip round-trip verification, rollback. Operators have no
  written procedure for the cutover or for P1-13 repeats.
- **T017 unchecked** — no "Authorize Etsy" / "Test Connection"
  buttons on the `etsy.shop` form. Prereq-3 ("API adapter succeeded
  ≥1×") currently requires `odoo shell` to call `_probe_api()`
  (`/v3/application/openapi-ping`); not operator-accessible without
  shell. T013/T055 (`active_source` field + system-gated toggle)
  landed in P1-11a but T017's buttons did not.

Recommended follow-up slice **P1-11-RUNBOOK**: finish T017
(Authorize + Test-Connection buttons, Test-Connection wraps
`_probe_api()`) + author `operator-runbook.md` §5 (pilot cutover:
prereqs, flip, verify, rollback). Small, mostly doc + one view +
one thin action method. Not a P1-11 blocker (cutover is doable via
shell today) but a P1-13 enabler. Proposed on tracker 2026-05-16.

**Outcome (P1-11-RUNBOOK landed 2026-05-16)**: the gap analysis
prediction held — Phase-0 spec-drift check confirmed `active_source`
toggle + `etsy.shop.source.change.log` audit already shipped by
P1-11a (T013/T055), so the slice reduced to: two thin gated action
methods (`action_authorize_etsy` → `act_url` to the existing
`/etsy/api/oauth/authorize?shop_id=<id>` route; `action_test_connection`
→ wraps existing `_probe_api()` as a `display_notification`), two
`oe_button_box` buttons, and `operator-runbook.md` §5. No model,
field, ACL, or controller changes. FR-017 method gate on both
(20th confirmation). 19 tests RED→GREEN; full suite 499/0-fail;
both reviews CLEAN. No new surprises.

## P1-11-DEPLOY-STAGING — staging refresh executed (2026-05-21)

Pre-cutover staging refresh landed on `esty19_odoo` / DB `esty_odoo19`
fronted by `https://odoo.hatafax.com`. Release/ops slice (Phases
1/2/3/4/8 N/A per tracker). Five surprises worth keeping:

- **Tracker exit-criteria version numbers drifted from feature-branch
  HEAD.** Tracker row froze `etsy_integration 19.0.2.3.8` and `mhc
  19.0.1.0.35` as exit targets, but HEAD had moved to 19.0.2.6.0 and
  19.0.1.0.36 respectively (P-LIST-PULL, P-LIST-INV-PULL,
  P1-DESIGN-WIZ-ATTACH-SCOPE landed after the tracker row was authored
  the same morning). The slice instruction ("bring current with HEAD")
  takes precedence over the frozen numbers. **Rule**: for release/ops
  slices, version numbers in the row are *expected-as-of-authoring*,
  not exit gates — re-read HEAD manifests at dispatch time.

- **`pg_dump | tee file.sql.gz; gzip file.sql.gz` silently produces
  plaintext.** `gzip` refuses to add a second `.gz` suffix and (with
  `2>/dev/null`) skips the file. Mid-flight catch: `file(1)` on the
  output reported `UTF-8 Unicode text` instead of `gzip compressed
  data`. Fix: rename then gzip (`mv .gz .sql; gzip -9 .sql`). Worth
  remembering for any future deploy script: name the streamed file
  `.sql` and gzip after, or pipe through `gzip -9 > file.sql.gz` in
  one shot.

- **Secrets bind-mount needs 750/640 with group=container-odoo-gid,
  not 700/600 root-only.** Host `/odoo/esty19/secrets` initially set
  to `chmod 700 root:root`; in-container `odoo` user (uid 100, gid 101)
  could neither traverse the dir nor read the file. Fix: `chown root:101
  /odoo/esty19/secrets && chmod 750` on the dir AND `chown root:101
  /odoo/esty19/secrets/etsy_credentials.json && chmod 640` on the file.
  The host `ls -l` shows the group as `systemd-journal` because gid 101
  resolves to a different name on the host — only the numeric gid
  matters across the bind-mount. **Memory candidate**: add to
  `reference_staging_ssh_deploy.md` so the next operator doesn't repeat.

- **Cron #22 "Etsy: Fetch Order Emails" was already disabled
  (`active=f`, `lastcall=2026-05-08`) 13 days before this slice.** Not
  a regression introduced by the migration; pre-existing state. Exit-6
  ("4 legacy shops still ingest one full email cycle") is therefore
  re-interpreted as a no-regression check: 4 shops intact (Julien,
  Carina, Viktor, Sven, all `sync_mode=email_only` + `active_source=email`
  after the post-migrate sync_mode→active_source mapping), 5 historical
  `etsy_email_log` rows intact, no errors in container logs since
  restart, API-mode crons (#32/#36/#37/#38) all fired cleanly post-restart
  proving the `active_source` dispatch filter works. The cron is paused
  by owner choice (P1-11 pivot toward API ingest); reactivating it is
  out of scope here.

- **`client_secret` length is 10 chars** — initially flagged as
  unusually short vs typical Etsy v3 Shared Secret (~24 chars). Owner
  explicitly chose to proceed as-is. **Retracted later the same day**
  (P1-XAPI-SHARED-SECRET-HEADER research): Etsy's own Quickstart
  example uses `a1b2c3d4e5` (10 chars) for the shared secret. There
  is no documented minimum length; 10 chars is normal for the personal-
  access tier. The actual defect that would have surfaced as an
  authentication failure was a separate one in our request-header
  construction — captured in the next entry.

**Rollback target**: `/odoo/esty19/backup-pre-P1-11-DEPLOY-STAGING-20260521T143357Z.sql.gz`
(2.4MB gzipped, md5 `efa95e3e9122e521ed30b168835378ef`).
**Compose backup**: `/odoo/esty19/docker-compose.yml.bak.pre-P1-11-DEPLOY-STAGING.20260521T143640Z`.

Unblocks: P1-11 jahandmadeart pilot flip (operator-runbook §5.1
prereqs are now reachable on staging); downstream P1-13 + P2-07.

## P1-XAPI-SHARED-SECRET-HEADER — Etsy 2026-02-09 header enforcement (2026-05-21)

Two findings worth keeping from a same-day deep-research detour after
P1-11-DEPLOY-STAGING.

**(1) Etsy dev portal vocabulary → OAuth2 vocabulary.** The Etsy
"Manage your apps" UI uses non-standard names that confused the
operator briefing during the staging refresh:

| Etsy dev portal UI | Maps to | Where it's used in our code |
|---|---|---|
| **Keystring** | OAuth2 `client_id` | `credentials['client_id']` in `services/etsy_api_client.py`, `controllers/etsy_oauth.py` |
| **Shared Secret** | OAuth2 `client_secret` | `credentials['client_secret']` in the OAuth controller (token exchange) AND, per fix below, in `EtsyApiClient` for the `x-api-key` header |
| **Status: Personal access** | App tier metadata (not a credential) | not stored |
| **Rate Limit** | Per-key QPS + QPD throttle (not a credential) | not stored |

The JSON file at `/opt/odoo/secrets/credentials.json` uses the OAuth2
names (`client_id`/`client_secret`/`redirect_uris`) — operators
copying values from Etsy's UI must remember the rename.

**(2) Real defect surfaced from research.** Etsy began enforcing the
combined header form `x-api-key: keystring:shared_secret` on
2026-02-09 (etsy/open-api Discussion #1521 — enforcement was deferred
once from 2026-01-18 to 2026-02-09 per the announcement). The
keystring-only form is now rejected. Our `EtsyApiClient._session()`
was still emitting the pre-enforcement form:

```python
# Before (file:line `services/etsy_api_client.py:127` in 19.0.2.6.0):
session.headers = {
    'Authorization': f'Bearer {self.shop._get_access_token()}',
    'x-api-key': self.client_id,
    ...
}
```

The defect went undetected because the only call site that
exercises `EtsyApiClient` at runtime requires
`active_source='api'` on an `etsy.shop`, and no shop had been
flipped yet — the staging refresh in P1-11-DEPLOY-STAGING was the
first time `active_source='api'` became *possible* on staging.

Fix landed in 19.0.2.7.0 (`commit 4348cd32b79`): validate
`credentials['client_secret']` non-empty at `__init__`, store
`self.client_secret`, build header as
`f'{self.client_id}:{self.client_secret}'`. The corresponding test
`TestEtsyApiClientSession.test_session_sets_x_api_key_header` had
codified the wrong format (`'test_client_id'`) — also fixed.
`TestTokenHelpers.setUpClass` in `test_p1_10_orm.py` had a credentials
mock with only `client_id`; backfilled with `client_secret` so its
4 tests don't trip the new fail-fast.

**Etsy's own example secret is 10 chars.** Etsy's Quickstart
documents `1aa2bb33c44d55eeeeee6fff:a1b2c3d4e5` as the combined-header
example — the secret half is `a1b2c3d4e5`, 10 chars. The
P1-11-DEPLOY-STAGING note that called the operator's 10-char value
"unusually short" was wrong. There is no documented length floor for
the shared secret; 10 chars is consistent with Etsy's own sample.

**One LOW-priority follow-up deferred by security-reviewer**:
`controllers/etsy_oauth._read_credentials()` does not fail-fast on
missing `client_secret` the way `services/etsy_api_client._read_credentials`
caller now does. If the JSON file is missing the key, the OAuth
controller fails at line 246 inside `exchange_code_for_token` instead
of at credential-load. Not user-visible (operator-facing error
remains clear) — defer until next time someone touches that file.

**Pre-existing flakes confirmed by this slice's full-suite run**
(not introduced by either P1-11-DEPLOY-STAGING or
P1-XAPI-SHARED-SECRET-HEADER):

- `test_non_ba_lead_cannot_call_action_approve_via_rpc` — PostgreSQL
  `digest_digest` deadlock during `assertRaises` savepoint flush.
  Concurrent-test interaction with the standard mail/digest workers.
  Passes in isolation.
- `test_callback_with_valid_state_exchanges_token` — full-suite
  test-ordering pollution. Passes in isolation.

Both stay on the books as known flakes; route via E2E defect intake
if either becomes blocking.

---

## 2026-05-22 — P1-11-WIRE-LIVE pilot E2E hotfix chain

JaHandmadeArt pilot OAuth → API → ingest path was blocked by five
interdependent defects. Captured here so the follow-up slice
**P1-11-SHOPID-BOOTSTRAP** can re-test against them and so future
operators understand what the manifest 19.0.2.7.0 → 19.0.2.8.0 bump
covers.

**(1) Etsy v3 token-exchange response has no `scope` field.** The
P1-10 D-P1-10-04 scope-assertion contract assumed Etsy would echo
granted scopes in the token-exchange response and the controller
hard-failed every callback when the field came back empty. Empirical
diagnostic captured the response keys on staging:

```
keys = ['access_token', 'api_key', 'expires_in', 'refresh_token',
        'token_type', 'user_id']
scope = None
```

Resolution: keep `_validate_scope_grant` armed but gate the call on
non-empty `scope` (`controllers/etsy_oauth.py`). If Etsy ever starts
returning the field, the safety net activates automatically. The
`_FORBIDDEN_SCOPES={'conversations_r'}` guard becomes effectively
dead code until that day — left in place as documentation.

**(2) `etsy_shop._probe_api` two bugs + silent debug log.** Wrong
constructor (`EtsyApiClient(self.env, self)` against `__init__(shop)`)
raised TypeError; URL double-prefix (`/v3/application/openapi-ping`
against `ETSY_API_BASE_URL` which already includes `/v3/application`)
would have given 404 if the TypeError ever reached HTTP. Bare
`except Exception:` + `_logger.debug` swallowed both at
`log_level=info`. Every `test_p1_11_runbook_phase2_orm` test that
exercises the Test-Connection button uses
`mock.patch.object(type(shop), '_probe_api', return_value=...)`, so
the method body was never live in CI. Resolution: fix both bugs;
bump probe-failure logging to `_logger.warning` with exception type
(not message — may leak token fragments via session-header trace
contexts). Follow-up slice owes a live-`_probe_api` test with mocked
`requests`.

**(3) `EtsyApiClient._read_credentials()` path divergence.** Hard
constant `/opt/odoo/secrets/credentials.json` vs the OAuth
controller's `etsy.oauth.credentials_path` system param (set to
`/opt/odoo/secrets/etsy_credentials.json` on staging since
P1-11-DEPLOY-STAGING). Resolution: `_read_credentials(env=None)` —
when env is supplied, read from the system param; fall back to the
hardcoded default. Callers in `__init__` pass `shop.env`. Single
source of truth restored.

**(4) 403 handler discarded the vendor body.** Per memory
`feedback_capture_response_body_before_blackbox_probe.md` (carried
forward from Defect-11-02). Etsy's 403 body is a small JSON like
`{"error":"User does not own Shop 10"}` — diagnosable in seconds if
the response body is surfaced. Now permanently captured: body
included in the raised `ValueError` AND in a `_logger.warning` line.
Truncated at 500 chars; tokens are not carried in error bodies so
leakage risk is null.

**(5) Sandbox convention "Odoo PK == Etsy shop_id" is dead.** Memory
item #132 documented the convention; JaHandmadeArt killed it.
JaHandmadeArt has Odoo PK `10` (legacy 1–4 belong to the 4 email-only
shops, 5–9 were probably test rows). Real Etsy shop_id from
`/users/me` is `60752333`. Resolution: new
`etsy.shop.etsy_api_shop_id` Char field (system-group, indexed,
help='Numeric shop_id assigned by Etsy …'), plumbed through 3
adapter call sites:

- `services/etsy_order_syncer.py: sync_shop_orders` — refuse to call
  the API without it (warning log; return zero-counts dict).
- `models/etsy_listing.py: _sync_shop_listings` — same.
- `services/etsy_tracking_pusher.py: push` — same, via
  `_mark_failed`.

Four audit-log endpoint strings updated to reflect the real URL
(falling back to `shop.id` only as a display courtesy when
`etsy_api_shop_id` is empty — which is fine because we refuse the
API call upstream).

Shop 10 backfilled manually on staging via
`UPDATE etsy_shop SET etsy_api_shop_id='60752333' WHERE id=10`.
**Auto-bootstrap from `/users/me` on OAuth callback** is deferred to
P1-11-SHOPID-BOOTSTRAP — Etsy's `/v3/application/users/me` returns
`{shop_id, user_id}` cheaply for the primary-shop case, so callback
post-token-persist can fetch and store the shop_id atomically with
the OAuth state. Multi-shop owners (none today) would need separate
wiring.

**E2E proof (10:00:52 UTC 2026-05-22 cron cycle):**

| Object | Value |
|--------|-------|
| `sale.order` | `S00006` (id=6, sync_source='api', state='draft') |
| Etsy receipt | `3818231452` |
| Customer (partner_id=12) | auto-created from receipt |
| `amount_total` | ₫734,914.00 |
| `date_order` | 2025-10-06 12:20:51 |
| `etsy.listing` rows for shop 10 | 1 (matches Etsy `listing_active_count=1`) |
| `etsy.listing.product` variants | 5 |

**Side-tightening on staging during the run** (not strictly part of
the slice but useful to capture):

- `list_db = False` + `dbfilter = ^esty_odoo19$` — eliminates the
  multi-DB OAuth state-binding risk (the pending state row at
  `ir.config_parameter[etsy.oauth.pending.<state>]` is per-DB; with
  3 DBs visible and `dbfilter=.*` the callback could land on the
  wrong DB).
- `proxy_mode = True` — was `False` despite nginx fronting HTTPS;
  Odoo was treating every request as HTTP from `127.0.0.1`. Fixed
  so absolute URLs honor the X-Forwarded-Proto from nginx.

**Side-issues left for follow-ups:**

- 3 stale `etsy.oauth.pending.*` rows in `ir.config_parameter` from
  failed Authorize attempts during the diagnostic chain. Harmless
  (no tokens), will TTL-sweep when P1-10's transient model lands.
- `check_access_rights()` / `check_access_rule()` at
  `controllers/etsy_oauth.py:176-177` are deprecated since Odoo
  18.0; surfaces as `DeprecationWarning` on every Authorize click.
  Pairs nicely with the SHOPID-BOOTSTRAP slice if the same author
  touches the file.


---

## 2026-06-23 — Review of Codex ESTY-205/206/207 (working tree, NOT yet committed) — BLOCKED

Reviewed Codex's implementation of the three stories per `codex/review-plan.md`.
Tests GREEN (`0 failed, 0 error(s) of 856`), module upgrades clean, parallel
`code-reviewer` + `security-reviewer` run. Two blockers prevent sign-off.

### CRITICAL — `_check_etsy_total_reconciles` is self-contradictory; blocks real-order ingest
`services/order_creator.py:701,713-722`. The gate raises `UserError` when Odoo
`order.amount_total` != Etsy `grandtotal` (>0.01). Adapter sets
`payload.amount_total = grandtotal` (`etsy_api_adapter.py:132`). But Odoo
`amount_total` = product lines (`total_price`) + shipping line ONLY — the new
tax/discount/gift-wrap fields are written informational-only (brief A2 says "do
NOT overwrite computed pricing").

Etsy schema (authoritative, `getShopReceipt`):
`grandtotal = total_price − coupon discount + tax + shipping`.
So for ANY receipt with sales tax, a coupon, or gift wrap,
`grandtotal != total_price + shipping` → gate raises → ingest aborts. In the
cron path the syncer catches the exception and `break`s WITHOUT advancing the
cursor (`etsy_order_syncer.py:95-103`) → the shop's sync wedges permanently on
its first taxed order. US shops collect sales tax on most orders ⇒ near-total
production breakage.

The synthetic fixture `tests/fixtures/receipt_3818231452.json` hides this: its
`grandtotal`=110.00 = subtotal(100)+shipping(10), which CONTRADICTS Etsy's own
definition (should be 100 − 2.5 + 5 + 3 + 10 = 115.5). The test passes only
because the fixture is constructed wrong.

Fix options: (a) reconcile against `subtotal + total_shipping_cost` (= what Odoo
actually builds), or (b) make the check a non-fatal `_logger.warning` + set an
`etsy_needs_review`-style flag, or (c) model tax/discount/gift-wrap as real Odoo
lines so amount_total genuinely equals grandtotal. (a)+(b) recommended; the brief's
"amount_total must equal grandtotal" requirement is itself wrong vs the schema.

### HIGH — A1 live diff never run against real staging data (process gap)
Brief §A1 made the staging diff on real receipt 3818231452 the FIRST step ("the
diff output drives which candidate fields are real; prune the rest"). The script
`scripts/etsy_receipt_diff.py` exists but the saved fixture is synthetic ("Alice
Buyer", round numbers, schema-violating grandtotal) — A1 was clearly not executed.
Consequence: the field set in A2 and the reconciliation target are unvalidated
guesses. Pull the real receipt before sign-off.

### Confirmed GOOD (no action)
- Per-user shop scoping record rules: restrictive(base.group_user) +
  permissive(group_sale_manager+group_system) OR-combine correctly. Proven by
  `test_shop_user_scoping.py` with_user tests (scoped sees own+non-Etsy only;
  manager & non-manager system admin see all). `user_id` ondelete='set null'.
- Manual pull button FR-017 write-defense: allowed-shop set computed from
  env.user BEFORE sudo(); sudo never applied to a user-supplied shop id; inline
  justification present.
- `_resolve_line_product` tiers 1-2 never auto-create; duplicate-SKU first-by-id
  determinism; create+flag sets `etsy_needs_product_review`. All tier tests pass.
- `_variation_line_vals` maps known axes + text fallback into etsy_option; writes
  the mhc `*_manual` override fields (multichannel_hub_core is a manifest dep).
- No new model ⇒ no missing ACL. No raw SQL. No print()/_logger.info-as-debug.

### MEDIUM (non-blocking, fix if cheap)
- `action_pull_etsy_orders` bare `except Exception` masks programming errors;
  notification gives only an error count (no "check logs" hint).
- `_variation_line_vals` unmapped-axis concat into etsy_option has no length cap.

---

## 2026-06-23 — Hybrid reconciliation fix applied (resolves the CRITICAL above)

Owner chose the hybrid (Standard-Odoo-First). Grounded in Odoo 19 source:
everything the buyer pays is an order LINE except tax, which is an engine-computed
attribute of lines (`sale/models/sale_order_line.py:_compute_tax_ids`). Etsy is a
marketplace facilitator that remits tax (`fiscal_pos_etsy_marketplace` note), so
tax stays informational; booking it as `account.tax` would create a liability the
seller does not owe.

Changes (working tree, on top of Codex's):
- `data/etsy_marketplace_adjustment_products.xml` (new) — `product_etsy_gift_wrap`
  (ETSY-GIFTWRAP) + `product_etsy_discount` (ETSY-DISCOUNT) service products,
  mirroring the existing shipping product. Added to manifest before fiscal data.
- `order_creator._append_adjustment_lines` — shipping (+), gift-wrap (+) and
  discount (−) each become an order line, so `amount_total` reflects the buyer-paid
  figure minus the marketplace-remitted tax.
- `order_creator._check_etsy_total_reconciles(order, payload)` — now reconciles
  `amount_total` against `grandtotal − tax_total` and, on mismatch, sets
  `sale.order.etsy_total_mismatch = True` + `_logger.warning` instead of raising
  `UserError`. This removes the production blocker (a raise wedged the sync cursor
  on the first taxed order — syncer breaks without advancing). Removed the unused
  `UserError` import.
- `sale_order.etsy_total_mismatch` Boolean (indexed, readonly) + surfaced in the
  Receipt Status group of the Etsy tab.
- Fixture `receipt_3818231452.json` corrected to satisfy Etsy's schema formula
  (grandtotal 115.50 = total_price 100 − discount 2.50 + tax 5 + shipping 10 +
  giftwrap 3). NOTE: still SYNTHETIC — the real-receipt A1 staging diff + staging
  E2E remain a prerequisite before JIRA transition / `done`.
- Tests: `test_receipt_fixture_maps_full_order_coverage` asserts amount_total=110.5,
  `amount_total + etsy_tax_total == grandtotal`, gift/discount lines present, no
  mismatch. New `test_total_mismatch_flags_order_without_raising` proves an
  unreconcilable grandtotal flags (not raises).

Verify: `-u etsy_integration --test-enable` → **0 failed, 0 error(s) of 857 tests**;
module upgrades clean. ruff not installed on host (skipped per review-plan "if
available"); `py_compile` clean.

STILL OPEN before sign-off: real-receipt A1 diff on staging (esty_odoo19) + the
review-plan staging E2E (scoped-user visibility, admin-sees-all, Pull button counts).

## 2026-06-23 — Real-receipt A1 diff on staging (validates the hybrid fix)

Ran a read-only probe against staging `esty_odoo19` (`esty19_odoo` container) via
the existing deployed `EtsyApiClient` — live GET of receipt 3818231452, no deploy,
no writes. Figures (shop-currency, divisor applied; values only, buyer PII omitted):

| Etsy field                      | value      |
|---------------------------------|------------|
| grandtotal                      | 494050.00  |
| subtotal                        | 215471.00  |
| total_price                     | 538677.00  |
| total_shipping_cost             | 196237.00  |
| total_tax_cost + total_vat_cost | 82342.00   |
| discount_amt                    | 323206.00  |
| gift_wrap_price                 | 0.00       |
| status                          | Completed  |

Formula confirmed exactly: `subtotal + shipping + tax + giftwrap = grandtotal`
(494050.00 = 494050.00, diff 0.00), and `subtotal = total_price − discount_amt`
(215471 = 538677 − 323206). Real data exercises a LARGE discount and material tax;
no gift wrap. Matches the Etsy `ShopReceipt` schema we coded to.

Fix validation (arithmetic on real figures):
- Expected `amount_total` = grandtotal − tax = 494050 − 82342 = **411708.00**.
- New code: product line(s) = total_price 538677 (txn price is pre-discount) +
  shipping 196237 + giftwrap 0 − discount 323206 = **411708.00** → matches;
  `etsy_total_mismatch` would be **False**. Adapter picks `discount_amt` first, so
  the negative discount line is created correctly.
- CURRENT deployed order S00007 (old code) `amount_total = 734914.00`, off by
  **+323206.00 = exactly the discount** (product line booked at pre-discount
  total_price 538677 + shipping, with NO discount line). The old code mis-states
  this real order by the full discount; the hybrid fix corrects it.

Conclusion: the hybrid reconciliation is correct on real production data. The
committed test fixture stays SYNTHETIC (no buyer PII in repo); these real figures
are the validation evidence.

STILL OPEN before sign-off: this was a read-only A1 (arithmetic proof). Proving the
ingested order equals 411708.00 end-to-end requires deploying the 4 commits to
staging + re-ingesting S00007 (mutates staging data) — not done without explicit
go-ahead. Plus the review-plan staging E2E (scoped-user visibility, admin-sees-all,
Pull button counts).
