# UAT Walkthrough — Tạo sản phẩm mới (click-by-click)

**Phiên bản:** 1.0 · **Ngày:** 2026-05-26 · **Ngôn ngữ:** Tiếng Việt
**Đối tượng:** Owner / BA Lead chạy UAT bằng tay trên trình duyệt
**Môi trường mặc định:** Staging `https://odoo.hatafax.com` · DB `esty_odoo19`
**Tài liệu nghiệp vụ:** [`HUONG_DAN_TAO_SAN_PHAM_VN.md`](./HUONG_DAN_TAO_SAN_PHAM_VN.md) §11

> Script này là phiên bản "Owner làm tay" của 12 test case TC-001..TC-012. Mỗi TC có:
> - **Pre-condition** — phải có gì trước khi bắt đầu
> - **Các bước** — đánh số click-by-click
> - **Kỳ vọng** — kết quả phải thấy
> - **Pass / Fail** — owner ghi vào checkbox
>
> Nếu owner muốn chạy tự động → dùng Playwright suite `tests/e2e/tests/uat_huong_dan_tao_san_pham.spec.ts` (chạy `npm run test` trong `tests/e2e/`).

---

## Setup chung (làm 1 lần trước khi UAT)

1. Mở Chrome / Edge / Firefox bản mới ở chế độ Ẩn danh (tránh cache cookie cũ).
2. Truy cập `https://odoo.hatafax.com/web/login`.
3. Đăng nhập với tài khoản BA Lead (mặc định Owner đã có). Nếu chưa có → liên hệ Admin.
4. Mở 2 tab trình duyệt:
   - Tab 1: Odoo staging (đang dùng UAT)
   - Tab 2: `https://www.etsy.com/your/shops/jahandmadeart/tools/listings/drafts` (kiểm tra Etsy Draft cho TC-005)
5. Sẵn sàng giấy bút / Google Doc để ghi Pass/Fail mỗi TC.

> **Lưu ý:** TC-005 sẽ tạo một Etsy Draft listing thực trên JaHandmadeArt. Owner cần dọn dẹp listing đó sau khi UAT xong (Etsy Shop Manager → Drafts → tick + Delete).

---

## TC-001 — Tạo SP Mug bằng Wizard cũ (Cách 1A)

**Pre-condition**
- Đã đăng nhập BA Lead.

**Các bước**

1. Trong Odoo, mở menu **Sản phẩm** (thanh trên cùng).
2. Chọn **Tạo sản phẩm mới (Wizard)**.
   - _Nếu không thấy menu này:_ chạy `URL /odoo/action-multichannel_hub_core.action_product_creation_wizard` trực tiếp.
3. Form Wizard mở ra. Điền:
   - **Name:** `UAT-TAOSP Mug 2026 <date>` (ví dụ `UAT-TAOSP Mug 2026 0526a`)
   - **Internal Reference (SKU):** `UAT-MUG-001-<date>` (ví dụ `UAT-MUG-001-0526a`)
   - **Product Category:** chọn `All` từ dropdown
   - **Listing Price (USD):** `12.99`
   - **Internal Shipping Price (VND):** `20000`
   - **Channels Applicability:** click vào ô, chọn `Etsy` từ dropdown
4. Bấm nút **Create** (góc trên trái form).

**Kỳ vọng**

- Wizard đóng, form `product.template` của SP mới hiển thị.
- Trường **Internal Reference** = SKU đã nhập.
- Tab **Channels** (hoặc **Kênh**) có dòng "Etsy — Draft / Nháp".

**Pass / Fail:** ☐ Pass  ☐ Fail
**Note (nếu Fail):** ____________________

---

## TC-002 — Tạo SP Dropship Gearment (Wizard cũ)

**Pre-condition**
- BA Lead đã login.

**Các bước**

1. Mở Wizard tạo sản phẩm (như TC-001 bước 1-2).
2. Điền tất cả trường như TC-001 nhưng thêm:
   - **Name:** `UAT-TAOSP Dropship <date>`
   - **Internal Reference:** `UAT-MUG-002-<date>`
   - **Listing Price:** `19.99`
   - **Gearment SKU:** `GEAR-UAT-002-<date>`
   - Channels: `Etsy`
3. Bấm **Create**.

**Kỳ vọng**

- Form SP mới mở ra.
- Trường **Gearment SKU** trên form SP = `GEAR-UAT-002-<date>`.
- Cờ **Is Dropship** = ✅ (hoặc huy hiệu "Dropship" hiển thị).

**Pass / Fail:** ☐ Pass  ☐ Fail

---

## TC-003 — Wizard SKU Drift "Keep Legacy"

