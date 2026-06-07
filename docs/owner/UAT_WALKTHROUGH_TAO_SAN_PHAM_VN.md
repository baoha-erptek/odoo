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

1. Wizard cũ chưa có menu — truy cập URL `/odoo/action-multichannel_hub_core.action_product_creation_wizard` trực tiếp (follow-up slice `P-HUB-WIZARD-MENU` sẽ thêm menu).
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

1. Mở menu **Operations → Configuration → Build SKU & Create Product** (hoặc URL `/odoo/action-multichannel_hub_core.action_product_sku_builder_wizard`).
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

## TC-013 — Publish giá USD lên shop Etsy dùng VND không lỗi `price_too_low`

> Mới từ 2026-06-06. Kiểm tra hệ thống tự đổi giá USD sang đơn vị tiền của shop Etsy (ví dụ VND) khi đăng listing.

**Pre-condition**
- Đã chạy trên **Staging**, shop *JaHandmadeArt* (đơn vị tiền Etsy = **VND**).
- Admin đã set sẵn (1 lần) trên môi trường test:
  - Bật **VND** ở menu *Cài đặt → Đơn vị tiền tệ → Currencies* (active = ✅).
  - Có **tỷ giá USD → VND** ngày hôm nay ở *Cài đặt → Đơn vị tiền tệ → Rates* (ví dụ `25400`).
  - Shop Etsy có trường **Listing Currency** = `VND` (hệ thống tự bootstrap khi cài bản mới — Admin xem ở Etsy → Shop Settings).
- BA Lead login.

**Các bước**

1. Tạo 1 sản phẩm thử qua menu **Operations → Configuration → Build SKU & Create Product** với:
   - **Product Name:** `UAT-CURRENCY <date>`
   - **Family / Material / Size:** chọn bất kỳ giá trị hợp lệ
   - **Listing Price (USD):** `12.99`
2. Bấm **Create** → SP được tạo, sang form Sản phẩm.
3. Trên form SP, chọn shop Etsy `JaHandmadeArt` (nếu có chọn nhiều shop) → bấm **Publish to Etsy**.
4. Đợi hệ thống gọi API Etsy. Quan sát thông báo / chatter.

**Kỳ vọng**

