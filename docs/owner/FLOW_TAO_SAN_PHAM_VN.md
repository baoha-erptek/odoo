# Quy trình tạo sản phẩm mới (cho Chủ shop)

**Phiên bản:** 1.2 · **Ngày:** 2026-05-28 · **Ngôn ngữ:** Tiếng Việt

> Tài liệu này hướng dẫn cách thêm sản phẩm mới vào hệ thống. Dùng cho Chủ shop và nhân viên BA. Không có thuật ngữ kỹ thuật.

> **Cập nhật v1.2 (2026-05-28):** Đổi cách tạo sản phẩm — dùng **form Sản phẩm chuẩn** thay cho các Wizard riêng. Mã SKU **tự sinh** từ Danh mục + Biến thể (BA không phải gõ tay đúng format nữa). Bổ sung mô tả 7 nhóm thông tin mới khi đăng Etsy (Tags, Cá nhân hoá, Vật liệu, Ảnh phụ, Override Etsy theo sản phẩm, Cân nặng & Kích thước, Thuộc tính biến thể).

---

## Tổng quan

Sản phẩm trong hệ thống là "bản gốc duy nhất" — sau khi tạo, nó tự động sẵn sàng để đăng bán trên các kênh (Etsy, sau này là Amazon, Website…). Mỗi sản phẩm chỉ tồn tại **một** lần trong hệ thống — các kênh chỉ là "nơi xuất hiện" chứ không phải nơi lưu sản phẩm.

Có **một** cách tạo sản phẩm bằng tay (đã hoạt động):

1. **Form Sản phẩm chuẩn** — BA mở menu Sản phẩm → bấm Tạo mới → điền Tên + Danh mục + Biến thể + giá. Mã SKU tự sinh từ Danh mục + Biến thể.

Và một cách tự động (sắp ra mắt):

2. **Đồng bộ từ file Excel** — BA đặt file Excel danh mục vào Google Drive → hệ thống tự nhập hàng đêm.

> Trước đây hệ thống có 2 Wizard riêng (Wizard cũ + SKU Builder 4 bước). Từ phiên bản này, **form Sản phẩm chuẩn đã đủ** — Wizard đã được ẩn khỏi menu.

---

## Cách 1: Form Sản phẩm chuẩn

### Khi nào dùng

- BA muốn tạo một sản phẩm mới bằng tay.
- Nhập sản phẩm có Mã SKU legacy (mã cũ) — chỉ cần gõ tay vào ô Mã SKU, hệ thống lưu nguyên trạng.

### Các bước

1. Mở **Sản phẩm** → bấm **Tạo mới**.
2. Điền các ô:
   - **Tên sản phẩm** — ví dụ "Custom Coffee Mug 11oz" (tiếng Anh, hiển thị trên Etsy).
   - **Danh mục sản phẩm** — chọn từ dropdown (Mug / Apron / Doormat …).
   - **Biến thể** — thêm dòng biến thể (Chất liệu, Kích thước, Màu sắc) nếu sản phẩm có nhiều phiên bản.
   - **Giá bán (USD)** — giá Etsy, phải lớn hơn 0.
   - **Các kênh áp dụng** — chọn ít nhất một kênh (mặc định Etsy).
3. Ô **Mã SKU** sẽ tự điền sau khi BA chọn Danh mục + Biến thể. Ví dụ:
   - Danh mục `Mug` + Chất liệu `Ceramic + Chrome` + Size `11 oz` → `MUG-CR-F11`.
   - Danh mục `Apron` + Chất liệu `Textile` + Size `Medium` → `APR-TX-AM`.
   BA xem lại, hoặc gõ tay sửa nếu muốn (ví dụ giữ mã legacy).
4. (Tùy chọn) Điền **Mã SKU Gearment** nếu sản phẩm sẽ giao qua Gearment → hệ thống tự bật chế độ Dropship.
5. (Tùy chọn) Điền các Thông tin bổ sung (xem mục riêng bên dưới).
6. Nhấn **Lưu**.

### Hệ thống làm gì sau khi bấm Lưu

- Tự kiểm tra Mã SKU theo quy chuẩn (xem phần "Kiểm tra Mã SKU" bên dưới).
- Lưu sản phẩm vào kho dữ liệu chung.
- Tạo "trạng thái kênh" cho từng kênh đã chọn — bắt đầu ở trạng thái "Nháp".
- Hiển thị ngay form sản phẩm vừa tạo, sẵn sàng để đăng lên Etsy.

---