**Pre-condition**
- Phải có ít nhất 1 SP trên staging có `x_sku_v2_status = 'non_canonical'`.
  - _Nếu chưa có:_ chạy TC-001 với SKU `MUG-001` (legacy format) trước → SP đó sẽ có status `non_canonical`.

**Các bước**

1. Vào menu **Sản phẩm → SKU Drift**.
2. Danh sách SP non-canonical hiển thị. Click vào dòng SP test.
3. Mở tab **SKU Drift** trên form.
4. Bấm nút **Keep Legacy** (giữ mã cũ).

**Kỳ vọng**

- Modal confirm (nếu có) → confirm.
- Sau khi reload, SP biến mất khỏi danh sách **SKU Drift**.
- Trên form SP: `x_sku_v2_status` = `ba_approved_legacy` (xem ở Developer Mode hoặc dev tools).

**Pass / Fail:** ☐ Pass  ☐ Fail  ☐ Skip (thiếu seed)

---

## TC-004 — Wizard SKU Drift "Accept Canonical" (SP đã đăng Etsy)

**Pre-condition**
- 1 SP đã publish Etsy (có `etsy_listing_id` ≠ NULL).
- Mã SKU hiện tại là legacy.
- Có Etsy sandbox/staging kết nối API.

**Các bước**

1. Mở SP đó (menu Sản phẩm → search theo SKU legacy).
2. Tab **SKU Drift**.
3. Bấm **Accept Canonical**.
4. Đợi spinner ~5 giây.

**Kỳ vọng**

- SKU SP đổi sang format v2 (ví dụ `MUG-001` → `MUG-CR-F11`).
- Tab **Channels**: trạng thái "Inventory push pending" → "pushed" trong vài giây.
- Mở Etsy Shop Manager → listing tương ứng có SKU mới phản ánh.
- Nếu Etsy lỗi → rollback (SKU trở về mã cũ, ghi lỗi trong tab Channels).

**Pass / Fail:** ☐ Pass  ☐ Fail  ☐ Skip (thiếu setup)

---

## TC-005 — Đăng SP lên Etsy (Draft mode, LIVE JaHandmadeArt)

> ⚠️ **Sẽ tạo 1 listing Draft thực trên Etsy shop JaHandmadeArt.** Owner cần dọn dẹp sau UAT.

**Pre-condition**
- Owner đã phê duyệt (✅ 2026-05-26).
- Có 1 SP UAT tạo từ TC-001 hoặc TC-008.
- SP có ít nhất 1 ảnh upload.
- Shop JaHandmadeArt đã cấu hình đủ 4 default IDs (taxonomy / shipping profile / return policy / readiness state).

**Các bước**

1. Mở form SP UAT (ví dụ SP tạo từ TC-001).
2. Upload 1 ảnh vào trường **Image** (drag & drop hoặc click → chọn file).
3. Save form (Ctrl+S hoặc nút Save).
4. Bấm nút **Publish to Etsy** ở header form.
5. Wizard `etsy.publish.wizard` mở ra.
6. Bấm **Run Publish Draft Only** (không phải Run Publish full — tránh listing fee).
7. Đợi 5-15 giây.

**Kỳ vọng**

- Wizard đóng, thông báo "Listing created successfully" (hoặc tương tự).
- Mở tab Etsy Shop Manager (`https://www.etsy.com/your/shops/jahandmadeart/tools/listings/drafts`) → listing UAT mới xuất hiện ở **Drafts**.
- Trên Odoo, tab **Channels** của SP: status `Etsy — Published (draft)` + `External Ref` = listing_id (chuỗi số).

**Pass / Fail:** ☐ Pass  ☐ Fail

**Cleanup sau test:** Etsy Shop Manager → Drafts → tick listing UAT → Delete.

---

## TC-006 — BA User vẫn thấy nút "Publish to Etsy"

> **Sửa từ v1.0:** Kỳ vọng ngược lại với doc cũ. Mọi BA tier publish được.

**Pre-condition**
- Tài khoản BA User (login `uat_ba_user@hatafax.demo` đã seed sẵn).
- Password BA User: lấy từ `tests/e2e/artifacts/_seed_state.json` hoặc env var `STAGING_BA_USER_PASSWORD`.

**Các bước**

1. Logout khỏi BA Lead.
2. Login BA User (`uat_ba_user@hatafax.demo`).
3. Vào menu **Inventory → Products** (hoặc **Sales → Products**).
4. Click vào SP bất kỳ trong danh sách.
5. Quan sát header form.

**Kỳ vọng**

