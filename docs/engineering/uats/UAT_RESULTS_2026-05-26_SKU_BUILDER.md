# UAT Results — 2026-05-26 — SKU Builder Extension (P-UAT-SKU-BUILDER-EXTEND)

**Slice**: `P-UAT-SKU-BUILDER-EXTEND` (Spec 009 Phase 3b)
**Run timestamp**: 2026-05-26 07:02–07:03 UTC
**Branch**: `feature/006-master-plan-coding`
**Staging**: `https://odoo.hatafax.com` / db `esty_odoo19` / mhc `19.0.1.0.52`
**Spec**: `tests/e2e/tests/uat_huong_dan_tao_san_pham.spec.ts`
**HTML report**: `tests/e2e/reports/html/` (gitignored — open via `npm run report` from `tests/e2e/`)

> This is an **engineering** results doc. Owner-facing `FLOW_TAO_SAN_PHAM_VN.md` + `HUONG_DAN_TAO_SAN_PHAM_VN.md` are deliberately NOT updated this slice (D7 constraint: refresh in one clean pass after all 3 SKU-v2 features ship).

## Summary

**8 PASS / 4 SKIP / 0 FAIL** (12 test cases). 1m12s end-to-end including BA User seed + cleanup. No regression from `P-HUB-SKU-BUILDER` (mhc 19.0.1.0.52) on the legacy `product.creation.wizard` flow.

## Coverage matrix

| TC | Description | Result | Layer |
|---|---|---|---|
| TC-001 | BA Lead creates Mug via legacy wizard | PASS | Browser |
| TC-002 | Gearment SKU set → Dropship inferred | PASS | Browser |
| TC-003 | SKU drift "Keep Legacy" | SKIP | Needs seed |
| TC-004 | SKU drift "Accept Canonical" + Etsy push | SKIP | Needs Etsy API |
| TC-005 | Publish Etsy draft from product form | SKIP | Chained from TC-001 |
| TC-006 | BA tier visibility — Publish-to-Etsy button | PASS | Browser |
| TC-007 | Validator: Listing Price > 0 | PASS | Browser |
| TC-008 | NEW — Build `MUG-CR-F11` (mug 11oz happy path) | PASS | Browser + JSON-RPC verify |
| TC-009 | NEW — Build `MUG-CR-F15-BK` (mug 15oz + VAR2 Black) | PASS | Browser + JSON-RPC verify |
| TC-010 | NEW — Build `APR-TX-AM` (apron Medium, apparel-size-gated) | PASS | Browser + JSON-RPC verify |
| TC-011 | NEW — Build `DMT-TX-R30X18` (doormat 30×18 rectangular) | PASS | Browser + JSON-RPC verify |
| TC-012 | NEW — FR-017 24th: non-BA blocked at `action_create` | SKIP | Stub; covered in unit test `test_phase2_hub_sku_builder_orm.py::test_non_ba_user_blocked_before_template_create` |

## What landed in code this slice

| File | Change |
|---|---|
| `tests/e2e/page-objects/product_sku_builder_wizard.ts` | NEW — Playwright page object for the 4-step builder wizard (step nav, per-step fill, preview/submit, color-blur fix) |
| `tests/e2e/tests/uat_huong_dan_tao_san_pham.spec.ts` | Append TC-008..TC-012 + `countProductsBySku` JSON-RPC helper |
| `tests/e2e/fixtures/cleanup_uat_data.py` | Extend archive domain to also match `name LIKE 'UAT-SKU-BUILDER%'` (builder TC use deterministic SKUs like `MUG-CR-F11`, not the `UAT-` prefix) |
| `.env` (gitignored) | Add `STAGING_*` credentials (admin/admin substitute per owner directive) |
| `specs/009-product-hub/tasks.md` | Append slice T054–T060 (UAT-only, no Odoo code) |
| `specs/009-product-hub/findings.md` | Prepend §P-UAT-SKU-BUILDER-EXTEND with full run outcome + memory-worthy surprises |
| `.claude/plans/006-master-plan-tracking.md` | Insert `P-UAT-SKU-BUILDER-EXTEND` row (state `doing` → `done` on commit) |

## What did NOT land (deliberately out of scope)

- Owner-facing doc refresh (`FLOW_TAO_SAN_PHAM_VN.md` / `HUONG_DAN_TAO_SAN_PHAM_VN.md`) — D7 constraint, will happen after the last of the 3 SKU-v2 features (V2-VALIDATE + MISSING-INFO) ships.
- Real BA Lead user seed on staging — admin/admin substitutes for now per owner directive 2026-05-26.
- TC-012 browser promotion — covered at correct layer by unit test; promote later via `P-UAT-FR017-BUILDER-BROWSER` if owner wants browser-level enforcement evidence.

## Defects surfaced during the run

Three iterations of RED→GREEN happened *within the UAT authoring*, not against the wizard code. All findings were test-side fixes (test used wrong display name strings):

1. **Material name drift** — `MUG-CR-` expected, got `MUG-CE-`. Test typed "Ceramic" → autocomplete picked plain Ceramic (CE). Owner-doc SKU_GRAMMAR.md row 30 specifies "ceramic+chrome combo" for the canonical mug — display name on staging is "Ceramic + Chrome" (x_code CR). Fix: TC-008/009 type the full long-form material name.
2. **Size name drift** — `MUG-CR-F11` expected, got timeout waiting for "11 fl oz" dropdown item. Seed display is "11 oz" not "11 fl oz". Same fix pattern.
3. **Color compute not settled** — `MUG-CR-F15-BK` expected, got `MUG-CR-F15`. Color m2o was clicked but `preview_sku` compute hadn't fired before the test read. Fix: blur + `waitForTimeout(300)` in `fillStep4Color`. The other steps don't need this because the `clickNext()` between steps acts as an implicit blur.

**No defects in the wizard itself.** All 4 happy paths produced the SKUs the doc + unit tests already specified.

## How to re-run

```bash
cd tests/e2e
npm run test:tao-san-pham
# or single test:
npx playwright test uat_huong_dan_tao_san_pham.spec.ts -g "TC-008"
# HTML report:
npm run report
```

Prerequisites:
- `.env` has `STAGING_*` populated (admin/admin substitute or real values)
- `node_modules/` and Playwright browser binary installed (`npm install && npx playwright install chromium`)
- Staging running mhc ≥ `19.0.1.0.52`

## Next dispatch (after this slice lands)

1. **`P-HUB-V2-VALIDATE-ON-CREATE`** — currently blocked by (a) D-V2-2 decision pending in `docs/owner/SKU_GRAMMAR.md:390` (soft-warn vs hard-fail), (b) T054–T0?? tasks not yet enumerated in spec 009 `tasks.md`. Owner action required.
2. **`P-HUB-MISSING-INFO-WIZARD`** — same blocker pattern (T0??–TBD not enumerated).
3. After both ship: refresh `docs/owner/FLOW_TAO_SAN_PHAM_VN.md` + `HUONG_DAN_TAO_SAN_PHAM_VN.md` in one clean pass, then run UAT again with the spec drift TC re-enabled (currently SKIP).
