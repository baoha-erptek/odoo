# Quy trình tiếp nhận đơn hàng Etsy (cho Chủ shop)

**Phiên bản:** 1.0 · **Ngày:** 2026-05-23 · **Ngôn ngữ:** Tiếng Việt

> Tài liệu này mô tả cách đơn hàng Etsy chạy từ lúc khách bấm mua đến lúc đơn vào hệ thống quản lý. Dùng cho Chủ shop và đội BA. Không có thuật ngữ kỹ thuật.

---

## Hai con đường vào hệ thống

Hôm nay đơn hàng Etsy đến với chúng ta theo hai con đường:

1. **API (đường mới)** — hệ thống đọc đơn trực tiếp từ Etsy 5 phút một lần.
2. **Email (đường cũ, dự phòng)** — Etsy gửi email báo đơn vào hộp thư, hệ thống đọc email và tạo đơn.

Mỗi shop chỉ dùng **một** đường tại một thời điểm — cấu hình quyết định đường nào đang hoạt động cho shop đó. Hôm nay shop **JaHandmadeArt** đã chuyển sang API; các shop khác vẫn dùng email cho đến khi BA xác nhận chuyển.

---

## Đường API (đang hoạt động cho JaHandmadeArt)

### Hệ thống làm gì

- Mỗi 5 phút: hệ thống gọi Etsy để lấy các đơn mới và cập nhật đơn cũ.
- Lần đầu: lấy hết các đơn chưa có trong hệ thống.
- Lần sau: chỉ lấy các đơn có thay đổi sau lần lấy trước (tiết kiệm bandwidth).
- Mỗi đơn được lưu thành **một sale.order** (đơn bán) với đầy đủ thông tin khách, sản phẩm, địa chỉ giao, ghi chú.

### Lợi ích so với đường email

- Không phụ thuộc vào lịch gửi email của Etsy.
- Đơn xuất hiện trong hệ thống trong vòng 5 phút.
- Nếu khách sửa địa chỉ giao trên Etsy, đơn trong hệ thống tự động cập nhật.
- Nhật ký gọi API được lưu cho mỗi shop để BA xem khi cần.

### Khi nào BA cần quan tâm

- Khi Etsy báo lỗi "scope/permission" → token có thể đã hết hạn → BA bấm "Authorize Etsy" trên form shop để cấp lại quyền.
- Khi đơn không xuất hiện trong hệ thống → mở form shop, bấm "Test Connection" để kiểm tra kết nối.

---

## Đường Email (cho các shop chưa chuyển)

### Hệ thống làm gì

- Mỗi 10 phút: đọc các email mới trong hộp thư Gmail đã cấu hình.
- Phát hiện email báo đơn (chủ đề có "New order from your Etsy shop").
- Bóc tách thông tin: khách hàng, sản phẩm, địa chỉ, ghi chú cá nhân hoá.
- Tạo **một sale.order** mỗi email.

### Hạn chế

- Email có thể đến trễ (Etsy gửi không tức thời).
- Một số định dạng đặc biệt có thể không bóc tách được → email rơi vào hộp "Etsy Email Log — chưa xử lý" để BA xem thủ công.
- Không bắt được thay đổi đơn sau khi tạo (chỉ tạo lúc nhận email đầu tiên).

---

## Sau khi đơn vào hệ thống

Đơn xuất hiện trong **Dashboard Vận hành** (Operations Dashboard) với các trường:

- Mã đơn nội bộ (S00001, S00002…)
- Mã đơn Etsy (gọi là "Receipt ID")
- Tên shop nguồn
- Khách hàng + địa chỉ giao
- Danh sách sản phẩm + cá nhân hoá (chữ khắc, ảnh thiết kế đính kèm…)
- Tổng tiền + chi phí vận chuyển + tổng chiết khấu
- Trạng thái pipeline VN — 17 trạng thái mô tả từ "mới nhận" đến "đã giao"

### Quyết định đầu tiên: in nội bộ hay dropship?

- Sản phẩm có **mã Gearment** → đi đường **Dropship**: BA xác nhận giá Gearment, hệ thống gửi đơn sang Gearment, Gearment in + đóng gói + giao tận khách.
- Sản phẩm **không có** mã Gearment → đi đường **MTO (Make-to-Order)** in nội bộ: hệ thống tạo phiếu sản xuất + chuyển sang đội thiết kế và đội in.

Hai đường dùng cùng một pipeline 17-trạng-thái nhưng các bước khác nhau (xem `FLOW_GIAO_HANG_VN.md`).

---

## Câu hỏi thường gặp

**Q:** _Tôi muốn xem đơn nào đến trong 24 giờ qua._
A: Mở **Dashboard Vận hành** → lọc "Ngày đặt" trong 24 giờ. Cũng có thể lọc theo shop, theo pipeline, theo nhân viên BA phụ trách.

**Q:** _Đơn Etsy có ghi chú khách hàng đặc biệt (chữ khắc, ảnh đính kèm) — chỗ nào xem?_
A: Mở chi tiết đơn → cuộn xuống dòng sản phẩm → cột "Cá nhân hoá" có toàn bộ chữ + link ảnh thiết kế (nếu có).

**Q:** _Khách yêu cầu đổi địa chỉ giao sau khi đặt — sao xử lý?_
A: Bấm nút **"Yêu cầu đổi địa chỉ"** trên form đơn → mô tả thay đổi → hệ thống tạo "Yêu cầu thay đổi địa chỉ", BA Lead duyệt → địa chỉ mới được áp dụng. Trước khi duyệt, các trường địa chỉ bị **khoá** để tránh đụng vào do bất cẩn.

**Q:** _Đơn báo "lỗi đồng bộ" — làm gì?_
A: Mở form đơn → tab "Etsy" → xem trường "Lỗi đồng bộ gần nhất". Nếu lỗi liên quan đến token / kết nối → BA chạy lại Authorize. Nếu lỗi dữ liệu → mở "Etsy API Log" để xem chi tiết, có thể cần kỹ thuật can thiệp.

---

## Liên hệ

- Đơn không xuất hiện trong hệ thống → Đội Kỹ thuật (kiểm tra Cron + Etsy API Log).
- Đơn có nhưng thiếu thông tin → BA Lead (kiểm tra parser cho Email, hoặc dữ liệu raw API).
- Etsy báo "scope/permission" → Chủ shop + Đội Kỹ thuật (Authorize Etsy lại).

> Tài liệu chi tiết cho đội kỹ thuật xem trong `specs/005-etsy-api-channel/` + `specs/001-etsy-order-migration/` (tiếng Anh).
