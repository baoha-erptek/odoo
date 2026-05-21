# Tài liệu Yêu cầu Phần mềm (SRS)
## Hệ thống quản lý đơn hàng Etsy đa kênh

**Phiên bản:** 1.0
**Ngày phát hành:** 2026-05-21
**Liên quan:** `BRD_VN.md` (Tài liệu Yêu cầu Kinh doanh)
**Phục vụ sync Jira:** Project `ESTY` trên `erptek.atlassian.net`
**Trạng thái:** Bản nháp chờ Chủ dự án duyệt

> Tài liệu này mô tả **chức năng cụ thể** của hệ thống bằng tiếng Việt nghiệp vụ. Mỗi mục là một **Story** sẽ được tạo trên Jira. Sáu **Epic** đại diện cho 6 phase nghiệp vụ trong BRD. Sau khi CDA duyệt, BA sẽ sync toàn bộ lên Jira.

---

## Quy ước trạng thái và ưu tiên

### Cờ trạng thái

| Cờ | Ý nghĩa |
|----|---------|
| ✅ **Xong** | Đã coding xong, đã chạy thử trên môi trường staging, sẵn sàng dùng |
| 🟡 **Đang làm** | Đang phát triển hoặc đang chỉnh sửa |
| 🟥 **Bị chặn** | Chờ Chủ dự án hoặc đối tác bên ngoài (Etsy, Gearment) phản hồi |
| ⏳ **Sắp làm** | Đã có kế hoạch, chưa bắt đầu |

### Mức ưu tiên

| Mức | Ý nghĩa |
|-----|---------|
| **P0** | Bắt buộc — không có thì hệ thống không vận hành được |
| **P1** | Quan trọng — cần để go-live đầy đủ |
| **P2** | Nâng cao — có sau khi hệ thống chạy ổn |
| **P3** | Tương lai — Phase 3+ |

---

## EPIC 1 — Nhập đơn tự động (Order Intake)

**Mục tiêu:** Đơn từ Etsy tự chảy vào hệ thống trong vòng 5 phút; không phải nhập tay từ Gmail. Làm sạch 17.659 đơn cũ.

### Story 1.1 — Kết nối tài khoản Etsy an toàn

- **Mô tả:** Chủ dự án vào trang cấu hình, bấm "Connect Etsy", đăng nhập 1 lần. Hệ thống nhớ kết nối, tự gia hạn, cảnh báo trước 7 ngày khi cần kết nối lại.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0 | **ETA:** đã go-live 2026-05-12
- **Tiêu chí nghiệm thu:**
  - Đăng nhập 1 lần, không phải làm lại trong 90 ngày
  - Có thông báo trên dashboard khi sắp hết hạn
  - Có nút "Test connection" để kiểm tra ngay

### Story 1.2 — Tự động kéo đơn mới mỗi 5 phút

- **Mô tả:** Hệ thống tự lấy đơn mới và đơn bị sửa từ Etsy mỗi 5 phút. Không tạo trùng. Không ghi đè ghi chú nội bộ của Marketing.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Đơn mới trên Etsy xuất hiện trong hệ thống trong ≤5 phút
  - Đơn bị sửa địa chỉ trên Etsy thì hệ thống cập nhật trạng thái nhưng giữ nguyên ghi chú MP
  - Trong 7 ngày không có đơn nào bị trùng

### Story 1.3 — Email parser dự phòng

- **Mô tả:** Nếu Etsy API gặp lỗi 3 lần liên tiếp, hệ thống tự chuyển sang đọc email Gmail để không sót đơn. Khi API khôi phục, tự chuyển ngược lại.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Tự chuyển sang email trong 15 phút khi API hỏng
  - Có cảnh báo HIGH gửi cho admin khi xảy ra
  - Tự khôi phục về API sau khi API ổn 6 lần liên tiếp

### Story 1.4 — Làm sạch 17.659 đơn cũ (Migration)

