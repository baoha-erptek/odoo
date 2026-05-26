# Quy trình tạo sản phẩm mới (cho Chủ shop)

**Phiên bản:** 1.1 · **Ngày:** 2026-05-26 · **Ngôn ngữ:** Tiếng Việt

> Tài liệu này hướng dẫn cách thêm sản phẩm mới vào hệ thống. Dùng cho Chủ shop và nhân viên BA. Không có thuật ngữ kỹ thuật.

> **Cập nhật v1.1 (2026-05-26):** thêm Wizard mới **"SKU Builder 4 bước"** giúp BA dựng mã SKU đúng quy ước mà không phải nhớ format. Bổ sung mô tả validator mã SKU mới (chế độ mềm/cứng) và sub-form bổ sung kích thước khi tên sản phẩm thiếu thông tin.

---

## Tổng quan

Sản phẩm trong hệ thống là "bản gốc duy nhất" — sau khi tạo, nó tự động sẵn sàng để đăng bán trên các kênh (Etsy, sau này là Amazon, Website…). Mỗi sản phẩm chỉ tồn tại **một** lần trong hệ thống — các kênh chỉ là "nơi xuất hiện" chứ không phải nơi lưu sản phẩm.

Có hai cách tạo sản phẩm bằng tay:

1. **Wizard cổ điển (1 form)** — dùng khi BA đã biết chính xác mã SKU. _(đã hoạt động hôm nay)_
2. **SKU Builder Wizard (4 bước)** — dùng khi muốn hệ thống giúp dựng mã SKU đúng quy ước. _(mới từ 2026-05-26)_

Và một cách tự động:

3. **Đồng bộ từ file Excel** — dùng khi nhập nhiều sản phẩm cùng lúc từ danh mục Excel. _(sẽ ra mắt trong phiên bản kế tiếp)_

---

## Cách 1A: Wizard cổ điển

### Khi nào dùng

- BA đã quen format SKU mới (`MUG-CR-F11`, `APR-TX-AM`…) và biết chính xác mã muốn dùng.
- Muốn tạo nhanh một sản phẩm thử nghiệm.
- Nhập sản phẩm có mã SKU legacy (mã cũ) — chấp nhận hệ thống cảnh báo mềm.

### Các bước

1. Mở **Sản phẩm → Tạo sản phẩm mới (Wizard)**.
2. Điền các ô bắt buộc:
   - **Tên sản phẩm** — ví dụ "Custom Coffee Mug 11oz"
   - **Mã SKU nội bộ** — BA tự gõ. Hệ thống chỉ gợi ý phần Family (3 ký tự đầu); phần còn lại BA tự dựng.
   - **Nhóm sản phẩm** — chọn từ danh mục có sẵn.
   - **Giá niêm yết (USD)** — giá bán trên Etsy. Phải lớn hơn 0.
   - **Phí vận chuyển nội bộ** — ước tính chi phí vận chuyển.
   - **Các kênh áp dụng** — chọn ít nhất một kênh (mặc định Etsy).
3. (Tùy chọn) Điền **Mã SKU Gearment** nếu sản phẩm sẽ giao qua Gearment. Hệ thống tự động đặt chế độ "Dropship" cho sản phẩm này.
4. Nhấn **Tạo sản phẩm**.

### Hệ thống làm gì sau khi bấm Tạo

- Chạy validator mã SKU (xem phần "Validator v2" bên dưới).
- Lưu sản phẩm vào kho dữ liệu chung.
- Tạo "trạng thái kênh" cho từng kênh đã chọn — bắt đầu ở trạng thái "Nháp".
- Hiển thị ngay form sản phẩm vừa tạo, sẵn sàng để đăng lên Etsy.

---

## Cách 1B: SKU Builder Wizard (4 bước) — mới

### Khi nào dùng

- BA chưa quen format mới và muốn hệ thống dựng giúp.
- Tạo sản phẩm thuộc family ít gặp (BA không nhớ mã family/material/size cho family đó).
- Muốn thấy preview SKU trước khi commit.

### Các bước

1. Mở **Operations → Configuration → SKU Builder Wizard**.
2. **Bước 1 — Family**: gõ tên sản phẩm tiếng Anh. Hệ thống tự nhận biết family (Mug, Apron, Doormat…). Nếu sai, BA chỉnh thủ công.
3. **Bước 2 — Material**: chọn chất liệu (Ceramic, Wood, Textile, Metal…).
4. **Bước 3 — Size**: chọn kích thước. Wizard chỉ hiện các size hợp lệ cho family đó (mug → fluid oz, apron → S/M/L, doormat → rect W×H…).
   - Nếu tên sản phẩm không chứa thông tin size (ví dụ "Color Changing Beverage" không có "11 oz") → wizard hiện thêm ô bổ sung để BA tự điền size hoặc kích thước W/H.
