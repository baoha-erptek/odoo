# Hướng dẫn thiết lập tồn kho ban đầu trên Odoo

Tài liệu này hướng dẫn anh nạp **tồn kho hiện tại** (file Excel `Tồn kho PD_Hatafa.xlsx`)
vào Odoo lần đầu, và giải thích các lựa chọn cấu hình quan trọng đi kèm.

Đối tượng đọc: chủ doanh nghiệp + bộ phận vận hành kho.
Thời lượng nạp lần đầu: ~30 phút (4 bước upload + click "Apply").

---

## 1. Loại sản phẩm — chọn "Có thể lưu kho" (Storable)

Trên Odoo, mỗi mặt hàng có 1 trong 3 loại:

| Loại | Khi nào dùng | Có theo dõi số lượng tồn? |
|---|---|---|
| **Có thể lưu kho** (Storable) | Mặt hàng có thật, đếm được, cần biết tồn | ✅ Có |
| Tiêu hao (Consumable) | Hàng dùng nội bộ không cần đếm chính xác | ❌ Không |
| Dịch vụ (Service) | Phí, công, dịch vụ phi vật lý | ❌ Không |

**Khuyến nghị:** tất cả 133 mặt hàng trong file `Tồn kho PD_Hatafa.xlsx`
**đều chọn "Có thể lưu kho"** — vì chúng đều có số lượng cụ thể trong file
và đều cần theo dõi tồn để vận hành.

---

## 2. Cách theo dõi tồn kho — chọn "Không theo dõi" (No Tracking)

Odoo cung cấp 3 mức theo dõi tồn ở từng sản phẩm
(tham khảo: [Odoo 19 — Product tracking](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/product_management/product_tracking.html)):

| Mức | Nghĩa | Thao tác mỗi lần nhập/xuất | Khi nào nên dùng |
|---|---|---|---|
| **Không theo dõi** (None) | Chỉ đếm số lượng tổng | Không cần gì thêm | Hàng sản xuất hàng loạt, in theo yêu cầu, không cần truy vết từng cái |
| Theo lô (Lots) | Nhóm theo mẻ sản xuất | Phải gắn số lô khi nhập/xuất | Hàng dễ lỗi cả mẻ (ví dụ: gốm sứ nung cùng lò có thể lỗi đồng loạt) |
| Theo số serial | Mỗi cái 1 mã định danh | Phải quét mã từng cái | Hàng độc bản, đắt tiền, cần truy vết cá thể |

**Khuyến nghị:** **chọn "Không theo dõi"** cho cả 133 mặt hàng ban đầu.

Lý do:
- Mô hình kinh doanh hiện tại là handmade + POD, không cần biết "cái mug khách
  X nhận chính xác là cái nào trong kho".
- Bật Lots/Serial sẽ phát sinh **bắt buộc nhập số lô mỗi lần nhập hàng** —
  thao tác kho nặng hơn nhiều mà chưa cần thiết.
- **Lưới an toàn:** sau này nếu phát sinh trường hợp cần theo dõi (ví dụ: cả
  mẻ gốm sứ lỗi từ 1 lò nung cụ thể), có thể bật **"Theo lô"** cho riêng dòng
  sản phẩm đó — không cần đụng tới 132 mặt hàng còn lại.

---

## 3. Đơn vị tính — PCS (Cái)

Tất cả mặt hàng trong file Excel hiện đang tính bằng **PCS** (cột `ĐƠN VỊ`
trong file `File Vat dung - QUẢN LÝ XUẤT NHẬP KHO.xlsx`).

Script sẽ gán đơn vị **`Units`** (Cái) cho mọi mặt hàng. Sau khi nạp xong,
nếu có mặt hàng cần đơn vị khác (kg, mét, cuộn…), anh có thể chỉnh trực tiếp
trên form sản phẩm.

---

## 4. Phương pháp tính giá vốn — Standard Price (giá vốn cố định)

Odoo có 3 phương pháp:

| Phương pháp | Cách tính | Ưu / nhược |
|---|---|---|
| **Standard Price** (giá vốn cố định) | Giá vốn 1 mức cố định, anh tự cập nhật | Đơn giản nhất, đủ dùng cho khởi đầu |
| Average Cost (giá vốn bình quân) | Tự động bình quân lại sau mỗi lần nhập | Cần dữ liệu chi phí nhập đầy đủ |
| FIFO (nhập trước xuất trước) | Trừ kho theo lô nhập sớm | Cần lots; phức tạp nhất |

**Khuyến nghị:** mở đầu dùng **Standard Price**.
Nếu sau này anh muốn báo cáo lãi/lỗ chính xác hơn theo từng lô nhập,
có thể đổi sang Average Cost ở từng `Danh mục sản phẩm` (Product Category)
mà không phải làm lại từ đầu.

---

## 5. Kho và vị trí — 1 kho duy nhất (WH/Stock)

Hiện tại Odoo chỉ tạo 1 kho mặc định: **WH** (warehouse) với vị trí
**WH/Stock**. Toàn bộ 133 mặt hàng sẽ được nạp vào vị trí này.

