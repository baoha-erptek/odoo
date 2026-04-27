# SRS — Hệ thống quản lý đơn hàng Etsy đa kênh (Vietnamese)

**Phiên bản:** v2.2 (đồng bộ với EN v2.2 — tiếp thu các clarification chiều 2026-04-26 + các ADR Stage-2)
**Ngày phát hành:** 2026-04-26
**Chủ dự án:** Chủ dự án Etsy Shop
**Trạng thái:** Bản nháp chờ các phòng ban duyệt
**Phạm vi:** Hệ thống quản lý đơn hàng Etsy tập trung — kéo đơn qua Etsy API (với email parser làm failover vĩnh viễn), quản lý trên 3 dashboard, đẩy sang sản xuất nội bộ hoặc đối tác Gearment, cập nhật tracking ngược về Etsy.
**Nguồn yêu cầu:** Feedback Phòng BA / Marketing / Sản xuất (PD) / Kiểm soát giá (RD/Sales Audit) + đề xuất hệ thống mẫu + bản red-pen của Owner trên `.0temp/E2_Quy_trinh_san_xuat_edit.pdf` + Stage-1 synthesis (2026-04-26).

> **Đây là bản tiếng Việt mirror của `SRS_Multichannel_Hub_EN.md` v2.2.** Bản EN v2.2 hiện là source-of-truth (đã chỉnh trước); bản VN này được mirror sau. File Excel (`SRS_Multichannel_Hub_VN.xlsx`) cần regenerate qua `build_srs.py` sau khi VN markdown này được duyệt.

## Thay đổi so với v2.1

1. **REQ-SYN-00 RESOLVED** (trước là BLOCKER). Câu hỏi "ROI của Etsy API" được đặt lại: lý do KHÔNG phải tỷ lệ lỗi, mà là **template-drift** (Etsy đơn phương kiểm soát cấu trúc HTML email; API mới là contract có version). Xem `clarifications/spec-005-roi-memo.md` v2 + `adrs/ADR-008a-email-as-mandatory-backup.md` v2.
2. **Họ REQ mới REQ-SRC-01..04** — Hợp đồng source-switching cho pipeline ingestion duy nhất. Email parser giờ là **failover vĩnh viễn** đứng sau cùng một pipeline canonical (không dual-write, không reconciliation). Auto-failover khi health-check fail; auto-recovery khi probe success.
3. **Họ REQ mới REQ-PIP-01..09** — Pipeline đơn hàng configurable + resource assignment. 17 sub-state Việt Nam giờ là **default seed pipeline** (admin có thể edit hoặc thêm pipeline mới). Resource assignment per-stage với per-order override. Thay thế cho enum `mrp.production.x_substate` hardcode + `mrp.routing` audit-log model.
4. **REQ-PRO-03 / REQ-PRO-04 / REQ-PRO-09 viết lại** — đều trỏ tới pipeline configurable (REQ-PIP-*). Process Dashboard giờ hiển thị `x_pipeline_state_id` của order; định nghĩa stage quản lý qua REQ-PIP-* (§10.5).
5. **REQ-MSG-01 viết lại** — giờ ingest field `buyer_message` qua scope `transactions_r` (đã có sẵn). Hiển thị inline trên form đơn hàng + trên view top-level "Customer Message Hub". Quyền đọc: MP+BA+Owner. **Không** ingest content của Etsy Conversations (scope bị reject). Resolve mâu thuẫn H8 với pain #17 trong E2.
6. **REQ-FIL-04 mở rộng** — trỏ tới ADR-012. Discord là escape hatch thủ công vĩnh viễn (không sunset). GDrive dùng service account; failure → alert + queue + backoff (KHÔNG auto-failover xuống Discord).
7. **REQ-FIL-05 / REQ-FIL-06 mới** — backed by ADR-009 (file lifecycle data model: `design.file`, `design.file.route`, `design.print.batch`).
8. **§11 Module map mới** — confirm 4-module split của ADR-001 (D-20) và liệt kê quyền sở hữu module cho mỗi họ REQ-*.

---