- **Mô tả:** Đọc file Excel lịch sử (17.659 đơn) và tạo trong hệ thống. Có thể chạy lại nếu gián đoạn. Tự nhận diện tiền tệ (USD, EUR, GBP, CAD, VND). Tách phí ship thành dòng riêng.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Tổng số đơn nhập khớp tổng trong Excel
  - Tổng doanh thu khớp trong sai số $0.01/đơn
  - Báo cáo có danh sách đơn lỗi để BA xử lý tay
  - BA Lead ký xác nhận trước khi sang giai đoạn tiếp

### Story 1.5 — Sửa 423 đơn ghi giá $0

- **Mô tả:** Hệ thống tính lại giá cho 423 đơn ghi $0 từ nguồn gốc. Đơn không tính được sẽ liệt kê cho BA xử lý tay.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - ≥80% trong 423 đơn được tính lại tự động
  - Đơn không tính được có lý do rõ ràng

### Story 1.6 — Gộp khách hàng trùng (có BA duyệt)

- **Mô tả:** Hệ thống đề xuất danh sách khách trùng → xuất Excel → BA tick chọn → upload lại để gộp. **KHÔNG tự gộp** — phải có BA duyệt.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Excel xuất ra rõ ràng (tên, email, số đơn từng khách)
  - Sau khi upload, có báo cáo "gộp thành công X / lỗi Y"
  - Có nút hoàn tác trong 24h

### Story 1.7 — Đồng bộ danh sách sản phẩm và tồn kho từ Etsy

- **Mô tả:** Tải danh sách sản phẩm và số lượng tồn kho từ Etsy về hệ thống. Chỉ đọc, không sửa được.
- **Trạng thái:** 🟡 Đang làm | **Ưu tiên:** P1 | **ETA:** tuần đầu tháng 6/2026
- **Tiêu chí nghiệm thu:**
  - Mỗi shop xem được số sản phẩm và tồn kho hiện tại
  - Có cảnh báo khi tồn kho lệch >10% giữa Etsy và hệ thống

### Story 1.8 — Bật API cho shop thí điểm (Pilot)

- **Mô tả:** Chủ dự án chọn 1 shop để bật chế độ API (thay vì email). Theo dõi 1-2 tuần để đảm bảo không sót đơn.
- **Trạng thái:** 🟥 Bị chặn (CDA cần thao tác) | **Ưu tiên:** P0 | **ETA:** tuần 3 tháng 5/2026
- **Tiêu chí nghiệm thu:**
  - Shop thí điểm chạy API trong 14 ngày không sót đơn
  - Không có khiếu nại nào từ Marketing
  - Có quy trình rollback (về lại email) nếu cần

### Story 1.9 — Bật API cho 18 shop còn lại

- **Mô tả:** Sau khi shop thí điểm ổn, mở rộng ra 18 shop còn lại, mỗi đợt 2-4 shop.
- **Trạng thái:** ⏳ Sắp làm | **Ưu tiên:** P0 | **ETA:** tháng 6-7/2026
- **Tiêu chí nghiệm thu:**
  - Tất cả 19 shop chạy API
  - Email cron tự tắt sau khi hoàn tất
  - Không có đơn nào sót trong 14 ngày sau cùng

---

## EPIC 2 — Duyệt thiết kế (Design Approval)

**Mục tiêu:** File thiết kế upload 1 lần, các bộ phận xem đúng phiên bản, in được hàng loạt.

### Story 2.1 — BA upload file thiết kế lên Google Drive

- **Mô tả:** BA upload file lớn (vd 150MB) cho đơn. Hệ thống lưu trên Google Drive, ghi nhớ link và phiên bản. Có thể xóa và upload lại bản mới; bản cũ vẫn lưu để truy vết.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - File >100MB upload được trong ≤2 phút
  - Mỗi lần upload tạo 1 phiên bản mới, không ghi đè
  - Lịch sử phiên bản hiển thị rõ trên form đơn

### Story 2.2 — Quy trình duyệt 3 trạng thái

