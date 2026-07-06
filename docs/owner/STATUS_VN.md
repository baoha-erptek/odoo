# Dashboard Tình hình Dự án (Daily View)

**Cập nhật:** 2026-07-06 | **Soạn:** BA | **Đọc cho:** Chủ dự án (CDA)

> **Mốc lớn 2026-07-05A:** Cả **5 luồng nghiệp vụ chính** (Tạo sản phẩm → Nhận đơn → Giao nội bộ → Dropship Gearment → Hậu mãi) đã **kiểm thử E2E đầy đủ trên môi trường staging**, chạy bằng API thật (Etsy + Gearment). Lỗi báo giá Gearment đã đóng — báo giá thật $12.99 trả về đúng. Bộ tài liệu hướng dẫn kèm ảnh chụp màn hình thật đã sẵn sàng gửi người dùng UAT.
>
> **Mốc lớn 2026-07-06:** **Kiểm thử lại toàn bộ 5 luồng chính sau đợt sửa luồng sản phẩm (06-07)** — mỗi luồng chạy 2 lần ĐẠT trên staging với API thật. Các hành vi mới đã kiểm chứng: đơn SKU lạ bị GIỮ thay vì tự tạo sản phẩm; giao nội bộ tự nhảy "Đã gửi" khi xuất kho; lời chúc tặng quà gửi kèm đơn Gearment; sản phẩm nhiều biến thể phải gán mã Gearment từng biến thể (thiếu là chặn đẩy đơn); SKU tự sinh khi đăng bán được lưu lại để đơn quay về khớp đúng biến thể. Phát hiện + sửa 1 lỗi bản dịch tiếng Việt làm hỏng nút duyệt đổi địa chỉ. Ảnh chụp màn hình + tài liệu + trang docs.hatafa đã làm mới.
>
> **Mốc lớn 2026-07-05B:** **Hatafa UI live + v2.0 guides ready** — Giao diện hệ thống được làm mới với theme Hatafa (thanh điều hướng tím, sidebar tối), menu chính sắp xếp lại thành "Vận hành" (hub 6 phần). Tất cả 4 bộ HUONG_DAN (Tiếp nhận đơn, Giao hàng, Hậu mãi, Tạo sản phẩm) đã cập nhật v2.0 với menu paths mới + ảnh chụp màn hình thật từ staging 2026-07-05.

> File 1 trang. Đọc trong 2 phút. Chi tiết xem `SRS_VN.md` hoặc Jira board.

---

## Tổng quan

**Tiến độ coding tổng:** **76%** (42/55 Story xong)
**Mục tiêu cuối:** Toàn bộ 19 shop Etsy chạy API, Gearment đẩy đơn tự động, Excel/Google Sheet ngừng dùng, hệ thống là bản gốc danh mục sản phẩm.
**Ước tính go-live đầy đủ:** **Cuối tháng 7/2026** (nếu CDA xử lý 3 việc dưới đây)

---

## 7 Phase nghiệp vụ — hôm nay

| # | Phase | % xong | Đang làm | Tiếp theo | Cần ai xử lý |
|---|-------|--------|----------|-----------|---------------|
| 1 | **Nhập đơn tự động** | 95% | — | Bật API cho shop pilot | **CDA bật shop pilot** |
| 2 | **Duyệt thiết kế** | 100% | — | (đã đủ) | — |
| 3 | **Sản xuất** | 90% | — | Auto-chuyển stage MRP | Dev (giữa tháng 6) |
| 4 | **Vận chuyển & tracking** | 80% | — | Bulk-send + Hoàn/refund | **CDA cấp API key Gearment** |
| 5 | **Tin nhắn khách hàng** | 80% | — | Re-submit Etsy scope | **CDA submit Etsy** |
| 6 | **Báo cáo & quản trị** | 70% | — | Việt hoá + Tài chính + Kiểm soát giá | Dev (tháng 6-7) |
| 7 | **Trung tâm sản phẩm + xuất kênh** _(thêm 2026-05-23)_ | 86% | Đồng bộ Excel định kỳ | Tải ảnh từ Excel | Dev (tuần đầu tháng 6) |

