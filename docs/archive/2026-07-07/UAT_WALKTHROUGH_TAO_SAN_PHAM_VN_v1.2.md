# UAT Walkthrough — Tạo sản phẩm + publish Etsy (v1.2 — Wave 2/3)

**Phiên bản:** 1.2 · **Ngày:** 2026-06-07 · **Ngôn ngữ:** Tiếng Việt
**Đối tượng:** Owner / BA Lead chạy UAT bằng tay trên trình duyệt
**Môi trường mặc định:** Staging `https://odoo.hatafax.com` · DB `esty_odoo19`
**Sản phẩm thử:** Apron (giá VND ≥ 250,000 cho JaHandmadeArt)
**Tài liệu nghiệp vụ:** [`HUONG_DAN_TAO_SAN_PHAM_VN.md`](./HUONG_DAN_TAO_SAN_PHAM_VN.md)
**Test tự động tương ứng:** `tests/e2e/tests/uat_wave_2_3_*.spec.ts`

> **v1.2 thay đổi so với v1.0:**
> - Bỏ TC-001..TC-003 (wizard cũ đã retire).
> - Thêm TC-W23-CFG-01, TC-W23-BULK-01, TC-W23-PUB-01 cho Wave 2/3 (ESTY-189..199).
> - TC-006..TC-012 (FR-017 BA-role gate, SKU drift) vẫn dùng v1.0 — không đổi.
>
> **Mục đích:** Cho phép Owner verify thủ công 11 Jira tickets ESTY-187..199
> đã land trên `feature/006-master-plan-coding` trước khi merge sang `main`.

---

## Setup chung (1 lần trước khi UAT)

1. Mở Chrome / Edge ở chế độ Ẩn danh.
2. Mở 3 tab:
   - **Tab 1 — Odoo:** `https://odoo.hatafax.com/web/login`
     Login với BA Lead (mặc định Owner đã có).
   - **Tab 2 — Etsy Shop Manager:** `https://www.etsy.com/your/shops/jahandmadeart/tools/listings/drafts`
   - **Tab 3 — Etsy Dev Portal** (chỉ cho TC-W23-CFG-01 verify shop config): `https://www.etsy.com/developers/your-apps`
3. Sẵn sàng ghi Pass/Fail.

> **Cảnh báo:** TC-W23-PUB-01 tạo Etsy Draft thật. Title sẽ có prefix `[UAT-2026-06-07]` để dễ tìm + xoá sau.
> Sau UAT: chạy `python3 scripts/cleanup_uat_etsy_drafts.py --apply` (cần `ETSY_CLIENT_ID/SECRET` trong `.env`).
> Hoặc xoá thủ công trên Tab 2 (Drafts → tick → Delete).

---

## Tổng kết test case (Wave 2/3)

| TC ID | Tên | Wave | Jira coverage | Mức độ ảnh hưởng |
|---|---|---|---|---|
| TC-W23-CFG-01 | Verify Publisher Defaults trên JaHandmadeArt shop | 2 | ESTY-189/191/193/194 + 190/195 | Read-only |
| TC-W23-BULK-01 | Bulk action Mark Ready + Reset Draft | 2 | ESTY-197 | Tạo + xoá 2 listing test (auto cleanup) |
| TC-W23-PUB-01 | Tạo Apron + publish draft live + verify auto-fields | 2+3 | ESTY-189/190/191/192/193/195/199 | **Tạo 1 Etsy draft thật** |
| TC-006..TC-012 | Xem [`UAT_WALKTHROUGH_TAO_SAN_PHAM_VN.md`](./UAT_WALKTHROUGH_TAO_SAN_PHAM_VN.md) (v1.0) | — | — | (không đổi) |

---

## TC-W23-CFG-01 — JaHandmadeArt Publisher Defaults

**Pre-condition**
- Login BA Lead hoặc Admin (Admin có quyền xem trường `groups="base.group_system"`).
- Shop JaHandmadeArt tồn tại với `etsy_api_shop_id = 60752333`.

**Các bước**

1. Trên Tab 1, mở menu **Etsy → Shops** (hoặc URL `/odoo/action-etsy_integration.action_etsy_shops`).
2. Click vào shop **JaHandmadeArt**.
3. Trên form mở ra, click tab **Publisher Defaults**.

