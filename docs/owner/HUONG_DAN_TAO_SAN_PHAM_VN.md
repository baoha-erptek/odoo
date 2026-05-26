# Hướng dẫn sử dụng — Tạo sản phẩm mới

**Phiên bản:** 1.1 · **Ngày:** 2026-05-26 · **Ngôn ngữ:** Tiếng Việt
**Đối tượng:** Chủ shop, BA Lead, BA User
**Hệ thống:** Odoo 19 — module `multichannel_hub_core` + `etsy_integration`
**Tài liệu nghiệp vụ tham chiếu:** [`FLOW_TAO_SAN_PHAM_VN.md`](./FLOW_TAO_SAN_PHAM_VN.md)

> Hướng dẫn từng bước cho việc thêm sản phẩm mới vào hệ thống và đăng lên Etsy. Không yêu cầu kiến thức kỹ thuật — chỉ cần biết dùng trình duyệt web.

> **Cập nhật v1.1 (2026-05-26):** thêm Wizard mới **"Tạo sản phẩm theo SKU Builder (4 bước)"** kèm validator mã v2 (soft/hard) và sub-form bổ sung kích thước khi tên sản phẩm thiếu thông tin. Sửa ma trận quyền (BA User có thể đăng Etsy) và chính tả validator giá (`> 0`, không phải `>= 0.20`). Thêm TC-008..TC-012 vào checklist UAT.

---

## Mục lục

