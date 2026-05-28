# Báo cáo sync Jira — hoàn tất

**Ngày thực hiện:** 2026-05-21
**Người thực hiện:** BA (qua script `.claude/scripts/push_owner_jira.py`)
**Project:** ESTY tại `https://erptek.atlassian.net/`
**Link board:** https://erptek.atlassian.net/jira/software/projects/ESTY/board

---

## Tổng kết

| Hạng mục | Số lượng | Trạng thái |
|----------|----------|------------|
| Issue cũ đã xóa | 116 | ✓ |
| Epic mới tạo | 6 (ESTY-120 → ESTY-125) | ✓ |
| Story mới tạo | 48 (ESTY-126 → ESTY-173) | ✓ |
| **Tổng issue mới** | **54** | **✓** |
| Story chuyển sang Done | 33 | ✓ |
| Story chuyển sang In Review | 1 | ✓ |
| Story ở To Do (bao gồm Sắp làm + Bị chặn) | 14 | ✓ |

---

## 6 Epic — Jira keys

| Epic | Jira key | Status | Link |
|------|----------|--------|------|
| Epic 1 — Nhập đơn tự động | **ESTY-120** | In Review | https://erptek.atlassian.net/browse/ESTY-120 |
| Epic 2 — Duyệt thiết kế | **ESTY-121** | In Review | https://erptek.atlassian.net/browse/ESTY-121 |
| Epic 3 — Sản xuất | **ESTY-122** | In Review | https://erptek.atlassian.net/browse/ESTY-122 |
| Epic 4 — Vận chuyển & tracking | **ESTY-123** | In Review | https://erptek.atlassian.net/browse/ESTY-123 |
| Epic 5 — Tin nhắn khách hàng | **ESTY-124** | To Do | https://erptek.atlassian.net/browse/ESTY-124 |
| Epic 6 — Báo cáo & quản trị | **ESTY-125** | In Review | https://erptek.atlassian.net/browse/ESTY-125 |

---

## 3 Story cần CDA thao tác ngay