## Thông tin bổ sung khi đăng Etsy

Trên form Sản phẩm chuẩn, BA có thể điền **7 nhóm thông tin** giúp sản phẩm đủ chi tiết khi đăng lên Etsy. Mặc định để trống thì hệ thống dùng giá trị chung của shop hoặc bỏ qua.

1. **Tags (từ khoá tìm kiếm)** — tối đa 13 tag, mỗi tag tối đa 20 ký tự. Giúp khách Etsy tìm sản phẩm dễ hơn.
2. **Cá nhân hoá** — cho phép khách yêu cầu khắc/in tên lên sản phẩm. 4 ô: Cho phép, Bắt buộc khách điền, Số ký tự tối đa (mặc định 256), Hướng dẫn cho khách.
3. **Vật liệu** — hệ thống **tự suy ra** từ thuộc tính Chất liệu của Biến thể. BA không nhập lại.
4. **Ảnh phụ** — ngoài ảnh chính, BA upload thêm ảnh phụ vào trang Extra Images. Hệ thống gửi tối đa 10 ảnh lên Etsy theo thứ tự BA sắp.
5. **Override Etsy theo sản phẩm** — Danh mục Etsy / Ai làm / Khi nào làm. Mặc định dùng giá trị chung của shop; BA điền khi sản phẩm này cần khác biệt.
6. **Cân nặng & Kích thước** — Cân nặng từ trường Weight chuẩn (kg, hệ thống tự chuyển sang oz/g). Kích thước tự suy ra từ Size của Biến thể (ví dụ `R30X18` cho Doormat → dài 30, rộng 18; Mug "11 oz" không có kích thước hình học).
7. **Thuộc tính biến thể** — Material / Color / Size / Shape / Fluid oz / Apparel Size. Hệ thống gửi lên Etsy theo cặp (loại thuộc tính, giá trị) cho khách xem.

Đầy đủ chi tiết từng nhóm: xem [`HUONG_DAN_TAO_SAN_PHAM_VN.md`](./HUONG_DAN_TAO_SAN_PHAM_VN.md) mục 4.

---

## Kiểm tra Mã SKU

Hệ thống có một bộ kiểm tra format Mã SKU theo định dạng chuẩn (`<Family>-<Material>-<Size>[-<Variant>]`):

- **Chế độ mềm (mặc định)**: Mã không đúng format vẫn được lưu, chỉ cảnh báo. Thích hợp cho giai đoạn đầu khi catalog còn nhiều mã legacy.
- **Chế độ chặt**: Mã không đúng format bị từ chối ngay. Bật khi đã chuẩn hoá xong catalog.

Đổi chế độ trong Cấu hình hệ thống (Admin). Mỗi BA không tự đổi được.

> Sản phẩm cũ (mã legacy) **không** bị validator chặn — chỉ Mã SKU tạo mới hoặc sửa lại mới qua kiểm tra. Sản phẩm legacy được đánh dấu "BA-approved legacy" tự động khi đi qua quy trình lần đầu.

---

## Cách 2: Đồng bộ từ Excel (sắp ra mắt)

> _Phần này mô tả luồng trong phiên bản kế tiếp — chưa hoạt động hôm nay nhưng đã được thiết kế._

Khi BA đặt file Excel danh mục lên Google Drive thư mục quy định:

1. Mỗi đêm hệ thống tự động đọc file (khoảng 2h sáng).
2. Mỗi dòng trong Excel = một sản phẩm.
3. Nếu Mã SKU đã có trong hệ thống → cập nhật tên, giá, mô tả… **theo Excel** (Excel thắng).
4. Nếu Mã SKU chưa có → tạo sản phẩm mới.
5. **Các kênh đã chọn cho sản phẩm cũ KHÔNG bị xoá** — chỉ thêm cập nhật nội dung, không động đến quyết định "bán trên kênh nào" của BA.
6. Báo cáo kết quả gửi vào Inbox của BA mỗi sáng: bao nhiêu sản phẩm thêm mới, bao nhiêu cập nhật, bao nhiêu lỗi.

### Khi nào dùng

- Nhập danh mục lần đầu từ file Excel có sẵn.
- Cập nhật giá / mô tả hàng loạt.
- Đồng bộ nhanh các sản phẩm mới tạo trong tuần.

---

## SKU — câu chuyện hai mã

Hệ thống dùng **hai bộ Mã SKU song song**:

