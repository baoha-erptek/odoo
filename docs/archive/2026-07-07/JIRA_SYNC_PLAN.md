# Kế hoạch sync Jira (Phase 2)

**Phiên bản:** 1.0
**Ngày:** 2026-05-21
**Trigger:** Chạy SAU KHI Chủ dự án duyệt `BRD_VN.md` và `SRS_VN.md`
**Project:** `ESTY` trên `https://erptek.atlassian.net/`
**Người thực thi:** BA, dùng skill `/jira-create`

---

## 1. Tổng quan sync

- **6 Epic** (1 Epic / phase nghiệp vụ)
- **48 Story** (33 Done, 1 In Progress, 3 Blocked, 11 To Do)
- **Mỗi Story có:** Summary (tiếng Việt), Description, Status, Priority, Labels, Assignee (optional), Story Points (estimate ngày), Epic Link
- **Lifecycle Status:** Done / In Progress / Blocked / To Do (ánh xạ qua Jira workflow ESTY)
- **Priority:** Highest (P0) / High (P1) / Medium (P2) / Low (P3)

---

## 2. Quy ước

### Issue Type
- `Epic` cho 6 phase
- `Story` cho 48 Story con
- (`Sub-task` không dùng — giữ phẳng để CDA dễ đọc)

### Labels mặc định
Mỗi Story gán **3 nhãn**:
1. `phase-X` (1..6)
2. `spec-XXX` (001..008 hoặc `crosscut`)
3. `owner-action` hoặc `dev-action` (cho biết ai unblock)

### Story Points (estimate)
- Story đã Done → không cần SP
- Story In Progress / To Do → SP = số ngày dự kiến (Fibonacci: 1, 2, 3, 5, 8, 13, 21)
- Story Blocked → SP = 0 nếu chỉ owner-op, hoặc SP dev sau khi unblock

### Fix Version
- `v1.0` — Phase 1+2+3 đã closed (gắn cho Story Done)
- `v1.1` — Phase 4+6 đang triển khai
- `v1.2` — Phase 5 (chờ Etsy)

---

## 3. 6 Epic — kế hoạch tạo

| Epic ID | Summary | Description (1 câu) | Status | Priority | Labels |
|---------|---------|----------------------|--------|----------|--------|
| ESTY-E1 | Epic 1 — Nhập đơn tự động | Đơn từ Etsy chảy vào hệ thống trong 5 phút, không phải nhập tay | In Progress | Highest | `phase-1` |
| ESTY-E2 | Epic 2 — Duyệt thiết kế | File thiết kế upload 1 lần, duyệt 3 trạng thái, in hàng loạt | In Progress | High | `phase-2` |
| ESTY-E3 | Epic 3 — Sản xuất | Pipeline 17 trạng thái VN cấu hình được, gán team, scan barcode | In Progress | High | `phase-3` |
| ESTY-E4 | Epic 4 — Vận chuyển & tracking | Đẩy Gearment, import GKE, tracking ngược Etsy, duyệt đổi địa chỉ | In Progress | High | `phase-4` |
| ESTY-E5 | Epic 5 — Tin nhắn khách hàng | Hub tin nhắn 19 shop, CRM lead, mail alias | Blocked | High | `phase-5` |
| ESTY-E6 | Epic 6 — Báo cáo & quản trị | Dashboard, audit log, phân vai trò, Việt hoá, kiểm soát giá | In Progress | High | `phase-6` |

---

## 4. 48 Story — bảng đầy đủ

### Epic 1 — Nhập đơn tự động (9 Story)