- **Mô tả:** File có 3 trạng thái: **Chờ duyệt → Đã duyệt → Cần chỉnh lại**. PD bấm duyệt hoặc chọn "Cần chỉnh" (phải nhập lý do). Ghi nhận ai duyệt, khi nào.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - 3 trạng thái rõ ràng trên giao diện
  - "Cần chỉnh lại" bắt buộc nhập lý do ≥10 ký tự
  - Lịch sử duyệt hiển thị trên form đơn

### Story 2.3 — Bảng kanban hàng đợi duyệt

- **Mô tả:** Designer và BA thấy danh sách đang chờ duyệt theo dạng cột (3 cột tương ứng 3 trạng thái). Kéo-thả hoặc click để chuyển trạng thái.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P1
- **Tiêu chí nghiệm thu:**
  - 3 cột hiển thị đúng số file
  - Cập nhật real-time khi có người duyệt

### Story 2.4 — Tự động gửi file đến các bộ phận liên quan

- **Mô tả:** Khi BA duyệt đơn, hệ thống tự cấp quyền đọc file cho PD, MP, hoặc đối tác (Gearment) tùy đơn. Không cần BA gửi tay.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Mỗi đơn duyệt → file tự gửi đến đúng người trong ≤2 phút
  - Có badge cảnh báo nếu gửi thất bại sau 2 giờ

### Story 2.5 — PD bulk-download in A4

- **Mô tả:** PD tick các file đã duyệt → bấm "Download A4" → hệ thống tạo file PDF dàn sẵn để in. Cache 24 giờ để in lại không phải chờ.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P1
- **Tiêu chí nghiệm thu:**
  - Bulk-download ≤50 file trong ≤30 giây
  - PDF in được trên máy in A4 thông thường

### Story 2.6 — Tự lưu trữ file đã in

- **Mô tả:** File đã in xong và đơn đã giao thì tự chuyển sang trạng thái "Đã lưu trữ" để không hiển thị trong danh sách hàng ngày, tránh rối mắt.
- **Trạng thái:** ⏳ Sắp làm | **Ưu tiên:** P2 | **ETA:** cuối tháng 5/2026
- **Tiêu chí nghiệm thu:**
  - File tự ẩn sau 30 ngày kể từ ngày đơn giao
  - Có filter "Xem cả file đã lưu trữ" để xem lại

### Story 2.7 — Cảnh báo file thiếu trước sản xuất

- **Mô tả:** Khi đơn được đẩy sản xuất nhưng chưa có file thiết kế duyệt, hệ thống chặn và cảnh báo BA.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Đơn không có file duyệt → không đẩy được sang PD/Gearment
  - Cảnh báo hiển thị rõ trên form đơn

---

## EPIC 3 — Sản xuất (Production)

**Mục tiêu:** Thấy đơn đang ở công đoạn nào, ai phụ trách, có trễ không. Cho phép cấu hình các bước sản xuất riêng.

### Story 3.1 — Dashboard sản xuất với 17 trạng thái Việt Nam

- **Mô tả:** PD và BA xem đơn theo cột "Trạng thái" với 17 bước chuẩn (CHỜ FILE → ... → VN-Fulfilled). Đơn US và VN cùng dashboard.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - 17 cột hiển thị đúng số đơn
  - Click trạng thái để mở danh sách đơn
  - Tô màu khác nhau cho từng trạng thái

### Story 3.2 — Pipeline đơn cấu hình được

- **Mô tả:** Admin có thể tạo pipeline mới (vd cho dòng sản phẩm khác), thêm/xóa/sửa stage, đổi tên, đổi màu. Không cần lập trình.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Admin tạo được pipeline mới qua giao diện
  - Đổi tên stage không ảnh hưởng đơn đang chạy
  - Audit log ghi mọi thay đổi cấu trúc

### Story 3.3 — Tuyến Dropship và Make-to-Order (MTO)

