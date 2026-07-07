# Tài liệu dành cho Chủ dự án (CDA)

Thư mục này chứa tài liệu nghiệp vụ về dự án **Hệ thống quản lý đơn hàng Etsy đa kênh**, viết bằng tiếng Việt nghiệp vụ để Chủ dự án đọc và duyệt mà không cần kiến thức kỹ thuật.

> Tài liệu kỹ thuật dành cho dev (ADR, slice tracker, spec.md, playbook) nằm trong `specs/` và `.claude/plans/` — **không cần đọc** từ thư mục này.

---

## 4 file chính

| File | Đọc trong | Ai đọc | Mục đích |
|------|-----------|--------|----------|
| **[BRD_VN.md](BRD_VN.md)** | 10 phút | Chủ dự án (ký) | Bức tranh kinh doanh: vấn đề, tầm nhìn, lợi ích, phạm vi, lộ trình, tiêu chí thành công, rủi ro |
| **[SRS_VN.md](SRS_VN.md)** | 30 phút | CDA + BA | Chi tiết 55 chức năng (Story) trong 7 phase, mỗi chức năng có trạng thái, ưu tiên, ngày dự kiến |
| **[STATUS_VN.md](STATUS_VN.md)** | 2 phút | CDA (hàng tuần) | Dashboard nhanh: % xong, đang làm gì, cần CDA xử lý gì |
| **[JIRA_SYNC_REPORT.md](JIRA_SYNC_REPORT.md)** | 3 phút | CDA + BA | Báo cáo sau khi sync — Epic/Story key, link Jira, filter quick-links |

> **Đã sync lên Jira ngày 2026-05-21** (lần đầu) **+ delta sync 2026-05-25** (3 Story Done + Epic 7).
> **Board Jira:** https://erptek.atlassian.net/jira/software/projects/ESTY/board
> **Confluence (bản tài liệu đầy đủ):** https://erptek.atlassian.net/wiki/spaces/HEP
> **Trang Confluence dự án:** https://erptek.atlassian.net/jira/software/projects/ESTY/pages
> Xem `JIRA_SYNC_REPORT.md` để biết chi tiết keys.

---

## Sơ đồ quy trình (Process Flow Diagrams)

Sơ đồ bơi làn (swimlane) — ai làm gì, theo thứ tự nào — dùng để phổ biến nội bộ và onboard nhân viên mới.

| Sơ đồ | Mô tả | Xem PNG | Chỉnh sửa |
|---|---|---|---|
| **AS-IS — Quy trình hiện tại** | Toàn bộ luồng thủ công trước khi dùng Odoo: 9 làn (Khách hàng, Etsy, Hệ thống cũ, MP, BA, PD, Kho, RD, Gearment). Có điểm đau (⚠) và 2 nhánh Route US-od / Vietnam-od. | [`process-flows/AS-IS_Quy_trinh_hien_tai.drawio.png`](../process-flows/AS-IS_Quy_trinh_hien_tai.drawio.png) | [`process-flows/AS-IS_Quy_trinh_hien_tai.drawio`](../process-flows/AS-IS_Quy_trinh_hien_tai.drawio) |
| **TO-BE — Với Odoo Standard** | Luồng sau triển khai Odoo 19 CE: Hệ thống tự nhận đơn, tự tạo Lệnh SX / Yêu cầu mua hàng Gearment, tự trừ kho, tự gửi tracking về Etsy. 3 nhánh Route A (nội bộ) / Route B (Gearment POD) / Route C (chờ xếp loại). | [`process-flows/TO-BE_Voi_Odoo_Standard.drawio.png`](../process-flows/TO-BE_Voi_Odoo_Standard.drawio.png) | [`process-flows/TO-BE_Voi_Odoo_Standard.drawio`](../process-flows/TO-BE_Voi_Odoo_Standard.drawio) |

