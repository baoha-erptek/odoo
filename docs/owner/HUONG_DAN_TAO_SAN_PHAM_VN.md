# Hướng dẫn sử dụng — Tạo sản phẩm mới

**Phiên bản:** 1.0 · **Ngày:** 2026-05-26 · **Ngôn ngữ:** Tiếng Việt
**Đối tượng:** Chủ shop, BA Lead, BA User
**Hệ thống:** Odoo 19 — module `multichannel_hub_core` + `etsy_integration`
**Tài liệu nghiệp vụ tham chiếu:** [`FLOW_TAO_SAN_PHAM_VN.md`](./FLOW_TAO_SAN_PHAM_VN.md)

> Hướng dẫn từng bước cho việc thêm sản phẩm mới vào hệ thống và đăng lên Etsy. Không yêu cầu kiến thức kỹ thuật — chỉ cần biết dùng trình duyệt web.

---

## Mục lục

1. [Yêu cầu trước khi bắt đầu](#1-yêu-cầu-trước-khi-bắt-đầu)
2. [Vai trò và quyền](#2-vai-trò-và-quyền)
3. [Cách 1 — Tạo sản phẩm bằng Wizard (đang hoạt động)](#3-cách-1--tạo-sản-phẩm-bằng-wizard)
4. [Cách 2 — Đồng bộ từ Excel (sắp ra mắt)](#4-cách-2--đồng-bộ-từ-excel)
5. [Quản lý mã SKU — câu chuyện hai mã](#5-quản-lý-mã-sku)
6. [Đăng sản phẩm lên Etsy](#6-đăng-sản-phẩm-lên-etsy)
7. [Câu hỏi thường gặp](#7-câu-hỏi-thường-gặp)
8. [Checklist kiểm thử UAT](#8-checklist-kiểm-thử-uat)
9. [Báo lỗi cho ai](#9-báo-lỗi-cho-ai)

---

## 1. Yêu cầu trước khi bắt đầu

- Có tài khoản đăng nhập Odoo với vai trò **BA User** hoặc cao hơn.
- Đã chuẩn bị các thông tin cho sản phẩm mới:
  - Tên sản phẩm (tiếng Anh, dùng cho Etsy).
  - Nhóm sản phẩm (Mug / Ring Dish / T-shirt / Tattoo …).
  - Giá niêm yết (USD cho Etsy, VND cho sản xuất).
  - Mã SKU nội bộ (nếu đã có) hoặc để hệ thống gợi ý.
  - (Tuỳ chọn) Mã SKU Gearment nếu giao qua Gearment.
- Trình duyệt Chrome / Edge / Firefox bản mới.

---

## 2. Vai trò và quyền

| Vai trò | Tạo sản phẩm | Đăng Etsy | Sửa SKU | Xoá sản phẩm |
|---|---|---|---|---|
| **BA User** | ✅ | ❌ | ❌ | ❌ |
| **BA Lead** | ✅ | ✅ | ✅ | ❌ |
| **BA Manager** | ✅ | ✅ | ✅ | ✅ |
| **Admin** | ✅ | ✅ | ✅ | ✅ |

Nếu không thấy menu **Sản phẩm → Tạo sản phẩm mới (Wizard)**, hãy liên hệ Admin để cấp quyền.

---

## 3. Cách 1 — Tạo sản phẩm bằng Wizard

### 3.1 Mở Wizard

1. Đăng nhập Odoo (mặc định: `https://odoo.hatafax.com`).
2. Mở menu **Sản phẩm** ở thanh trên cùng.
3. Chọn **Tạo sản phẩm mới (Wizard)**.

> Ảnh chụp màn hình: _đặt vào_ `docs/screenshots/wizard_create_product_menu.png`

### 3.2 Điền các trường bắt buộc

| Trường | Bắt buộc | Ví dụ | Ghi chú |
|---|---|---|---|
| **Tên sản phẩm** | ✅ | `Custom Coffee Mug 11oz` | Tiếng Anh; hiển thị trên Etsy |
| **Mã SKU nội bộ** | ✅ | `MUG-CE-S35-D0001` | Hệ thống gợi ý mã v2; có thể sửa |
| **Nhóm sản phẩm** | ✅ | `Mug` | Chọn từ dropdown |
| **Giá niêm yết (USD)** | ✅ | `19.99` | Giá bán Etsy |
| **Phí vận chuyển nội bộ (VND)** | ✅ | `25000` | Ước tính chi phí ship trong nước |
| **Các kênh áp dụng** | ✅ | ☑ Etsy | Mặc định Etsy; Amazon đang tắt |
| **Mã SKU Gearment** | ❌ | `GEAR-MUG-11OZ-BL` | Có giá trị → bật Dropship |
| **Mô tả** | ❌ | _free text_ | Hiển thị trên Etsy |
| **Ảnh sản phẩm** | ❌ | _upload_ | Có thể upload sau |

### 3.3 Nhấn "Tạo sản phẩm"

Hệ thống làm các việc sau (mất ≤ 3 giây):

- Tạo bản ghi `product.template` với thông tin đã điền.
- Tự sinh `product.product` (variant mặc định).
- Tạo `product.channel.status` cho từng kênh đã chọn — trạng thái `draft`.
- Nếu có mã Gearment → đặt cờ `is_dropship = True`.
- Mở form sản phẩm vừa tạo.

### 3.4 Kiểm tra ngay sau khi tạo

Trên form sản phẩm mới, kiểm tra:

- [ ] Tab **Thông tin chung**: tên, SKU, giá, nhóm — đúng như đã nhập.
- [ ] Tab **Kênh**: thấy dòng "Etsy — Nháp".
- [ ] Tab **Drift mã SKU**: nếu hệ thống gợi ý mã khác → BA quyết định giữ cũ hay đổi.
- [ ] Nút **"Đăng lên Etsy"** xuất hiện ở đầu form (chỉ BA Lead/Manager mới bấm được).

---

## 4. Cách 2 — Đồng bộ từ Excel

> ⚠️ **Chưa hoạt động hôm nay.** Tính năng đã thiết kế (Spec 010) nhưng chưa triển khai. Mô tả dưới đây là kế hoạch.

### 4.1 Đường dẫn upload

Khi BA đặt file Excel danh mục vào thư mục Google Drive đã cấu hình:

```
GDrive: /Hatafax_Catalog/<năm>/<tên_file>.xlsx
```

### 4.2 Cron tự động

- Lịch chạy: mỗi đêm khoảng **02:00 VN**.
- Hệ thống đọc file mới nhất theo timestamp.
- Mỗi dòng = một sản phẩm.

### 4.3 Quy tắc cập nhật

| Tình huống | Hành vi |
|---|---|
| SKU mới (chưa có trong hệ thống) | Tạo sản phẩm mới |
| SKU đã có | **Excel thắng** — cập nhật tên, giá, mô tả theo Excel |
| Sản phẩm cũ có kênh đã chọn | Không xoá — chỉ cập nhật nội dung |
| Dòng Excel lỗi format | Bỏ qua + ghi vào báo cáo |

### 4.4 Báo cáo cron

Mỗi sáng BA Lead nhận email tóm tắt:
- Số sản phẩm thêm mới
- Số sản phẩm cập nhật
- Số dòng bị lỗi (kèm lý do)

---

## 5. Quản lý mã SKU — câu chuyện hai mã

### 5.1 Hai bộ mã song song

| Mã | Khi nào dùng | Ví dụ |
|---|---|---|
| **Mã cũ (legacy)** | SKU BA đã dùng lâu nay; giữ trong "Lưu trữ SKU cũ" | `MUG-001`, `T-SHIRT-XL-RED` |
| **Mã chuẩn v2** | SKU mặc định cho sản phẩm mới | `MUG-CE-S35-D0001` |

### 5.2 Cấu trúc mã v2

`{3 ký tự nhóm}-{2 ký tự chất liệu}-{cỡ}-{mã thiết kế}`

Ví dụ: `MUG-CE-S35-D0001`
- `MUG` = nhóm Mug
- `CE` = chất liệu Ceramic
- `S35` = cỡ 350ml
- `D0001` = mã thiết kế số 1

### 5.3 Wizard chuẩn hoá SKU

Khi mở sản phẩm có mã legacy → tab **Drift mã SKU** hiện:

```
SKU hiện tại:   MUG-001        [Mã cũ]
SKU gợi ý v2:   MUG-CE-S35-D0001

[Giữ mã cũ]    [Chấp nhận mã v2]
```

- **Giữ mã cũ** → hệ thống nhớ quyết định, không hỏi lại.
- **Chấp nhận mã v2** → cập nhật mã trong Odoo + tự push lên Etsy (Etsy đang ở trạng thái "Còn hàng"). Nếu Etsy lỗi → rollback + ghi lỗi.

### 5.4 Xem danh sách SKU drift

**Menu:** Sản phẩm → **Drift mã SKU** → danh sách các sản phẩm có mã chưa khớp v2.

Bấm vào mỗi dòng để giải quyết.

---

## 6. Đăng sản phẩm lên Etsy

### 6.1 Điều kiện trước khi đăng

- [ ] Đã có ít nhất 1 ảnh sản phẩm.
- [ ] Tên sản phẩm tiếng Anh không có ký tự đặc biệt vượt quá 140 ký tự.
- [ ] Giá USD ≥ $0.20.
- [ ] Shop Etsy nguồn đã có `default_taxonomy_id` + `default_shipping_profile_id` + `default_return_policy_id` + `default_readiness_state_id` (Admin cấu hình một lần).

### 6.2 Bấm "Đăng lên Etsy"

1. Mở form sản phẩm.
2. Nhấn nút **"Đăng lên Etsy"** ở đầu form (chỉ BA Lead/Manager mới thấy).
3. Wizard hỏi xác nhận shop nguồn (nếu sản phẩm áp dụng nhiều shop).
4. Bấm **Đăng**.

Hệ thống làm các bước:

1. Gọi Etsy `createListing` → tạo listing Nháp trên Etsy.
2. Upload từng ảnh sản phẩm.
3. Gọi Etsy `push_inventory` → đẩy SKU + tồn kho lên Etsy.
4. Cập nhật `product.channel.status` từ `draft` → `published`.

### 6.3 Sau khi đăng

- [ ] Mở Etsy Shop Manager → thấy listing mới ở mục **Drafts** hoặc **Active** (tuỳ cấu hình).
- [ ] Trên Odoo, tab **Kênh** hiển thị "Etsy — Published" + Etsy listing_id.
- [ ] Nếu lỗi → tab **Kênh** hiển thị "Etsy — Failed" + thông báo lỗi → BA xem rồi bấm "Đăng lại".

---

## 7. Câu hỏi thường gặp

**Q:** _Tôi tạo nhầm sản phẩm. Xoá thế nào?_
A: Chỉ Admin mới xoá được. Liên hệ Admin và cung cấp SKU + lý do. Nếu sản phẩm chưa đăng lên Etsy → xoá an toàn. Nếu đã đăng → phải hạ listing Etsy trước.

**Q:** _Sản phẩm tạo xong nhưng không thấy nút "Đăng lên Etsy"._
A: Bạn đang ở vai trò BA User — chỉ BA Lead/Manager đăng được. Nhờ BA Lead bấm hoặc xin Admin nâng quyền.

**Q:** _Tôi muốn cùng một sản phẩm bán trên Etsy + Amazon._
A: Hôm nay chỉ Etsy hoạt động. Amazon được đánh dấu "không hoạt động" trong cấu hình. Khi Amazon ra mắt (Phase 5), BA chỉ cần tích thêm ☑ Amazon trong Wizard.

**Q:** _Mã SKU Gearment có bắt buộc không?_
A: Không. Để trống → sản phẩm chạy theo đường MTO (in nội bộ). Có giá trị → chạy theo đường Dropship Gearment.

**Q:** _Tôi đăng lên Etsy bị lỗi "A readiness_state_id is required for physical listings."_
A: Shop Etsy nguồn chưa cấu hình `default_readiness_state_id`. Liên hệ Admin để cấu hình từ menu **Etsy → Shop Settings**.

---

## 8. Checklist kiểm thử UAT

> Người kiểm thử: BA Lead · **Ngày kiểm:** _________ · **Môi trường:** Staging (`https://staging.odoo.hatafax.com`)

### TC-001: Tạo sản phẩm Mug bằng Wizard

- [ ] Đăng nhập vai trò BA User
- [ ] Mở Wizard tạo sản phẩm
- [ ] Điền: Tên = "UAT Mug 2026", SKU = (để hệ thống gợi ý), Nhóm = Mug, Giá USD = 12.99, Phí ship = 20000, Kênh = ☑ Etsy
- [ ] Bấm "Tạo sản phẩm"
- [ ] **Mong đợi:** Form sản phẩm mới hiển thị, tab Kênh có "Etsy — Nháp"
- [ ] **Kết quả thực tế:** _____
- [ ] **Pass / Fail:** _____

### TC-002: Tạo sản phẩm Dropship Gearment

- [ ] Mở Wizard
- [ ] Điền tất cả trường bắt buộc + Mã SKU Gearment = "GEAR-UAT-001"
- [ ] Bấm "Tạo sản phẩm"
- [ ] **Mong đợi:** Sản phẩm có cờ `is_dropship = True`, hiển thị huy hiệu "Dropship" trên form
- [ ] **Kết quả thực tế:** _____
- [ ] **Pass / Fail:** _____

### TC-003: Wizard Drift SKU — giữ mã cũ

- [ ] Mở sản phẩm có SKU legacy (ví dụ MUG-001)
- [ ] Mở tab "Drift mã SKU"
- [ ] Bấm "Giữ mã cũ"
- [ ] **Mong đợi:** Tab biến mất / hiển thị "Đã chốt giữ mã cũ"; sản phẩm không xuất hiện trong danh sách Drift nữa
- [ ] **Pass / Fail:** _____

### TC-004: Wizard Drift SKU — chấp nhận v2 (sản phẩm đã đăng Etsy)

- [ ] Mở sản phẩm đã đăng Etsy + có mã legacy
- [ ] Bấm "Chấp nhận mã v2"
- [ ] **Mong đợi:** Mã SKU đổi sang v2, tab Kênh hiển thị "Inventory push pending" rồi chuyển "pushed"; Etsy Shop Manager phản ánh SKU mới
- [ ] **Pass / Fail:** _____

### TC-005: Đăng sản phẩm lên Etsy (Draft mode)

- [ ] Mở sản phẩm UAT vừa tạo (có ít nhất 1 ảnh)
- [ ] Bấm "Đăng lên Etsy" (Draft)
- [ ] **Mong đợi:**
  - Trên Etsy Shop Manager → listing mới xuất hiện ở Drafts
  - Tab Kênh trong Odoo: "Etsy — Published (draft)" + listing_id
- [ ] **Pass / Fail:** _____

### TC-006: Phân quyền — BA User không đăng được Etsy

- [ ] Đăng nhập tài khoản BA User
- [ ] Mở sản phẩm bất kỳ
- [ ] **Mong đợi:** Không thấy nút "Đăng lên Etsy"; nếu cố gọi từ URL thì hệ thống báo `AccessError`
- [ ] **Pass / Fail:** _____

### TC-007: Validation — giá USD < 0.20

- [ ] Mở Wizard, điền giá USD = 0.10
- [ ] Bấm "Tạo sản phẩm"
- [ ] **Mong đợi:** Thông báo lỗi "Giá Etsy tối thiểu $0.20"
- [ ] **Pass / Fail:** _____

### Tổng kết UAT

- [ ] 7/7 test cases Pass → **Approve**
- [ ] Có Fail → ghi cụ thể vào báo cáo lỗi + tạo Jira sub-task

---

## 9. Báo lỗi cho ai

| Loại lỗi | Liên hệ |
|---|---|
| Wizard không mở / lỗi UI | Đội Kỹ thuật |
| Mã SKU bị nghi sai | BA Manager |
| Etsy báo lỗi khi đăng | BA Lead → Đội Kỹ thuật (kèm screenshot + listing_id) |
| Cron Excel không chạy | Đội Kỹ thuật |
| Quyền truy cập / role | Admin |

---

> **Tài liệu liên quan:**
> - Tổng quan nghiệp vụ: [`FLOW_TAO_SAN_PHAM_VN.md`](./FLOW_TAO_SAN_PHAM_VN.md)
> - Tài liệu kỹ thuật (tiếng Anh): `specs/009-product-hub/`, `specs/010-catalog-excel-sync/`, `specs/011-etsy-outbound-publish/`
> - BRD: `docs/owner/BRD_VN.md` (Epic 7)