1. [Yêu cầu trước khi bắt đầu](#1-yêu-cầu-trước-khi-bắt-đầu)
2. [Vai trò và quyền](#2-vai-trò-và-quyền)
3. [Hai cách tạo sản phẩm — chọn cái nào?](#3-hai-cách-tạo-sản-phẩm--chọn-cái-nào)
4. [Cách 1A — Wizard tạo sản phẩm cổ điển (Creation Wizard)](#4-cách-1a--wizard-tạo-sản-phẩm-cổ-điển)
5. [Cách 1B — SKU Builder Wizard (4 bước, có hướng dẫn)](#5-cách-1b--sku-builder-wizard-4-bước)
6. [Validator mã SKU v2 (soft / hard mode)](#6-validator-mã-sku-v2)
7. [Cách 2 — Đồng bộ từ Excel (sắp ra mắt)](#7-cách-2--đồng-bộ-từ-excel)
8. [Quản lý mã SKU — câu chuyện hai mã](#8-quản-lý-mã-sku--câu-chuyện-hai-mã)
9. [Đăng sản phẩm lên Etsy](#9-đăng-sản-phẩm-lên-etsy)
10. [Câu hỏi thường gặp](#10-câu-hỏi-thường-gặp)
11. [Checklist kiểm thử UAT](#11-checklist-kiểm-thử-uat)
12. [Báo lỗi cho ai](#12-báo-lỗi-cho-ai)

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

| Vai trò | Tạo sản phẩm (Wizard cũ) | Tạo SP (SKU Builder) | Đăng Etsy | Sửa SKU | Xoá sản phẩm |
|---|---|---|---|---|---|
| **BA User** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **BA Lead** | ✅ | ✅ | ✅ | ✅ | ❌ |
| **BA Manager** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Admin** | ✅ | ✅ | ✅ | ✅ | ✅ |

> **Lưu ý quan trọng (đã sửa từ v1.0):** Mọi user thuộc tier **BA** (User / Lead / Manager) đều có quyền đăng sản phẩm lên Etsy. Cổng kiểm tra (`group_ba_user`) được dùng nhất quán ở 26 chỗ trong code — đây là thiết kế chính thức (defense-in-depth: view + method-top gate). Tài liệu v1.0 ghi "BA User ❌ Đăng Etsy" là **sai** — đã sửa.

Nếu không thấy menu **Sản phẩm → Tạo sản phẩm mới (Wizard)** hoặc **Sản phẩm → SKU Builder Wizard**, hãy liên hệ Admin để cấp quyền `group_ba_user`.

---

## 3. Hai cách tạo sản phẩm — chọn cái nào?

| Tính năng | Cách 1A — Wizard cũ | Cách 1B — SKU Builder (4 bước) |
|---|---|---|
| **Khi nào dùng** | Đã biết chính xác SKU muốn dùng (legacy hoặc v2 tự gõ) | Tạo SP mới muốn hệ thống tự dựng SKU v2 đúng grammar |
| **Số bước** | 1 form duy nhất | 4 bước có statusbar (Family → Material → Size → Preview) |
| **Tự gợi ý SKU?** | Có (chỉ FAM3) | Có (đầy đủ FAM3-MAT2-SIZE[-VAR2]) |
| **Có hỏi thiếu thông tin?** | Không — báo lỗi cho BA tự sửa | Có — sub-form bổ sung size khi tên SP không đủ thông tin |
| **Validator v2** | Có (soft/hard) — kiểm tra `default_code` BA gõ | Có (soft/hard) — preview SKU luôn hợp lệ vì hệ thống dựng |
| **Tốc độ với SP đơn giản** | Nhanh hơn (1 click Create) | Chậm hơn 1-2 click (Next/Next/Next/Create) |
| **Tốc độ với SP phức tạp** | Chậm (phải gõ tay đúng) | Nhanh hơn (hệ thống giúp dựng) |

> **Gợi ý:** Mỗi BA chọn theo thói quen. Hai wizard cùng tồn tại — không có cái nào "sắp bị bỏ". Mã SKU sinh ra từ cả hai đều đi qua cùng validator v2 ở mục 6.

---

## 4. Cách 1A — Wizard tạo sản phẩm cổ điển

### 4.1 Mở Wizard

1. Đăng nhập Odoo (mặc định: `https://odoo.hatafax.com`).
2. Mở menu **Sản phẩm** ở thanh trên cùng.
3. Chọn **Tạo sản phẩm mới (Wizard)**.

### 4.2 Điền các trường bắt buộc

| Trường | Bắt buộc | Ví dụ | Ghi chú |
|---|---|---|---|
| **Tên sản phẩm** | ✅ | `Custom Coffee Mug 11oz` | Tiếng Anh; hiển thị trên Etsy |
| **Mã SKU nội bộ** | ✅ | `MUG-CR-F11` | Hệ thống gợi ý FAM3 (`MUG`); BA gõ phần còn lại theo grammar v2.1 (xem §8) |
| **Nhóm sản phẩm** | ✅ | `All` (an toàn) hoặc nhóm cụ thể | Chọn từ dropdown |
| **Giá niêm yết (USD)** | ✅ | `19.99` | Giá bán Etsy; phải `> 0` |
| **Phí vận chuyển nội bộ (VND)** | ✅ | `25000` | Ước tính chi phí ship trong nước |
| **Các kênh áp dụng** | ✅ | ☑ Etsy | Mặc định Etsy; Amazon đang tắt |
| **Mã SKU Gearment** | ❌ | `GEAR-MUG-11OZ-BL` | Có giá trị → bật Dropship |
| **Mô tả** | ❌ | _free text_ | Hiển thị trên Etsy |
| **Ảnh sản phẩm** | ❌ | _upload_ | Có thể upload sau |

### 4.3 Nhấn "Tạo sản phẩm"

Hệ thống làm các việc sau (mất ≤ 3 giây):

- Chạy validator v2 trên `default_code` (xem mục 6).
- Tạo bản ghi `product.template` với thông tin đã điền.
- Tự sinh `product.product` (variant mặc định).
- Tạo `product.channel.status` cho từng kênh đã chọn — trạng thái `draft`.
- Nếu có mã Gearment → đặt cờ `is_dropship = True`.
- Mở form sản phẩm vừa tạo.

### 4.4 Kiểm tra ngay sau khi tạo

Trên form sản phẩm mới, kiểm tra:

- [ ] Tab **Thông tin chung**: tên, SKU, giá, nhóm — đúng như đã nhập.
- [ ] Tab **Channels** (Kênh): thấy dòng "Etsy — Draft".
- [ ] Tab **SKU Drift**: nếu hệ thống gợi ý mã khác → BA quyết định giữ cũ hay đổi (xem mục 8).
- [ ] Nút **"Publish to Etsy"** xuất hiện ở header form (mọi BA tier đều thấy).

---

## 5. Cách 1B — SKU Builder Wizard (4 bước)

> **Mới từ 2026-05-26** (slice MP006 `P-HUB-SKU-BUILDER` + `P-HUB-MISSING-INFO-WIZARD`).

### 5.1 Mở Wizard

1. Menu **Operations → Configuration → SKU Builder Wizard** (hoặc URL action `multichannel_hub_core.action_product_sku_builder_wizard`).
2. Form 4 bước hiển thị; statusbar trên đầu chỉ bước hiện tại (Family → Material → Size → Preview).

### 5.2 Bước 1 — Family (Nhóm sản phẩm)

| Trường | Bắt buộc | Ví dụ | Ghi chú |
|---|---|---|---|
| **Product Name** | ✅ | `Custom Coffee Mug 11oz` | Đầu vào tiếng Anh — hệ thống phân loại family từ đây |
| **Family (auto)** | _readonly_ | `MUG` | Hệ thống tự gợi ý dựa trên tên, ví dụ từ "mug" → `MUG` |
| **Family (override)** | ❌ | `MUG` (giữ nguyên) | Nếu auto-suggest sai → BA chọn family đúng từ dropdown 22 family |

> Hệ thống dùng bảng 22 family (xem `docs/owner/SKU_GRAMMAR.md` §2). Nếu tên sản phẩm không khớp family nào → auto-suggest = `MSC` (Misc) và BA cần override.

Nhấn **Next** để qua bước 2.

### 5.3 Bước 2 — Material (Chất liệu)

| Trường | Bắt buộc | Ví dụ | Ghi chú |
|---|---|---|---|
| **Material** | ✅ | `Ceramic + Chrome` (mã `CR`) | Many2one chọn từ `product.attribute.value` thuộc attribute "Material" |

Bảng tóm tắt 7 mã chất liệu (mục 3 SKU_GRAMMAR.md):

| Mã | Material | Ví dụ tên display |
|---|---|---|
| `CE` | Ceramic | "Ceramic" |
| `WD` | Wood | "Wood" |
| `PA` | Paper / Card | "Paper" |
| `TX` | Textile | "Textile" |
| `MT` | Metal | "Metal" |
| `CR` | Ceramic + chrome | "Ceramic + Chrome" |
| `MX` | Mixed / Unknown | "Mixed" |

> **Tip:** Mỗi family có `default_material` riêng — wizard sẽ pre-select gợi ý (ví dụ MUG → CR). BA xác nhận hoặc đổi.

Nhấn **Next**.

### 5.4 Bước 3 — Size (Kích thước)

Hệ thống **gate theo family**: chỉ hiển thị size hợp lệ cho family đó.

| Family | Namespace size | Ví dụ giá trị |
|---|---|---|
| MUG / TUM | Fluid oz | `F11` (11 oz), `F15` (15 oz), `F20` (20 oz) |
| APR / APP | Apparel | `AS/AM/AL/AX/AXX` (S/M/L/XL/XXL) |
| RDS / TRK / JWD / CDS / WDS | Shape hoặc Dim | `SQ/HT/OV` (shape) hoặc `S35` (3.5") |
| DMT / RUG | Rectangular | `R30X18` (30" × 18") |

#### 5.4.1 Trường hợp tên SP đã đủ thông tin

- BA chọn **Size** từ dropdown → wizard tự suy ra mã (ví dụ "11 oz" → `F11`).
- Nhấn **Next**.

#### 5.4.2 Trường hợp tên SP thiếu thông tin (Missing Info)

> **Tính năng mới 2026-05-26** — slice `P-HUB-MISSING-INFO-WIZARD`.

Nếu tên sản phẩm không chứa thông tin size (ví dụ `Color Changing Beverage` không có "11 oz") → wizard hiển thị **sub-form bổ sung** trong Bước 3:

| Trường | Bắt buộc | Ghi chú |
|---|---|---|
| **Size (manual)** | Chọn 1 trong 2 | Many2one tới `product.attribute.value` — chọn từ dropdown |
| **Rect W (manual)** | Chọn 1 trong 2 | Integer (1-999) — dùng cho doormat / rug |
| **Rect H (manual)** | Chọn 1 trong 2 | Integer (1-999) — đi kèm Rect W |

Wizard tự nhận biết family nào dùng size_id, family nào dùng `rect_w/rect_h`. Sub-form chỉ hiện khi:
- Tên SP không chứa token size khớp với family namespace, VÀ
- Family yêu cầu size (không phải MSC).

Sau khi điền → nhấn **Next**.

### 5.5 Bước 4 — Preview & Create

| Trường | Bắt buộc | Ví dụ | Ghi chú |
|---|---|---|---|
| **Color (VAR2)** | ❌ | `Black` (mã `BK`) | Optional — chỉ dùng cho variant cố định (xem §5 SKU_GRAMMAR.md) |
| **Preview SKU** | _readonly_ | `MUG-CR-F11-BK` | Hệ thống tự dựng từ FAM3 + MAT2 + SIZE + VAR2 |

Kiểm tra preview SKU đúng → nhấn **Create**.

Hệ thống làm:

- Gọi `_check_ba_or_raise()` (FR-017 gate) — chặn user không có `group_ba_user`.
- Kiểm tra preview SKU với validator v2 (luôn pass vì wizard tự dựng).
- Tạo `product.template` với `default_code = preview_sku`.
- Sinh variant mặc định + `product.channel.status` (channel `etsy` default).
- Đóng wizard, mở form sản phẩm vừa tạo.

### 5.6 Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách xử lý |
|---|---|---|
| **Access Error** ở bước Create | User không có `group_ba_user` | Liên hệ Admin nâng quyền |
| **Size or manual fallback required** | Bước 3: family yêu cầu size nhưng tên SP không có token VÀ sub-form chưa điền | Điền `Size (manual)` hoặc `Rect W` + `Rect H` |
| **Size doesn't match family namespace** | Bước 3: chọn size không hợp lệ cho family (ví dụ `Medium` cho family `MUG`) | Đổi size hoặc đổi family ở Bước 1 |
| **Rectangle dimensions must be 1-999** | Bước 3 sub-form: Rect W/H ≤ 0 hoặc ≥ 1000 | Sửa giá trị |

---

## 6. Validator mã SKU v2

> **Mới từ 2026-05-26** — slice MP006 `P-HUB-V2-VALIDATE-ON-CREATE`.

### 6.1 Quy tắc v2

Mỗi SKU mới phải khớp regex sau (xem `docs/owner/SKU_GRAMMAR.md` §7.1):

```
^[A-Z]{3}-[A-Z]{2}-(SQ|HT|OV|LSQ|WV|AR|BW|RD|S\d+|F\d+|A[A-Z]+|R\d+X\d+)(-[A-Z]{2})?$
```

Độ dài: 8 ≤ chars ≤ 14.

Ví dụ hợp lệ: `MUG-CR-F11`, `APR-TX-AM`, `DMT-TX-R30X18`, `MUG-CR-F15-BK`.
Ví dụ không hợp lệ: `MUG-001` (legacy), `mug-cr-f11` (chữ thường), `MUG-CR-F11-EXTRA-LONG`.

### 6.2 Hai mode

Mode được cấu hình qua ICP (Settings → Technical → Parameters → System Parameters) `multichannel_hub.sku_v2_enforce_mode`:

| Mode | Hành vi | Mặc định? |
|---|---|---|
| **soft** | SKU không hợp lệ vẫn được lưu, set `x_sku_v2_status = 'ba_approved_legacy'` + log WARNING + banner UI | ✅ Mặc định |
| **hard** | SKU không hợp lệ → `UserError`, không tạo sản phẩm | ❌ Bật khi đã sẵn sàng enforce |

### 6.3 Khi nào validator chạy

- **Wizard cũ (Cách 1A)**: chạy trong `_validate()` trước khi `Template.create()`. Nếu soft + SKU legacy → pin `x_sku_v2_status='ba_approved_legacy'` để skip kiểm lại.
- **SKU Builder (Cách 1B)**: chạy nhưng preview SKU luôn pass vì hệ thống tự dựng đúng grammar.
- **Wizard SKU Drift** (mục 8): không re-validate — đã có flow riêng.

### 6.4 Sản phẩm cũ (legacy) có bị ảnh hưởng?

Không. Sản phẩm có sẵn không bị re-validate. Chỉ SKU **tạo mới** và **sửa lại** mới qua validator. Sản phẩm legacy được pin `ba_approved_legacy` tự động khi đi qua wizard lần đầu.

---

## 7. Cách 2 — Đồng bộ từ Excel

> ⚠️ **Chưa hoạt động hôm nay.** Tính năng đã thiết kế (Spec 010) nhưng cron chưa wire. Mô tả dưới đây là kế hoạch (sub-phase 3c).

### 7.1 Đường dẫn upload

Khi BA đặt file Excel danh mục vào thư mục Google Drive đã cấu hình:

```
GDrive: /Hatafax_Catalog/<năm>/<tên_file>.xlsx
```

### 7.2 Cron tự động

- Lịch chạy: mỗi đêm khoảng **02:00 VN**.
- Hệ thống đọc file mới nhất theo timestamp.
- Mỗi dòng = một sản phẩm.

### 7.3 Quy tắc cập nhật

| Tình huống | Hành vi |
|---|---|
| SKU mới (chưa có trong hệ thống) | Tạo sản phẩm mới |
| SKU đã có | **Excel thắng** — cập nhật tên, giá, mô tả theo Excel |
| Sản phẩm cũ có kênh đã chọn | Không xoá — chỉ cập nhật nội dung |
| Dòng Excel lỗi format | Bỏ qua + ghi vào báo cáo |

### 7.4 Báo cáo cron

Mỗi sáng BA Lead nhận email tóm tắt:
- Số sản phẩm thêm mới
- Số sản phẩm cập nhật
- Số dòng bị lỗi (kèm lý do)

---

## 8. Quản lý mã SKU — câu chuyện hai mã

### 8.1 Hai bộ mã song song

| Mã | Khi nào dùng | Ví dụ |
|---|---|---|
| **Mã cũ (legacy)** | SKU BA đã dùng lâu nay; giữ trong "Lưu trữ SKU cũ" | `MUG-001`, `T-SHIRT-XL-RED` |
| **Mã chuẩn v2** | SKU mặc định cho sản phẩm mới | `MUG-CR-F11`, `APR-TX-AM` |

### 8.2 Cấu trúc mã v2

`{FAM3}-{MAT2}-{SIZE}[-{VAR2}]`

Ví dụ: `MUG-CR-F11-BK`
- `MUG` = nhóm Mug (FAM3)
- `CR` = chất liệu Ceramic + Chrome (MAT2)
- `F11` = 11 oz fluid (SIZE — fluid_oz namespace)
- `BK` = màu Black (VAR2 — optional)

Đầy đủ 22 family + 7 material + 5 size namespace: xem `docs/owner/SKU_GRAMMAR.md`.

### 8.3 Wizard chuẩn hoá SKU

Khi mở sản phẩm có mã legacy → tab **SKU Drift** hiện:

```
SKU hiện tại:   MUG-001        [Mã cũ]
SKU gợi ý v2:   MUG-CR-F11

[Giữ mã cũ]    [Chấp nhận mã v2]
```

- **Giữ mã cũ** → hệ thống nhớ quyết định (`x_sku_v2_status='ba_approved_legacy'`), không hỏi lại.
- **Chấp nhận mã v2** → cập nhật mã trong Odoo + tự push lên Etsy (nếu sản phẩm đang Etsy "Còn hàng"). Nếu Etsy lỗi → rollback + ghi lỗi.

### 8.4 Xem danh sách SKU drift

**Menu:** Sản phẩm → **SKU Drift** → danh sách các sản phẩm có mã chưa khớp v2.

Bấm vào mỗi dòng để giải quyết.

---

## 9. Đăng sản phẩm lên Etsy

### 9.1 Điều kiện trước khi đăng

- [ ] Đã có ít nhất 1 ảnh sản phẩm.
- [ ] Tên sản phẩm tiếng Anh không vượt quá 140 ký tự.
- [ ] Giá USD `> 0` (Etsy enforce minimum $0.20 ở bước push của họ, không phải ở wizard của ta).
- [ ] Shop Etsy nguồn đã có **4 default IDs**: `default_taxonomy_id` + `default_shipping_profile_id` + `default_return_policy_id` + `default_readiness_state_id` (Admin cấu hình một lần tại **Etsy → Shop Settings → Publisher Defaults**).

### 9.2 Bấm "Publish to Etsy"

1. Mở form sản phẩm.
2. Nhấn nút **"Publish to Etsy"** ở header form (mọi BA tier đều thấy).
3. Wizard `etsy.publish.wizard` mở ra:
   - **Action: Run Publish (full)** — create draft → upload images → push inventory → publish (active).
   - **Action: Run Publish Draft Only** — dừng ở `state='draft'`, không phát sinh listing fee $0.20.
4. Nhấn nút tương ứng.

Hệ thống làm các bước:

1. Gọi Etsy `POST /shops/{id}/listings` → tạo listing Draft.
2. Upload từng ảnh sản phẩm qua `POST /listings/{id}/images`.
3. Gọi `PUT /listings/{id}/inventory` → đẩy SKU + tồn kho.
4. (Nếu action full) gọi `PATCH /listings/{id}` `{state: 'active'}`.
5. Cập nhật `product.channel.status` từ `draft` → `published` (hoặc dừng ở `draft`).

### 9.3 Sau khi đăng

- [ ] Mở Etsy Shop Manager → thấy listing mới ở mục **Drafts** hoặc **Active** (tuỳ action).
- [ ] Trên Odoo, tab **Channels** hiển thị "Etsy — Published" + Etsy listing_id (Char vì Etsy ID có thể > 2.1B).
- [ ] Nếu lỗi → tab **Channels** hiển thị "Etsy — Error" + thông báo lỗi → BA xem rồi bấm **"Resume Publish"** (nút đổi tên khi `state='error'`).

### 9.4 Lỗi thường gặp khi publish

| Lỗi | Nguyên nhân | Cách xử lý |
|---|---|---|
| `A readiness_state_id is required for physical listings.` | Shop Etsy nguồn chưa cấu hình `default_readiness_state_id` | Admin vào Etsy → Shop Settings → Publisher Defaults |
| `All offerings need readiness state` | Push inventory: từng offering chưa carry `readiness_state_id` | Code đã fix; nếu vẫn lỗi → liên hệ Đội Kỹ thuật |
| `int exceeds XML-RPC limits` | Listing_id > 2.1B chưa cast `str()` | Code đã fix; báo nếu tái phát |

---

## 10. Câu hỏi thường gặp

**Q:** _Tôi tạo nhầm sản phẩm. Xoá thế nào?_
A: Chỉ Admin mới xoá được. Liên hệ Admin và cung cấp SKU + lý do. Nếu sản phẩm chưa đăng lên Etsy → xoá an toàn. Nếu đã đăng → phải hạ listing Etsy trước.

**Q:** _Sản phẩm tạo xong nhưng không thấy nút "Publish to Etsy"._
A: Bạn chưa có quyền `group_ba_user`. Liên hệ Admin để cấp quyền (mọi BA tier đều publish được — không cần BA Lead).

**Q:** _Tôi muốn cùng một sản phẩm bán trên Etsy + Amazon._
A: Hôm nay chỉ Etsy hoạt động. Amazon được đánh dấu "không hoạt động" trong `multichannel.sales.channel`. Khi Amazon ra mắt (Phase 5), BA chỉ cần tích thêm ☑ Amazon trong Wizard.

**Q:** _Mã SKU Gearment có bắt buộc không?_
A: Không. Để trống → sản phẩm chạy theo đường MTO (in nội bộ). Có giá trị → chạy theo đường Dropship Gearment (cờ `is_dropship=True` tự bật).

**Q:** _Tôi nên dùng Wizard cũ (1A) hay SKU Builder (1B)?_
A: Tùy thói quen. SKU Builder hữu ích khi BA chưa quen grammar v2 hoặc muốn hệ thống dựng SKU đúng format. Wizard cũ nhanh hơn nếu BA biết chính xác SKU cần gõ. Cả hai cùng đi qua validator v2 ở mục 6.

**Q:** _Tôi đăng lên Etsy bị lỗi "A readiness_state_id is required for physical listings."_
A: Shop Etsy nguồn chưa cấu hình `default_readiness_state_id`. Liên hệ Admin để cấu hình từ menu **Etsy → Shop Settings → Publisher Defaults**.

**Q:** _Tôi bật mode "hard" cho validator v2 thì sao?_
A: Vào Settings → Technical → Parameters → System Parameters → tìm `multichannel_hub.sku_v2_enforce_mode` → đổi từ `soft` sang `hard`. Từ lúc đó mọi SKU không khớp regex v2 sẽ bị `UserError` chặn ngay, không tạo sản phẩm. Khuyến nghị: chỉ bật sau khi đã canonicalise hết catalog legacy.

---

## 11. Checklist kiểm thử UAT

> Người kiểm thử: BA Lead · **Ngày kiểm:** _________ · **Môi trường:** Staging (`https://odoo.hatafax.com`)

### TC-001: Tạo sản phẩm Mug bằng Wizard cũ (Cách 1A)

- [ ] Đăng nhập vai trò BA Lead
- [ ] Mở Wizard tạo sản phẩm (Cách 1A)
- [ ] Điền: Tên = "UAT-TAOSP Mug 2026", SKU = unique, Nhóm = All, Giá USD = 12.99, Phí ship = 20000, Kênh = ☑ Etsy
- [ ] Bấm "Tạo sản phẩm"
- [ ] **Mong đợi:** Form sản phẩm mới hiển thị, tab Channels có "Etsy — Draft"
- [ ] **Kết quả thực tế:** _____
- [ ] **Pass / Fail:** _____

### TC-002: Tạo sản phẩm Dropship Gearment (Wizard cũ)

- [ ] Mở Wizard (Cách 1A)
- [ ] Điền tất cả trường bắt buộc + Mã SKU Gearment = "GEAR-UAT-..."
- [ ] Bấm "Tạo sản phẩm"
- [ ] **Mong đợi:** Sản phẩm có cờ `is_dropship = True`, hiển thị huy hiệu "Dropship" trên form
- [ ] **Pass / Fail:** _____

### TC-003: Wizard SKU Drift — giữ mã cũ

- [ ] _**Yêu cầu seed**: cần 1 sản phẩm có `x_sku_v2_status='non_canonical'` trên staging_
- [ ] Mở sản phẩm có SKU legacy (ví dụ `MUG-001`)
- [ ] Mở tab "SKU Drift"
- [ ] Bấm "Keep Legacy"
- [ ] **Mong đợi:** Status → `ba_approved_legacy`; SP không xuất hiện trong danh sách Drift nữa
- [ ] **Pass / Fail:** _____

### TC-004: Wizard SKU Drift — chấp nhận v2 (SP đã đăng Etsy)

- [ ] _**Yêu cầu seed**: cần 1 SP đã publish Etsy + có mã legacy + sandbox Etsy_
- [ ] Mở SP đã đăng Etsy + có mã legacy
- [ ] Bấm "Accept Canonical"
- [ ] **Mong đợi:** Mã SKU đổi sang v2, tab Channels hiển thị "Inventory push pending" → "pushed"; Etsy Shop Manager phản ánh SKU mới
- [ ] **Pass / Fail:** _____

### TC-005: Đăng SP lên Etsy (Draft mode) — live JaHandmadeArt

- [ ] _**Yêu cầu**: owner pre-approved (đã cấp ✅ 2026-05-26)_
- [ ] Mở SP UAT vừa tạo (có ít nhất 1 ảnh)
- [ ] Bấm "Publish to Etsy" → **Action: Run Publish Draft Only**
- [ ] **Mong đợi:**
  - Trên Etsy Shop Manager → listing mới xuất hiện ở Drafts
  - Tab Channels trong Odoo: "Etsy — Published (draft)" + listing_id
- [ ] **Pass / Fail:** _____

### TC-006: Phân quyền — BA User vẫn thấy nút "Publish to Etsy"

> **Sửa từ v1.0:** Kỳ vọng ngược lại — code thiết kế cho mọi BA tier publish được.

- [ ] Đăng nhập tài khoản BA User
- [ ] Mở sản phẩm bất kỳ
- [ ] **Mong đợi:** Nút "Publish to Etsy" **hiện** trên header form; có thể bấm và chạy được wizard
- [ ] **Pass / Fail:** _____

### TC-007: Validator giá — Listing Price phải `> 0`

> **Sửa từ v1.0:** validator chỉ check `> 0`, không phải `>= $0.20` (mức $0.20 là Etsy enforce ở push step).

- [ ] Mở Wizard (Cách 1A), điền giá USD = 0
- [ ] Bấm "Tạo sản phẩm"
- [ ] **Mong đợi:** Modal lỗi "Listing Price must be greater than 0."
- [ ] **Pass / Fail:** _____

### TC-008: SKU Builder — Build `MUG-CR-F11` (mug 11oz happy path)

- [ ] Đăng nhập BA Lead
- [ ] Mở SKU Builder Wizard (Cách 1B)
- [ ] Bước 1: Tên = "UAT-SKU-BUILDER Mug 11oz ..." → auto family = `MUG`
- [ ] Bước 2: Material = "Ceramic + Chrome" (mã `CR`)
- [ ] Bước 3: Size = "11 oz" (mã `F11`)
- [ ] Bước 4: không chọn color → Preview SKU = `MUG-CR-F11`
- [ ] Bấm Create → JSON-RPC verify `product.template.search_count(default_code='MUG-CR-F11') ≥ 1`
- [ ] **Pass / Fail:** _____

### TC-009: SKU Builder — Build `MUG-CR-F15-BK` (mug 15oz + VAR2 Black)

- [ ] Mở SKU Builder Wizard
- [ ] Bước 1: Tên = "UAT-SKU-BUILDER Mug 15oz Black ..." → family `MUG`
- [ ] Bước 2: Material `CR`
- [ ] Bước 3: Size = "15 oz" → `F15`
- [ ] Bước 4: Color = "Black" → `BK` → Preview = `MUG-CR-F15-BK`
- [ ] Bấm Create → verify
- [ ] **Pass / Fail:** _____

### TC-010: SKU Builder — Build `APR-TX-AM` (apparel-size-gated)

- [ ] Mở SKU Builder Wizard
- [ ] Bước 1: Tên = "UAT-SKU-BUILDER Cotton Apron M ..." → family `APR`
- [ ] Bước 2: Material `TX` (Textile)
- [ ] Bước 3: Size = "Medium" (apparel namespace, mã `AM`)
- [ ] Bước 4: không color → Preview = `APR-TX-AM`
- [ ] Bấm Create → verify
- [ ] **Pass / Fail:** _____

### TC-011: SKU Builder — Build `DMT-TX-R30X18` (doormat rectangular)

- [ ] Mở SKU Builder Wizard
- [ ] Bước 1: Tên = "UAT-SKU-BUILDER Doormat 30x18 ..." → family `DMT`
- [ ] Bước 2: Material `TX`
- [ ] Bước 3: sub-form rectangular: Rect W = 30, Rect H = 18 → `R30X18`
- [ ] Bước 4: Preview = `DMT-TX-R30X18`
- [ ] Bấm Create → verify
- [ ] **Pass / Fail:** _____

### TC-012: SKU Builder — FR-017 24th: non-BA user bị chặn

- [ ] _**Note:** Đã cover ở mhc unit test `test_phase2_hub_sku_builder_orm::test_non_ba_user_blocked_before_template_create`. Browser stub kept for traceability._
- [ ] **Mong đợi (manual):** user chỉ có `base.group_user` (không thuộc `group_ba_user`) → bấm Create ở Bước 4 → modal `Access Error` + KHÔNG có `product.template` mới
- [ ] **Pass / Fail:** _____ (hoặc skip, cite unit test)

### Tổng kết UAT

- [ ] 11/12 test cases Pass (TC-012 manual skip với citation OK) → **Approve**
- [ ] Có Fail → ghi cụ thể vào `docs/owner/UAT_FINDINGS_<date>.md` + tạo Jira sub-task

---

## 12. Báo lỗi cho ai

| Loại lỗi | Liên hệ |
|---|---|
| Wizard không mở / lỗi UI | Đội Kỹ thuật |
| Mã SKU bị nghi sai | BA Manager |
| Etsy báo lỗi khi đăng | BA Lead → Đội Kỹ thuật (kèm screenshot + listing_id) |
| Cron Excel không chạy | Đội Kỹ thuật (khi cron đi vào hoạt động) |
| Quyền truy cập / role | Admin |
| Validator v2 báo lỗi | BA Manager (quyết định soft/hard mode) |

---

> **Tài liệu liên quan:**
> - Tổng quan nghiệp vụ: [`FLOW_TAO_SAN_PHAM_VN.md`](./FLOW_TAO_SAN_PHAM_VN.md)
> - Walkthrough UAT click-by-click: [`UAT_WALKTHROUGH_TAO_SAN_PHAM_VN.md`](./UAT_WALKTHROUGH_TAO_SAN_PHAM_VN.md)
> - SKU grammar đầy đủ: [`SKU_GRAMMAR.md`](./SKU_GRAMMAR.md)
> - Tài liệu kỹ thuật (tiếng Anh): `specs/009-product-hub/`, `specs/010-catalog-excel-sync/`, `specs/011-etsy-outbound-publish/`
> - BRD: `docs/owner/BRD_VN.md` (Epic 7)
> - UAT findings gần nhất: `docs/owner/UAT_FINDINGS_2026-05-26.md`