- **Mô tả:** Hệ thống tự quyết định đơn nào đi tuyến "Dropship" (gửi thẳng từ Gearment) hay "MTO" (sản xuất nội bộ) dựa trên loại sản phẩm.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Đơn POD (Gearment) → tuyến Dropship
  - Đơn sản xuất nội bộ → tuyến MTO
  - Có thể override tay khi cần

### Story 3.4 — Gán team phụ trách cho từng stage

- **Mô tả:** Mỗi stage trong pipeline có thể gán cho một team (vd "Team thêu", "Team in"). Đơn ở stage đó hiển thị tên team phụ trách.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Mỗi stage gán được 1 team default
  - PD lead có thể override per-đơn
  - Filter theo team hoạt động

### Story 3.5 — Scan barcode để chuyển trạng thái

- **Mô tả:** PD scan barcode đơn → hệ thống tự chuyển sang stage "Đã fulfilled", ghi ngày ship, ai scan.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P1
- **Tiêu chí nghiệm thu:**
  - Scan 1 đơn xong trong ≤2 giây
  - Audit log ghi đúng người scan

### Story 3.6 — Tự chuyển stage khi xong workorder MRP

- **Mô tả:** Khi PD hoàn thành 1 công đoạn trong MRP, hệ thống tự đẩy đơn sang stage tiếp theo trong pipeline. PD không phải bấm tay 2 nơi.
- **Trạng thái:** ⏳ Sắp làm | **Ưu tiên:** P1 | **ETA:** tuần 2 tháng 6/2026
- **Tiêu chí nghiệm thu:**
  - Hoàn thành workorder → stage pipeline đổi trong ≤5 giây
  - Có nút tắt auto-advance nếu PD muốn kiểm soát tay

### Story 3.7 — Widget thống kê sản xuất

- **Mô tả:** Trên dashboard sản xuất có widget hiển thị: tổng đơn đang chạy, đơn sắp trễ, đơn theo loại sản phẩm, đơn theo team.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P2
- **Tiêu chí nghiệm thu:**
  - Cập nhật real-time khi có đơn mới
  - Click widget mở danh sách lọc

---

## EPIC 4 — Vận chuyển & tracking (Fulfillment & Tracking)

**Mục tiêu:** Đẩy đơn sang đối tác (Gearment), nhập tracking GKE, cập nhật tracking về Etsy, duyệt đổi địa chỉ.

### Story 4.1 — Kết nối Gearment, đẩy đơn qua API

- **Mô tả:** BA bấm "Push to Gearment" trên đơn → hệ thống gửi sang Gearment qua API, kèm file thiết kế. Theo dõi trạng thái Draft → Quote → Confirm.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Push thành công trong ≤10 giây
  - Đơn lên Gearment với đúng SKU và địa chỉ
  - File thiết kế đính kèm đúng

### Story 4.2 — Nhận webhook trạng thái từ Gearment

- **Mô tả:** Khi Gearment update đơn (vd: đang sản xuất, đã ship, có tracking), hệ thống nhận tự động qua webhook. Không cần BA bấm refresh.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Webhook xử lý trong ≤5 giây
  - Đơn update đúng trạng thái
  - Có cron pull dự phòng mỗi 5 phút nếu webhook miss

### Story 4.3 — Import tracking từ file Excel GKE

- **Mô tả:** BA upload file Excel GKE → hệ thống đọc, khớp Order ID, tự điền tracking + carrier. Hàng không khớp được liệt kê cho BA xử lý tay.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - File Excel chuẩn GKE đọc đúng 100%
  - Báo cáo matched / unmatched rõ ràng
  - Có cron tự đọc file mới upload lên Google Drive

### Story 4.4 — Tự nhận diện carrier từ mã tracking

- **Mô tả:** Hệ thống tự đoán carrier (USPS / UniUni / YunExpress / Other) từ format mã tracking. BA không phải chọn tay.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - ≥95% mã tracking nhận đúng carrier
  - Mã không nhận được → carrier = "Other"

### Story 4.5 — Đẩy tracking ngược về Etsy

