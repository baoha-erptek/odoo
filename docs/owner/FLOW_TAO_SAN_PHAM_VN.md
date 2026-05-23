# Quy trình tạo sản phẩm mới (cho Chủ shop)

**Phiên bản:** 1.0 · **Ngày:** 2026-05-23 · **Ngôn ngữ:** Tiếng Việt

> Tài liệu này hướng dẫn cách thêm sản phẩm mới vào hệ thống. Dùng cho Chủ shop và nhân viên BA. Không có thuật ngữ kỹ thuật.

---

## Tổng quan

Sản phẩm trong hệ thống là "bản gốc duy nhất" — sau khi tạo, nó tự động sẵn sàng để đăng bán trên các kênh (Etsy, sau này là Amazon, Website…). Mỗi sản phẩm chỉ tồn tại **một** lần trong hệ thống — các kênh chỉ là "nơi xuất hiện" chứ không phải nơi lưu sản phẩm.

Có hai cách tạo sản phẩm:

1. **Tạo từng cái (Wizard)** — dùng khi thêm 1-2 sản phẩm mới mỗi lần. _(đã hoạt động hôm nay)_
2. **Đồng bộ từ file Excel** — dùng khi nhập nhiều sản phẩm cùng lúc từ danh mục Excel. _(sẽ ra mắt trong phiên bản kế tiếp)_

---

## Cách 1: Tạo từng sản phẩm bằng Wizard

### Khi nào dùng

- Khi thiết kế mới một sản phẩm và muốn đăng lên Etsy ngay.
- Khi cần tạo nhanh một sản phẩm thử nghiệm.

### Các bước

1. Mở **Sản phẩm → Tạo sản phẩm mới (Wizard)**.
2. Điền các ô bắt buộc:
   - **Tên sản phẩm** — ví dụ "Custom Coffee Mug 11oz"
   - **Mã SKU nội bộ** — mã ngắn để gọi tên (ví dụ "MUG-CE-S35-D0001"). Hệ thống tự gợi ý mã chuẩn dựa trên tên sản phẩm — Chủ shop có thể chấp nhận gợi ý hoặc dùng mã cũ.
   - **Nhóm sản phẩm** — chọn từ danh mục có sẵn (Mug, Ring Dish, T-shirt…).
   - **Giá niêm yết (USD)** — giá bán trên Etsy.
   - **Phí vận chuyển nội bộ** — ước tính chi phí vận chuyển.
   - **Các kênh áp dụng** — chọn ít nhất một kênh (mặc định Etsy).
3. (Tùy chọn) Điền **Mã SKU Gearment** nếu sản phẩm sẽ giao qua Gearment. Hệ thống tự động đặt chế độ "Dropship" cho sản phẩm này.
4. Nhấn **Tạo sản phẩm**.

### Hệ thống làm gì sau khi bấm Tạo

- Lưu sản phẩm vào kho dữ liệu chung.
- Tạo "trạng thái kênh" cho từng kênh đã chọn — bắt đầu ở trạng thái "Nháp".
- Hiển thị ngay form sản phẩm vừa tạo, sẵn sàng để đăng lên Etsy.

### Kiểm tra trước khi đăng lên Etsy

Trên form sản phẩm có:

- **Tab "Kênh"** — danh sách các kênh áp dụng + trạng thái từng kênh (Nháp / Đã đăng / Lỗi).
- **Tab "Drift mã SKU"** — nếu mã SKU hiện tại không khớp gợi ý chuẩn, hệ thống nêu ra để BA quyết định giữ mã cũ hay chuyển sang mã mới.
- **Nút "Đăng lên Etsy"** ở đầu form — chỉ BA mới bấm được.

---

## Cách 2: Đồng bộ từ Excel (sắp ra mắt)

> _Phần này mô tả luồng trong phiên bản kế tiếp — chưa hoạt động hôm nay nhưng đã được thiết kế._

Khi BA đặt file Excel danh mục lên Google Drive thư mục quy định:

1. Mỗi đêm hệ thống tự động đọc file (khoảng 2h sáng).
2. Mỗi dòng trong Excel = một sản phẩm.
3. Nếu mã SKU đã có trong hệ thống → cập nhật tên, giá, mô tả… **theo Excel** (Excel thắng).
4. Nếu mã SKU chưa có → tạo sản phẩm mới.
5. **Các kênh đã chọn cho sản phẩm cũ KHÔNG bị xóa** — chỉ thêm cập nhật nội dung, không động đến quyết định "bán trên kênh nào" của BA.
6. Báo cáo kết quả gửi vào Inbox của BA mỗi sáng: bao nhiêu sản phẩm thêm mới, bao nhiêu cập nhật, bao nhiêu lỗi.

### Khi nào dùng

- Nhập danh mục lần đầu từ file Excel có sẵn.
- Cập nhật giá / mô tả hàng loạt.
- Đồng bộ nhanh các sản phẩm mới tạo trong tuần.

---

## SKU — câu chuyện hai mã

Hệ thống dùng **hai bộ mã SKU song song**:

- **Mã cũ (legacy)** — mã BA đã dùng lâu nay; vẫn giữ trong "Lưu trữ SKU cũ" trên sản phẩm.
- **Mã chuẩn v2** — mã theo hệ ngữ pháp mới (3 ký tự nhóm + 2 ký tự chất liệu + cỡ + mã thiết kế).

Khi tạo mới, hệ thống dùng mã chuẩn v2 mặc định. Nếu BA muốn giữ mã cũ cho sản phẩm cũ đã đăng trên Etsy → bấm **"Giữ mã cũ"** trên Wizard chuẩn hoá SKU. Hệ thống nhớ quyết định này và không hỏi lại.

Nếu BA chấp nhận mã chuẩn cho một sản phẩm đã có trên Etsy → hệ thống tự động cập nhật mã đó lên Etsy (Etsy hiện đang đặt trạng thái "Còn hàng"). Nếu Etsy báo lỗi → hệ thống rollback (giữ mã cũ + ghi lỗi vào nhật ký để BA xem).

---

## Câu hỏi thường gặp

**Q:** _Tôi muốn xem sản phẩm nào chưa có trên Etsy._
A: Mở **Sản phẩm → Drift mã SKU** — danh sách các sản phẩm có mã SKU chưa khớp v2; bấm vào mỗi dòng để chọn giữ-cũ / chấp-nhận-mới.

**Q:** _Tôi cần đăng cùng một sản phẩm trên Etsy lẫn Amazon._
A: Hôm nay chỉ Etsy hoạt động. Amazon được đánh dấu "không hoạt động" trong cấu hình — khi Amazon ra mắt (Phase 5), BA chỉ cần bật "Amazon" trong kênh áp dụng của sản phẩm.

**Q:** _Tôi đặt mã Gearment xong nhưng vẫn muốn tự sản xuất._
A: Xóa ô "Mã SKU Gearment" trong form sản phẩm → hệ thống tự tắt chế độ Dropship.

**Q:** _Sản phẩm bị lỗi khi đăng — làm sao biết?_
A: Mở form sản phẩm → tab "Kênh" → cột "Lỗi đồng bộ gần nhất" hiển thị thông tin lỗi. Bấm **"Đăng lên Etsy"** sẽ tiếp tục từ bước bị lỗi (không tạo lại từ đầu).

---

## Liên hệ

- Vấn đề chức năng → BA Lead.
- Mã SKU bị nghi sai → BA Manager.
- Lỗi kỹ thuật / Etsy báo lỗi → Đội Kỹ thuật.

> Tài liệu sản phẩm chi tiết cho đội kỹ thuật xem trong `specs/009-product-hub/` (tiếng Anh).