| Jira key | Story | Tại sao gấp |
|----------|-------|-------------|
| [ESTY-133](https://erptek.atlassian.net/browse/ESTY-133) | 1.8 Bật API cho shop pilot | Chặn toàn bộ Phase 1 mở rộng |
| [ESTY-134](https://erptek.atlassian.net/browse/ESTY-134) | 1.9 Bật API cho 18 shop còn lại | Phase 2 exit |
| [ESTY-162](https://erptek.atlassian.net/browse/ESTY-162) | 5.5 Re-submit Etsy app xin `conversations_r` | Etsy duyệt 3-8 tuần, càng chậm submit càng chậm Phase 5 |

Lọc nhanh trên board: filter `labels = "owner-action"`.

---

## 3 Story đang Blocked

| Jira key | Story | Chờ |
|----------|-------|-----|
| ESTY-133 | 1.8 Bật API cho shop pilot | CDA thao tác |
| ESTY-162 | 5.5 Re-submit Etsy app conversations_r | CDA thao tác |
| ESTY-163 | 5.6 Kéo tin nhắn Etsy qua API | Sau khi 5.5 xong |

Lọc nhanh: filter `labels = "blocked"`.

---

## Mapping Story → Epic (đầy đủ 48)

### Epic 1 — Nhập đơn tự động (ESTY-120)
- ESTY-126: 1.1 Kết nối tài khoản Etsy an toàn — Done
- ESTY-127: 1.2 Tự động kéo đơn mới mỗi 5 phút — Done
- ESTY-128: 1.3 Email parser dự phòng — Done
- ESTY-129: 1.4 Làm sạch 17.659 đơn cũ — Done
- ESTY-130: 1.5 Sửa 423 đơn ghi giá $0 — Done
- ESTY-131: 1.6 Gộp khách hàng trùng có BA duyệt — Done
- ESTY-132: 1.7 Đồng bộ sản phẩm + tồn kho — In Review
- ESTY-133: 1.8 Bật API cho shop pilot — To Do (blocked)
- ESTY-134: 1.9 Bật API cho 18 shop còn lại — To Do

### Epic 2 — Duyệt thiết kế (ESTY-121)
- ESTY-135: 2.1 Upload Google Drive — Done
- ESTY-136: 2.2 Quy trình duyệt 3 trạng thái — Done
- ESTY-137: 2.3 Bảng kanban hàng đợi — Done
- ESTY-138: 2.4 Tự gửi file đến bộ phận — Done
- ESTY-139: 2.5 PD bulk-download in A4 — Done
- ESTY-140: 2.6 Tự lưu trữ file đã in — To Do
- ESTY-141: 2.7 Cảnh báo file thiếu trước sản xuất — Done

### Epic 3 — Sản xuất (ESTY-122)
- ESTY-142: 3.1 Dashboard 17 trạng thái VN — Done
- ESTY-143: 3.2 Pipeline cấu hình được — Done
- ESTY-144: 3.3 Tuyến Dropship + MTO — Done
- ESTY-145: 3.4 Gán team theo stage — Done
- ESTY-146: 3.5 Scan barcode — Done
- ESTY-147: 3.6 Auto-chuyển stage MRP — To Do
- ESTY-148: 3.7 Widget thống kê — Done

### Epic 4 — Vận chuyển & tracking (ESTY-123)
- ESTY-149: 4.1 Kết nối Gearment — Done
- ESTY-150: 4.2 Nhận thông báo Gearment — Done
- ESTY-151: 4.3 Import tracking GKE — Done
- ESTY-152: 4.4 Tự nhận diện carrier — Done
- ESTY-153: 4.5 Đẩy tracking ngược Etsy — Done
- ESTY-154: 4.6 Duyệt đổi địa chỉ — Done
- ESTY-155: 4.7 Bulk-send Gearment — To Do
- ESTY-156: 4.8 Xử lý hoàn/refund — To Do
- ESTY-157: 4.9 Trạng thái tracking real-time — Done

### Epic 5 — Tin nhắn khách hàng (ESTY-124)
- ESTY-158: 5.1 Buyer message trên form đơn — Done
- ESTY-159: 5.2 Hub tin nhắn khách — Done
- ESTY-160: 5.3 CRM lead từ tin nhắn — Done
- ESTY-161: 5.4 Mail alias gom phản hồi — To Do
- ESTY-162: 5.5 Re-submit Etsy app — To Do (blocked)
- ESTY-163: 5.6 Kéo tin nhắn Etsy qua API — To Do (blocked)

### Epic 6 — Báo cáo & quản trị (ESTY-125)
- ESTY-164: 6.1 Dashboard Đơn hàng — Done
- ESTY-165: 6.2 Dashboard Tracking — Done
- ESTY-166: 6.3 Dashboard Sản xuất — Done
- ESTY-167: 6.4 Dashboard Tài chính — To Do
- ESTY-168: 6.5 Dashboard Kiểm soát giá — To Do
- ESTY-169: 6.6 Audit log mọi thao tác — Done
- ESTY-170: 6.7 Phân vai trò người dùng — Done
- ESTY-171: 6.8 Việt hoá giao diện — To Do
- ESTY-172: 6.9 Health monitoring — To Do
- ESTY-173: 6.10 Báo cáo email hàng ngày — To Do

---

## Filter quick-links cho CDA

| Filter | JQL | Mục đích |
|--------|-----|----------|
| Tất cả Epic | `project = ESTY AND issuetype = Epic` | Xem 6 phase tổng thể |
| Cần CDA thao tác | `project = ESTY AND labels = "owner-action"` | 3 việc gấp |
| Đang bị chặn | `project = ESTY AND labels = "blocked"` | Việc đang đợi unblock |
| Sắp tới ưu tiên cao | `project = ESTY AND status = "To Do" AND priority in ("Highest", "High")` | Việc dev sẽ làm tiếp |
| Đã hoàn thành | `project = ESTY AND status = Done` | 33 Story đã xong |

CDA copy JQL vào ô tìm kiếm trên Jira board để áp dụng filter.

---

## Delta sync 2026-05-25

**Sự kiện:** sau 4 ngày kể từ sync gốc (2026-05-21), 3 Story đã hoàn thành + 1 Epic mới (Epic 7) được thêm vào SRS với 7 Story con. Lần này BA chạy delta sync (chỉ những thay đổi).

### Story chuyển sang Done (3)

| Jira key | Story | Bằng chứng |
|----------|-------|------------|
| [ESTY-132](https://erptek.atlassian.net/browse/ESTY-132) | 1.7 Đồng bộ sản phẩm + tồn kho | Backfill listing Etsy + bản sản phẩm + dòng trạng thái kênh (2026-05-23) |
| [ESTY-140](https://erptek.atlassian.net/browse/ESTY-140) | 2.6 Tự lưu trữ file đã in | Soft-archive sibling design files (2026-05-23) |
| [ESTY-161](https://erptek.atlassian.net/browse/ESTY-161) | 5.4 Mail alias gom phản hồi khách | Email alias provisioning + form button (2026-05-24) |

### Epic 7 — Trung tâm sản phẩm + xuất kênh (mới)

Epic + 7 Story con đẩy lên Jira ngày 2026-05-25.

**Epic 7 — [ESTY-174](https://erptek.atlassian.net/browse/ESTY-174) — In Review**

| Story (SRS §) | Trạng thái | Jira key |
|---------------|------------|----------|
| 7.1 Mô hình sản phẩm thống nhất | ✅ Xong | [ESTY-175](https://erptek.atlassian.net/browse/ESTY-175) |
| 7.2 Wizard tạo sản phẩm | ✅ Xong | [ESTY-176](https://erptek.atlassian.net/browse/ESTY-176) |
| 7.3 Wizard chuẩn hoá SKU | ✅ Xong | [ESTY-177](https://erptek.atlassian.net/browse/ESTY-177) |
| 7.4 Backfill listing Etsy hiện có | ✅ Xong | [ESTY-178](https://erptek.atlassian.net/browse/ESTY-178) |
| 7.5 Tab Kênh + nút Đăng lên Etsy | ✅ Xong | [ESTY-179](https://erptek.atlassian.net/browse/ESTY-179) |
| 7.6 Đồng bộ định kỳ từ file Excel | 🔄 Đang triển khai | [ESTY-180](https://erptek.atlassian.net/browse/ESTY-180) |
| 7.7 Xuất lên Etsy (Outbound Publish) | ✅ Xong (smoke test JaHandmadeArt thành công 2026-05-25) | [ESTY-181](https://erptek.atlassian.net/browse/ESTY-181) |

### Tổng kết lại

| Hạng mục | Số lượng |
|----------|----------|
| Epic tổng cộng | 7 (+1 Epic 7) |
| Story tổng cộng | 55 (+7 Epic 7) |
| Story Done | 42 (33 cũ + 3 transition + 6 Epic 7) |
| Story To Do / Đang làm | 13 |
| Story bị chặn (CDA action) | 3 (1.8, 5.5, 5.6) |

**Mới đạt mốc:** Tiến độ coding **76%** (so với 73% ngày 2026-05-21).

### Hành động cần CDA

CDA chọn 1 trong 3 nhánh ưu tiên sắp tới (xem `STATUS_VN.md` mục "Sắp làm"):

- **Nhánh A** — Hoàn thiện Phase 7 (Excel cron + tải ảnh)
- **Nhánh B** — Hậu mãi & tài chính (Bulk-send Gearment + hoàn/refund)
- **Nhánh C** — Bổ trợ vận hành (Việt hoá UI + dashboard tài chính + 18 shop API)

---

## Bảo trì sau sync

### Quy ước cập nhật

| Sự kiện | Ai làm | Hành động |
|---------|--------|-----------|
| Dev land 1 Story | Dev hoặc BA | Mở Jira Story → bấm "Done" |
| Story bị chặn được unblock | BA | Xoá label `blocked` |
| Story mới phát sinh | BA | Thêm vào `SRS_VN.md` + tạo issue qua `/jira-create` |
| Mỗi 2 tuần | BA | Refresh `STATUS_VN.md` theo Jira |
| Mỗi tháng | BA + CDA | Họp review tổng kết |

### Backup mapping

File `.docs/tasks/_owner_sync_2026-05-21.json` lưu mapping Epic/Story → Jira key. Giữ lại để truy vết khi cần.

---

*Hết. Liên hệ BA nếu phát hiện sai sót.*