- **Mô tả:** Khi tracking vào hệ thống, tự đẩy lên Etsy trong ≤5 phút (theo cài đặt từng shop).
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Tracking lên Etsy trong ≤5 phút
  - Marketing có công tắc "Auto-push" bật/tắt từng shop
  - Có retry tối đa 3 lần nếu Etsy fail

### Story 4.6 — Duyệt đổi địa chỉ giao hàng

- **Mô tả:** Marketing không sửa địa chỉ trực tiếp được. Phải tạo "Yêu cầu đổi địa chỉ" → BA duyệt/từ chối → mới sửa. Trong khi chờ duyệt, không cho mua label.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - MP không có quyền sửa địa chỉ trực tiếp
  - Yêu cầu duyệt xử lý trong ≤24h
  - Đơn đang chờ duyệt địa chỉ → nút "Buy Label" bị khóa
  - Có badge cảnh báo trên dashboard

### Story 4.7 — Bulk-action "Gửi đơn đã duyệt sang Gearment"

- **Mô tả:** BA tick nhiều đơn → bấm "Send approved to Gearment" để đẩy hàng loạt thay vì từng đơn.
- **Trạng thái:** ⏳ Sắp làm | **Ưu tiên:** P1 | **ETA:** cuối tháng 5/2026
- **Tiêu chí nghiệm thu:**
  - Đẩy được ≤50 đơn/lần
  - Báo cáo: thành công X / lỗi Y
  - Đơn lỗi không chặn các đơn khác

### Story 4.8 — Xử lý đơn hoàn / refund

- **Mô tả:** Có form tạo ticket replace / refund / discount trên đơn. MP nhập lý do + ảnh → BA duyệt → hệ thống tự xử lý (refund → credit note; replace → đơn mới link đơn gốc).
- **Trạng thái:** ⏳ Sắp làm | **Ưu tiên:** P1 | **ETA:** tháng 7/2026
- **Tiêu chí nghiệm thu:**
  - Tạo ticket trong ≤3 phút
  - BA duyệt → tự xử lý không sai
  - Có lịch sử ticket trên form đơn

### Story 4.9 — Hiển thị trạng thái tracking (In-transit / Delivered / Returned)

- **Mô tả:** Hệ thống nhận webhook từ carrier (USPS, UniUni, YunExpress) và hiển thị trạng thái real-time trên dashboard Tracking.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P1
- **Tiêu chí nghiệm thu:**
  - Trạng thái cập nhật trong ≤5 phút sau khi carrier báo
  - Dashboard tô màu khác nhau cho từng trạng thái

---

## EPIC 5 — Tin nhắn khách hàng (Customer Conversations)

**Mục tiêu:** Đọc và trả lời tin nhắn 19 shop ở một chỗ. Tự tạo CRM lead khi cần.

### Story 5.1 — Hiển thị "buyer message" trên form đơn

- **Mô tả:** Khi khách ghi chú khi đặt đơn (vd custom name, gift message), nội dung này hiển thị nổi bật trên form đơn để MP và PD không bỏ sót.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Buyer message hiển thị trên top form đơn
  - PD thấy nội dung custom trước khi sản xuất

### Story 5.2 — Hub tin nhắn khách (Customer Message Hub)

- **Mô tả:** Một trang duy nhất hiển thị tin nhắn khách của 19 shop. Có search, filter theo shop, theo ngày.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P1
- **Tiêu chí nghiệm thu:**
  - Hiển thị tin nhắn của tất cả shop đã connect API
  - Search hoạt động trên nội dung và tên khách

### Story 5.3 — Tạo CRM lead từ tin nhắn khách

- **Mô tả:** Khi tin nhắn khách chứa câu hỏi mua hàng (vd hỏi giá custom), MP có nút tạo CRM lead trực tiếp. BA theo dõi lead trên dashboard CRM.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P1
- **Tiêu chí nghiệm thu:**
  - Tạo lead trong ≤1 click
  - Lead link với tin nhắn gốc
  - Có dashboard CRM lead riêng