Trong các file Excel hiện tại có nhắc đến mã kho **BH1 / BH2 / SG1**
(file `File Tem Amazon - Quản lý tem hàng kho Ha Ta Fa.xlsx`).
Việc tách thành nhiều kho/nhiều chi nhánh là một bước **mở rộng riêng**
(không nằm trong lần nạp này) — khi cần, sẽ có hướng dẫn tiếp theo.

---

## 6. Mã sản phẩm (SKU) — theo chuẩn v2.1

Mỗi mặt hàng cần một mã định danh **độc nhất** để Odoo tra cứu nhanh.
Hệ thống đang áp dụng chuẩn SKU v2.1: **`FAM3-MAT2-SIZE[-VAR2]`**
(xem chi tiết: [SKU_GRAMMAR.md](SKU_GRAMMAR.md)).

Ví dụ:
- `MUG-CR-F11` = Mug, gốm + chrome, 11 oz
- `RDS-CE-SQ` = Ring Dish, gốm, vuông
- `APR-TX-AM` = Tạp dề, vải, size M

**Script tự gợi ý mã** dựa trên tên tiếng Việt của sản phẩm
(ví dụ "Đĩa bèo" → nhận diện họ `CDS` = Ceramic Dish → SKU gợi ý `CDS-MX-S001`).

Một số mặt hàng (ví dụ: vật tư đóng gói, băng keo, kéo, giấy in...) sẽ rơi
vào nhóm fallback **`MSC`** — đây là dấu hiệu để anh **xem lại cột
`default_code` trong file `02_product_templates.xlsx`** trước khi upload,
và chỉnh sửa thủ công nếu muốn.

Báo cáo conversion (file `conversion_report.txt`) liệt kê đầy đủ:
- Các mặt hàng không có dữ liệu trong file `File Vat dung` (thiếu đơn vị / danh mục / điểm đặt hàng).
- Các mặt hàng rơi vào fallback `MSC`.

---

## 7. Quy tắc đặt hàng lại (Reorder rules)

Trong file `File Vat dung`, anh đã có 3 cột:
- `Tồn kho an toàn` (safety stock)
- `Điểm đặt hàng` (reorder point)
- `Số lượng đặt hàng` (reorder quantity)

Script sẽ chuyển 3 cột này sang **Quy tắc đặt hàng lại** của Odoo:

| Cột Excel | Sang Odoo (`stock.warehouse.orderpoint`) |
|---|---|
| `Tồn kho an toàn` | `product_min_qty` (mức tối thiểu — khi giảm xuống dưới mức này thì Odoo cảnh báo) |
| `Điểm đặt hàng` | `product_max_qty` (mức Odoo sẽ "đặt hàng lên đến") |
| `Số lượng đặt hàng` | *Không có trường tương đương trong Odoo 19* — bội đặt hàng giờ được khai báo trên packaging của UoM. Cột này chỉ được liệt kê trong `conversion_report.txt` để anh tham khảo, không nạp vào Odoo. |

⚠️ **Cần xác nhận:** cách hiểu hiện tại đang là:
"khi tồn ≤ `product_min_qty` → Odoo cảnh báo và đề xuất bổ sung lên `product_max_qty`".
Nếu trong Excel của anh "Điểm đặt hàng" có nghĩa khác (ví dụ chính là ngưỡng
trigger, chứ không phải mức bổ sung lên đến), anh phản hồi để chỉnh script.

Chỉ những mặt hàng có **cả hai** ô `Tồn kho an toàn` và `Điểm đặt hàng`
trong file Excel mới được tạo quy tắc đặt hàng lại — các mặt hàng bỏ trống
2 ô này sẽ không có rule (anh có thể tạo thủ công trên Odoo sau).

---

## 8. Cách nạp 4 file vào Odoo (4 bước, ~30 phút)

Trước khi bắt đầu: chạy script để tạo 4 file XLSX import.

```bash
python3 scripts/build_inventory_import_xlsx.py
```

File sẽ nằm trong thư mục `.0temp/import/inventory/<thời-gian>/`.
Mở file `conversion_report.txt` để rà soát trước (đặc biệt: cột SKU
fallback và các mặt hàng thiếu dữ liệu).

### Bước 1 — Nạp danh mục sản phẩm (Product Categories)

1. Vào **Settings → Technical → Database Structure → Import records**
   *(hoặc Inventory → Configuration → Products → Product Categories → ⋮ → Import records)*.
2. Chọn model **`product.category`**, upload **`01_product_categories.xlsx`**.
3. Click **Test** để Odoo preview cột mapping → nếu OK, click **Import**.
4. Kỳ vọng: tạo mới 15 danh mục (ĐĨA, TẠP DỀ, HỘP, BAO BÌ…).

### Bước 2 — Nạp danh mục sản phẩm chính (Products)

1. Vào **Inventory → Products → Products → ⋮ → Import records**.
2. Upload **`02_product_templates.xlsx`** → Test → Import.
3. Kỳ vọng: tạo 133 sản phẩm mới (với loại "Có thể lưu kho", "Không theo dõi",
   đơn vị "Units", mã SKU v2.1, danh mục đã liên kết).

