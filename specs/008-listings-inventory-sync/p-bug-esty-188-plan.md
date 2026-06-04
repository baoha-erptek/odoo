# P-BUG-ESTY-188 — createListing 400 fix plan

**Slice**: `P-BUG-ESTY-188` (Sub-phase 3h, Wave 1)
**Jira**: ESTY-188 (6.11b - "Lỗi Bug ko publish listing lên Etsy được")
**Branch**: `feature/006-master-plan-coding`
**Planner**: opus (planner agent, 2026-06-04)
**Status**: Phase 1 plan landed; awaiting owner approval to proceed to Phase 2 (RED)

---

## Root-cause hypothesis (highest confidence)

**Staging shop JaHandmadeArt (`etsy_api_shop_id=60752333`) has a NULL `default_readiness_state_id`**, triggering Etsy's "A readiness_state_id is required for physical listings" 400 response from `POST /v3/application/shops/60752333/listings`.

### Evidence chain

1. **Memory** `reference_etsy_createlisting_2025_readiness.md` item (1) documents the exact failure mode: "createListing 400s without `readiness_state_id` for physical listings; each push_inventory offering must also carry it." JaHandmadeArt's known real value: `1406133708616`.

2. **Code** — field exists and was added in `19.0.2.15.0`:
   - `custom_addons/etsy_integration/models/etsy_shop.py:95-101` defines `default_readiness_state_id` as `Char` (correct for int64 Etsy IDs that overflow XML-RPC int32 — see memory entry 144).
   - `custom_addons/etsy_integration/services/etsy_listing_publisher.py:237-238` includes the field in the createListing payload **only when truthy** — so a NULL on the shop omits the key entirely, which Etsy rejects.
   - `custom_addons/etsy_integration/services/etsy_api_client.py:277` already carries a comment referencing the exact "A readiness_state_id is required for physical listings" error message — strong signal this exact 400 has been seen before.

3. **Data gap** — `custom_addons/etsy_integration/data/demo_data.xml` demo shops lack the field; no migration ever bootstrapped it for existing-on-staging shops created BEFORE `19.0.2.15.0` shipped.

4. **Test coverage gap** — all Phase 2 ORM tests under `tests/test_phase2_pub_draft_orm.py:46-64` mock the Etsy client, so they never hit the real API where this would fail. A test that asserts the payload key is **present** (not just that the field exists on the model) would have caught this.

### Why this is more likely than candidate #1 (personalization regression)