---

## 3 việc CDA cần làm gấp (chặn dự án nếu không xử lý)

| # | Việc | Tại sao gấp | Hạn |
|---|------|-------------|-----|
| 1 | **Bật API cho 1 shop pilot** (cutover chính thức) | Chặn xác nhận "push tracking lên Etsy" trên đơn thật — bước cuối trước go-live | Tuần này |
| 2 | **Submit lại Etsy app xin quyền `conversations_r`** | Etsy duyệt 3-8 tuần; submit muộn = chậm Phase 5 từng tuần | Tuần này |
| 3 | **Huỷ các đơn NHÁP test trên Gearment dashboard** | Kiểm thử E2E tạo đơn nháp thật trên Gearment (không xác nhận, không mất phí) — cần vào dashboard huỷ. Đợt 06-07 thêm 6 đơn nháp mới (mã 260706P-GM3MUJU-*, danh sách đầy đủ trong tài liệu kiểm thử) | Khi tiện |

> ~~Lấy API key Gearment~~ — **XONG**: key production hoạt động; báo giá + đẩy đơn nháp tự động chạy được từ 2026-07-05.

---

## Đã làm xong (highlights)

- ✅ Kết nối Etsy API 4/5 quyền (2026-05-12)
- ✅ Làm sạch 17.659 đơn cũ + sửa 423 đơn giá $0 + gộp khách trùng
- ✅ Dashboard Đơn hàng + Tracking + Sản xuất (3 dashboard chính)
- ✅ Quy trình duyệt file thiết kế 3 trạng thái + bulk in A4
- ✅ Pipeline 17 trạng thái Việt Nam, cấu hình được
- ✅ Kết nối Gearment + nhận thông báo trạng thái tự động + đẩy file thiết kế kèm đơn
- ✅ Import tracking GKE từ Excel, tự nhận diện carrier
- ✅ Duyệt đổi địa chỉ giao hàng
- ✅ CRM lead từ tin nhắn khách + email alias gom phản hồi
- ✅ Audit log mọi thao tác
- ✅ E2E pipeline (Etsy → Odoo → Gearment → tracking ngược) đã đóng vòng ngày 2026-05-16
- ✅ Đồng bộ danh sách + tồn kho từ Etsy (Story 1.7) — đã go-live 2026-05-23
- ✅ Tự lưu trữ file đã in (Story 2.6) — đã go-live 2026-05-23
- ✅ **Trung tâm sản phẩm + chuẩn hoá SKU + backfill listing Etsy** (Epic 7 — Story 7.1 → 7.5) — đã go-live 2026-05-23
- ✅ **Pilot live publish Etsy JaHandmadeArt thành công** (2026-05-25) — tạo được listing thật trên Etsy, đã sửa 7 lỗi đường biên Etsy 2025 API
- ✅ 4 quy trình Việt Nam (Tạo sản phẩm / Nhập đơn / Giao hàng / Hậu mãi) — tài liệu hoàn chỉnh 2026-05-23
- ✅ **Kiểm thử E2E cả 5 luồng chính trên staging bằng API thật** — Tạo sản phẩm→publish Etsy live, nhận đơn API+email, giao nội bộ (MO→tracking GKE), dropship Gearment (đơn nháp + báo giá thật $12.99), hậu mãi (đổi địa chỉ / in lại / ticket hoàn tiền) (2026-07-04 → 07-05)
- ✅ **Lỗi báo giá Gearment đóng hẳn** — schema đơn nháp + báo giá sửa theo phản hồi live 200 (2026-07-05)
- ✅ Tab "Original Design" lưu file thiết kế gốc trên form sản phẩm + huy hiệu "Design Ready" trên lệnh sản xuất (2026-07-05)
- ✅ Bộ hướng dẫn UAT kèm ảnh chụp màn hình thật (8 tài liệu + PDF hợp nhất) (2026-07-05)