**Kỳ vọng** (đánh dấu mỗi mục)

- ☐ **ESTY-189** Trường `Default Etsy Taxonomy ID` có giá trị số (ví dụ `1406133708616` cho readiness).
- ☐ **ESTY-191** Trường `Default Etsy Shipping Profile ID` có giá trị số.
- ☐ Trường `Default Return Policy ID` có giá trị.
- ☐ Trường `Default Readiness State ID` có giá trị.
- ☐ **ESTY-193** `Default Who Made`, `Default When Made`, `Default Is Supply` đều có giá trị.
- ☐ **ESTY-190** Group "Shop Brand-Voice Defaults" hiển thị với 3 trường: `Default Title`, `Default Description`, `Default Image`.
- ☐ **ESTY-194** Bảng "Attribute Mapping" hiển thị (có thể rỗng — chỉ cần render đúng).
- ☐ **ESTY-195** Trên tab General / Header: `Listing Currency` có giá trị (ví dụ VND hoặc USD).

**Pass / Fail:** ☐ Pass  ☐ Fail
**Note (nếu Fail):** ____________________

---

## TC-W23-BULK-01 — Bulk action Mark Ready + Reset Draft

**Pre-condition**
- Login Admin (cần quyền tạo `multichannel.listing` test rows).
- Đã có ít nhất 1 product.template trong hệ thống.

**Các bước**

1. Mở menu **Operations → Listings** (URL `/odoo/action-multichannel_hub_core.action_multichannel_listing`).
2. Click nút **New** ở list view → tạo 2 listing test với:
   - **Product Template:** chọn bất kỳ
   - **Channel:** Etsy
   - **Shop Ref:** `jahandmadeart`
   - **Title:** `[UAT-2026-06-07] bulk-test-A` (cho row 1), `[UAT-2026-06-07] bulk-test-B` (cho row 2)
   - **State:** Draft (mặc định)
3. Quay về list view (click breadcrumb).
4. Search box: gõ `[UAT-2026-06-07]` + Enter — chỉ thấy 2 dòng test.
5. Tick header checkbox để chọn cả 2 dòng.
6. Click dropdown **Actions** (gear icon trên control panel).
7. Chọn **Mark Ready for Publish**.

**Kỳ vọng giai đoạn 1:**

- ☐ Notification xanh "X marked ready" hiển thị.
- ☐ Cả 2 dòng đổi cột State từ `draft` (badge xanh dương) sang `ready` (badge vàng).

8. Tick lại header checkbox (Odoo clear selection sau action).
9. Click **Actions → Reset to Draft**.

**Kỳ vọng giai đoạn 2:**

- ☐ Notification xanh "X reset" hiển thị.
- ☐ Cả 2 dòng đổi State `ready` → `draft`.

10. **Cleanup:** tick 2 dòng → Actions → Delete.

**Pass / Fail:** ☐ Pass  ☐ Fail
**Note:** ____________________

---

## TC-W23-PUB-01 — Apron live publish + verify auto-fields

**Pre-condition**
- Login BA Lead.
- Etsy shop JaHandmadeArt đã có `active_source = 'api'` + access_token valid.
- Đã chạy TC-W23-CFG-01 PASS (publisher defaults sẵn sàng).

**Các bước**

1. Menu **Inventory → Products → New**.
2. Điền form (tab General):
   - **Name:** `[UAT-2026-06-07] Apron PUB-01`
   - **Category:** chọn `Apron` (autocomplete)
   - **Listing Price:** `250000` (VND — đáp ứng giá tối thiểu JaHandmadeArt)
3. Tab **Attributes & Variants**:
   - Add line: Attribute `Material`, Value `Textile`
   - Add line: Attribute `Apparel Size`, Value `Medium`
   - Add line: Attribute `Color`, Values `Black` + `White` (2 giá trị → 2 variants)