Personalization fields were gated OFF in commit `643370c9837` (per memory item (2)). The planner verified that gating is still on HEAD; without it, every createListing call (not just owner's) would 400. The bug appears to be shop-specific (staging JaHandmadeArt) which fits "data missing on this shop" better than "code regression affecting all shops".

### Fallback if hypothesis is wrong

If the `psql` discovery step (below) shows `default_readiness_state_id` IS already `1406133708616` on shop 60752333, pivot to:
- **Candidate #2 (inventory offerings missing readiness)**: each push_inventory offering must ALSO carry `readiness_state_id` per same memory. Verify `EtsyInventoryPusher.push` threading.
- **Candidate #3 (new 2026 mandatory field)**: capture the 400 response body verbatim per `feedback_capture_response_body_before_blackbox_probe.md` and grep `~/.cache/etsy-developer-docs/documentation_tutorials_listings.md` for any new required field.

---

## Discovery step — GO-condition-zero (run BEFORE any code changes)

```bash
# Per reference_staging_ssh_deploy.md
ssh -i secrets/ssh-key-2023-02-24.key ubuntu@129.150.63.207

# Query: is the field NULL on the failing shop?
sudo docker exec esty19_odoo psql -U odoo -d esty_odoo19 -c \
  "SELECT id, name, etsy_api_shop_id, default_readiness_state_id
   FROM etsy_shop WHERE etsy_api_shop_id='60752333';"
```

**GO condition**: result row shows `default_readiness_state_id IS NULL` or `''`.
**NO-GO** (field already populated): pivot to candidate #2 or #3 — re-plan, capture the 400 body via Etsy app logs or a probe script before changing code.

Capture the response body alongside the psql output regardless. The 400 body is the source of truth (`feedback_capture_response_body_before_blackbox_probe.md` rule).

---

## Files to modify

| File | Reason |
|------|--------|
| `custom_addons/etsy_integration/migrations/19.0.2.31.0/post-migrate.py` (new) | Bootstrap `default_readiness_state_id` on existing shops by calling `GET /shops/{shop_id}/readiness-state-definitions` and writing the first definition's id. Skip email-only shops. Per-shop try/except so one failure doesn't block the migration. |
| `custom_addons/etsy_integration/data/demo_data.xml` | Add `<field name="default_readiness_state_id">1406133708616</field>` to demo shop records (defensive — for fresh installs on dev DBs). |
| `custom_addons/etsy_integration/__manifest__.py` | Bump version to `19.0.2.33.0` (per existing pattern). |
| `custom_addons/etsy_integration/tests/test_p_bug_esty_188_phase1_db.py` (new) | Phase 1 DB tests (see test plan). |
| `custom_addons/etsy_integration/tests/test_p_bug_esty_188_phase2_orm.py` (new) | Phase 2 ORM tests (see test plan). |
| `custom_addons/etsy_integration/tests/__init__.py` | Register both new test modules (memory entry: tdd-guide skips this; orchestrator must add). |

---

## Two-phase test plan

### Phase 1 (direct DB verification)

`tests/test_p_bug_esty_188_phase1_db.py`:

- `test_default_readiness_state_id_column_exists` — query `information_schema.columns` for `(table_name='etsy_shop', column_name='default_readiness_state_id')`; assert row exists.
- `test_default_readiness_state_id_is_char_not_int` — assert `data_type IN ('character varying', 'text')` (Etsy IDs overflow int32 — memory entry 144).
- `test_migration_19_0_2_33_0_post_migrate_file_exists` — file is at `migrations/19.0.2.33.0/post-migrate.py`. RED until migration written.

### Phase 2 (ORM unit tests with mocked Etsy client)

`tests/test_p_bug_esty_188_phase2_orm.py`:

- `test_payload_includes_readiness_state_id_when_set` — `shop.default_readiness_state_id = '1406133708616'` → payload dict has `'readiness_state_id': 1406133708616` (int cast). RED until publisher payload cast is added — actually it's already there at publisher.py:237-238 but verify the cast type is correct.
- `test_payload_omits_readiness_state_id_when_null` — `shop.default_readiness_state_id = False` → key NOT in payload (legacy sandbox compat preserved).
- `test_post_migrate_bootstraps_existing_shops` — invoke post-migrate function directly on a shop missing the field + mocked `client.get('/shops/{id}/readiness-state-definitions')` returning `[{'readiness_state_definition_id': 1406133708616, ...}]`; assert shop.default_readiness_state_id is now `'1406133708616'`.
- `test_post_migrate_skips_email_only_shops` — shop with `active_source='email'` should not be touched.
- `test_post_migrate_swallows_per_shop_failures` — mock the API call to raise; assert the migration completes for OTHER shops without re-raising.
- `test_demo_data_shops_have_readiness_state_id` — assert demo_data.xml-installed shops have non-empty `default_readiness_state_id` after fresh install.

**RED-quality discipline**: per memory entries 147–154, the tests MUST be confirmed failing with the EXPECTED error message before GREEN. Run the suite. Inspect the failure tail. If a test passes for the wrong reason (e.g. `assertEqual(field, 0)` on a NULL Integer coerced to 0 — entry 154), force-fail it via a wrong-default assertion first, then write the real one.

---

## Risk register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Post-migrate fails on shops without OAuth tokens (refresh expired) | Medium | Medium | Skip shops where token refresh fails; log WARNING per-shop; continue. |
| Hypothesis wrong (shop field already set) | Low | High | psql discovery step gates Phase 2; pivot to candidate #2 or #3. |
| Etsy `/readiness-state-definitions` rate-limits during migration | Low | Medium | One call per shop, small N; sequential with existing 429 retry in `EtsyApiClient`. |
| Demo shops don't get updated on `-u` (noupdate seed never lands on existing DBs — memory `feedback_etsy_inventory_property_name_and_noupdate_seed.md`) | Medium | Low | Demo shops use `noupdate=0` for this field OR the post-migrate also handles demo shop names. Decide during Phase 2 RED. |
| 400 is intermittent (rate limit masquerade) | Very low | Medium | Owner's two attempts BOTH 400d on the same payload — not rate limit; capture body confirms. |

---

## Exit-criteria mapping

| Playbook criterion | How verified |
|---|---|
| Every slice task `[X]` | Tasks #9–#15 in this session marked completed; tasks #16–#18 are exit-gates. |
| Tests pass; coverage ≥80% on changed lines | Phase 1 (3) + Phase 2 (6) = 9 tests pass; modified lines are publisher.py:237-238 (already covered by existing tests + new test_payload_includes_*) and post-migrate.py (covered by test_post_migrate_*). |
| Module installs cleanly | `docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_integration --stop-after-init` exit 0; staging `-u` exit 0. |
| ACLs / sudo / raw SQL | No new model → no new ACL row needed. Post-migrate uses Odoo env, no `sudo()` privilege escalation, no raw SQL. **Verify by `git diff` review at Phase 4.** |
| Tracker state updated | Phase 7 flips P-BUG-ESTY-188 `doing` → `done`. |
| `/learn` insight captured | Phase 8 — likely "post-migrate bootstrap for fields added in a later patch never lands on existing DBs unless an explicit migration writes them" (extends existing memory). |
| findings.md updated | Append a P-BUG-ESTY-188 entry to `specs/008-listings-inventory-sync/findings.md` summarising hypothesis-confirmed/-rejected and the discovery psql result. |

---

## No-new-model assertion

This slice modifies an EXISTING field on an EXISTING model. No `_name = 'new.model'`. No new `ir.model.access.csv` row. No new field. Standard-Odoo-First decision tree N/A — this is a data + payload-construction fix, not a customisation.

---

## Executive summary

P-BUG-ESTY-188 root cause: **staging shop JaHandmadeArt has NULL `default_readiness_state_id`**, so the createListing payload omits the key and Etsy 400s with "A readiness_state_id is required for physical listings". Fix is data-only: (1) post-migrate `19.0.2.33.0` bootstraps the field by calling `/shops/{id}/readiness-state-definitions` for each shop, (2) demo_data.xml gets the JaHandmadeArt value as defensive default. 9 new tests (3 Phase-1 DB + 6 Phase-2 ORM). No new models, no new ACLs. Discovery `psql` query against staging confirms hypothesis before Phase 2 RED — that's GO-condition-zero. If psql shows the field is already populated, pivot to candidate #2 (inventory offerings missing readiness) or #3 (capture the 400 body and grep dev-docs for new mandatory fields).
