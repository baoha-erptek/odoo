# Regression prompt — verify the 2026-06-21 session didn't break anything

> Paste the block below into a **fresh session** to run a full regression sweep
> across all module test suites and confirm this session's changes are safe.
> Written 2026-06-21. Self-contained.

```
Run a FULL regression sweep on the odoo19_esty project to confirm the 2026-06-21
session's changes did not break any pre-existing behaviour. Work LOCAL-FIRST
(db namco_odoo19, container namco_odoo19, http://localhost:8169, admin/admin).

BRANCH: feature/006-master-plan-coding (do NOT branch).

WHAT CHANGED THIS SESSION (3 code changes across 2 modules — scrutinize these):
1. Phase C (c0fdfbb) — multichannel_hub_core/views/product_template_views.xml:
   added 2 inherits of stock views hiding the `operations` group, description
   note blocks, and `responsible_id` behind groups="base.group_no_one". VIEW-ONLY.
2. D#8 (6c10014) — multichannel_hub_fulfillment:
   - models/sale_order_fulfillment.py: +5 fields (gearment_order_ref related,
     gearment_last_webhook_at/topic, etsy_tracking_pushed/_at).
   - services/gearment_webhook_dispatcher.py: _inbound_stamp() merged into the 4
     business handlers; _handle_tracking_order_updated NOW ALWAYS WRITES (was
     `if vals:`) + sets etsy_tracking_pushed after a successful EtsyTrackingPusher.push.
   - views/sale_order_fulfillment_views.xml: new form/list/menu.
3. D#3 wizard fix (b02af9d) — multichannel_hub_core/wizards/order_pipeline_transition_wizard.py:
   added default_get override seeding pipeline_id + current_state_id.

HIGHEST REGRESSION RISK (check first): the dispatcher's
_handle_tracking_order_updated now writes unconditionally (even with no tracking
number/url) and does a second write on Etsy-push success. Any pre-existing test
asserting "no fulfillment write when payload has no tracking" would break. The
new-field writes are NOT in _BUS_TRIGGER_FIELDS / _ADDRESS_LOCK_FIELDS, so no bus
or FR-017 side effects — confirm that holds.

STEP 1 — establish the BEFORE baseline (changes reverted):
  Run the suites at the pre-session freeze commit 591498a1df2 (parent of c0fdfbb)
  in a throwaway worktree so the live DB/registry is untouched, OR just trust the
  freeze was green (the contract froze at "12 tests 0 failed"). Recommended: use a
  git worktree at 591498a to run the 3 suites and record pass counts, then discard.
  (using-git-worktrees skill; the worktree shares the same DB — run with a separate
  --http-port to avoid clashes and DO NOT -u against the shared DB from two trees.)

STEP 2 — run the AFTER suites (current HEAD) and confirm all green:
  # IMPORTANT: -u reloads schema; run each module's FULL suite, not just new classes.
  docker exec namco_odoo19 odoo -d namco_odoo19 \
    -u multichannel_hub_core,multichannel_hub_fulfillment,etsy_integration \
    --test-enable \
    --test-tags /multichannel_hub_core,/multichannel_hub_fulfillment,/etsy_integration \
    --http-port 8170 --no-http --stop-after-init 2>&1 | grep -iE "tests when loading|FAIL:|ERROR.*test_"

  Then per-module (clearer attribution if the combined run shows failures):
  for m in multichannel_hub_core multichannel_hub_fulfillment etsy_integration; do
    docker exec namco_odoo19 odoo -d namco_odoo19 -u $m --test-enable \
      --test-tags /$m --http-port 8170 --no-http --stop-after-init 2>&1 \
      | grep -iE "tests when loading database 'namco"
  done

STEP 3 — install-clean check (exit 0):
  docker exec namco_odoo19 odoo -d namco_odoo19 \
    -u multichannel_hub_core,multichannel_hub_fulfillment,etsy_integration \
    --http-port 8170 --no-http --stop-after-init ; echo "exit=$?"

SUCCESS CRITERIA:
  - Every module suite: 0 failed, 0 error.
  - Install exit 0.
  - No NEW failures vs the BEFORE baseline (a test red both before and after is a
    pre-existing flake, not a regression — note it, don't chase it).

IF A TEST FAILS: triage whether this session's 3 changes caused it (most likely the
dispatcher always-write change). If a real regression, STOP and fix minimally with a
regression test, re-run, commit `fix(regression): ...`. If a pre-existing flake,
document it in findings and move on.

GOTCHAS (learned 2026-06-21, all in auto-memory):
- After ANY `-u ... --stop-after-init`, the live web server keeps a STALE registry;
  `docker restart namco_odoo19` before any /browse or /qa. (Not needed for headless
  test runs, which spawn their own process.)
- In-container tests need `--http-port 8170 --no-http` to avoid the 8069 clash.
- assertRaises opens a savepoint that rolls back except-block writes (memory).
- A wizard M2O domain on a `related` field needs the related seeded in default_get
  (this session's D#3 fix; memory feedback_wizard_domain_on_related_field_needs_default_get_seed).

After regression passes, update CONTRACT-v1.0.md §3 verification line + UAT gates,
and report the before/after pass counts.
```