| Story | Summary | Status | Priority | SP | Labels | ETA |
|-------|---------|--------|----------|----|----|-----|
| 1.1 | Kết nối tài khoản Etsy an toàn | Done | Highest | — | `phase-1` `spec-005` `dev-action` | 2026-05-12 |
| 1.2 | Tự động kéo đơn mới mỗi 5 phút | Done | Highest | — | `phase-1` `spec-005` `dev-action` | — |
| 1.3 | Email parser dự phòng | Done | Highest | — | `phase-1` `spec-001` `dev-action` | — |
| 1.4 | Làm sạch 17.659 đơn cũ | Done | Highest | — | `phase-1` `spec-002` `dev-action` | — |
| 1.5 | Sửa 423 đơn ghi giá $0 | Done | Highest | — | `phase-1` `spec-002` `dev-action` | — |
| 1.6 | Gộp khách hàng trùng có BA duyệt | Done | Highest | — | `phase-1` `spec-002` `dev-action` | — |
| 1.7 | Đồng bộ danh sách SP + tồn kho từ Etsy | In Progress | High | 5 | `phase-1` `spec-008` `dev-action` | tuần 1 tháng 6 |
| 1.8 | Bật API cho shop pilot | Blocked | Highest | 0 | `phase-1` `crosscut` `owner-action` | tuần 4 tháng 5 |
| 1.9 | Bật API cho 18 shop còn lại | To Do | Highest | 13 | `phase-1` `crosscut` `owner-action` | tháng 6-7 |

### Epic 2 — Duyệt thiết kế (7 Story)

| Story | Summary | Status | Priority | SP | Labels | ETA |
|-------|---------|--------|----------|----|----|-----|
| 2.1 | BA upload file thiết kế lên Google Drive | Done | Highest | — | `phase-2` `spec-003` `dev-action` | — |
| 2.2 | Quy trình duyệt 3 trạng thái | Done | Highest | — | `phase-2` `spec-003` `dev-action` | — |
| 2.3 | Bảng kanban hàng đợi duyệt | Done | High | — | `phase-2` `spec-003` `dev-action` | — |
| 2.4 | Tự gửi file đến bộ phận liên quan | Done | Highest | — | `phase-2` `spec-003` `dev-action` | — |
| 2.5 | PD bulk-download in A4 | Done | High | — | `phase-2` `spec-003` `dev-action` | — |
| 2.6 | Tự lưu trữ file đã in | To Do | Medium | 3 | `phase-2` `spec-003` `dev-action` | cuối tháng 5 |
| 2.7 | Cảnh báo file thiếu trước sản xuất | Done | Highest | — | `phase-2` `spec-003` `dev-action` | — |

### Epic 3 — Sản xuất (7 Story)

| Story | Summary | Status | Priority | SP | Labels | ETA |
|-------|---------|--------|----------|----|----|-----|
| 3.1 | Dashboard sản xuất 17 trạng thái VN | Done | Highest | — | `phase-3` `spec-003` `dev-action` | — |
| 3.2 | Pipeline đơn cấu hình được | Done | Highest | — | `phase-3` `spec-003` `dev-action` | — |
| 3.3 | Tuyến Dropship + MTO | Done | Highest | — | `phase-3` `spec-004` `dev-action` | — |
| 3.4 | Gán team phụ trách cho từng stage | Done | Highest | — | `phase-3` `spec-003` `dev-action` | — |
| 3.5 | Scan barcode để chuyển trạng thái | Done | High | — | `phase-3` `spec-003` `dev-action` | — |
| 3.6 | Tự chuyển stage khi xong workorder MRP | To Do | High | 5 | `phase-3` `crosscut` `dev-action` | tuần 2 tháng 6 |
| 3.7 | Widget thống kê sản xuất | Done | Medium | — | `phase-3` `spec-003` `dev-action` | — |

### Epic 4 — Vận chuyển & tracking (9 Story)