- **Mã cũ (legacy)** — mã BA đã dùng lâu nay; vẫn giữ trong "Lưu trữ SKU cũ" trên sản phẩm.
- **Mã chuẩn** — mã theo định dạng mới `<Family>-<Material>-<Size>[-<Variant>]` (ví dụ `MUG-CR-F11-BK`). Hệ thống tự sinh khi BA chọn Danh mục + Biến thể.

Khi tạo mới, hệ thống dùng mã chuẩn mặc định. Nếu BA muốn giữ mã cũ cho sản phẩm cũ đã đăng trên Etsy → bấm **"Keep Legacy"** trên trang SKU Drift. Hệ thống nhớ quyết định này và không hỏi lại.

Nếu BA chấp nhận mã chuẩn cho một sản phẩm đã có trên Etsy → hệ thống tự động cập nhật mã đó lên Etsy. Nếu Etsy báo lỗi → hệ thống rollback (giữ mã cũ + ghi lỗi vào nhật ký để BA xem).

---

## Câu hỏi thường gặp

**Q:** _Trước đây có Wizard cũ và SKU Builder — sao bây giờ không thấy nữa?_
A: Từ phiên bản này, **form Sản phẩm chuẩn đã đủ** — hệ thống tự sinh Mã SKU từ Danh mục + Biến thể nên không cần Wizard riêng nữa. Wizard cũ đã được ẩn khỏi menu để tránh nhầm lẫn.

**Q:** _Mã SKU tự sinh có sai không?_
A: Hệ thống dựa trên Danh mục + Biến thể để sinh Mã SKU. Nếu BA chọn đúng → Mã SKU sẽ đúng định dạng. BA vẫn có thể sửa tay nếu cần.

**Q:** _Tôi muốn giữ mã legacy cho sản phẩm cũ — hệ thống có cho phép không?_
A: Có. BA chỉ cần gõ tay mã cũ vào ô Mã SKU — hệ thống lưu nguyên trạng, không bắt đổi.

**Q:** _Tôi muốn xem sản phẩm nào chưa khớp mã chuẩn._
A: Mở **Sản phẩm → SKU Drift** — danh sách các sản phẩm có Mã SKU chưa khớp định dạng mới; bấm vào mỗi dòng để chọn giữ-cũ / chấp-nhận-mới.

**Q:** _Tôi cần đăng cùng một sản phẩm trên Etsy lẫn Amazon._
A: Hôm nay chỉ Etsy hoạt động. Khi Amazon ra mắt, BA chỉ cần bật "Amazon" trong kênh áp dụng của sản phẩm.

**Q:** _Tôi đặt mã Gearment xong nhưng vẫn muốn tự sản xuất._
A: Xoá ô "Mã SKU Gearment" trong form sản phẩm → hệ thống tự tắt chế độ Dropship.

**Q:** _Sản phẩm bị lỗi khi đăng — làm sao biết?_
A: Mở form sản phẩm → trang "Channels" → cột "Lỗi đồng bộ gần nhất" hiển thị thông tin lỗi. Nút **"Publish to Etsy"** sẽ đổi tên thành **"Resume Publish"** — bấm sẽ tiếp tục từ bước bị lỗi (không tạo lại từ đầu).

**Q:** _Validator ở chế độ "chặt" thì sản phẩm cũ có bị ảnh hưởng?_
A: Không. Sản phẩm cũ (legacy SKU) không bị re-validate khi đổi chế độ. Chỉ Mã SKU **tạo mới** hoặc **sửa lại** mới qua kiểm tra. Sản phẩm legacy đã được đánh dấu "BA-approved legacy" và không bị bắt buộc đổi.

**Q:** _Tôi điền tags / personalization / weight nhưng Etsy listing không thấy?_
A: Kiểm tra (1) đã bấm Lưu chưa, (2) đã chạy "Publish to Etsy" hoặc "Resume Publish" chưa. Etsy listing chỉ cập nhật khi BA bấm publish — không tự đồng bộ.

---

## Liên hệ

- Vấn đề chức năng → BA Lead.
- Mã SKU bị nghi sai → BA Manager.
- Lỗi kỹ thuật / Etsy báo lỗi → Đội Kỹ thuật.
- Đổi chế độ validator (mềm → chặt) → Admin.
- Cài đặt mặc định shop Etsy (Danh mục Etsy / Readiness / Shipping / Return) → Admin.

> Tài liệu thao tác chi tiết: [`HUONG_DAN_TAO_SAN_PHAM_VN.md`](./HUONG_DAN_TAO_SAN_PHAM_VN.md).