## Mục lục
1. [Tổng quan & Lộ trình](#1-tổng-quan--lộ-trình-3-giai-đoạn)
2. [Vai trò người dùng](#2-vai-trò-người-dùng)
3. [Đồng bộ đơn Etsy (single pipeline + source switching)](#3-đồng-bộ-đơn-etsy-single-pipeline--source-switching)
4. [Chuẩn hóa dữ liệu cũ](#4-chuẩn-hóa-17659-đơn-cũ)
5. [Dashboard Đơn hàng](#5-dashboard-đơn-hàng-ba--marketing)
6. [Dashboard Tracking](#6-dashboard-tracking-ba)
7. [Dashboard Sản xuất](#7-dashboard-sản-xuất-pd--ba)
8. [Quy trình duyệt](#8-quy-trình-duyệt-file-thiết-kế--địa-chỉ--ticket)
9. [Tracking & Fulfillment](#9-nhập-tracking--đẩy-đơn-sản-xuất)
10. [File lifecycle, auto-transition & customer-message hub](#10-file-lifecycle-auto-transition--customer-message-hub)
10.5. [Pipeline đơn hàng configurable](#105-pipeline-đơn-hàng-configurable-new-v22)
11. [Module map (theo ADR-001)](#11-module-map-theo-adr-001)
12. [Tính năng mở rộng (Phase 2-3)](#12-tính-năng-mở-rộng-phase-2-3)
13. [Phê duyệt & chữ ký](#13-phê-duyệt--chữ-ký)

---

## 1. Tổng quan & Lộ trình 3 giai đoạn

### Hệ thống này làm gì?
1. Tự động kéo đơn mới từ Etsy qua API (chính), với email parser làm **failover vĩnh viễn** đứng sau cùng pipeline canonical.
2. Hiển thị đơn trên 3 dashboard chuyên biệt cho BA, Marketing, Sản xuất.
3. Cho đội thiết kế (BA) upload file in và đội PD duyệt qua MP.
4. Đẩy đơn đã duyệt sang xưởng nội bộ hoặc đối tác Gearment, rồi cập nhật tracking ngược về Etsy.
5. File thiết kế upload **một lần**; route quyền đọc cho MP/BA/PD/Partner; PD bulk-download dàn A4 in.
6. Customer Message Hub gom `buyer_message` từ 19 shop (qua scope `transactions_r`; không động Conversations content).
7. **(NEW v2.2)** Workflow đơn hàng chạy trên **pipeline configurable** per-product/category — team định nghĩa stage, transition, resource assignment qua admin UI thay vì code.

### Quyết định chiến lược (đã ký trong `decision-log.md`)
- Etsy API là nguồn chính; email parser là failover vĩnh viễn (D-13 RESOLVED — xem ADR-008a v2).
- Chạy trên Odoo 19 CE (không mua Enterprise).
- Tiếng Việt là ngôn ngữ giao diện mặc định.
- Gearment là đối tác fulfillment chính trong Phase 2.
- 4-module split theo ADR-001 (D-20 — chờ Owner xác nhận một dòng; default assumption: in force).
- Pipeline đơn hàng configurable theo user (D-11 + D-12 + D-16 RESOLVED — xem ADR-010).

### Lộ trình 3 giai đoạn

| Giai đoạn | Nội dung & điều kiện nghiệm thu |
|---|---|
| **Giai đoạn 1 — MVP (~3-4 tháng)** | Đồng bộ Etsy API (với email failover) • Source-switching health-check + auto-recovery • Chuẩn hóa 17.659 đơn cũ • 3 dashboard: Đơn hàng, Tracking, Sản xuất • Pipeline đơn hàng configurable (default seed = 17 stage Việt Nam) • File lifecycle (1 upload nhiều route) • Duyệt đổi địa chỉ • Nhập tracking từ Excel GKE. **NGHIỆM THU:** BA Lead ký đối chiếu; Odoo thay Sheet 1 tháng, drift <1%; default seed pipeline hoạt động với ≥80% đơn đến terminal stage. |
| **Giai đoạn 2 — Mở rộng (~3-4 tháng)** | Đẩy đơn sang Gearment qua API và nhận tracking • Hệ thống ticket replace/refund (BA duyệt) • Dashboard Pricing Audit với quy đổi EUR + daily check • Customer Message Hub (`buyer_message` ingestion). **NGHIỆM THU:** đơn Gearment chạy live không lỗi 2 tuần liên tiếp; RD nghiệm thu Pricing Audit. |
| **Giai đoạn 3 — Tương lai (~4-6 tháng)** | Quản lý tồn kho NVL + dự báo 1/3/12 tháng • Catalog Dashboard cho từng SP • Scan sheet barcode cho PD • Mở Amazon và Website • Tích hợp AI analytics / BI tool. **NGHIỆM THU:** quyết định chi tiết khi kết thúc Giai đoạn 2. |

---

## 2. Vai trò người dùng

(v2.1 — đã sửa theo bản red-pen của Owner; không đổi trong v2.2)

| STT | Phòng ban / Vai trò | Công việc chính | Màn hình họ dùng nhiều nhất |
|---|---|---|---|
| 1 | **Chủ dự án** | Quyết định chiến lược, ký duyệt từng giai đoạn, theo dõi tiến độ và kết quả tổng. | Bản tóm tắt KPI hằng tuần; tất cả dashboard (đọc). |
| 2 | **Phòng BA** | **Làm file thiết kế** và đẩy nội bộ cho MP duyệt; điều phối đơn (US-od / VN-od); cung cấp tracking; duyệt đổi địa chỉ; duyệt ticket replace/refund. | Dashboard Đơn hàng, Dashboard Tracking, Duyệt đổi địa chỉ, Ticket, **Customer Message Hub** (đọc). |
| 3 | **Phòng Marketing (MP)** | Quản lý 19 store Etsy, push đơn ưu tiên, **duyệt file thiết kế do BA làm**, gửi file preview cho khách, xử lý tin nhắn khách, gửi yêu cầu đổi địa chỉ, set US-od / Vietnam-od. | Dashboard Đơn hàng, form chi tiết đơn, popup, **Customer Message Hub** (đọc + search). |
| 4 | **Phòng Sản xuất (PD)** | Sản xuất thực tế; **duy trì pipeline state** qua các stage (configurable per ADR-010); scan parcel khi xong; quản tồn kho NVL. | Dashboard Sản xuất, Scan sheet, tồn kho NVL, Bulk-print wizard. |
| 5 | **Phòng Kiểm soát giá (RD / Sales Audit)** | **Kiểm tra giá bán + giá ship hàng ngày**; phát hiện đơn lệch giá; báo cáo đa tiền tệ; báo Discord để MP sửa trong ngày. | Dashboard Pricing Audit. |
| 6 | **Kho** | Xuất nguyên liệu khi PD yêu cầu. Sau Odoo: NVL được trừ tự động khi pipeline đến stage được cấu hình. | Inventory; Forecast 30/90/365 ngày. |

---

## 3. Đồng bộ đơn Etsy (single pipeline + source switching)

| Mã YC | Tên yêu cầu | Mô tả | Ai đề xuất | Ưu tiên | Giai đoạn |
|---|---|---|---|---|---|
| **REQ-SYN-00** *(rev v2.2)* | **Etsy API + email failover (đã chốt)** | RESOLVED. Owner direction (2026-04-26): API chính; email là failover **vĩnh viễn** sau cùng pipeline canonical (không dual-write, không reconciliation). Lý do: template-drift (Etsy đơn phương kiểm soát format email); API có version contract. Xem `decision-log.md` D-13 + ADR-008a v2. | Owner | n/a | locked |
| REQ-SYN-01 | Kết nối tài khoản Etsy an toàn | Owner vào Settings → 'Connect Etsy' → đăng nhập một lần. Hệ thống nhớ kết nối và tự gia hạn; cảnh báo trước 7 ngày khi cần re-auth. | Chủ dự án | P0 | GĐ 1 |
| REQ-SYN-02 | Tự kéo đơn mới mỗi 5 phút | Hệ thống kéo đơn mới hoặc đơn bị sửa từ Etsy mỗi 5 phút qua *active source* (REQ-SRC-02). Không tạo trùng. | BA, MP | P0 | GĐ 1 |
| REQ-SYN-03 | Không ghi đè dữ liệu nghiệp vụ nhập | Khi upstream báo cập nhật đơn đã có, hệ thống chỉ cập nhật trạng thái thanh toán/vận chuyển từ upstream; giữ nguyên note MP, người phụ trách, trạng thái duyệt thiết kế. | BA | P0 | GĐ 1 |
| REQ-SYN-04 | Đẩy tracking về Etsy tự động | Khi BA nhập tracking + carrier, hệ thống gửi về Etsy trong 5 phút. | BA, MP | P0 | GĐ 1 |
| REQ-SYN-05 | Toggle auto-push tracking per-store | Marketing có công tắc 'Auto-push tracking về Etsy' theo từng store. | MP | P1 | GĐ 1 |
| REQ-SYN-06 | Xuất lịch sử tin nhắn Etsy | Marketing chọn khoảng thời gian → 'Xuất tin nhắn' → tải Excel toàn bộ tin nhắn (lấy từ `etsy.buyer.message` theo REQ-MSG-01). | MP (#6) | P1 | GĐ 2 |
| **REQ-SRC-01** *(NEW v2.2)* | **Hợp đồng canonical payload** | Cả `EtsyApiAdapter` và `EtsyEmailAdapter` tạo cùng một canonical record (`etsy.order.payload`). Field source-specific cho phép null; UI downstream hiển thị "—" khi missing. Code downstream là source-agnostic. | Owner direction | P0 | GĐ 1 |
| **REQ-SRC-02** *(NEW v2.2)* | **Field `etsy.shop.active_source`** | Field mới với giá trị `api` / `email`. Default sau khi scope được duyệt: `api`. Default trước khi scope: `email`. Admin có quyền manual override. Thay thế enum `sync_mode` của ADR-002. | Owner direction | P0 | GĐ 1 |
| **REQ-SRC-03** *(NEW v2.2)* | **Cron health-check + auto-failover** | Mỗi 5 phút, probe nguồn đang active. Sau 3 lần fail liên tiếp → tự switch sang nguồn còn lại; raise alert HIGH; ghi vào `etsy.shop.source.change.log`. Configurable per-shop. | Owner direction | P0 | GĐ 1 |
| **REQ-SRC-04** *(NEW v2.2)* | **Cron recovery-probe + auto-switch-back** | Khi đang ở failover, probe nguồn primary ban đầu mỗi giờ. Sau 6 lần thành công liên tiếp → tự switch về, trừ khi `etsy.shop.auto_recovery=False` (sticky manual override). | Owner direction | P0 | GĐ 1 |

---

## 4. Chuẩn hóa 17.659 đơn cũ

(không đổi trong v2.2; đơn historical default `state='done'` với `x_pipeline_id=NULL` theo ADR-010 §10)

| Mã YC | Tên yêu cầu | Mô tả | Ai đề xuất | Ưu tiên | Giai đoạn |
|---|---|---|---|---|---|
| REQ-MIG-01 | Upload 17.659 đơn cũ từ Excel | Admin upload Excel lịch sử, hệ thống đọc và tạo các đơn. Resumable nếu gián đoạn. | Chủ dự án | P0 | GĐ 1 |
| REQ-MIG-02 | Sửa 423 đơn giá $0 | 423 đơn ghi $0. Hệ thống tính lại từ source; đơn không khôi phục được → list cho BA xử lý tay. | RD | P0 | GĐ 1 |
| REQ-MIG-03 | Nhận diện tiền tệ USD / EUR / GBP / CAD / VND | Đọc ký hiệu ($, €, £, C$, ₫) và gán đúng tiền tệ. Đơn vẫn giữ tiền gốc. | RD | P0 | GĐ 1 |
| REQ-MIG-04 | Tách phí ship thành dòng riêng | Mỗi đơn có dòng 'Etsy shipping fee' riêng để tổng đơn khớp source trong sai số $0.01. | RD | P0 | GĐ 1 |
| REQ-MIG-05 | Gộp khách trùng có BA duyệt | Hệ thống đề xuất danh sách trùng → xuất Excel → BA tick → upload lại để gộp. **Không tự gộp.** | BA | P0 | GĐ 1 |
| REQ-MIG-06 | Báo cáo đối chiếu & ký nhận | Sau khi chạy chuẩn hóa, xuất báo cáo (tổng đơn, doanh thu, phí ship, đơn lỗi). BA Lead ký trước khi sang giai đoạn tiếp. | Chủ dự án, BA | P0 | GĐ 1 |
| **REQ-MIG-07** *(NEW v2.2)* | **Placeholder pipeline cho đơn historical** | Theo ADR-010 §10: đơn cũ default `state='done'`, `x_pipeline_id=NULL`, `x_pipeline_state_id=NULL`. Bulk-assign sang pipeline "Historical / archived" (single terminal stage) là tùy chọn admin. | Owner direction | P0 | GĐ 1 |

---

## 5. Dashboard Đơn hàng (BA + Marketing)

(không đổi trong v2.2 ngoại trừ REQ-ORD-16 mới)

| Mã YC | Tên yêu cầu | Mô tả | Ai đề xuất | Ưu tiên | Giai đoạn |
|---|---|---|---|---|---|
| REQ-ORD-01 | Hiển thị 10 cột cốt lõi | Shop, Order ID, Tracking, IMG, Date, Tình trạng, Quantity, Shipping Service, Country, Giá tổng. | BA (#1) | P0 | GĐ 1 |
| REQ-ORD-02 | Shop và Order ID ở 2 cột đầu | Search hoạt động trên cả hai. | BA (#1) | P1 | GĐ 1 |
| REQ-ORD-03 | Bỏ cột Ship-out, retail price, PIC | Ship-out tự set khi PD scan; retail gộp vào Total; PIC suy ra từ shop. | BA (#1) | P1 | GĐ 1 |
| REQ-ORD-04 | Gộp Tracking + Label state + Carrier thành 1 cột | Hiển thị: 'Awaiting label' / 'Buying label' / `<carrier>: <number>`. | BA (#1), Đề xuất hệ thống mẫu | P0 | GĐ 1 |
| REQ-ORD-05 | Ảnh sản phẩm trên mỗi đơn | Thumbnail 128px, click xem ảnh lớn. | MP (#2, #10) | P0 | GĐ 1 |
| REQ-ORD-06 | Inline-edit cột thao tác | BA chỉnh inline: Tracking, Carrier, Label state, Order status, Note. | BA, MP | P1 | GĐ 1 |
| REQ-ORD-07 | Tô màu hàng theo loại đơn | qty ≥ 2 → cam; trùng mã → tím; Push → đỏ; Amazon → đỏ. | PD | P1 | GĐ 1 |
| REQ-ORD-08 | Nút Push đánh dấu đơn ưu tiên | MP bấm Push → đơn được đánh dấu + tô đỏ; lịch sử log ai/khi nào. Đơn Amazon đặt cùng ngày Etsy auto-PUSH. | MP (#4) | P1 | GĐ 1 |
| REQ-ORD-09 | Badge quá hạn duyệt (>2 ngày) | Đơn quá 2 ngày chưa duyệt file → cảnh báo + tô vàng. | MP (#7) | P2 | GĐ 1 |
| REQ-ORD-10 | Cột hạn ship (Ship-by deadline) | Hiện 'Tracking deadline' từ Etsy. Quá hạn → đỏ. | MP (#3) | P1 | GĐ 1 |
| REQ-ORD-11 | Avatar người quản lý store | Avatar/icon của người quản lý store trên mỗi đơn. | MP (#8) | P2 | GĐ 1 |
| REQ-ORD-12 | Popup thông báo sự kiện đặc biệt | Push, hold, đổi địa chỉ → popup tới đúng người trong 10 giây. | MP (#9) | P2 | GĐ 1 |
| REQ-ORD-13 | Field 'MP Note' trên đơn | Tách riêng với 'Sale note'; MP ghi yêu cầu custom của khách. | BA (#6) | P1 | GĐ 1 |
| REQ-ORD-14 | Lịch sử thay đổi trạng thái đơn | History tab: ai đổi, khi nào, từ giá trị gì sang giá trị gì. (Backed by `order.pipeline.transition.log` theo ADR-010.) | BA (#4), MP (#5) | P1 | GĐ 1 |
| REQ-ORD-15 | Tên SP + BA phân loại thủ công | BA có thể override phân loại tự động. | BA (#9) | P2 | GĐ 1 |
| **REQ-ORD-16** *(NEW v2.2)* | **Badge trạng thái design file** | Theo ADR-009: mỗi hàng hiện badge pending/approved/needs-revision cho design file của đơn. Click → mở form `design.file`. | BA, MP | P1 | GĐ 1 |

---

## 6. Dashboard Tracking (BA)

(không đổi trong v2.2)

| Mã YC | Tên yêu cầu | Mô tả | Ai đề xuất | Ưu tiên | Giai đoạn |
|---|---|---|---|---|---|
| REQ-TRK-01 | Trang Tracking riêng | Menu 'Tracking' mở trang riêng (không phải filter của Order Dashboard). | BA (#2) | P0 | GĐ 1 |
| REQ-TRK-02 | 13 cột tracking | Order ID, Tracking, Carrier, Tình trạng, Loại SP, Quantity, Tên, Địa chỉ 1-2, Thành phố, Bang, Zip, Quốc gia. | BA, Đề xuất hệ thống mẫu | P0 | GĐ 1 |
| REQ-TRK-03 | Export Excel | Tải Excel theo bộ lọc hiện tại. | BA (#2) | P1 | GĐ 1 |
| REQ-TRK-04 | Bulk chuyển label state | Chọn nhiều đơn → 'Awaiting label' → 'Buying label' trong 1 thao tác. | BA (#2) | P1 | GĐ 1 |
| REQ-TRK-05 | Search tracking / Order ID / tên khách | Ô search nhanh đầu trang. | BA (#2) | P1 | GĐ 1 |
| REQ-TRK-06 | Đồng bộ về Order Dashboard | Cập nhật phản ánh trong 5 giây. | BA (#2) | P0 | GĐ 1 |
| REQ-TRK-07 | Khóa mua label khi đang đổi địa chỉ | Vô hiệu Buy Label + cảnh báo. | BA (#5 — an toàn) | P0 | GĐ 1 |
| REQ-TRK-08 *(rev v2.2)* | Hiển thị state tracking (in-transit, delivered, returned) | Carrier webhook (USPS/UniUni/YunExpress nơi có) → ghi vào `stock.picking.x_tracking_state`; live update qua `bus.bus`. Pain #16. | MP | P1 | GĐ 2 |

---

## 7. Dashboard Sản xuất (PD + BA)

| Mã YC | Tên yêu cầu | Mô tả | Ai đề xuất | Ưu tiên | Giai đoạn |
|---|---|---|---|---|---|
| REQ-PRO-01 | Đặt tên 'Process Dashboard' | BA và PD cùng thao tác; cả đơn VN và US. | BA (#10) | P1 | GĐ 1 |
| REQ-PRO-02 | Cột sản xuất theo đề xuất PD | Ngày duyệt file, Download file, Tình trạng, Note, Ảnh, Gift message, Personalisation, Loại SP, Option, Quantity, Mã đơn, Shop, Tên KH, Địa chỉ, Shipping service, Ngày đặt, Ngày đi, Scan, Thống kê tự động. | PD | P0 | GĐ 1 |
| **REQ-PRO-03** *(rev v2.2)* | **Cột pipeline-state (configurable)** | Dashboard hiển thị `x_pipeline_state_id` hiện tại của đơn cùng màu của stage. Định nghĩa stage quản lý qua REQ-PIP-* (xem §10.5). Default seed pipeline ship sẵn 17 stage Việt Nam từ E2 §6 (CHỜ FILE → … → VN-Fulfilled), nhưng admin có thể edit, thêm, xóa, hoặc thay thế. **Ý nghĩa stage ("VN-Packed 1 nghĩa là gì?", "[Fix]VN-Dish trigger khi nào?") là user-config tại runtime, không hardcode** — xem ADR-010 §9. | PD, Owner red-pen | P0 | GĐ 1 |
| **REQ-PRO-04** *(rev v2.2)* | **Resource assignment per-stage** | Mỗi pipeline stage mang `responsible_team_id` mặc định (tùy chọn — model `pipeline.team`). Dashboard group hoặc filter theo team. Admin/PD-lead có quyền per-order override. Xem ADR-010 §6. | PD, Owner red-pen | P0 | GĐ 1 |
| REQ-PRO-05 | Hiển thị ảnh thiết kế và preview | 2 thumbnail mỗi hàng: file thiết kế gốc + preview. | MP (#2) | P1 | GĐ 1 |
| REQ-PRO-06 | Widget thống kê | Đếm theo: pipeline state, option, loại SP, quantity. | PD | P2 | GĐ 1 |
| REQ-PRO-07 | Scan → Fulfilled | Scan barcode → đẩy pipeline state đến terminal stage được mark "fulfilled" trong pipeline definition; ngày ship tự set, log ai/khi nào. | PD, BA (#1) | P1 | GĐ 1 |
| REQ-PRO-08 | (deprecated v2.2 — gộp vào REQ-PIP-*) | Trước: "4 trạng thái sản xuất nội bộ." Giờ: pipeline nào cũng có thể khai báo qua stage definition. Không còn enum riêng. | — | n/a | n/a |
| **REQ-PRO-09** *(rev v2.2)* | **Audit log + governance cho pipeline changes** | Mọi edit cấu trúc pipeline, đổi tên stage, reassign resource, và transition per-order đều log vào `order.pipeline.transition.log` (single audit table; enum `change_type`). Pipeline auto-version trên first-use edit (xem ADR-010 §5); order in-flight snapshot version tại thời điểm confirm. Reassign resource của stage không ảnh hưởng order đã ở stage đó (snapshot on entry theo ADR-010 §6). | Devil's advocate N3 | P0 | GĐ 1 |

---

## 8. Quy trình duyệt (file thiết kế / địa chỉ / ticket)

(không đổi trong v2.2; cơ chế duyệt design-file giờ backed by ADR-009)

| Mã YC | Tên yêu cầu | Mô tả | Ai đề xuất | Ưu tiên | Giai đoạn |
|---|---|---|---|---|---|
| REQ-DUY-01 | Upload file in cỡ lớn, xóa và up lại | Designer upload file lớn (vd 150MB lên GDrive); xóa và up lại; bản cũ vẫn lưu để truy vết (theo ADR-009 §1: chuỗi `parent_file_id`). | BA (#8) | P0 | GĐ 1 |
| REQ-DUY-02 | Quy trình duyệt design file | Awaiting → Approved / Needs revision (phải nhập lý do). Ghi ai duyệt khi nào. (Theo ADR-009 §2 lifecycle.) | PD | P0 | GĐ 1 |
| REQ-DUY-03 | Hàng đợi thiết kế dạng kanban | 3 cột; kéo-thả hoặc click chuyển. (Backed by `design.file.state` theo ADR-009.) | Designer, BA | P1 | GĐ 1 |
| REQ-DUY-04 | Duyệt đổi địa chỉ | MP không sửa địa chỉ trực tiếp. Tạo yêu cầu → BA duyệt/từ chối → mới sửa được. | BA (#5 — an toàn) | P0 | GĐ 1 |
| REQ-DUY-05 | Khóa Buy Label khi đang pending đổi địa chỉ | Vô hiệu thao tác Buy Label; badge cảnh báo trên Tracking. | BA (#5 — an toàn) | P0 | GĐ 1 |
| REQ-DUY-06 | Tạo ticket replace/refund từ chi tiết đơn | Form đơn có nút 'Tạo ticket'; MP nhập lý do + ảnh; chọn replace/refund/discount; gửi BA duyệt. | BA (#3) | P1 | GĐ 2 |
| REQ-DUY-07 | BA duyệt ticket → tự xử lý | Refund → credit note; Replace → đơn mới link đơn gốc; Discount → ghi giảm giá. | BA (#3) | P1 | GĐ 2 |
| REQ-DUY-08 | Lịch sử ticket trong đơn | Tab Lịch sử hiển thị toàn bộ thao tác ticket. | BA (#4) | P2 | GĐ 2 |

---

## 9. Nhập tracking & đẩy đơn sản xuất

(không đổi trong v2.2 ngoại trừ REQ-TRF-09 nhắc orphan policy)

| Mã YC | Tên yêu cầu | Mô tả | Ai đề xuất | Ưu tiên | Giai đoạn |
|---|---|---|---|---|---|
| REQ-TRF-01 | Nhập tracking từ Excel GKE | Upload Excel chuẩn GKE; khớp Order ID → tự điền tracking + carrier. Hàng không khớp → log cho BA xử lý tay. | BA (#2), Logistics | P0 | GĐ 1 |
| REQ-TRF-02 | Auto-detect carrier từ tracking | 20-22 chữ số → USPS; 'UU' → UniUni; 'YT' → YunExpress; khác → 'Other'. | Logistics | P0 | GĐ 1 |
| REQ-TRF-03 | Xử lý đơn '-replace' + lưu URL label/QR | Đơn có hậu tố '-replace' link đơn gốc. URL label + QR lưu trên đơn. | BA, Logistics | P1 | GĐ 1 |
| REQ-TRF-04 | Báo cáo import (matched / unmatched) | Wizard tóm tắt; click xem chi tiết từng dòng lỗi. | BA | P1 | GĐ 1 |
| REQ-TRF-05 | Kết nối Gearment + đẩy đơn | Cấu hình Gearment 1 lần. BA bấm 'Push to Gearment' để gửi đơn + design file (theo ADR-009 routing policy). | Chủ dự án, BA | P0 | GĐ 2 |
| REQ-TRF-06 | Quy trình 4 bước Gearment | Draft → quote → BA/operator duyệt → confirm. | BA | P0 | GĐ 2 |
| REQ-TRF-07 | Nhận tracking và state Gearment | Webhook hoặc cron pull → cập nhật đơn → đẩy lên Etsy (nếu MP bật auto-push). | BA, MP | P0 | GĐ 2 |
| REQ-TRF-08 | Xử lý lỗi và retry | Retry tối đa 3 lần; fail → log + cảnh báo admin. | Chủ dự án | P1 | GĐ 2 |
| REQ-TRF-09 | Chính sách orphan Gearment khi rework | Khi MP trigger rework supersede draft Gearment (vd stage "[Fix]" của seed pipeline), draft/quote Gearment cũ phải được cancel hoặc auto-expire. Policy cần confirm với Gearment support (D-21 OPEN). | Devil's advocate N5 | P0 | GĐ 2 |

---

## 10. File lifecycle, auto-transition & customer-message hub

(họ NEW v2.1; mở rộng v2.2 — REQ-FIL-* giờ backed by ADR-009; REQ-MSG-01 viết lại)

| Mã YC | Tên yêu cầu | Mô tả | Ai đề xuất | Ưu tiên | Giai đoạn |
|---|---|---|---|---|---|
| **REQ-FIL-01** *(rev v2.2)* | **Model `design.file` — 1 upload, route nhiều nơi** | BA upload 1 lần; hệ thống tạo record `design.file` với GDrive primary URL + checksum + version. Theo ADR-009 §1. | MP, BA, PD (#11, #18) | P0 | GĐ 1 |
| **REQ-FIL-02** *(rev v2.2)* | **`design.file.route` — delivery state per recipient** | Mỗi `design.file` link tới N route: `recipient_type` (MP/BA/PD/partner), `state` (pending/sent/acknowledged/failed), `delivery_method`, audit timestamp. Theo ADR-009 §1+§4. | BA (#11) | P0 | GĐ 1 |
| **REQ-FIL-03** *(rev v2.2)* | **`design.print.batch` — wizard bulk-download A4** | PD tick file đã duyệt → wizard render PDF A4 → cache 24h. Theo ADR-009 §1. | PD (#12) | P1 | GĐ 1 |
| **REQ-FIL-04** *(rev v2.2)* | **GDrive failover + Discord là escape hatch vĩnh viễn** | Theo ADR-012: service account, alert + queue + backoff khi auth fail, **KHÔNG auto-fallback xuống Discord**. Discord giữ làm escape hatch **thủ công** vĩnh viễn (không sunset). | Devil's advocate N4 | P1 | GĐ 1 |
| **REQ-FIL-05** *(NEW v2.2)* | **Re-upload tạo row `design.file` mới (immutable history)** | Theo ADR-009 §2: file bị reject ở `state='needs_revision'`; upload mới tạo row mới với `parent_file_id` set + `version+1`. Cho phép tính KPI tỷ lệ duyệt lần đầu. | BA, PD | P1 | GĐ 1 |
| **REQ-FIL-06** *(NEW v2.2)* | **Route delivery qua queued job với badge cảnh báo route stuck** | Theo ADR-009 §4: route delivery action (cấp permission GDrive, push API Gearment, v.v.) chạy như queued job. Route pending/failed >2h nổi badge cảnh báo trên hàng Process Dashboard của đơn. | PD, BA | P1 | GĐ 1 |
| **REQ-AUT-01** *(rev v2.2)* | **Trigger auto-transition (Phase 2 layer)** | Theo ADR-010 §8: Phase 1 ship `auto_advance_trigger='none'` thôi. Phase 2+ thêm trigger built-in (`on_payment`, `on_design_approved`, `on_tracking_imported`) qua UI cấu hình pipeline-stage. | MP, BA, PD (#13) | P2 | GĐ 2 |
| **REQ-AUT-02** *(rev v2.2)* | **Route file design trên `sale.order.action_confirm()`** | Khi BA confirm đơn có `design.file` đã duyệt, pipeline routing policy của đơn tạo record `design.file.route` theo ADR-009 §4. State=pending → queued job chạy → state=sent hoặc failed. | BA | P1 | GĐ 1 |
| **REQ-MSG-01** *(rev v2.2)* | **Customer Message Hub — ingest `buyer_message`** | Cron pull field `buyer_message` qua `GET /v3/application/shops/:shop_id/receipts` (đã có trong scope `transactions_r`). Lưu vào model mới `etsy.buyer.message` (1 row mỗi receipt có buyer message non-empty). Hiển thị (a) tab trên form đơn và (b) view top-level "Customer Message Hub" (search + filter cross-shop). Quyền đọc: MP + BA + Owner. **Không ingest content của Etsy Conversations** (scope đã reject). | MP (#17) | P1 | GĐ 2 |

---

## 10.5. Pipeline đơn hàng configurable (NEW v2.2)

(Backed by ADR-010. Resolve D-11, D-12, D-16. Thay thế cho enum `mrp.production.x_substate` hardcode.)

| Mã YC | Tên yêu cầu | Mô tả | Ai đề xuất | Ưu tiên | Giai đoạn |
|---|---|---|---|---|---|
| **REQ-PIP-01** | **Model `order.pipeline`** | Định nghĩa pipeline có tên, có version. Theo ADR-010 §1. | Owner direction | P0 | GĐ 1 |
| **REQ-PIP-02** | **Model `order.pipeline.state`** | Stage trong pipeline: name, sequence, is_initial, is_terminal, color, optional `next_stage_ids` (DAG), optional `responsible_team_id`. Theo ADR-010 §1. | Owner direction | P0 | GĐ 1 |
| **REQ-PIP-03** | **Model `pipeline.team` + team assignment** | Model team custom nhẹ (decoupled khỏi MRP và CRM). Theo ADR-010 §6. | Owner direction | P0 | GĐ 1 |
| **REQ-PIP-04** | **`order.pipeline.transition.log` — single audit table** | Mọi edit cấu trúc pipeline, đổi tên stage, reassign resource, transition của order đều log ở đây (enum `change_type`). Theo ADR-010 §1. | Devil's advocate N3 | P0 | GĐ 1 |
| **REQ-PIP-05** | **Pipeline assignment scope: per-product với category default** | `product.template.x_default_pipeline_id`, fallback `product.category.x_default_pipeline_id`, fallback system parameter. Theo ADR-010 §2. | Owner direction (Q1=C) | P0 | GĐ 1 |
| **REQ-PIP-06** | **Mixed-pipeline order: manual với default** | Khi line item thuộc các pipeline khác nhau, default theo pipeline của line đầu tiên; UI flag để BA confirm. Theo ADR-010 §3 (Q2=D). | Owner direction | P1 | GĐ 1 |
| **REQ-PIP-07** | **Pipeline auto-version trên first-use edit** | Edit pipeline đang có order in-flight → tạo row `order.pipeline` mới với `parent_pipeline_id` set + `version+1`. Order cũ tiếp tục dùng version cũ. Theo ADR-010 §5 (Q5=A). | Owner direction | P0 | GĐ 1 |
| **REQ-PIP-08** | **Transition policy per pipeline** | Field `transition_policy` per-pipeline với giá trị `dag_strict` / `dag_with_admin_override` (default) / `free_form`. Backward jump và rework loop là `next_stage_ids` cycle khai báo rõ ràng. Theo ADR-010 §7 (Q7=C). | Owner direction | P0 | GĐ 1 |
| **REQ-PIP-09** | **Default seed pipeline** | `data/order_pipeline_seed.xml` ship: (a) "Vietnam Internal Production" (17 stage từ E2 §6), (b) "Gearment POD" (4-stage), (c) "Multi-Technique Hybrid" (template). Theo ADR-010 §9 (Q9=A). | Owner direction | P0 | GĐ 1 |

---

## 11. Module map (theo ADR-001)

(NEW v2.2 — confirm 4-module split của ADR-001; D-20 chờ Owner xác nhận một dòng; default assumption: in force)

| Module | Sở hữu các REQ | Phụ thuộc |
|---|---|---|
| **`multichannel_hub_core`** | REQ-PIP-01..09 (pipeline configurable + team + audit log), REQ-FIL-01..06 (file lifecycle), REQ-DUY-01..08 (approval flow), REQ-PRO-01..09 (cơ chế Process Dashboard chia sẻ giữa các kênh), REQ-ORD-01..16 (cơ chế Order Dashboard chia sẻ giữa các kênh), REQ-TRK-01..08 (Tracking Dashboard) | `sale_management`, `stock`, `mail`, `contacts` |
| **`etsy_channel_api`** | REQ-SYN-01..06 (Etsy account / API sync / push-back), REQ-SRC-01..04 (canonical payload + active-source field + health-check + recovery probe), REQ-MSG-01 (`buyer_message` ingestion qua API), REQ-MIG-01..07 (công cụ chuẩn hóa legacy có pull từ API để verify) | `multichannel_hub_core` |
| **`etsy_channel_email`** *(rename từ `etsy_channel_legacy` theo ADR-008a)* | Email parser (tiếp tục hoạt động làm failover sau REQ-SRC-02..04), Gmail cron, metric parser-template-drift | `multichannel_hub_core` |
| **`gearment_partner`** | REQ-TRF-05..09 (Gearment integration — push đơn, nhận tracking, error handling, orphan policy) | `multichannel_hub_core` |

4 module install độc lập. `multichannel_hub_core` cung cấp abstraction; các module channel/partner triển khai adapter upstream/downstream.

---

## 12. Tính năng mở rộng (Phase 2-3)

(trước là §11 trong v2.1; renumber thành §12 trong v2.2)

| Mã YC | Tên yêu cầu | Mô tả | Ai đề xuất | Ưu tiên | Giai đoạn |
|---|---|---|---|---|---|
| REQ-EXT-01 | Pricing Audit Dashboard | 25 cột; A-F nhập tay, G-T tự lấy từ đơn. Đa tiền tệ. | RD | P1 | GĐ 2 |
| REQ-EXT-02 | Quy đổi giá về EUR | Tự quy đổi USD/VND/CAD theo tỷ giá ngày đặt. Hiển thị 'Giá tổng (EUR)'. | RD | P1 | GĐ 2 |
| REQ-EXT-03 | Tô màu chênh lệch giá vs catalog | Đỏ (thấp) / vàng (bằng) / tím (cao). | RD | P1 | GĐ 2 |
| REQ-EXT-03b | Daily auto-flag đơn lệch giá | Cron mỗi sáng list đơn vượt threshold; ping RD + tô màu dashboard. | RD, devil's advocate N7 | P1 | GĐ 2 |
| REQ-EXT-04 | Upload tồn kho NVL từ Excel | PD upload Excel → hệ thống tạo tồn kho đầu kỳ. | PD | P1 | GĐ 3 |
| REQ-EXT-05 | Auto-trừ NVL khi pipeline đến terminal | Khi `x_pipeline_state_id` của đơn đến stage được mark `is_terminal_for_inventory`, trừ theo BoM. | PD | P1 | GĐ 3 |
| REQ-EXT-06 | Forecast 1 / 3 / 12 tháng | Dashboard: tồn kho hiện tại đủ dùng bao nhiêu tháng. | PD | P2 | GĐ 3 |
| REQ-EXT-07 | Cảnh báo NVL <2 tháng | PD Lead nhận thông báo + dashboard tô đỏ. | PD | P2 | GĐ 3 |
| REQ-EXT-08 | Catalog Dashboard per-SP | Form SP: design template, mockup, lịch sử bán. Theo ADR-009 §3 (record `design.file` cho sample/mockup). | BA (#7) | P2 | GĐ 3 |
| REQ-EXT-09 | Lưu template + mockup trên SP | 2 trường file: template gốc + mockup. | BA (#7) | P2 | GĐ 3 |
| REQ-EXT-10 | Scan sheet barcode cho PD | Trang scan đơn giản: focus tự động, enter xác nhận. | BA (#11), PD | P2 | GĐ 3 |
| REQ-EXT-11 | Scan đồng bộ tất cả dashboard | Cập nhật trong 5 giây. | BA, PD | P2 | GĐ 3 |
| REQ-EXT-12 | Tích hợp Amazon | Amazon Seller Central → đơn vào Dashboard chung. Module mới `amazon_channel` theo pattern ADR-001. | PD | P2 | GĐ 3 |
| REQ-EXT-13 | Mở Website Odoo | Dùng module Website của Odoo; đơn vào Dashboard chung. Module mới `website_channel`. | Chủ dự án | P2 | GĐ 3 |
| REQ-EXT-14 | AI analytics — schema export contract | Defer build sang Phase 3+. Phase 1: lock schema export cho `sale.order`, `order.pipeline*`, `design.file*`, `etsy.shop.source.change.log`, v.v. để BI tool đọc sau. | MP, BA, PD (#19) | P2 | GĐ 3 |
| REQ-EXT-15 | (deprecated v2.2 — supersede bởi REQ-PIP-09) | Trước: "Multi-technique routing". Giờ: handle bằng pipeline "Multi-Technique Hybrid" theo ADR-010 §9. Không cần model mới. | — | n/a | n/a |

---

## 13. Phê duyệt & chữ ký

(trước là §12 trong v2.1; renumber thành §13 trong v2.2)

| STT | Vai trò | Họ tên | Ngày ký | Chữ ký | Ghi chú / Điều kiện |
|---|---|---|---|---|---|
| 1 | Chủ dự án | | | | |
| 2 | Trưởng phòng BA | | | | |
| 3 | Trưởng phòng Marketing | | | | |
| 4 | Trưởng phòng Sản xuất (PD) | | | | |
| 5 | Trưởng phòng Kiểm soát giá (Sales Audit) | | | | |

> **Điều kiện ký cho v2.2:**
> - REQ-SYN-00 RESOLVED trong `decision-log.md` D-13 (không cần memo Owner riêng; Stage-1 synthesis đã ghi nhận).
> - D-20 (xác nhận 4-module split của ADR-001) là decision critical-path duy nhất còn ngỏ; default assumption "in force" chờ Owner xác nhận một dòng.
> - REQ-PIP-* / REQ-FIL-* / REQ-SRC-* được chấp nhận qua các ADR Stage-2 (009, 010, 008a, 012) đã ký trong `decision-log.md`.
> - Vào Phase 2 phụ thuộc D-21 (orphan policy Gearment) được chốt trước khi triển khai REQ-TRF-05.

---

*Hết SRS v2.2 (VN). Bản English: `SRS_Multichannel_Hub_EN.md` v2.2. File Excel `SRS_Multichannel_Hub_VN.xlsx` cần regenerate qua `build_srs.py` sau khi VN markdown này được duyệt.*