### Bước 3 — Nạp tồn kho ban đầu (Initial On-Hand)

1. Vào **Inventory → Operations → Physical Inventory → ⋮ → Import records**.
2. Upload **`03_initial_on_hand.xlsx`** → Test → Import.
3. Sau khi import xong: trên màn hình Physical Inventory, **chọn tất cả các
   dòng vừa import và click "Apply"** — Odoo sẽ ghi nhận tồn kho thực tế
   vào WH/Stock.

### Bước 4 — Nạp quy tắc đặt hàng lại (Reorder Rules)

1. Vào **Inventory → Operations → Replenishment** (hoặc **Reordering Rules**) → ⋮ → **Import records**.
2. Upload **`04_reorder_rules.xlsx`** → Test → Import.
3. Kỳ vọng: tạo 5 rule (chỉ cho các sản phẩm có đầy đủ safety + reorder
   point trong file Excel của anh).

Sau khi xong 4 bước, mở 1 vài sản phẩm bất kỳ để kiểm tra:
- Tồn kho hiển thị đúng số trong file `Tồn kho PD_Hatafa.xlsx`.
- Danh mục đã được gán.
- Đơn vị là "Units".
- (Với 5 sản phẩm có rule) thấy đề xuất bổ sung khi tồn xuống dưới mức an toàn.

---

## 9. Khi nào chạy lại (rerun)

Nếu cần điều chỉnh và nạp lại — ví dụ chỉnh sửa file Excel gốc, hoặc đổi
cách phân loại SKU — anh **chỉ cần chạy lại script và upload lại 4 file**.

Cơ chế **External ID** (mỗi sản phẩm có mã định danh
`inv_initial_load.tonkho_pd_hatafa_NNN`) đảm bảo:
- Lần upload thứ 2 với cùng file → Odoo **cập nhật-tại-chỗ**, KHÔNG tạo
  bản ghi trùng.
- Đếm số sản phẩm trên Odoo trước/sau lần rerun phải bằng nhau (133 mặt hàng).

⚠️ Trường hợp anh đổi tên sản phẩm trong file Excel gốc theo cách khác
(ví dụ "Đĩa bèo" → "Đĩa bèo size lớn"), thì script vẫn ghi cùng external ID
nếu **dòng đó vẫn ở vị trí cũ** trong file Excel — tức là Odoo sẽ cập nhật
tên sản phẩm cũ chứ không tạo mới. Nếu anh muốn tạo sản phẩm mới hoàn toàn,
chèn dòng mới vào cuối file Excel.

---

## 10. Câu hỏi thường gặp

**Hỏi:** Nếu tôi nhập sai một mặt hàng (ví dụ số tồn sai) sau khi đã import?
**Đáp:** Vào Inventory → Operations → Physical Inventory → tạo phiếu kiểm kho
mới cho riêng mặt hàng đó, nhập số đúng, click Apply. Hệ thống tự sinh
phiếu chênh lệch (stock.move) ghi nhận điều chỉnh.

**Hỏi:** 41 mặt hàng có SKU `MSC-...` thì có vấn đề gì?
**Đáp:** Chỉ là dấu hiệu "phân loại tự động không nhận ra" — sản phẩm vẫn
hoạt động bình thường (bán được, tồn vẫn đếm). Khi có thời gian, anh có thể
mở từng sản phẩm và đổi SKU sang đúng họ (ví dụ "Khung thêu" có thể chuyển
thành họ riêng).

**Hỏi:** Sao file `Tồn kho PD_Hatafa.xlsx` chỉ có 133 mặt hàng nhưng kho
thực tế nhiều hơn?
**Đáp:** Đây là điểm cần anh xác nhận — file này có phải là **toàn bộ**
tồn kho hiện tại không? Nếu thiếu, bổ sung vào file rồi rerun script.

**Hỏi:** Có cần backup trước khi import không?
**Đáp:** Khuyến nghị có. Trên môi trường production: tạo snapshot DB
PostgreSQL trước Bước 1. Trên staging: không bắt buộc (có thể reset).

---

## 11. Bước tiếp theo (sau khi nạp xong)

- **Phân kho nhiều địa điểm (BH1/BH2/SG1):** sẽ có hướng dẫn riêng khi
  anh sẵn sàng tách kho.
- **Nguyên vật liệu (raw materials):** file `PHIẾU NHẬP - XUẤT NGUYÊN LIỆU
  HÀNG NGÀY.xlsx` chứa dữ liệu chi tiết hơn — sẽ xử lý ở giai đoạn sau
  khi vận hành đã ổn định.
- **Phiếu nhập / xuất hàng ngày:** sau khi tồn kho ban đầu đã chính xác,
  mọi phiếu nhập / xuất tiếp theo nên thao tác trực tiếp trên Odoo
  (Inventory → Operations → Receipts / Deliveries) thay vì cập nhật file
  Excel song song — đây là điều kiện để Odoo phản ánh tồn kho chính xác
  theo thời gian thực.
