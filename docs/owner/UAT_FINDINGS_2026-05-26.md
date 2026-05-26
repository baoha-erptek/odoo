# UAT Findings — 2026-05-26

**Người chạy:** Playwright UAT script (tests/e2e/) + `scripts/e2e_product_listing.py` (TC-005)
**Môi trường:** `https://odoo.hatafax.com` · DB `esty_odoo19`
**Phạm vi:** ESTY-183 — `HUONG_DAN_TAO_SAN_PHAM_VN.md` TC-001..TC-012
**Status:** **Closed** — owner đã quyết các F1/F2 + TC-005 live ran successfully (2026-05-26 22:19 UTC)

---

## Tổng kết Pass/Fail (rerun sau v1.1 doc refresh)

| TC | Mô tả | Kết quả ban đầu (sáng) | Kết quả sau khi update doc + chạy lại | Note |
|---|---|---|---|---|
| TC-001 | BA Lead tạo SP Mug bằng Wizard | ✅ Pass | ✅ Pass | Product archived after run |
| TC-002 | SP có Mã Gearment → Dropship | ✅ Pass | ✅ Pass | Product archived after run |
| TC-003 | SKU drift "Keep Legacy" | ⏸ Skip | ⏸ Skip | Cần seed `seed_uat_data.py` (theo dõi như follow-up) |
| TC-004 | SKU drift "Accept Canonical" + Etsy push | ⏸ Skip | ⏸ Skip | Cần product đã publish Etsy + sandbox shop |
| TC-005 | Đăng SP lên Etsy (Draft) | ⏸ Skip | ✅ **PASS (live)** | Listing 4511807545 trên JaHandmadeArt; owner cleanup needed |
| TC-006 | BA User & Publish button | ⚠️ Finding F1 | ✅ Pass (doc updated) | Code assert đúng — `groups=group_ba_user` |
| TC-007 | Validator giá `> 0` | ✅ Pass | ✅ Pass | Modal "Listing Price must be greater than 0" |
| TC-008 | SKU Builder MUG-CR-F11 | ✅ Pass | ✅ Pass | (mới — added 2026-05-26) |
| TC-009 | SKU Builder MUG-CR-F15-BK | ✅ Pass | ✅ Pass | |
| TC-010 | SKU Builder APR-TX-AM | ✅ Pass | ✅ Pass | |
| TC-011 | SKU Builder DMT-TX-R30X18 | ✅ Pass | ✅ Pass | |
| TC-012 | FR-017 non-BA blocked | ⏸ Skip (cite unit test) | ⏸ Skip (cite unit test) | Covered ở `test_phase2_hub_sku_builder_orm::test_non_ba_user_blocked_before_template_create` |

**Net:** 9 PASS / 3 SKIP / 0 FAIL (12 TC). Tất cả Skip là có lý do (seed thiếu / cover ở layer khác). Tất cả "Finding" được resolve.

---

## Resolved findings (owner decisions 2026-05-26)

### F1 — Doc-vs-Code mismatch: BA User vs nút "Publish to Etsy"

**Resolution: D1 — update doc to match code (owner-approved 2026-05-26).**

- Doc `HUONG_DAN_TAO_SAN_PHAM_VN.md` v1.0 §2 ghi "BA User | Đăng Etsy: ❌" — **sai**.
- Code (view + `_check_ba_or_raise()`) thiết kế: mọi BA tier (User/Lead/Manager) publish được.
- FR-017 pattern được xác nhận 26 lần trong code (`feedback_fr017_write_defense_in_depth.md`).
- **Action taken:** `HUONG_DAN_TAO_SAN_PHAM_VN.md` updated to v1.1 — role matrix mới: `BA User | Đăng Etsy: ✅`. Lý do được giải thích trong tài liệu kèm cảnh báo "sửa từ v1.0".
- **TC-006 reverted expectation:** browser test giờ assert nút **VISIBLE** + executable cho BA User → PASS.

### F2 — TC-007 spec drift: $0.20 vs `> 0`

**Resolution: update doc to match code (owner-approved 2026-05-26).**

- Doc v1.0 §11 TC-007 ghi "Validation — giá USD < 0.20 → 'Giá Etsy tối thiểu $0.20'".
- Validator code chỉ check `> 0`; Etsy enforce $0.20 ở push step, không phải wizard step.
- **Action taken:** doc v1.1 TC-007 đổi text thành "Listing Price phải `> 0`" + giải thích Etsy minimum ở push step (mục 9.1 + 9.4).

### F3 — TC-003/004/005 seed/owner-approval

- **TC-003/TC-004:** vẫn skip — cần `fixtures/seed_uat_data.py` thêm vào globalSetup để chuẩn bị 1 SP `non_canonical` (TC-003) + 1 SP đã publish Etsy (TC-004). **Follow-up slice candidate**: `P-UAT-SEED-DRIFT-DATA` (Phase 3e doc-slice extension).
- **TC-005:** ✅ resolved — owner approved live re-run. Chạy lúc 2026-05-26 22:19 UTC qua `scripts/e2e_product_listing.py`. Kết quả:
  ```
  Product created: tmpl=41, SKU=E2E-20260526-221925-TAT1
  Etsy listing created: 4511807545
  channel.status: state=draft, external_ref='4511807545'
  Odoo product auto-archived after verification
  ```
  HTTP 403 trên `GET /listings/4511807545` là **expected behavior** — Etsy private-app token không thấy draft của shop khác (chỉ owner UI thấy được).