- Nút **Publish to Etsy** **hiển thị** ở header form (KHÔNG bị ẩn).
- Click thử nút → wizard mở ra (BA User được phép).

**Pass / Fail:** ☐ Pass  ☐ Fail

---

## TC-007 — Validator: Listing Price phải `> 0`

> **Sửa từ v1.0:** validator code chỉ check `> 0`, không phải `>= $0.20`.

**Pre-condition**
- BA Lead login.

**Các bước**

1. Mở Wizard tạo sản phẩm (Cách 1A).
2. Điền các trường bắt buộc nhưng đặt **Listing Price (USD):** `0`.
3. Bấm **Create**.

**Kỳ vọng**

- Modal lỗi hiện ra với title "Validation Error" (hoặc "User Error") và message: **"Listing Price must be greater than 0."**.
- Wizard KHÔNG đóng — form vẫn mở.
- Không có SP mới được tạo.

**Pass / Fail:** ☐ Pass  ☐ Fail

---

## TC-008 — SKU Builder: Build `MUG-CR-F11` (mug 11oz happy path)

> Mới từ 2026-05-26 (slice P-HUB-SKU-BUILDER).

**Pre-condition**
- BA Lead login.
- mhc module ≥ 19.0.1.0.52 đã deploy trên staging.

**Các bước**

1. Mở menu **Operations → Configuration → SKU Builder Wizard** (hoặc URL `/odoo/action-multichannel_hub_core.action_product_sku_builder_wizard`).
2. Form 4 bước hiển thị với statusbar trên đầu.
3. **Bước 1 — Family:**
   - **Product Name:** `UAT-SKU-BUILDER Mug 11oz <date>`
   - Click ra ngoài input (Tab) → **Family (auto)** badge hiện = `MUG`
   - Bấm **Next**
4. **Bước 2 — Material:**
   - **Material:** click ô, gõ `Ceramic + Chrome` → chọn từ dropdown
   - Bấm **Next**
5. **Bước 3 — Size:**
   - **Size:** click ô, gõ `11 oz` → chọn từ dropdown
   - Bấm **Next**
6. **Bước 4 — Preview:**
   - **Preview SKU** hiển thị: `MUG-CR-F11`
   - Bỏ qua **Color (VAR2)** (để trống)
   - Bấm **Create**.

**Kỳ vọng**

- Wizard đóng, message "Product created" hoặc redirect về form SP mới.
- Vào menu Sản phẩm → search SKU `MUG-CR-F11` → tìm thấy SP UAT.

**Pass / Fail:** ☐ Pass  ☐ Fail

---

## TC-009 — SKU Builder: Build `MUG-CR-F15-BK` (mug 15oz + VAR2 Black)

**Pre-condition**
- BA Lead login.

**Các bước**

1. Mở SKU Builder Wizard.
2. **Bước 1:** Product Name = `UAT-SKU-BUILDER Mug 15oz Black <date>` → family auto = `MUG` → Next.
3. **Bước 2:** Material = `Ceramic + Chrome` → Next.
4. **Bước 3:** Size = `15 oz` → Next.
5. **Bước 4:** Color (VAR2) = `Black` (chọn từ dropdown) → Preview SKU = `MUG-CR-F15-BK` → **Create**.

**Kỳ vọng**

- SP mới tạo, `default_code` = `MUG-CR-F15-BK`.

**Pass / Fail:** ☐ Pass  ☐ Fail

---

## TC-010 — SKU Builder: Build `APR-TX-AM` (apparel, family-size-gated)

**Pre-condition**
- BA Lead login.

**Các bước**

1. Mở SKU Builder Wizard.
2. **Bước 1:** Product Name = `UAT-SKU-BUILDER Cotton Apron M <date>` → family auto = `APR` → Next.
3. **Bước 2:** Material = `Textile` → Next.
4. **Bước 3:** Size = `Medium` (apparel namespace, mã `AM`) → Next.
5. **Bước 4:** Preview SKU = `APR-TX-AM` → **Create**.

**Kỳ vọng**

- SP mới với `default_code` = `APR-TX-AM`.
- Nếu thử chọn Size = `11 oz` (Fluid oz namespace) ở Bước 3 → wizard báo lỗi "Size doesn't match family namespace" (vì APR chỉ chấp nhận apparel size).

**Pass / Fail:** ☐ Pass  ☐ Fail

---

## TC-011 — SKU Builder: Build `DMT-TX-R30X18` (doormat rectangular)

**Pre-condition**
- BA Lead login.

**Các bước**