| Story | Summary | Status | Priority | SP | Labels | ETA |
|-------|---------|--------|----------|----|----|-----|
| 4.1 | Kết nối Gearment, đẩy đơn qua API | Done | Highest | — | `phase-4` `spec-004` `dev-action` | — |
| 4.2 | Nhận webhook trạng thái Gearment | Done | Highest | — | `phase-4` `spec-004` `dev-action` | — |
| 4.3 | Import tracking từ file Excel GKE | Done | Highest | — | `phase-4` `spec-004a` `dev-action` | — |
| 4.4 | Tự nhận diện carrier từ mã tracking | Done | Highest | — | `phase-4` `spec-004a` `dev-action` | — |
| 4.5 | Đẩy tracking ngược về Etsy | Done | Highest | — | `phase-4` `spec-005` `dev-action` | — |
| 4.6 | Duyệt đổi địa chỉ giao hàng | Done | Highest | — | `phase-4` `spec-003` `dev-action` | — |
| 4.7 | Bulk-action gửi đơn đã duyệt sang Gearment | To Do | High | 3 | `phase-4` `spec-004` `dev-action` | cuối tháng 5 |
| 4.8 | Xử lý đơn hoàn / refund | To Do | High | 8 | `phase-4` `spec-004` `dev-action` | tháng 7 |
| 4.9 | Hiển thị trạng thái tracking real-time | Done | High | — | `phase-4` `spec-004a` `dev-action` | — |

### Epic 5 — Tin nhắn khách hàng (6 Story)

| Story | Summary | Status | Priority | SP | Labels | ETA |
|-------|---------|--------|----------|----|----|-----|
| 5.1 | Hiển thị buyer message trên form đơn | Done | Highest | — | `phase-5` `spec-005` `dev-action` | — |
| 5.2 | Hub tin nhắn khách | Done | High | — | `phase-5` `spec-007` `dev-action` | — |
| 5.3 | Tạo CRM lead từ tin nhắn khách | Done | High | — | `phase-5` `spec-007` `dev-action` | — |
| 5.4 | Mail alias gom phản hồi khách | To Do | Medium | 5 | `phase-5` `spec-007` `dev-action` | tháng 7 |
| 5.5 | Re-submit Etsy app xin `conversations_r` | Blocked | High | 0 | `phase-5` `crosscut` `owner-action` | tuần này |
| 5.6 | Kéo tin nhắn Etsy qua API | Blocked | High | 5 | `phase-5` `spec-007` `dev-action` | sau 5.5 + 1 tuần |

### Epic 6 — Báo cáo & quản trị (10 Story)

| Story | Summary | Status | Priority | SP | Labels | ETA |
|-------|---------|--------|----------|----|----|-----|
| 6.1 | Dashboard Đơn hàng | Done | Highest | — | `phase-6` `spec-003` `dev-action` | — |
| 6.2 | Dashboard Tracking | Done | Highest | — | `phase-6` `spec-003` `dev-action` | — |
| 6.3 | Dashboard Sản xuất (xem 3.1) | Done | Highest | — | `phase-6` `spec-003` `dev-action` | — |
| 6.4 | Dashboard Tài chính | To Do | High | 8 | `phase-6` `spec-003` `dev-action` | tháng 6 |
| 6.5 | Dashboard Kiểm soát giá | To Do | High | 13 | `phase-6` `spec-004` `dev-action` | tháng 7 |
| 6.6 | Audit log mọi thao tác | Done | Highest | — | `phase-6` `crosscut` `dev-action` | — |
| 6.7 | Phân vai trò người dùng | Done | Highest | — | `phase-6` `crosscut` `dev-action` | — |
| 6.8 | Việt hoá toàn bộ giao diện | To Do | High | 8 | `phase-6` `crosscut` `dev-action` | tháng 6 |
| 6.9 | Kiểm tra sức khỏe hệ thống | To Do | Medium | 5 | `phase-6` `crosscut` `dev-action` | tháng 7 |
| 6.10 | Báo cáo định kỳ qua email | To Do | Medium | 3 | `phase-6` `crosscut` `dev-action` | tháng 7-8 |

---

## 5. Quy trình thực thi sync (BA chạy)

### Bước 1 — Chuẩn bị

```bash
# Verify .env chứa credentials
grep -E "JIRA_PROJECT_KEY|JIRA_SERVER_URL|JIRA_USER_EMAIL" \
  /home/odoo/odoo_dev/other_projects/odoo19_esty/.env
```

Kết quả mong đợi: `JIRA_PROJECT_KEY=ESTY`, `JIRA_SERVER_URL=https://erptek.atlassian.net/`, `JIRA_USER_EMAIL=bao.ha@erptek.net`.

### Bước 2 — Test với 1 Story trước khi rollout