5. **Bước 4 — Preview**: thấy mã SKU dự kiến (ví dụ `MUG-CR-F11-BK`). Có thể chọn color phụ (VAR2) nếu muốn. Bấm **Create**.

### Lợi ích

- BA không cần thuộc lòng grammar SKU v2.
- Hệ thống tự gate size theo family — không tạo ra SKU sai logic (ví dụ "Mug size M" — không hợp lệ vì M là apparel).
- Preview SKU trước khi commit → BA thấy ngay nếu auto-suggest sai và quay lại sửa.

---

## Validator mã SKU v2 — mới

Hệ thống có một bộ kiểm tra format mã SKU theo grammar v2:

- **Chế độ mềm (mặc định)**: SKU không đúng format vẫn được lưu, chỉ cảnh báo. Thích hợp cho giai đoạn đầu khi catalog còn nhiều mã legacy.
- **Chế độ cứng**: SKU không đúng format bị từ chối ngay. Bật khi đã chuẩn hoá xong catalog.

Đổi chế độ trong Cấu hình hệ thống (Admin). Mỗi BA không tự đổi được.

> Sản phẩm cũ (legacy SKU) **không** bị validator chặn — chỉ SKU tạo mới hoặc sửa lại mới qua kiểm tra.

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
- **Mã chuẩn v2** — mã theo hệ ngữ pháp mới `<FAM3>-<MAT2>-<SIZE>[-<VAR2>]` (ví dụ `MUG-CR-F11-BK`).

Khi tạo mới, hệ thống dùng mã chuẩn v2 mặc định. Nếu BA muốn giữ mã cũ cho sản phẩm cũ đã đăng trên Etsy → bấm **"Keep Legacy"** trên Wizard chuẩn hoá SKU. Hệ thống nhớ quyết định này và không hỏi lại.

Nếu BA chấp nhận mã chuẩn cho một sản phẩm đã có trên Etsy → hệ thống tự động cập nhật mã đó lên Etsy (Etsy hiện đang đặt trạng thái "Còn hàng"). Nếu Etsy báo lỗi → hệ thống rollback (giữ mã cũ + ghi lỗi vào nhật ký để BA xem).

---

## Câu hỏi thường gặp

**Q:** _Tôi muốn xem sản phẩm nào chưa khớp mã chuẩn v2._
A: Mở **Sản phẩm → SKU Drift** — danh sách các sản phẩm có mã SKU chưa khớp v2; bấm vào mỗi dòng để chọn giữ-cũ / chấp-nhận-mới.

**Q:** _Tôi cần đăng cùng một sản phẩm trên Etsy lẫn Amazon._
A: Hôm nay chỉ Etsy hoạt động. Amazon được đánh dấu "không hoạt động" trong cấu hình — khi Amazon ra mắt (Phase 5), BA chỉ cần bật "Amazon" trong kênh áp dụng của sản phẩm.

**Q:** _Tôi đặt mã Gearment xong nhưng vẫn muốn tự sản xuất._
A: Xóa ô "Mã SKU Gearment" trong form sản phẩm → hệ thống tự tắt chế độ Dropship.

**Q:** _Sản phẩm bị lỗi khi đăng — làm sao biết?_
A: Mở form sản phẩm → tab "Channels" → cột "Lỗi đồng bộ gần nhất" hiển thị thông tin lỗi. Nút **"Publish to Etsy"** sẽ đổi tên thành **"Resume Publish"** — bấm sẽ tiếp tục từ bước bị lỗi (không tạo lại từ đầu).

**Q:** _Wizard cũ (1A) và SKU Builder (1B) — chọn cái nào?_
A: Tùy thói quen. SKU Builder phù hợp với BA chưa quen grammar v2. Wizard cũ nhanh hơn cho người đã thuộc format. Hai wizard cùng tồn tại — không có cái nào "sắp bị bỏ".

**Q:** _Validator v2 ở chế độ "cứng" thì sản phẩm cũ có bị ảnh hưởng?_
A: Không. Sản phẩm cũ (legacy SKU) không bị re-validate khi đổi mode. Chỉ SKU **tạo mới** hoặc **sửa lại** mới qua kiểm tra. Sản phẩm legacy đã được đánh dấu "BA-approved legacy" và không bị bắt buộc đổi.

---

## Liên hệ

- Vấn đề chức năng → BA Lead.
- Mã SKU bị nghi sai → BA Manager.
- Lỗi kỹ thuật / Etsy báo lỗi → Đội Kỹ thuật.
- Đổi chế độ validator (soft → hard) → Admin (cấu hình ICP).

> Tài liệu thao tác chi tiết: [`HUONG_DAN_TAO_SAN_PHAM_VN.md`](./HUONG_DAN_TAO_SAN_PHAM_VN.md).
> Tài liệu sản phẩm chi tiết cho đội kỹ thuật xem trong `specs/009-product-hub/`, `specs/010-catalog-excel-sync/`, `specs/011-etsy-outbound-publish/` (tiếng Anh).