### Story 5.4 — Mail alias gom phản hồi khách

- **Mô tả:** Tạo email alias riêng cho từng shop. Khi khách trả lời, hệ thống tự gom vào CRM lead tương ứng.
- **Trạng thái:** ⏳ Sắp làm | **Ưu tiên:** P2 | **ETA:** tháng 7/2026
- **Tiêu chí nghiệm thu:**
  - Email reply gom đúng lead
  - Không trùng (1 email = 1 entry)

### Story 5.5 — Re-submit Etsy app để xin quyền đọc tin nhắn đầy đủ

- **Mô tả:** Etsy hiện chỉ duyệt 4/5 quyền truy cập; thiếu quyền `conversations_r` (đọc tin nhắn Etsy đầy đủ). Cần submit lại đơn đăng ký.
- **Trạng thái:** 🟥 Bị chặn (CDA cần thao tác) | **Ưu tiên:** P1 | **ETA:** chờ Etsy 3-8 tuần sau khi submit
- **Tiêu chí nghiệm thu:**
  - CDA submit đơn đăng ký lại với justification rõ
  - Etsy phản hồi duyệt
  - Hệ thống bật module đọc tin nhắn đầy đủ

### Story 5.6 — Kéo tin nhắn Etsy qua API (sau khi được duyệt)

- **Mô tả:** Sau khi Etsy duyệt `conversations_r`, hệ thống tự kéo toàn bộ tin nhắn về Hub. Không phải xem từng shop.
- **Trạng thái:** 🟥 Bị chặn (chờ Story 5.5) | **Ưu tiên:** P1 | **ETA:** sau khi Etsy duyệt + 1 tuần code
- **Tiêu chí nghiệm thu:**
  - Tin nhắn mới về Hub trong ≤5 phút
  - Không trùng với tin nhắn đã có

---

## EPIC 6 — Báo cáo & quản trị (Reporting & Governance)

**Mục tiêu:** Mỗi bộ phận có dashboard riêng. Audit log mọi thao tác. Việt hoá toàn bộ giao diện. Kiểm soát giá.

### Story 6.1 — Dashboard Đơn hàng (BA + Marketing)

- **Mô tả:** Bảng đơn 10 cột cốt lõi: Shop, Order ID, Tracking, Ảnh, Ngày, Tình trạng, SL, Shipping, Quốc gia, Tổng giá. Inline edit. Tô màu theo loại đơn.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Hiển thị đủ 10 cột
  - Search hoạt động trên Shop + Order ID
  - Inline edit cho Tracking, Carrier, Label state, Note
  - Đơn qty≥2 → cam; đơn Push → đỏ; đơn quá hạn → vàng

### Story 6.2 — Dashboard Tracking (BA)

- **Mô tả:** Trang riêng cho tracking, 13 cột (Order ID, Tracking, Carrier, Tình trạng, ... Quốc gia). Export Excel. Bulk chuyển label state.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - 13 cột hiển thị đúng
  - Export Excel theo filter hiện tại
  - Bulk action: chọn nhiều → đổi label state 1 click

### Story 6.3 — Dashboard Sản xuất (PD + BA)

- Đã mô tả ở Story 3.1.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0

### Story 6.4 — Dashboard Tài chính

- **Mô tả:** Tổng doanh thu, chi phí, lợi nhuận theo shop / tháng / quý. Xuất Excel cho kế toán.
- **Trạng thái:** ⏳ Sắp làm | **Ưu tiên:** P1 | **ETA:** tháng 6/2026
- **Tiêu chí nghiệm thu:**
  - Doanh thu tổng khớp với báo cáo Etsy trong sai số 1%
  - Filter theo shop / khoảng ngày
  - Export Excel cho kế toán

### Story 6.5 — Dashboard Kiểm soát giá (Pricing Audit)