---

## Đang làm tuần này

- 🔄 **Đồng bộ Excel danh mục định kỳ** (Story 7.6) — mô hình dữ liệu xong, đang triển khai parser + cron + tải ảnh
- 🟡 Hotfix nhỏ Gearment payload (đã ổn từ 2026-05-11)

---

## Bị chặn — cần CDA hoặc đối tác bên ngoài

| Story | Bị chặn vì | Người unblock | Ước tính chờ |
|-------|------------|----------------|---------------|
| 1.8 Bật shop pilot | Cần CDA bấm flip switch | CDA | Tuần này |
| 5.5 Etsy scope `conversations_r` | Phải submit lại đơn đăng ký Etsy | CDA | Tuần này → 3-8 tuần Etsy duyệt |
| 5.6 Kéo tin nhắn API | Chờ Story 5.5 | (chuỗi) | Sau 5.5 |

---

## Sắp làm — 3 nhánh đang chờ CDA ưu tiên

CDA chọn 1 trong 3 nhánh (hoặc xếp thứ tự) để dev đẩy tiếp:

**Nhánh A — Hoàn thiện Phase 7 (Trung tâm sản phẩm):**
1. Đồng bộ Excel hàng đêm (Story 7.6 phần parser + cron)
2. Tải ảnh sản phẩm từ Excel (Story 7.6 phần ảnh)

**Nhánh B — Hậu mãi & tài chính:**
1. Bulk-send Gearment (Story 4.7) — cuối tháng 5/2026
2. Xử lý hoàn/refund Etsy + Gearment (Story 4.8)

**Nhánh C — Bổ trợ vận hành (làm song song):**
1. Tự lưu trữ file đã in (Story 2.6) — ✅ vừa xong
2. Auto-chuyển stage MRP (Story 3.6) — giữa tháng 6/2026
3. Việt hoá giao diện (Story 6.8) — tháng 6/2026
4. Dashboard Tài chính (Story 6.4) — tháng 6/2026
5. Mở rộng API 18 shop còn lại (Story 1.9) — tháng 6-7/2026
6. Dashboard Kiểm soát giá (Story 6.5) — tháng 7/2026
7. Health monitoring tile (Story 6.9) — tháng 7/2026
8. Báo cáo email hàng sáng (Story 6.10) — tháng 7-8/2026

> CDA chỉ cần trả lời "A trước" / "B trước" / "C trước" hoặc kết hợp; BA điều phối dev.

---

## Rủi ro hôm nay

| Mức | Rủi ro | Đối tượng cần biết |
|-----|--------|---------------------|
| 🟡 | Etsy chưa duyệt scope `conversations_r` → trễ Phase 5 | CDA |
| 🟡 | CDA chưa lấy được API key Gearment → Phase 4 chưa full automation | CDA |
| 🟡 | Bộ phận chưa quen UI, có thể quay lại Excel | BA + CDA (cần kế hoạch đào tạo) |
| 🟢 | Code đã ổn định, không có lỗi blocker trong 2 tuần qua. Pilot live publish Etsy thành công 2026-05-25. | — |

---

## Cách CDA theo dõi hàng ngày

1. **Mở Jira board:** `https://erptek.atlassian.net/jira/software/projects/ESTY/board`
2. **Lọc theo Epic** để xem từng phase (7 Epic tổng)
3. **Check cột "In Progress"** — biết ai đang làm gì
4. **Check cột "Blocked"** — biết việc gì chờ CDA
5. **Confluence HEP space:** `https://erptek.atlassian.net/wiki/spaces/HEP` — bản tài liệu nghiệp vụ đầy đủ

**Cập nhật file này:** mỗi 2 tuần BA refresh, hoặc khi có thay đổi lớn.

---

*Hết STATUS v1.1 (2026-05-25). Chi tiết yêu cầu xem `SRS_VN.md`. Tổng quan kinh doanh xem `BRD_VN.md`.*