- Publish **thành công** — không có thông báo lỗi `price_too_low`. Trên chatter có dòng "Published to Etsy" (hoặc tương đương) kèm **Listing ID** Etsy trả về.
- Vào Etsy Shop Manager (https://www.etsy.com/your/shops/JaHandmadeArt/listings) → tìm draft mới — **giá listing hiển thị bằng VND** (ví dụ `12.99 × 25.400 = 329.946 ₫`, có thể sai số do làm tròn).
- BA chỉ điền giá USD ở Odoo — hệ thống tự đổi sang VND khi đăng. BA không cần tự nhân tỷ giá.

**Trường hợp âm — kiểm tra hệ thống cảnh báo khi thiếu cấu hình**

5. (tuỳ chọn) Admin tạm tắt VND ở *Cài đặt → Đơn vị tiền tệ* HOẶC xoá tỷ giá USD→VND hôm nay.
6. Lặp lại bước 1–3 với SP mới (USD `12.99`).
7. Kỳ vọng: hiện thông báo lỗi rõ ràng (ví dụ "*No conversion rate found for VND on …*") — KHÔNG publish thầm với giá sai. Admin bật lại VND / thêm lại tỷ giá → publish lại OK.

**Cleanup**
- Vào Etsy Shop Manager → xoá draft UAT vừa tạo.
- Archive SP UAT trong Odoo (Action → Archive).

**Pass / Fail:** ☐ Pass  ☐ Fail  ☐ Skip (nếu không có quyền truy cập Etsy Shop Manager)

---

## TC-014 — Publish SP nhiều size: mỗi size có SKU + giá + hình riêng (LIVE JaHandmadeArt)

> Mới từ 2026-06-06 (P-BUG-ESTY-188 iter3). Kiểm tra hệ thống publish đúng mô hình "biến thể" (per-variant) của Etsy thay vì gửi một SKU/giá chung cho cả listing.

**Tại sao TC này quan trọng**

Trước iter3, hệ thống chỉ gửi 1 SKU + 1 giá + 1 hình cho cả listing (kể cả khi SP có nhiều size). Etsy từ chối với 2 lỗi:
- `400 /price empty` — nếu giá gốc SP là `0` và giá thật nằm ở "Giá thêm theo size" (price_extra).
- `quantity must be consistent across all products` — nếu mỗi size có số lượng tồn khác nhau.

Sau iter3 hệ thống tự:
- Lấy giá thấp nhất trong các biến thể làm giá "từ" cho listing.
- Mỗi size có SKU + giá + tồn riêng trong payload gửi Etsy.
- Nếu mỗi size có hình riêng (`Variant Image`), hệ thống tự upload + gán cho từng size trên Etsy.

**Pre-condition**
- Đã chạy trên **Staging**, shop *JaHandmadeArt*.
- Tỷ giá USD→VND của ngày hôm nay đã có (xem TC-013 prerequisites).
- BA Lead login.

**Các bước**

1. Vào menu **Sản phẩm → Tất cả Sản phẩm** → tạo SP mới (hoặc dùng wizard SKU Builder) với:
   - **Product Name:** `UAT-PV <date>` (PV = per-variant)
   - **List Price (USD):** `0.00` (cố ý để 0 — giá thật nằm ở size)
   - **Variants:** tab *Attributes & Variants*, thêm thuộc tính `Size` với 3 giá trị (ví dụ `4"`, `6"`, `8"`).
2. Mở tab *Attributes & Variants* → ở từng dòng giá trị Size, điền **Price Extra** lần lượt `10.00`, `20.00`, `30.00`.
3. Vào menu **Sản phẩm → Variants** (Biến thể), tìm 3 variant của SP `UAT-PV` → mỗi variant upload 1 hình khác nhau vào trường **Variant Image** (kích thước ≥ 1 MB, JPEG / PNG).
4. Quay lại form SP → bấm **Publish to Etsy** với shop `JaHandmadeArt`.
5. Đợi hệ thống gọi API Etsy. Quan sát thông báo / chatter.

**Kỳ vọng**

- Publish **thành công** — không có lỗi `/price empty` hoặc `quantity must be consistent`.
- Vào Etsy Shop Manager → tìm draft `UAT-PV <date>` → tab **Variations**:
  - Có 3 variation Size: 4", 6", 8" — mỗi cái có SKU + giá + tồn kho riêng.
  - Giá lần lượt khoảng `10 × 25.400 ≈ 254.000 ₫`, `20 × 25.400 ≈ 508.000 ₫`, `30 × 25.400 ≈ 762.000 ₫` (sai số làm tròn được).
  - Mỗi variation có **hình riêng** (Etsy hiển thị hình variant ở dropdown chọn size). Tức 4" hiện hình đã upload cho variant 4", v.v.

**Negative path — hệ thống chặn khi không có giá**

6. Tạo SP mới `UAT-PV-NOPRICE` với `List Price = 0` và KHÔNG điền `Price Extra` cho bất kỳ size nào.
7. Bấm **Publish to Etsy**.
8. Kỳ vọng: hệ thống chặn ngay (UserError "*Cannot resolve a positive starting price …*") — KHÔNG gọi API Etsy. Chatter ghi rõ thông báo. BA biết cần điền giá trước.

**Cleanup**
- Etsy Shop Manager → Drafts → xoá listing UAT-PV vừa tạo.
- Archive SP UAT trong Odoo.

**Pass / Fail:** ☐ Pass  ☐ Fail  ☐ Skip (nếu không có quyền truy cập Etsy Shop Manager)

---

## TC-015 — Tách lớp Sản phẩm/Listing — backfill ngày 1 + override title (LIVE JaHandmadeArt)

> Mới từ 2026-06-06 (P-LIST-MODEL, ADR-015). Kiểm tra hệ thống đã tự tạo "dòng Listing" cho mọi SP đã đăng Etsy + Marketing có thể override title riêng cho từng shop.

**Tại sao TC này quan trọng**

ADR-015 tách 2 khái niệm: "Sản phẩm" (BA sở hữu — kích thước/SKU/giá) vs "Listing" (Marketing sở hữu — title/mô tả marketing/category Etsy theo từng shop). Hệ thống tự backfill ngày 1 nên không gián đoạn các SP đã đăng. Sau đó Marketing có thể bắt đầu nhập override.

**Pre-condition**
- Đã rsync + `-u multichannel_hub_core` trên Staging.
- Tài khoản BA Lead + tài khoản Marketing (Admin gán quyền nếu chưa).
- Có ít nhất 1 SP `product.template` đã đăng Etsy thành công trước đây (ví dụ SP từ TC-014).

**Các bước**

**Phần 1 — Verify backfill (Admin / BA Lead login)**

1. Vào menu **Operations → Listings** (menu MỚI sau khi cài bản này).
2. Tìm dòng tương ứng SP đã đăng Etsy ở pre-condition.
3. Kỳ vọng: 1 dòng Listing tồn tại, **State = Draft**, **Title = trống** (rỗng), **Description = trống**, **Channel = Etsy**, **Shop = trống**, **External Reference = trống**.
4. Backfill chỉ tạo stub — override fields đều null. Vẫn lấy fallback từ SP master.

**Phần 2 — Verify publish không gián đoạn (BA Lead login)**

5. Vào SP master, bấm **Publish to Etsy** như TC-005.
6. Kỳ vọng: publish thành công, listing Etsy hiển thị title = `product.template.name` (như cũ, không thay đổi).

**Phần 3 — Marketing override title (Marketing login)**

7. Login bằng tài khoản Marketing. Vào **Operations → Listings**.
8. Mở dòng Listing của SP. **Title** trống → điền `Marketing Override Title <date>`.
9. Bấm Save.
10. Kỳ vọng: ghi được. (Nếu báo lỗi AccessError → kiểm tra quyền Marketing đã add đúng group `Multichannel Hub Core / Marketing User`.)

**Phần 4 — Verify override emit khi publish (BA Lead login lại)**

11. Login lại BA Lead. Mở SP master, bấm Publish to Etsy lần nữa với shop khác (hoặc archive listing cũ + publish lại).
12. Kỳ vọng: listing Etsy mới hiển thị title = `Marketing Override Title <date>` (đã override), KHÔNG dùng `product.template.name`.

**Phần 5 — Verify BA read-only trên Listing (BA Lead login)**

13. Vào **Operations → Listings**, mở 1 dòng bất kỳ.
14. Thử sửa Title.
15. Kỳ vọng: hệ thống chặn (AccessError "You do not have write access on multichannel.listing"). BA chỉ xem được, không sửa.

**Phần 6 — Verify record-rule chống unlink published listing (Marketing login)**

16. Login Marketing. Vào **Operations → Listings**.
17. Filter `State = Published`. Tick 1 dòng → Action → Delete.
18. Kỳ vọng: hệ thống chặn xoá (AccessError record rule). Marketing phải archive listing Etsy trước rồi mới xoá được.

**Cleanup**
- Sửa Title về trống ở các dòng đã override trong TC.
- Archive bất kỳ Etsy Draft nào tạo trong TC.

**Pass / Fail:** ☐ Pass  ☐ Fail  ☐ Skip (nếu không có tài khoản Marketing riêng)

---

## TC-016 — Upload video lên Etsy listing (P-LIST-VIDEO)

> Mới từ 2026-06-06 (P-LIST-VIDEO, Jira ESTY-199). Kiểm tra Marketing upload được 1 video cho từng listing và Etsy nhận đúng.

**Pre-condition**
- Đã rsync + `-u multichannel_hub_core,etsy_integration` trên Staging.
- Có 1 SP đã đăng Etsy thành công trên `JaHandmadeArt` (dùng TC-014/TC-015 hoặc SP cũ).
- Có 1 file video `.mp4` ngắn (10-30 giây) cỡ ≤ 50MB để upload.
- Tài khoản Marketing login.

**Các bước**

1. Login Marketing. Vào **Operations → Listings**.
2. Mở dòng Listing của SP × `JaHandmadeArt`.
3. Sang tab **Video** (tab mới).
4. Bấm vào trường **Video** → tải lên file `.mp4` chuẩn bị.
5. Save.
6. Login lại BA Lead.
7. Mở SP master, bấm **Publish to Etsy** với shop `JaHandmadeArt`.
8. Đợi hệ thống chạy hết publish chain (~30-60s).

**Kỳ vọng**

- Publish thành công. Trên chatter: không lỗi, có dòng log "Etsy createListing", "Etsy push_inventory", "Etsy uploadListingVideo" (hoặc tương đương).
- Vào Etsy Shop Manager → tìm draft mới → tab Listing details → mục Video: thấy video đã upload. Click play để xác nhận đúng video.

**Negative path — upload thất bại không chặn publish**

9. (tuỳ chọn) Marketing đổi file video bằng file rỗng (`.mp4` 0 byte) hoặc file lỗi format.
10. BA bấm Publish lại.
11. Kỳ vọng: listing vẫn publish thành công (không có video). Log có dòng WARNING "Etsy push_video failed for listing ...". Chatter SP hiển thị listing đã đăng nhưng video trống.

**Cleanup**
- Etsy Shop Manager → Drafts → xoá draft UAT.
- Operations → Listings → xoá file video khỏi tab Video (clear trường) — nếu listing chưa published thì có thể xoá luôn cả Listing row.

**Pass / Fail:** ☐ Pass  ☐ Fail  ☐ Skip (nếu không có file video sẵn)

---

## TC-017 — Chọn Etsy Category per-listing — fallback chain (P-LIST-CATEGORY)

> Mới từ 2026-06-06 (P-LIST-CATEGORY, Jira ESTY-189).

**Pre-condition**
- Đã rsync + `-u multichannel_hub_core,etsy_integration` trên Staging.
- Tài khoản Marketing + Admin login.

**Bước 1 — Sync taxonomy (Admin login lần đầu)**

1. Vào form Etsy Shop nào đó (Settings → Etsy Shops) → bấm **Sync Etsy Taxonomy** (hoặc đợi cron hàng tuần).
2. Đợi sync xong → thông báo `Etsy taxonomy synced: N new, 0 updated`.
3. Vào **Operations → Etsy Taxonomy** → thấy danh sách hàng nghìn nodes với cột `full_path` đầy đủ.

**Bước 2 — Marketing chọn category per-listing**

4. Login Marketing. Vào **Operations → Listings** → mở 1 dòng.
5. Tab **Etsy** → trường **Etsy Category** → gõ "Cookware" → autocomplete hiển thị `Home & Living / Kitchen / Cookware [#1234]` chẳng hạn → chọn.
6. Save.

**Bước 3 — BA publish và verify category override**

7. Login BA Lead. Mở SP master → Publish to Etsy với shop tương ứng.
8. Trên chatter / log: tìm dòng `Etsy createListing payload taxonomy_id=...` (hoặc xem Etsy Shop Manager).
9. Verify: listing được tạo với category Marketing đã chọn ở Listing layer (KHÔNG dùng category cũ ở Sản phẩm).

**Bước 4 — Negative: clear listing override → fallback về shop default**

10. Marketing vào Listing → clear trường **Etsy Category** → Save.
11. BA publish lại → verify category dùng `etsy.shop.default_taxonomy_id` (shop default).

**Pass / Fail:** ☐ Pass  ☐ Fail  ☐ Skip

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
| TC-013 | Publish USD→VND không lỗi `price_too_low` | ☐ | ☐ | ☐ | Cần shop VND + tỷ giá hôm nay |
| TC-014 | Publish SP nhiều size: SKU/giá/hình riêng (per-variant) | ☐ | ☐ | ☐ | Cần shop VND + tỷ giá; cleanup Etsy Draft sau |
| TC-015 | Tách lớp Sản phẩm/Listing — backfill day-1 + override title | ☐ | ☐ | ☐ | Marketing menu mới; SP đã đăng vẫn publish được không gián đoạn |
| TC-016 | Upload video lên Etsy listing (1 video/listing) | ☐ | ☐ | ☐ | Cần file .mp4 ≤ 100MB; cleanup video sau |
| TC-017 | Chọn Etsy Category per-listing — fallback chain | ☐ | ☐ | ☐ | Sync taxonomy trước nếu cache rỗng |
| TC-018 | Chọn Shipping Profile per-listing — fallback chain | ☐ | ☐ | ☐ | Sync shipping profiles trước; per-shop scope |
| TC-019 | "How it's made" per-listing — who/when/is_supply chain | ☐ | ☐ | ☐ | 3-tier listing → product → shop |
| TC-020 | Attribute mapping per-listing override — 3-tier chain | ☐ | ☐ | ☐ | Marketing override; blank row falls through |
| TC-021 | Shop attribute defaults — tier-2 fallback | ☐ | ☐ | ☐ | Etsy Shop Settings; pairs with TC-020 |
| TC-022 | Bulk Mark Ready + Reset to Draft + state-lock | ☐ | ☐ | ☐ | Operations → Listings list-view server actions |
| TC-023 | Shop Currency Preview hiển thị đúng số tiền VND | ☐ | ☐ | ☐ | Listing form → Shipping & Variations → Shop Currency Preview. Chọn shop VND, đảm bảo `res.currency.rate` USD→VND có sẵn, kiểm tra giá hiện ≠ 0.00 và bằng `list_price × rate`. Bỏ chọn shop → giá về 0.00, không crash. |
| TC-024 | Shop Brand-Voice Defaults — fallback chain | ☐ | ☐ | ☐ | Operations → Channels → Etsy Shops → mở shop → Publisher Defaults → Shop Brand-Voice Defaults. Set `default_title='Shop Title Test'`. Tạo sản phẩm KHÔNG có tiêu đề listing riêng, KHÔNG đổi product name → publish → kiểm tra payload Etsy (audit log) carry `title='Product Name'` (product layer wins, không xuống shop). Sau đó tạo product với name='' (test ORM-level — skip nếu khó) → kiểm tra shop default fires. Bỏ trống shop default → fallback về product name. |

**Người chạy:** ________________  **Ngày:** ____________  **Môi trường:** Staging / Production?

**Kết luận:**
- ☐ 12+/13 Pass → Approve.
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
