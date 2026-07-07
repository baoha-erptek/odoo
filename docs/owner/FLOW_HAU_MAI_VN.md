# Quy trình hậu mãi — In lại, Tin nhắn, Hoàn trả & Hoàn tiền

**Phiên bản:** 1.1 · **Ngày:** 2026-07-05 · **Ngôn ngữ:** Tiếng Việt

> Tài liệu mô tả các quy trình hậu mãi (sau khi đơn đã giao đến khách). Dùng cho Chủ shop, BA và Marketing. Phần "Hoàn trả & Hoàn tiền" đã hoạt động — quy trình ticket đã được E2E xác thực (2026-07-05).

### Màn hình thực tế

![Form ticket hậu mãi với các trường loại ticket, lý do, trạng thái và ghi chú](img/hau-mai-ticket-form.png)
*Giao diện form Ticket hậu mãi để theo dõi yêu cầu hoàn trả, hoàn tiền, in lại.*

---

## 1. In lại đơn (đang hoạt động)

### Khi nào dùng

- Khách báo sản phẩm bị lỗi (rách bao bì, in mờ, sai cá nhân hoá…).
- Đội QC phát hiện lỗi nội bộ trước khi giao.
- Đơn bị thất lạc trong vận chuyển và đã quá thời gian truy vết.

### Quy trình

1. Mở **đơn hàng gốc** trong Dashboard Vận hành.
2. Chuyển trạng thái pipeline VN sang **"In lại"** (trạng thái 16/17).
3. Ghi lý do in lại vào chatter (BA Lead duyệt qua chatter).
4. Đội sản xuất:
   - Tạo phiếu sản xuất MRP mới cho đơn.
   - Tái sử dụng file thiết kế cũ (Design Files đã có trên đơn).
5. Đội QC + Đóng gói: kiểm tra lại trước khi giao.
6. BA Shipping:
   - Đơn Dropship → gọi Gearment cho lô in lại (không tự động — phải tạo phiếu mới).
   - Đơn MTO → in nhãn vận chuyển mới + giao lại đối tác bưu vận.
7. Khi tracking mới có, hệ thống tự cập nhật lên Etsy (cùng cơ chế push tracking như đơn gốc).

### Lưu ý

- **Không tạo đơn Etsy mới** — chỉ tạo phiếu in lại nội bộ. Etsy vẫn nhìn đơn gốc.
- Đếm chi phí: phiếu in lại được ghi nhận chi phí riêng để dashboard Pricing Audit (đang xây) tính margin cuối tháng.
- Tracking thứ hai: tracking của lần in lại được push lên Etsy trên cùng receipt đơn gốc (Etsy hiển thị cả hai) — không tạo đơn Etsy mới.

---

## 2. Tin nhắn từ khách (đang hoạt động — đường email; đường API chờ Etsy duyệt)

### Khi nào dùng

- Khách hỏi về tình trạng đơn.
- Khách yêu cầu sửa địa chỉ giao.
- Khách báo lỗi sản phẩm.
- Khách hỏi cá nhân hoá / customization mới.

### Đường email (đang chạy)

1. Khách gửi tin nhắn qua Etsy → Etsy gửi email báo "buyer messaged you" đến shop inbox.
2. Cron Gmail mỗi 10 phút đọc email mới.
3. Hệ thống nhận diện email là tin-nhắn-khách (khác với email báo đơn mới).
4. Tin nhắn được liên kết với đơn (nếu nội dung có Receipt ID) → post vào chatter đơn đó.
5. Nếu chưa khớp đơn → giữ trong "Buffer" để cron đối chiếu khi đơn tới sau.
6. BA Marketing đọc + trả lời từ chatter của đơn (Odoo gửi email ra).

### Đường API (sẽ hoạt động khi Etsy duyệt scope `conversations_r`)

Khi Etsy bật quyền:

1. Cron mỗi 10 phút gọi Etsy Conversations API.
2. Lấy tin nhắn mới + ánh xạ vào đơn theo Receipt ID.
3. Đường API và đường email tự khử trùng lặp (không post 2 lần cùng một tin).

### Yêu cầu đổi địa chỉ qua tin nhắn

Khi khách yêu cầu đổi địa chỉ:

1. BA Marketing đọc tin nhắn trong chatter đơn.
2. Bấm **"Yêu cầu đổi địa chỉ"** trên form đơn.
3. Mô tả thay đổi trong wizard.
4. Hệ thống tạo "Yêu cầu thay đổi địa chỉ" + khoá trường địa chỉ trên đơn.
5. BA Lead duyệt → địa chỉ mới được áp dụng (chỉ khi đơn chưa in nhãn vận chuyển).

---

## 3. Hoàn trả & Hoàn tiền (đang hoạt động)

Quy trình ticket hậu mãi đã được E2E xác thực (2026-07-05). Hoàn tiền vẫn thực hiện thủ công trên Etsy.

### Quy trình Ticket (đang hoạt động)

1. Tạo Ticket để theo dõi mỗi yêu cầu hậu mãi (loại: hoàn trả / hoàn tiền / gửi lại).
2. BA Marketing tạo ticket trên đơn khi khách báo vấn đề.
3. Workflow: `draft` → `approved` / `rejected` → `refunded` (đã hoàn / đã gửi lại / đã đóng).
4. BA Lead duyệt + xác nhận xử lý trong ticket.
5. Khi refunded=đã hoàn tiền:
   - Ghi nhận chi phí hoàn vào đơn.
   - Báo cáo hoàn tiền hàng tháng cho Kế toán + Chủ shop.

### Hoàn tiền (vẫn thủ công)

- Hoàn tiền: BA refund trên Etsy buyer + ghi chú vào ticket trên hệ thống.
- Hoàn trả vật lý: chưa có quy trình hoá đơn ngược; đội kho ghi nhận thủ công.
- Báo cáo: BA xuất Excel hàng tháng từ Etsy Shop Manager.

---

## Câu hỏi thường gặp

**Q:** _Khách yêu cầu hủy đơn sau khi đã in nhãn._
A: Trong nhiều trường hợp không thể hủy. BA Marketing trả lời khách qua chatter, đơn vẫn giao + xử lý hoàn ở giai đoạn "Hoàn trả" sau khi khách nhận.

**Q:** _Đơn in lại nhưng khách báo vẫn lỗi._
A: Tạo phiếu in lại lần 2 + ghi rõ lý do "in lại lần 2" trong chatter. BA Lead xem xét có nên đổi đội thiết kế hay đổi đối tác in.

**Q:** _Tin nhắn từ buyer không liên kết được với đơn nào — phải làm gì?_
A: Tin nhắn ở "Buffer" 7 ngày → sau đó chuyển sang trạng thái "orphaned" để BA review. Nếu khách hỏi về đơn cụ thể nhưng không kèm Receipt ID, BA Marketing copy nội dung vào chatter đơn tương ứng.

**Q:** _Refund trên Etsy có tự cập nhật vào hệ thống không?_
A: Hiện tại chưa. BA Marketing phải ghi note vào chatter đơn (và cập nhật ticket hậu mãi). Tự động đồng bộ refund từ Etsy về hệ thống nằm trong kế hoạch phiên bản kế tiếp.

---

## Liên hệ

- Tin nhắn khách hàng → BA Marketing.
- In lại do lỗi sản xuất → BA Lead + Sản xuất.
- Hoàn trả vật lý / Hoàn tiền → BA Lead + Kế toán + Chủ shop.

> Tính năng `etsy.order.ticket` đã LIVE (E2E-verify 2026-07-05); phần tự động đồng bộ refund từ Etsy sẽ bổ sung ở phiên bản kế tiếp.