- **Mô tả:** 25 cột (A-F nhập tay, G-T tự lấy từ đơn). Quy đổi đa tiền tệ về EUR. Tô màu chênh lệch giá so với catalog. Cron mỗi sáng list đơn vượt ngưỡng.
- **Trạng thái:** ⏳ Sắp làm | **Ưu tiên:** P1 | **ETA:** tháng 7/2026
- **Tiêu chí nghiệm thu:**
  - 25 cột hiển thị đúng
  - Tô màu đỏ (thấp) / vàng (bằng) / tím (cao) so với catalog
  - Cron mỗi 7h sáng gửi danh sách đơn lệch giá cho RD

### Story 6.6 — Audit log mọi thao tác

- **Mô tả:** Mọi thay đổi trên đơn (đổi tracking, đổi địa chỉ, đổi trạng thái, duyệt file) đều ghi: ai, khi nào, từ giá trị nào sang giá trị nào.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Mỗi đơn có tab "Lịch sử" hiển thị đầy đủ
  - Search theo người sửa, theo loại thao tác

### Story 6.7 — Phân vai trò người dùng

- **Mô tả:** Phân quyền theo bộ phận (Chủ dự án / BA / MP / PD / RD). Mỗi vai trò chỉ thấy menu và dữ liệu của mình.
- **Trạng thái:** ✅ Xong | **Ưu tiên:** P0
- **Tiêu chí nghiệm thu:**
  - Đăng nhập tài khoản PD → chỉ thấy Dashboard Sản xuất
  - Đăng nhập tài khoản MP → không sửa được địa chỉ
  - Admin có thể override khi cần

### Story 6.8 — Việt hoá toàn bộ giao diện

- **Mô tả:** Tất cả nhãn, nút, thông báo trên giao diện chuyển sang tiếng Việt. Người dùng không cần biết tiếng Anh.
- **Trạng thái:** ⏳ Sắp làm | **Ưu tiên:** P1 | **ETA:** tháng 6/2026
- **Tiêu chí nghiệm thu:**
  - 100% nhãn hệ thống Việt hoá (trừ tên riêng Etsy/Gearment/SKU)
  - Người mới vào hiểu được mà không cần đào tạo tiếng Anh

### Story 6.9 — Kiểm tra sức khỏe hệ thống (Health Monitoring)

- **Mô tả:** Dashboard chuyên dụng hiển thị: API Etsy ổn không, Gearment ổn không, Google Drive ổn không, cron có chạy không, có job nào fail không.
- **Trạng thái:** ⏳ Sắp làm | **Ưu tiên:** P2 | **ETA:** tháng 7/2026
- **Tiêu chí nghiệm thu:**
  - 5 tile xanh/vàng/đỏ rõ ràng
  - Admin click tile để xem chi tiết lỗi

### Story 6.10 — Báo cáo định kỳ qua email

- **Mô tả:** Hàng sáng 7h, gửi email cho Chủ dự án: tổng đơn hôm qua, doanh thu, đơn lỗi, cảnh báo đặc biệt.
- **Trạng thái:** ⏳ Sắp làm | **Ưu tiên:** P2 | **ETA:** tháng 7-8/2026
- **Tiêu chí nghiệm thu:**
  - Email gửi đúng 7h sáng mỗi ngày
  - Nội dung đúng format CDA duyệt

---

## Tổng hợp Stories

| Epic | Số Story | Xong | Đang làm | Bị chặn | Sắp làm |
|------|----------|------|----------|---------|---------|
| 1. Nhập đơn | 9 | 6 | 1 | 1 | 1 |
| 2. Duyệt thiết kế | 7 | 6 | 0 | 0 | 1 |
| 3. Sản xuất | 7 | 6 | 0 | 0 | 1 |
| 4. Vận chuyển & tracking | 9 | 7 | 0 | 0 | 2 |
| 5. Tin nhắn khách hàng | 6 | 3 | 0 | 2 | 1 |
| 6. Báo cáo & quản trị | 10 | 5 | 0 | 0 | 5 |
| **Tổng** | **48** | **33 (69%)** | **1** | **3** | **11** |

