# Tài liệu Yêu cầu Kinh doanh (BRD)
## Hệ thống quản lý đơn hàng Etsy đa kênh

**Phiên bản:** 1.0
**Ngày phát hành:** 2026-05-21
**Người soạn:** Bộ phận Tư vấn Nghiệp vụ
**Người duyệt:** Chủ dự án Etsy Shop
**Trạng thái:** Bản nháp chờ Chủ dự án ký

> Tài liệu này viết bằng ngôn ngữ kinh doanh, dành cho Chủ dự án (CDA) đọc và duyệt. Không có thuật ngữ kỹ thuật. Bản chi tiết yêu cầu phần mềm xem trong `SRS_VN.md`.

---

## 1. Bối cảnh & vấn đề hiện tại

### 1.1 Hiện trạng vận hành

Hiện tại doanh nghiệp đang vận hành **19 cửa hàng Etsy**, kết hợp đối tác sản xuất ngoài (**Gearment**), nhà vận chuyển (**GKE Logistics**), và một phần kênh **Amazon**. Toàn bộ thao tác đang chạy trên:

- Email Gmail (nhận đơn từ Etsy)
- Google Sheet và file Excel (theo dõi đơn, tracking, sản xuất, doanh số)
- Tin nhắn rời rạc qua Etsy Messages, Discord, Zalo nội bộ
- Thao tác sao chép tay giữa email → Excel → file đối tác

### 1.2 Vấn đề chính (Pain points)

| # | Vấn đề | Hậu quả kinh doanh |
|---|--------|---------------------|
| 1 | Nhập đơn từ email vào Excel bằng tay (~17 đơn/ngày/người) | BA mất 2 giờ/ngày, dễ bỏ sót, sai số liệu |
| 2 | Khoảng **17.659 đơn cũ** trong hệ thống bị thiếu giá, trùng khách, thiếu thông tin | Không thể báo cáo doanh thu chính xác |
| 3 | **423 đơn** ghi giá $0 (lỗi nhập) | Sai lệch báo cáo tài chính |
| 4 | Không biết đơn nào đang sản xuất, đơn nào sắp trễ giao | Khách hủy, đánh giá xấu trên Etsy |
| 5 | Tin nhắn khách hàng rải rác 19 shop, không có chỗ trả lời tập trung | Trả lời chậm, mất doanh số |
| 6 | File thiết kế gửi đi gửi lại nhiều bộ phận, không biết bản nào mới nhất | Bộ phận Sản xuất in nhầm bản cũ |
| 7 | Tracking nhập tay từ file Excel của GKE | Chậm cập nhật, khách phàn nàn |
| 8 | Đổi địa chỉ giao hàng không có quy trình duyệt | Đã từng gửi nhầm đơn vì sửa địa chỉ tự ý |
| 9 | Giá bán, giá ship không có cách kiểm tra hàng ngày | Có đơn lệch giá vài USD/đơn, không phát hiện |
| 10 | Mỗi phòng giữ một file Excel riêng, dữ liệu không khớp | Họp giao ban mất 30 phút khớp số |

---

## 2. Tầm nhìn — hệ thống mới sẽ làm gì

**Một hệ thống duy nhất** thay thế Excel + Gmail + Discord, vận hành toàn bộ vòng đời đơn hàng:

```
Khách đặt đơn trên Etsy
        ↓
Hệ thống tự kéo đơn về (mỗi 5 phút)
        ↓
Duyệt file thiết kế (BA tải lên → PD duyệt)
        ↓
Đẩy sản xuất (nội bộ Việt Nam HOẶC Gearment)
        ↓
Cập nhật tracking ngược về Etsy
        ↓
Phản hồi tin nhắn khách trong cùng hệ thống
```

Năm bộ phận (Chủ dự án, BA, Marketing, Sản xuất, Kiểm soát giá) đều thao tác **trên cùng một hệ thống**, mỗi người thấy đúng phần dữ liệu của mình.

---

## 3. Lợi ích kinh doanh kỳ vọng