4. Tab **Channels:** add `Etsy`.
5. Tab **Inventory:** điền **Weight** = `0.40` kg.
6. Click **Save** (cloud icon).
7. _Optional — tải ảnh:_ Tab **Extra Images** → upload 1-2 ảnh PNG/JPG (hoặc bỏ qua, dùng default).
8. Header → click **Publish to Etsy** → wizard hiện ra.
9. Field `Shop`: chọn `JaHandmadeArt`.
10. Click **Run Publish Draft Only**.
11. Đợi 10-20s. Wizard tự đóng.

**Kỳ vọng — Trên Odoo:**

- ☐ Quay về form sản phẩm; không có lỗi đỏ.
- ☐ Menu **Operations → Listings** có 1 dòng mới cho sản phẩm này, shop_ref = `jahandmadeart`, state = `published`.
- ☐ Click vào dòng đó → form `multichannel.listing` mở:
  - ☐ **ESTY-189** `Etsy Taxonomy ID` đã tự điền (giá trị số, lấy từ shop default).
  - ☐ **ESTY-191** `Etsy Shipping Profile ID` đã tự điền.
  - ☐ **ESTY-193** Tab "How It's Made": `Etsy Who Made`, `Etsy When Made`, `Etsy Is Supply` đều có giá trị.
  - ☐ **ESTY-195** Tab "Shipping & Variations" — group "Shop Currency Preview" hiển thị `Display Price in Shop Currency` (số ≠ 0, ví dụ ~9.87 USD nếu shop currency = USD và rate 25,300 VND/USD).
  - ☐ **ESTY-199** Tab "Video" hiển thị field `Video Attachment` (rỗng nếu không tải video — OK).
  - ☐ **ESTY-190** Field `Title` rỗng hoặc match product name (fallback chain hoạt động).
  - ☐ Field `External Ref` có giá trị số (đó là Etsy listing_id).

**Kỳ vọng — Trên Etsy (Tab 2):**

- ☐ Drafts list hiển thị 1 listing mới với title `[UAT-2026-06-07] Apron PUB-01`.
- ☐ Click vào → xem detail:
  - ☐ Photo có (nếu đã upload ở bước 7).
  - ☐ Variations hiển thị: Black, White.
  - ☐ Price hiển thị bằng shop currency (USD đối với JaHandmadeArt).
  - ☐ Shipping profile assigned.

**Pass / Fail:** ☐ Pass  ☐ Fail
**Note:** ____________________

**Cleanup:**
- Tab 2 (Etsy): tick draft test → Delete.
- Hoặc: chạy `python3 scripts/cleanup_uat_etsy_drafts.py --apply` từ máy dev.

---

## TC-006..TC-012 (không đổi)

Tham chiếu [`UAT_WALKTHROUGH_TAO_SAN_PHAM_VN.md`](./UAT_WALKTHROUGH_TAO_SAN_PHAM_VN.md) v1.0 cho:

- TC-006 — FR-017 chặn BA User ở Create (không đổi)
- TC-007 — FR-017 cho phép BA Lead Create
- TC-008..TC-012 — SKU drift, attribute matching cũ, validation

Các TC này không bị ảnh hưởng bởi Wave 2/3 — quy trình test vẫn như v1.0.

---

## Báo cáo kết quả

Sau khi chạy hết Wave 2/3:

1. Điền pass/fail vào file này (commit dưới `docs/owner/UAT_RESULTS_<date>_WAVE_2_3.md` nếu muốn lưu).
2. Cập nhật `.claude/plans/006-master-plan-tracking.md` mỗi slice ESTY-* → flag UAT PASS/FAIL.
3. Ping channel Telegram cho engineer fix các FAIL.

---

## Liên kết test tự động

Tương đương Playwright (chạy nhanh hơn người):

```bash
cd tests/e2e
# Form-only:
npm run test:wave-2-3:cfg     # ↔ TC-W23-CFG-01
npm run test:wave-2-3:bulk    # ↔ TC-W23-BULK-01
# Live (cần RUN_ETSY_PUBLISH=1 + ETSY_*  env):
RUN_ETSY_PUBLISH=1 npm run test:wave-2-3:publish  # ↔ TC-W23-PUB-01
# Tất cả Wave 2/3:
RUN_ETSY_PUBLISH=1 npm run test:wave-2-3
# Cleanup drafts:
python3 ../../scripts/cleanup_uat_etsy_drafts.py --apply
```
