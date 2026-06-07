# Business flows — sơ đồ + ảnh chụp UAT

**Phiên bản:** 1.0 · **Ngày:** 2026-06-07 · **Đối tượng:** Chủ shop, BA Lead, Đội vận hành

Bộ sơ đồ kiến trúc nghiệp vụ + ảnh chụp màn hình thực tế cho 5 luồng chính
của hệ thống Odoo 19 + Etsy + Gearment.

## Cấu trúc

| Loại | Định dạng | Nguồn |
|---|---|---|
| Sơ đồ luồng (swimlane) | `flow-*.html` (Figma export) | `.0temp/figma/business-flows/` |
| Sơ đồ vai trò | `role-*.html` (Figma export) | `.0temp/figma/business-flows/` |
| Hướng dẫn + ảnh chụp UAT | `flow-*.md` (companion file này) | Playwright UAT artifacts |
| Trang chỉ mục | `index.html` (Figma export) | `.0temp/figma/business-flows/` |

Mỗi `flow-*.md` đi kèm `flow-*.html` để: (a) tham chiếu sơ đồ kiến trúc bất biến,
(b) chèn ảnh chụp UAT thật cho từng giai đoạn của luồng, (c) ghi chú vận hành
tiếng Việt cho người dùng cuối.

## 5 luồng nghiệp vụ

| # | Mã | Tên luồng | Tài liệu |
|---|---|---|---|
| 1 | flow-1 | Tạo sản phẩm + publish lên Etsy | [flow-1-tao-san-pham.md](./flow-1-tao-san-pham.md) + [.html](./flow-1-tao-san-pham.html) |
| 2 | flow-2 | Tiếp nhận đơn hàng Etsy | [flow-2-nhan-don-hang-etsy.md](./flow-2-nhan-don-hang-etsy.md) + [.html](./flow-2-nhan-don-hang-etsy.html) |
| 3a | flow-3a | Giao hàng — In nội bộ | [flow-3a-giao-hang-in-noi-bo.md](./flow-3a-giao-hang-in-noi-bo.md) + [.html](./flow-3a-giao-hang-in-noi-bo.html) |
| 3b | flow-3b | Giao hàng — Gearment dropship | [flow-3b-giao-hang-gearment-dropship.md](./flow-3b-giao-hang-gearment-dropship.md) + [.html](./flow-3b-giao-hang-gearment-dropship.html) |
| 4 | flow-4 | Hậu mãi (đổi/trả/refund) | [flow-4-hau-mai.md](./flow-4-hau-mai.md) + [.html](./flow-4-hau-mai.html) |

## 5 vai trò

| # | Vai trò | Tài liệu |
|---|---|---|
| 1 | BA Lead | [role-1-ba-lead.html](./role-1-ba-lead.html) |
| 2 | Marketing | [role-2-marketing.html](./role-2-marketing.html) |
| 3 | Sản xuất | [role-3-san-xuat.html](./role-3-san-xuat.html) |
| 4 | R&D | [role-4-rd.html](./role-4-rd.html) |
| 5 | Product Development | [role-5-pd.html](./role-5-pd.html) |

## Cách cập nhật ảnh chụp UAT

Ảnh chụp trong các `flow-*.md` được sinh tự động từ test suite Playwright:

```bash
cd tests/e2e
RUN_ETSY_PUBLISH=1 npm run test:wave-2-3
# Sau khi chạy: tests/e2e/artifacts/<spec-name>/*.png
```

Sao chép ảnh chụp đã chọn vào `docs/owner/business-flows/screenshots/<flow-id>/`
và cập nhật đường dẫn `![]()` trong file markdown tương ứng.

## Cập nhật sơ đồ Figma

File `*.html` là bản xuất từ Figma. Khi sơ đồ thay đổi:

1. Mở dự án Figma → frame tương ứng
2. Export → HTML
3. Ghi đè vào `docs/owner/business-flows/<file>.html`
4. Commit chung với mô tả `[docs] chore: re-export business-flows from Figma`

## Tham chiếu chéo

- Tài liệu nghiệp vụ chi tiết: `docs/owner/FLOW_*_VN.md`
- Hướng dẫn thao tác từng bước: `docs/owner/HUONG_DAN_*_VN.md`
- UAT walkthrough (kịch bản kiểm thử): `docs/owner/UAT_WALKTHROUGH_*_VN.md`
- Playwright tests: `tests/e2e/tests/uat_*.spec.ts`