| Lợi ích | Đo lường | Đối tượng hưởng lợi |
|---------|----------|----------------------|
| Tiết kiệm thời gian nhập đơn tay | BA giảm ~70% thời gian/đơn (2 giờ/ngày → 30 phút) | BA |
| Không bỏ sót đơn | Đơn vào hệ thống trong 5 phút sau khi khách đặt | BA, Chủ dự án |
| Phát hiện đơn trễ giao sớm | Cảnh báo trước hạn ship, không sau | Chủ dự án, Marketing |
| Trả lời khách trong ngày | Tin nhắn 19 shop hiện chung một chỗ | Marketing |
| In file thiết kế đúng phiên bản | Mỗi file có lịch sử duyệt, ai sửa khi nào | Sản xuất |
| Báo cáo doanh thu chính xác | Doanh thu cuối ngày tự ra, không phải khớp tay | Chủ dự án |
| Tracking đến Etsy nhanh hơn | <5 phút sau khi nhập vào hệ thống | BA, Khách hàng |
| Giảm rủi ro gửi nhầm địa chỉ | Đổi địa chỉ phải qua duyệt | Chủ dự án, Khách hàng |
| Kiểm soát giá hàng ngày | Đơn lệch giá tự nổi đỏ trên dashboard | Kiểm soát giá |

---

## 4. Phạm vi dự án

### 4.1 Trong phạm vi (In scope)

| Kênh / chức năng | Mô tả |
|------------------|-------|
| Kênh Etsy (19 shop) | Kéo đơn tự động, đẩy tracking, đọc tin nhắn khách |
| Đối tác sản xuất Gearment | Đẩy đơn sang Gearment, nhận tracking ngược |
| Nhập tracking GKE | Đọc file Excel từ GKE Logistics |
| Duyệt thiết kế | Tải file lên Google Drive, duyệt 3 trạng thái, in hàng loạt |
| Duyệt đổi địa chỉ | Marketing yêu cầu → BA duyệt → sửa địa chỉ |
| Dashboard nghiệp vụ | Đơn hàng / Tracking / Sản xuất / Tài chính / Kiểm soát giá |
| Lịch sử thao tác | Ai đổi cái gì, khi nào |
| Vai trò người dùng | Phân quyền theo bộ phận |

### 4.2 Ngoài phạm vi (Out of scope — phase sau)

| Mục | Lý do hoãn |
|-----|------------|
| Kênh Amazon đầy đủ | Phase 5; cần ổn định Etsy trước |
| Website tự xây | Phase 5; phụ thuộc Amazon trước |
| Quét barcode kho nguyên liệu | Phase 5 |
| Forecast tồn kho 12 tháng | Phase 3 |
| AI phân tích doanh số | Phase 3+ |

---

## 5. Các vai trò người dùng

| # | Vai trò | Trách nhiệm chính | Phần hệ thống dùng nhiều |
|---|---------|---------------------|---------------------------|
| 1 | **Chủ dự án** | Xem tổng quan, duyệt thay đổi lớn, ký báo cáo | Dashboard tổng hợp, báo cáo doanh thu |
| 2 | **BA (Business Analyst)** | Nhập tracking, duyệt thay đổi, đối chiếu dữ liệu, làm file thiết kế | Dashboard Đơn hàng, Dashboard Tracking, quy trình duyệt |
| 3 | **Marketing (MP)** | Quản 19 shop Etsy, duyệt file thiết kế, gửi preview cho khách, trả lời tin nhắn, đẩy đơn ưu tiên | Dashboard Đơn hàng, Hub tin nhắn khách |
| 4 | **Sản xuất (PD)** | Sản xuất thực tế, cập nhật trạng thái sản xuất, scan đơn khi xong, quản lý kho NVL | Dashboard Sản xuất, công cụ in hàng loạt |
| 5 | **Kiểm soát giá (RD)** | Kiểm tra giá bán và phí ship hàng ngày, phát hiện đơn lệch giá | Dashboard Kiểm soát giá |

---

## 6. Năm phase nghiệp vụ (= 6 nhóm Epic trên Jira)