1. Mở SKU Builder Wizard.
2. **Bước 1:** Product Name = `UAT-SKU-BUILDER Doormat 30x18 <date>` → family auto = `DMT` → Next.
3. **Bước 2:** Material = `Textile` → Next.
4. **Bước 3:**
   - Bỏ qua **Size** (M2O dropdown — DMT dùng rect)
   - **Rect W (manual):** `30`
   - **Rect H (manual):** `18`
   - Bấm Tab để commit.
   - Bấm Next.
5. **Bước 4:** Preview SKU = `DMT-TX-R30X18` → **Create**.

**Kỳ vọng**

- SP mới với `default_code` = `DMT-TX-R30X18`.
- Nếu điền Rect W = `0` hoặc `1000` → wizard báo "Rectangle dimensions must be 1-999".

**Pass / Fail:** ☐ Pass  ☐ Fail

---

## TC-012 — FR-017: Non-BA user bị chặn ở Create

> **Đã cover ở unit test `test_phase2_hub_sku_builder_orm::test_non_ba_user_blocked_before_template_create`.**
> Browser test này KHÔNG bắt buộc vì cần seed user "plain" (chỉ `base.group_user`) — không có sẵn.

**Pre-condition (nếu muốn test tay)**
- Admin seed 1 user `plain` chỉ có `base.group_user` (không thuộc `group_ba_user`).

**Các bước (manual)**

1. Login với user plain.
2. Đi đến URL `/odoo/action-multichannel_hub_core.action_product_sku_builder_wizard`.
3. Điền 4 bước như TC-008.
4. Bấm **Create** ở Bước 4.

**Kỳ vọng**

- Modal "Access Error" hiện với message yêu cầu group BA.
- Không có `product.template` mới được tạo.

**Pass / Fail:** ☐ Pass  ☐ Fail  ☐ Skip (cite unit test)

---

## Tổng kết UAT

| TC | Mô tả ngắn | Pass | Fail | Skip | Note |
|---|---|:-:|:-:|:-:|---|
| TC-001 | Wizard cũ — Mug | ☐ | ☐ | ☐ | |
| TC-002 | Wizard cũ — Dropship Gearment | ☐ | ☐ | ☐ | |
| TC-003 | SKU Drift Keep Legacy | ☐ | ☐ | ☐ | |
| TC-004 | SKU Drift Accept Canonical | ☐ | ☐ | ☐ | |
| TC-005 | Publish Etsy Draft (live) | ☐ | ☐ | ☐ | Cleanup Etsy Draft sau |
| TC-006 | BA User thấy nút Publish | ☐ | ☐ | ☐ | |
| TC-007 | Validator giá > 0 | ☐ | ☐ | ☐ | |
| TC-008 | SKU Builder MUG-CR-F11 | ☐ | ☐ | ☐ | |
| TC-009 | SKU Builder MUG-CR-F15-BK | ☐ | ☐ | ☐ | |
| TC-010 | SKU Builder APR-TX-AM | ☐ | ☐ | ☐ | |
| TC-011 | SKU Builder DMT-TX-R30X18 | ☐ | ☐ | ☐ | |
| TC-012 | FR-017 non-BA blocked | ☐ | ☐ | ☐ | OK skip + cite unit test |

**Người chạy:** ________________  **Ngày:** ____________  **Môi trường:** Staging / Production?

**Kết luận:**
- ☐ 11+/12 Pass → Approve.
- ☐ Có Fail → ghi chi tiết vào `docs/owner/UAT_FINDINGS_<date>.md` → tạo Jira ticket.

---

## Cleanup sau UAT

1. Vào menu **Sản phẩm**, filter theo SKU prefix `UAT-MUG-` hoặc `UAT-SKU-BUILDER-` hoặc `UAT-TAOSP`.
2. Tick tất cả SP UAT → **Action → Archive** (không xoá để giữ audit trail).
3. Nếu TC-005 chạy live → vào Etsy Shop Manager Drafts → Delete listing UAT.
4. Ghi UAT report vào `docs/owner/UAT_FINDINGS_<date>.md` (có sẵn template từ 2026-05-26).

---

> **Tài liệu liên quan:**
> - Hướng dẫn nghiệp vụ: [`HUONG_DAN_TAO_SAN_PHAM_VN.md`](./HUONG_DAN_TAO_SAN_PHAM_VN.md)
> - Tổng quan flow: [`FLOW_TAO_SAN_PHAM_VN.md`](./FLOW_TAO_SAN_PHAM_VN.md)
> - Auto UAT Playwright: `tests/e2e/tests/uat_huong_dan_tao_san_pham.spec.ts`
> - UAT findings 2026-05-26: `docs/owner/UAT_FINDINGS_2026-05-26.md`
