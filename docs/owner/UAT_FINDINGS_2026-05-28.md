# UAT Findings — 2026-05-28 (v1.2 standard-form flow)

**Người chạy:** Playwright UAT (`tests/e2e/tests/uat_huong_dan_tao_san_pham.spec.ts`)
**Môi trường:** `https://odoo.hatafax.com` · DB `esty_odoo19` · mhc `19.0.1.0.62` · etsy_integration `19.0.2.24.0`
**Phạm vi:** ESTY-183 — `HUONG_DAN_TAO_SAN_PHAM_VN.md` **v1.2** (form Sản phẩm chuẩn) TC-001..TC-015
**Status:** **Open** — form-only PASS; live-Etsy publish surfaced pre-existing publisher 400s (follow-up `R-PUB-RESPONSE-BODY-DIAGNOSE`).

> v1.2 retired the two creation wizards; products are now created on the **standard product form** with auto-derived SKU + 7 metadata pages. This run rewrote the whole suite onto that flow and, in doing so, surfaced + fixed three real product defects before any live publish.

---

## Tổng kết Pass/Fail

| TC | Mô tả | Form-only | Live (`RUN_ETSY_PUBLISH=1`) | Note |
|---|---|---|---|---|
| TC-001 | Tạo Mug form chuẩn → SKU tự sinh `MUG-CR-F11` + Etsy-Draft | ✅ Pass | — | Required all 3 fixes below |
| TC-002 | Mã SKU Gearment → Dropship | ✅ Pass | — | |
| TC-003 | SKU Drift "Keep Legacy" | ⏸ Skip | — | Seed product có (`UAT-MUG-001`); browser steps pending |
| TC-004 | SKU Drift "Accept Canonical" (published) | ⏸ Skip | — | Cần SP đã publish + live push |
| TC-005 | Đăng Draft lên Etsy | ⏸ (gated) | ⚠️ Pass alone / Fail in-suite | Created real draft when run alone; see F-LIVE |
| TC-006 | BA User thấy nút Publish | ✅ Pass | — | Matches code (v1.1 F1 resolution) |
| TC-007 | Giá 0 lưu được (drift) | ✅ Pass | — | See F-PRICE drift |
| TC-008 | Tags ≤13 / ≤20 chars | ⏸ Skip | — | Tags seeded (`uat-tag-01..15` + 21-char); browser steps pending |
| TC-009 | Cá nhân hoá + publish draft | ⏸ (gated) | ✘ Fail | createListing 400 |
| TC-010 | Cá nhân hoá char-count 1..1024 | ✅ Pass | — | ValidationError modal |
| TC-011 | Vật liệu auto + publish draft | ⏸ (gated) | ✅ **Pass (live)** | Real draft created |
| TC-012 | Ảnh phụ + thứ tự | ⏸ Skip | — | Image-binary upload manual/headless-fragile |
| TC-013 | Override taxonomy + publish draft | ⏸ (gated) | ✘ Fail | createListing 400 |
| TC-014 | Cân nặng + Kích thước + publish draft | ⏸ (gated) | ✘ Fail | createListing 400 |
| TC-015 | Variant property_values + publish draft | ⏸ (gated) | ✘ Fail | inventory push 400 |

**Form-only net:** 5 PASS / 4 SKIP / 0 FAIL (runnable subset).
**Live net:** 6 PASS / 5 FAIL — publish path proven (TC-005 + TC-011 created real JaHandmadeArt drafts); the 4 metadata-combo TCs + TC-005-in-suite hit publisher 400s (F-LIVE).

---

## Defects surfaced AND fixed this run (the UAT did its job)

### D1 — Auto-SKU froze after the first variant (`MUG-CR`, not `MUG-CR-F11`)
The standard-form onchange guard compared `default_code` to the name-only suggestion, so once it became `MUG-CR` it stopped re-deriving. **Fixed** with a dirty-flag (`x_sku_auto_value`, declared invisible in the form so it round-trips across onchange calls) — re-derives while still system-managed, preserves a manual BA edit. (commit `dfd5209d274`, mhc → 19.0.1.0.62)

### D2 — SKU segments ordered by attribute name, not grammar role (`MUG-F11-CR`)
"11 oz" is on the **Fluid oz** attribute; `evaluate()` sorted segments alphabetically, putting Fluid oz before Material. **Fixed** with grammar-role ordering (Material→MAT, Shape/Size/Fluid oz/Apparel Size→SIZE, Color→VAR2) → `MUG-CR-F11`.