Hệ thống được chia thành **5 nhóm chức năng kinh doanh** + 1 nhóm hỗ trợ (Báo cáo & quản trị). Trên Jira, mỗi nhóm là một **Epic**, mỗi đầu mục nhỏ là một **Story**.

| Phase | Tên Epic | Bộ phận chủ chốt | Mô tả 1 câu |
|-------|----------|------------------|--------------|
| 1 | **Nhập đơn tự động** | BA, Chủ dự án | Đơn từ Etsy tự chảy vào hệ thống, không phải nhập tay |
| 2 | **Duyệt thiết kế** | BA, Marketing, Sản xuất | File thiết kế upload 1 lần, duyệt rồi in được hàng loạt |
| 3 | **Sản xuất** | Sản xuất, BA | Thấy đơn đang ở công đoạn nào, ai phụ trách, có trễ không |
| 4 | **Vận chuyển & tracking** | BA, Marketing | Đẩy đơn sang đối tác, nhận tracking, cập nhật về Etsy |
| 5 | **Tin nhắn khách hàng** | Marketing, BA | Đọc và trả lời tin nhắn 19 shop ở một chỗ |
| 6 | **Báo cáo & quản trị** | Tất cả | Dashboard cho từng bộ phận, audit log, kiểm soát giá |

---

## 7. Lộ trình tổng thể (% hoàn thành đến 2026-05-21)

| Phase | Tình trạng | Đã làm | Đang làm | Còn lại | Dự kiến đóng phase |
|-------|------------|--------|----------|---------|---------------------|
| 1. Nhập đơn | **85%** | Kết nối Etsy API, làm sạch 17.659 đơn cũ, email dự phòng | Đồng bộ tồn kho | Bật API cho 19 shop sau khi pilot ổn | Tháng 6/2026 |
| 2. Duyệt thiết kế | **95%** | Upload Google Drive, duyệt 3 trạng thái, in hàng loạt | — | Tự lưu trữ file đã in | Tháng 5/2026 |
| 3. Sản xuất | **90%** | Dashboard 17 trạng thái VN, pipeline cấu hình được, Dropship + MTO | — | Tự chuyển trạng thái khi xong workorder | Tháng 6/2026 |
| 4. Vận chuyển & tracking | **80%** | Gearment API, tracking ngược Etsy, import GKE, duyệt đổi địa chỉ | Hotfix nhỏ Gearment | Bulk-send, xử lý hoàn/refund | Tháng 7/2026 |
| 5. Tin nhắn khách hàng | **60%** | Hiển thị buyer message, CRM lead từ tin nhắn | — | Re-submit Etsy scope, kéo đầy đủ tin nhắn | Tháng 7-8/2026 (chờ Etsy duyệt) |
| 6. Báo cáo & quản trị | **70%** | 3 dashboard chính, audit log | — | Việt hoá toàn bộ giao diện, dashboard tài chính, kiểm soát giá | Tháng 6-7/2026 |

> **Ghi chú**: Ngày dự kiến trên là **ước tính kỹ thuật**. Sau khi CDA duyệt BRD này, có thể điều chỉnh thứ tự ưu tiên theo nhu cầu kinh doanh.

**Tổng quan**: Toàn dự án đã coding xong khoảng **73%**. Phần còn lại chủ yếu là **vận hành** (Chủ dự án cần bật shop, đăng ký lại scope với Etsy, lấy API key Gearment) và **đánh bóng giao diện** (Việt hoá, dashboard tài chính).

---

## 8. Tiêu chí thành công (Success Criteria)

Hệ thống được coi là **thành công** khi đạt đủ các tiêu chí sau, trong vòng **8 tuần** kể từ ngày go-live đầy đủ:

| # | Tiêu chí kinh doanh | Cách đo |
|---|----------------------|--------|
| 1 | Google Sheet đơn hàng ngừng dùng, không có ai mở lại | BA + Marketing xác nhận sau 4 tuần liên tiếp |
| 2 | Không bỏ sót đơn nào | Đối chiếu số đơn trên Etsy vs hệ thống trong 10 ngày liên tiếp, sai lệch = 0 |
| 3 | BA giảm ≥70% thời gian nhập đơn tay | Đo trước/sau: từ 2 giờ/ngày xuống ≤30 phút/ngày |
| 4 | Tracking trễ <1% trong 2 tuần | Tracking nhập vào hệ thống nhưng quá 5 phút chưa lên Etsy |
| 5 | Không có vụ gửi nhầm địa chỉ nào trong 3 tháng | Quy trình duyệt đổi địa chỉ hoạt động |
| 6 | Không có file thiết kế nhầm phiên bản nào trong 3 tháng | Lịch sử duyệt hoạt động |
| 7 | RD phát hiện ≥90% đơn lệch giá trong ngày | Dashboard kiểm soát giá hoạt động |
| 8 | Tin nhắn khách được trả lời trong ngày ≥80% | Hub tin nhắn khách hoạt động |

---

## 9. Phụ thuộc bên ngoài và rủi ro chính

### 9.1 Phụ thuộc bắt buộc (CDA cần xử lý)

| # | Phụ thuộc | Trạng thái hôm nay | Tác động nếu chậm |
|---|-----------|---------------------|--------------------|
| 1 | **Etsy app duyệt 4 quyền truy cập** | ✅ Đã duyệt 4/5 (2026-05-12) | Đủ để vận hành; chỉ thiếu quyền đọc tin nhắn Conversations |
| 2 | **Etsy duyệt quyền đọc tin nhắn `conversations_r`** | ⚠️ Chưa submit lại | Chặn Phase 5 — không kéo được tin nhắn Etsy |
| 3 | **Khóa API Gearment (sandbox + production)** | ⏳ Đang chờ | Chặn Phase 4 — không đẩy đơn được tự động |
| 4 | **Tài khoản Google Drive service account** | ✅ Đã có (2026-04-27) | Không chặn |

### 9.2 Rủi ro chính

| # | Rủi ro | Khả năng | Tác động | Hướng xử lý |
|---|--------|----------|----------|-------------|
| 1 | Etsy đổi format email đột ngột, mất đơn | Trung bình | Cao | Đã chuyển sang API, email chỉ là dự phòng |
| 2 | Bộ phận không quen hệ thống mới, quay lại Excel | Cao | Cao | Cần đào tạo 1 buổi/bộ phận trước go-live + 2 tuần "song hành" Excel + Odoo |
| 3 | CDA bật API shop chưa quen, sót đơn | Trung bình | Trung bình | Quy trình bật từng shop (pilot trước, 18 shop sau), có rollback |
| 4 | Gearment không gửi thông báo tự động, đơn không cập nhật trạng thái | Trung bình | Cao | Hệ thống có cơ chế tự động hỏi lại Gearment mỗi 5 phút để dự phòng |
| 5 | Sai dữ liệu khi gộp khách trùng | Trung bình | Cao | Gộp khách chỉ thực hiện sau khi BA tick duyệt Excel — KHÔNG tự gộp |

---

## 10. Phê duyệt

Tài liệu này được duyệt sau khi 5 bên dưới đây ký xác nhận. Mỗi bên có quyền yêu cầu chỉnh sửa trước khi ký.

| STT | Vai trò | Họ tên | Ngày ký | Ghi chú |
|-----|---------|--------|---------|---------|
| 1 | **Chủ dự án** | | | |
| 2 | Trưởng phòng BA | | | |
| 3 | Trưởng phòng Marketing | | | |
| 4 | Trưởng phòng Sản xuất | | | |
| 5 | Trưởng phòng Kiểm soát giá | | | |

**Sau khi ký**:
1. Tài liệu chi tiết yêu cầu (`SRS_VN.md`) được khoá phiên bản
2. Bộ phận BA đồng bộ Epic + Story lên Jira (project ESTY trên `erptek.atlassian.net`)
3. Chủ dự án theo dõi tiến độ hàng ngày qua Jira

---

*Hết BRD v1.0. Bản chi tiết yêu cầu phần mềm xem `SRS_VN.md`. Bảng dashboard nhanh xem `STATUS_VN.md`.*