---

## Phụ lục — Mapping nội bộ (chỉ dành cho BA/Dev)

> Phần này dành cho BA và Dev khi cần đối chiếu với tài liệu kỹ thuật cũ và slice tracker. CDA không cần đọc.

| Story | Spec gốc | Slice ID nội bộ |
|-------|----------|------------------|
| 1.1 | Spec 005 | P0-14..17, P1-10, P1-11-RUNBOOK |
| 1.2 | Spec 005 | P1-10, P1-12 |
| 1.3 | Spec 001 + ADR-008a | P0-22 |
| 1.4 | Spec 002 US1-US6 | P0-05..07 |
| 1.5 | Spec 002 US2 | P0-05 |
| 1.6 | Spec 002 US5 | P0-06 |
| 1.7 | Spec 008 | P-LIST-PULL, P-LIST-INV-PULL |
| 1.8 | — | P1-11 (owner-op) |
| 1.9 | — | P1-13, P2-07, P2-08 |
| 2.1 | Spec 003, ADR-009 | P1-02a, P1-02b |
| 2.2 | Spec 003 US2 | P1-02b |
| 2.3 | Spec 003 | P1-02b |
| 2.4 | ADR-009 | P1-02c |
| 2.5 | Spec 003 | P1-02d (P1-lbl?) |
| 2.6 | — | P1-DESIGN-AUTO-ARCHIVE |
| 2.7 | Spec 003 | P1-DESIGN-WIZ-ATTACH-SCOPE |
| 3.1 | Spec 003 US3, ADR-010 | P1-PIPELINE-* |
| 3.2 | ADR-010 | P1-PIPELINE-* |
| 3.3 | ADR-010 amendment | P1-DROP-*, P1-MTO-* |
| 3.4 | ADR-010 §6 | P1-PIPELINE-* |
| 3.5 | Spec 003 | P1-* |
| 3.6 | — | P1-AUTO-TX |
| 3.7 | Spec 003 | — |
| 4.1 | Spec 004, ADR-005 | P4-01 + subs |
| 4.2 | Spec 004 | P4-01-d |
| 4.3 | Spec 004a | P2-01..06 |
| 4.4 | Spec 004a | P2-02 |
| 4.5 | Spec 005 | P1-12 |
| 4.6 | Spec 003 US5 | P1-04..06 |
| 4.7 | — | P4-01b |
| 4.8 | Spec 004 (was 004c) | P4-02 |
| 4.9 | Spec 004 | (in P4 batch) |
| 5.1 | Spec 005 | included in P0-17 |
| 5.2 | Spec 007 | included in lead model |
| 5.3 | Spec 007, ADR-011 | P3-LEAD-MODEL, P3-LEAD-CONVERT |
| 5.4 | Spec 007 | P3-LEAD-MAIL-ALIAS |
| 5.5 | E1 dep | P1-MSG-SCOPE (owner-op) |
| 5.6 | Spec 007 Family C | P1-MSG-API-PULL |
| 6.1 | Spec 003 US1, US6, US7 | P1-01 (CEO-merged with P1-03) |
| 6.2 | Spec 003 US1 | P1-03 (merged into P1-01) |
| 6.3 | Spec 003 US3 | P1-PIPELINE-* |
| 6.4 | Spec 003 US4 | (chưa có slice) |
| 6.5 | Spec 004, REQ-EXT-01..03b | P4-03 |
| 6.6 | Spec 003, audit log | P1-08 |
| 6.7 | (cross-cutting) | (in mhc) |
| 6.8 | (cross-cutting) | P1-07 |
| 6.9 | Spec 002, P0-11..13 | P0-11, P0-12, P0-13, P0-19 |
| 6.10 | — | (chưa có slice) |

---

*Hết SRS v1.0. Theo dõi tiến độ chi tiết trong Jira sau khi sync (xem `JIRA_SYNC_PLAN.md`).*