> **Cách mở để chỉnh sửa:** Tải file `.drawio` về → mở bằng [draw.io Desktop](https://github.com/jgraph/drawio-desktop/releases) hoặc truy cập [draw.io online](https://app.diagrams.net/) và kéo file vào.
> **Định dạng SVG** (vector, phóng to không vỡ): [`AS-IS_Quy_trinh_hien_tai.svg`](../process-flows/AS-IS_Quy_trinh_hien_tai.svg) · [`TO-BE_Voi_Odoo_Standard.svg`](../process-flows/TO-BE_Voi_Odoo_Standard.svg)

---

## Hướng dẫn nghiệp vụ (4 luồng chính)

| Luồng | Tài liệu nghiệp vụ | Hướng dẫn thao tác | Sơ đồ + ảnh chụp |
|---|---|---|---|
| Tạo sản phẩm | [`FLOW_TAO_SAN_PHAM_VN.md`](FLOW_TAO_SAN_PHAM_VN.md) | [`HUONG_DAN_TAO_SAN_PHAM_VN.md`](HUONG_DAN_TAO_SAN_PHAM_VN.md) | [`business-flows/flow-1-tao-san-pham.md`](business-flows/flow-1-tao-san-pham.md) |
| Tiếp nhận đơn Etsy | [`FLOW_DON_HANG_ETSY_VN.md`](FLOW_DON_HANG_ETSY_VN.md) | [`HUONG_DAN_DON_HANG_ETSY_VN.md`](HUONG_DAN_DON_HANG_ETSY_VN.md) | [`business-flows/flow-2-nhan-don-hang-etsy.md`](business-flows/flow-2-nhan-don-hang-etsy.md) |
| Giao hàng | [`FLOW_GIAO_HANG_VN.md`](FLOW_GIAO_HANG_VN.md) | [`HUONG_DAN_GIAO_HANG_VN.md`](HUONG_DAN_GIAO_HANG_VN.md) | [`business-flows/flow-3a-giao-hang-in-noi-bo.md`](business-flows/flow-3a-giao-hang-in-noi-bo.md) + [`flow-3b-giao-hang-gearment-dropship.md`](business-flows/flow-3b-giao-hang-gearment-dropship.md) |
| Hậu mãi | [`FLOW_HAU_MAI_VN.md`](FLOW_HAU_MAI_VN.md) | [`HUONG_DAN_HAU_MAI_VN.md`](HUONG_DAN_HAU_MAI_VN.md) | [`business-flows/flow-4-hau-mai.md`](business-flows/flow-4-hau-mai.md) |

Chỉ mục business-flows: [`business-flows/README.md`](business-flows/README.md)
Site business-flows hiện hành: [`business-flows/v3/index.html`](business-flows/v3/index.html)

> **Bộ PDF UAT hợp nhất** (gửi người dùng cuối, kèm ảnh chụp màn hình thật):
> [`../pdf/docs_huong_dan_uat_vn.pdf`](../pdf/docs_huong_dan_uat_vn.pdf) — gồm cả 4 luồng, mỗi luồng = tài liệu nghiệp vụ (FLOW) + hướng dẫn thao tác (HUONG_DAN). Build lại: `bash docs/pdf/build-pdfs.sh`.

## UAT (Owner kiểm thử)

| File | Mục đích | Phiên bản |
|---|---|---|
| [`HUONG_DAN_TAO_SAN_PHAM_VN.md`](HUONG_DAN_TAO_SAN_PHAM_VN.md) | Hướng dẫn hiện hành cho luồng tạo sản phẩm; mục 9 chứa checklist UAT | 2.0 — **dùng** |
| [`business-flows/flow-1-tao-san-pham.md`](business-flows/flow-1-tao-san-pham.md) | Luồng 1 kèm ảnh chụp UAT và liên kết sang site `v3/` | 1.0 |
| [`SKU_GRAMMAR.md`](SKU_GRAMMAR.md) | Ngữ pháp SKU + defect matrix | — |

## Lưu trữ (đã archive)

Tài liệu cũ / chạy log / draft email đã chuyển sang [`../archive/2026-06-07/`](../archive/2026-06-07/).
Kết quả UAT các đợt cũ (2026-05/06) đã chuyển sang [`../archive/2026-07-05/`](../archive/2026-07-05/).
Batch 2026-07-07: walkthrough v1.0 + v1.2, readiness assessment, inventory setup, Jira sync plan, business-flows mockup/superseded HTML, và `design-system/` đã chuyển sang [`../archive/2026-07-07/`](../archive/2026-07-07/).
Báo cáo UAT cấp engineering: [`../engineering/uats/`](../engineering/uats/).

---

## Quy trình đọc & duyệt

### Lần đầu (CDA)
1. Đọc `BRD_VN.md` từ đầu đến cuối (10 phút)
2. Đọc lướt `SRS_VN.md` — xem các Story đã Done có đúng kỳ vọng không (30 phút)
3. Đọc `STATUS_VN.md` để biết hôm nay đang ở đâu (2 phút)
4. Comment / yêu cầu chỉnh sửa nếu có
5. Ký `BRD_VN.md` §10

### Sau khi duyệt
1. BA dùng `JIRA_SYNC_REPORT.md` để mở đúng Jira filter / Epic / Story sau mỗi đợt sync
2. CDA mở Jira board hàng ngày để theo dõi tiến độ
3. BA refresh `STATUS_VN.md` mỗi 2 tuần

### Khi có thay đổi
- BA cập nhật Story trong `SRS_VN.md`
- BA sync Story tương ứng trên Jira
- BA cập nhật `STATUS_VN.md` nếu là Story P0/P1

---

## Liên hệ

| Vai trò | Người phụ trách | Trách nhiệm |
|---------|------------------|-------------|
| Chủ dự án | (CDA điền) | Duyệt BRD/SRS, bật shop, submit Etsy, lấy API Gearment |
| BA Lead | (BA Lead điền) | Cập nhật Story trên Jira, refresh STATUS, đối chiếu dữ liệu |
| Dev Lead | (Dev Lead điền) | Triển khai Story còn lại theo ưu tiên |

---

## Lịch sử phiên bản

| Phiên bản | Ngày | Người soạn | Thay đổi chính |
|-----------|------|-------------|-----------------|
| 1.0 | 2026-05-21 | BA Consultant | Tài liệu khởi tạo — 4 file owner-readable, chuẩn bị sync Jira |
| 1.1 | 2026-05-25 | BA Consultant | Delta sync — 3 Story Done, Epic 7 (Trung tâm sản phẩm + xuất kênh) thêm 7 Story, mirror lên Confluence space HEP |
| 1.2 | 2026-06-07 | UAT sweep | Thêm 5 business-flows companion markdown + UAT_WALKTHROUGH v1.2 Wave 2/3; archive 19 file E2E run logs / legacy guides sang `../archive/2026-06-07/` |
| 1.3 | 2026-07-05 | E2E close-out | Cả 5 luồng chính đã kiểm thử E2E trên môi trường staging (kể cả Hậu mãi). 4 bộ HUONG_DAN + 4 FLOW đều có ảnh chụp màn hình thật; bổ sung tab "Original Design" trên form sản phẩm. Bộ PDF UAT hợp nhất: `../pdf/docs_huong_dan_uat_vn.pdf` |
| 2.0 | 2026-07-05 | Hatafa UI live | Giao diện mới Hatafa + menu Vận hành mới + tiếng Việt + ảnh chụp mới (4 HUONG_DAN cập nhật v2.0) |

---

*Mọi câu hỏi liên hệ BA Lead. Tài liệu kỹ thuật chi tiết: xem `specs/` và `.claude/plans/`.*