### D3 — Standard-form save created no `channel.status` row
Only the retired wizard created the "Etsy — Draft" row. **Fixed** by syncing `product.channel.status` from channel applicability on `create()`/`write()` (additive, never clobbers Published/Error).

### D4 — "Publish Draft Only" button missing from the wizard UI
The model had the method but the form only showed "Publish (full)" (goes live + fee). **Fixed** by adding the button (commit `2e2ade6e595`, etsy → 19.0.2.24.0) — enabling fee-free draft UAT.

---

## Documented drift (no code change — assert actual behaviour)

### F-PRICE — TC-007: the ">0" floor was wizard-only
The standard `product.template` has no `list_price > 0` constraint (that lived in the retired wizard). Price 0 saves; Etsy enforces the $0.20 floor at push. TC-007 now asserts the form saves and flags this. **Owner decision needed:** add a form-level floor, or keep relying on Etsy's push-time enforcement (doc already says the latter).

---

## F-LIVE — Live-Etsy publish 400s (follow-up `R-PUB-RESPONSE-BODY-DIAGNOSE`)

Live run created **real drafts** for TC-005 (alone) and TC-011, proving the publish path + the new button. But:
- `POST /shops/60752333/listings` → **400** for TC-009 (personalization), TC-013 (taxonomy override), TC-014 (weight/dims).
- `PUT /listings/{id}/inventory` → **400** for TC-015 (variant property_values).
- TC-005 passed alone but failed inside the full live run — suggests Etsy rate-limit or duplicate-SKU behaviour across rapid sequential publishes.

**Root-cause blocker:** the Etsy API client raises `raise_for_status()` **without capturing the response body**, so the exact validator message is lost (anti-pattern). The fix is to capture the 4xx body first, then address each metadata payload. Shop config is NOT the cause — JaHandmadeArt has all 4 publisher defaults (taxonomy 2172, shipping 285149016922, return 1397855793400, readiness 1406133708616) + a valid token.

**Also note (test-data, already fixed in the suite):** JaHandmadeArt is a **VND** shop (Etsy min ~5,043 VND). Live-publish TCs must use `LIVE_PRICE=250000`; a USD-style price (e.g. 15.25) is treated as VND and 400s "price too low".

---

## Run evidence

```
# form-only (RUN_ETSY_PUBLISH unset)
✓ TC-001 (24.6s)  ✓ TC-002 (20.4s)  ✓ TC-006 (6.1s)  ✓ TC-007 (20.0s)  ✓ TC-010 (9.4s)
10 skipped · 5 passed

# live (RUN_ETSY_PUBLISH=1)
✓ TC-001  ✓ TC-002  ✘ TC-005  ✓ TC-006  ✓ TC-007  ✘ TC-009  ✓ TC-010  ✓ TC-011  ✘ TC-013  ✘ TC-014  ✘ TC-015
4 skipped · 6 passed · 5 failed (6.4m)
```

Unit coverage for the 3 fixes (staging, TransactionCase, 0 failed): role-ordering, manual-edit-preserve, channel-status create + idempotent write.

---

## Follow-up items

1. **`R-PUB-RESPONSE-BODY-DIAGNOSE`** (tracker `todo`): capture Etsy 4xx response body in `etsy_api_client._request`, then fix per-feature payloads (personalization / taxonomy / weight+dims / variant property_values) + check rate-limit/duplicate-SKU on rapid publishes.
2. **TC-007 decision** (owner): form-level price floor vs Etsy-push enforcement.
3. **Enable TC-003/004/008** browser steps now that `seed_uat_data.py` provides the legacy product + tags.
4. **Owner cleanup**: delete the UAT draft listings created on JaHandmadeArt during the live run (Shop Manager → Listings → Drafts).
5. **`P-UAT-AUTOMATION-SKILL`** (deferred): package reset → deploy → seed → run → report as a reusable skill.

---

## Playwright operability notes (for the next run)

- Standard form lazy-renders notebook pages → re-open the General tab before reading `default_code`.
- A bare-family SKU (`MUG`) triggers Odoo's "Internal Reference already exists" Note dialog → auto-dismissed via `page.addLocatorHandler`.
- Reset staging products between runs: `npm run reset:products` (dry-run) / `npm run reset:products:apply`.
- Seed runs automatically in `globalSetup` (`seed_ba_user.py` + `seed_uat_data.py`).