Dùng skill `/jira-create` push **Story 6.10** (rủi ro thấp nhất, chưa code) lên Jira. Kiểm tra trên Atlassian:
- Status đúng `To Do`
- Priority đúng `Medium`
- Labels đúng `phase-6`, `crosscut`, `dev-action`
- Story Points = 3
- Description hiển thị tiếng Việt không lỗi font

### Bước 3 — Tạo 6 Epic trước

Tạo 6 Epic theo bảng §3. Lưu ID Jira trả về (`ESTY-XX`) làm Epic Link cho các Story.

### Bước 4 — Tạo 48 Story theo Epic

- Push từng batch 10 Story
- Sau mỗi batch verify trên board
- Nếu sai → sửa skill `/jira-create` config rồi push tiếp

### Bước 5 — Verify cuối cùng

```
- [ ] 6 Epic hiển thị trên board, tô màu khác nhau
- [ ] 48 Story link đúng Epic
- [ ] Filter "Status = Done" → 33 issues
- [ ] Filter "Status = Blocked" → 3 issues
- [ ] Filter "Label = owner-action" → 3 issues (1.8, 1.9, 5.5)
- [ ] Backlog group by Epic hiển thị đúng cấu trúc
```

### Bước 6 — Bàn giao CDA

- Screen-share 15 phút hướng dẫn:
  - Mở board theo URL
  - Filter by Epic / Status / Label
  - Click Story để xem chi tiết
  - Comment trên Story khi cần
- Gửi CDA bookmark link board

---

## 6. Quy tắc bảo trì sau sync

### Khi dev land 1 Story

1. Dev push code → close slice trong tracker nội bộ
2. BA mở Jira → đổi status Story tương ứng sang `Done`
3. Nếu Story nằm trong các Story `Blocked` khác → unblock luôn

### Khi có Story mới phát sinh

1. BA thêm Story vào `SRS_VN.md` (mục Epic phù hợp)
2. Push lên Jira qua `/jira-create`, link đúng Epic
3. Cập nhật `STATUS_VN.md` nếu là Story P0/P1

### Cập nhật định kỳ

- **Hàng tuần:** BA review trạng thái Jira vs thực tế
- **Mỗi 2 tuần:** refresh `STATUS_VN.md` + báo cáo cho CDA
- **Mỗi tháng:** tổng kết Story closed / open / blocked

---

## 7. Risk khi sync

| # | Rủi ro | Mitigation |
|---|--------|-----------|
| 1 | Jira workflow ESTY chưa có status "Blocked" → fail | Verify trước Step 3; nếu thiếu → tạo qua workflow editor hoặc dùng label thay |
| 2 | Skill `/jira-create` không support Story Points custom field | Test ở Step 2 trước; nếu không support → ghi SP trong Description |
| 3 | Push 48 Story quá nhanh → rate limit Atlassian | Push batch 10, nghỉ 30s giữa batch |
| 4 | Encoding tiếng Việt bị lỗi | Verify ở Step 2; nếu sai → dùng UTF-8 explicit |
| 5 | CDA chưa có account Atlassian | CDA cần tạo account + invite vào project ESTY trước Step 6 |

---

## 8. Appendix — JSON payload mẫu

Mẫu payload tạo 1 Story qua `/jira-create`:

```json
{
  "project": "ESTY",
  "issuetype": "Story",
  "summary": "1.7 Đồng bộ danh sách sản phẩm và tồn kho từ Etsy",
  "description": "Tải danh sách sản phẩm và tồn kho từ Etsy về hệ thống. Chỉ đọc. Cảnh báo khi lệch >10%.\n\nAcceptance criteria:\n- Mỗi shop xem được số SP và tồn kho hiện tại\n- Có cảnh báo khi tồn kho lệch >10%\n\nETA: tuần 1 tháng 6/2026",
  "priority": "High",
  "labels": ["phase-1", "spec-008", "dev-action"],
  "epic_link": "ESTY-E1",
  "story_points": 5
}
```

---

*Hết JIRA_SYNC_PLAN v1.0. Chạy sau khi CDA ký BRD §10.*