**Cleanup needed (owner):** Etsy Shop Manager (JaHandmadeArt) → Listings → Drafts → tick listing `4511807545` → Delete.

---

## Doc deliverables landed 2026-05-26

| Doc | Phiên bản | Thay đổi |
|---|---|---|
| `HUONG_DAN_TAO_SAN_PHAM_VN.md` | 1.0 → **1.1** | Thêm 3 mục mới (Wizard cũ vs SKU Builder so sánh, SKU Builder 4-bước, Validator v2 soft/hard); fix F1 role matrix; fix F2 price text; thêm TC-008..TC-012 |
| `FLOW_TAO_SAN_PHAM_VN.md` | 1.0 → **1.1** | Thêm SKU Builder Wizard narrative + validator v2 + size-fallback (plain-business view, no code refs) |
| `UAT_WALKTHROUGH_TAO_SAN_PHAM_VN.md` | (mới) **1.0** | Manual click-by-click cho owner step-through 12 TC trong trình duyệt |
| `UAT_FINDINGS_2026-05-26.md` | 1.0 → **2.0** | This file — closed F1/F2, ran TC-005 live, updated tally to 9/3/0 |

---

## Playwright + manual run evidence

### Playwright suite (2026-05-26 22:16-22:18 UTC)

```
Running 12 tests using 1 worker

  ✓  TC-001 — BA Lead tạo sản phẩm Mug bằng Wizard (6.8s)
  ✓  TC-002 — Sản phẩm có Mã Gearment → đặt cờ Dropship (7.0s)
  -  TC-003 — SKU drift wizard "Keep Legacy" (skipped — seed gap)
  -  TC-004 — SKU drift wizard "Accept Canonical" (skipped — seed gap)
  -  TC-005 — Đăng lên Etsy (Draft mode) (skipped in Playwright; ran via scripts/e2e_product_listing.py)
  ✓  TC-006 — BA tier visibility of "Publish to Etsy" button (6.2s) — code-correct asserts after F1 D1
  ✓  TC-007 — Validation: Listing Price phải > 0 (wizard validator) (6.5s)
  ✓  TC-008 — Build MUG-CR-F11 (mug 11oz happy path) (10.7s)
  ✓  TC-009 — Build MUG-CR-F15-BK (mug 15oz + VAR2 black) (10.8s)
  ✓  TC-010 — Build APR-TX-AM (apron M, apparel-size-gated) (10.4s)
  ✓  TC-011 — Build DMT-TX-R30X18 (doormat rectangular) (9.6s)
  -  TC-012 — FR-017 24th: non-BA user blocked (skipped — covered by mhc unit test)

  4 skipped
  8 passed (1.3m)
```

### TC-005 live (2026-05-26 22:19 UTC)

Command:
```bash
source .venv-e2e/bin/activate
STAGING_BA_LOGIN=admin STAGING_BA_PASSWORD=*** \
  python scripts/e2e_product_listing.py --count 1 --shop JaHandmadeArt --db esty_odoo19 --cleanup
```

Log excerpt:
```
Step 4: run 1 row(s), prefix=E2E-20260526-221925-*
  picked: sheet=Accessories row=1 name='Temporary Tattoo' sku=TAT1
  wizard created: id=29
  product.template created: id=41
  channel.status pre-publish: {'id': 19, 'state': 'draft', 'external_ref': False}
  Etsy listing created: id=4511807545
  channel.status post-publish: {'id': 19, 'state': 'draft', 'external_ref': '4511807545'}
  etsy.listing row: {'id': 6, 'etsy_listing_id': '4511807545', 'state': 'inactive', 'title': 'Temporary Tattoo'}
  Etsy GET /listings/4511807545 -> HTTP 403 state=None  ← expected for draft via private app token
Step 5: cleanup — archive created product.templates
  Archived product.template id=41
```

---

## Follow-up items (NOT blockers for this UAT closure)

1. **R-UAT-SEED-DRIFT-DATA** (suggested slice): add `fixtures/seed_uat_data.py` for TC-003 (non_canonical SP) + TC-004 (published-on-Etsy SP). Wire into Playwright globalSetup. Estimated < 50 LOC.
2. **Owner cleanup**: delete Etsy draft listing `4511807545` from JaHandmadeArt Shop Manager (TC-005 artifact).
3. **mhc unit-test ref for TC-012**: keep cite link in `HUONG_DAN_TAO_SAN_PHAM_VN.md` TC-012 + `UAT_WALKTHROUGH_TAO_SAN_PHAM_VN.md` TC-012; promote to browser test only if owner needs visual evidence.
4. **Memory hit**: `feedback_e2e_pipeline_first.md` reaffirmed — owner-doc refresh + UAT rerun pattern (no new code, just docs + run) is the right cadence after a stack of feature slices ships.

---

## Conclusion

ESTY-183 UAT for `HUONG_DAN_TAO_SAN_PHAM_VN.md` v1.1: **APPROVED** (9 PASS / 3 SKIP-with-reason / 0 FAIL).

Sẵn sàng đóng ticket. Tiếp tục các ticket khác (ESTY-184/185/186) với cùng pattern: read tracker → confirm doc-vs-code → update doc → re-run Playwright → manual walkthrough for owner sign-off.
