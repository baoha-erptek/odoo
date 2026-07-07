# Business flows — sơ đồ + ảnh chụp UAT

> **Bản mới nhất: [`v3/`](./v3/index.html) (2026-07-05)** — ảnh chụp thật từ hệ thống
> đã lên giao diện Hatafa mới (menu Vận hành, thẻ KPI, tiếng Việt). Các file `flow-*`
> ở thư mục gốc là companion markdown; các mockup HTML cũ (`v2/`, `v2-uiux-improved/`
> và bản export ở thư mục gốc) đã được archive sau khi v3 lên live.

**Phiên bản:** 1.1 · **Ngày:** 2026-07-05 · **Đối tượng:** Chủ shop, BA Lead, Đội vận hành

Bộ sơ đồ kiến trúc nghiệp vụ + ảnh chụp màn hình thực tế cho 5 luồng chính
của hệ thống Odoo 19 + Etsy + Gearment.

## Cấu trúc

| Loại | Định dạng | Nguồn |
|---|---|---|
| Site luồng hiện hành | `v3/flow-*.html` | bộ site owner hiện hành |
| Site vai trò hiện hành | `v3/role-*.html` | bộ site owner hiện hành |
| Hướng dẫn + ảnh chụp UAT | `flow-*.md` (companion file này) | Playwright UAT artifacts |
| Trang chỉ mục hiện hành | `v3/index.html` | bộ site owner hiện hành |

Mỗi `flow-*.md` đi kèm trang `v3/flow-*.html` tương ứng để: (a) tham chiếu sơ đồ kiến trúc hiện hành,
(b) chèn ảnh chụp UAT thật cho từng giai đoạn của luồng, (c) ghi chú vận hành
tiếng Việt cho người dùng cuối.

## 5 luồng nghiệp vụ

| # | Mã | Tên luồng | Tài liệu |
|---|---|---|---|
| 1 | flow-1 | Tạo sản phẩm + publish lên Etsy | [flow-1-tao-san-pham.md](./flow-1-tao-san-pham.md) + [v3](./v3/flow-1-tao-san-pham.html) |
| 2 | flow-2 | Tiếp nhận đơn hàng Etsy | [flow-2-nhan-don-hang-etsy.md](./flow-2-nhan-don-hang-etsy.md) + [v3](./v3/flow-2-nhan-don-hang-etsy.html) |
| 3a | flow-3a | Giao hàng — In nội bộ | [flow-3a-giao-hang-in-noi-bo.md](./flow-3a-giao-hang-in-noi-bo.md) + [v3](./v3/flow-3a-giao-hang-in-noi-bo.html) |
| 3b | flow-3b | Giao hàng — Gearment dropship | [flow-3b-giao-hang-gearment-dropship.md](./flow-3b-giao-hang-gearment-dropship.md) + [v3](./v3/flow-3b-giao-hang-gearment-dropship.html) |
| 4 | flow-4 | Hậu mãi (đổi/trả/refund) | [flow-4-hau-mai.md](./flow-4-hau-mai.md) + [v3](./v3/flow-4-hau-mai.html) |

## 5 vai trò

| # | Vai trò | Tài liệu |
|---|---|---|
| 1 | BA Lead | [v3/role-1-ba-lead.html](./v3/role-1-ba-lead.html) |
| 2 | Marketing | [v3/role-2-marketing.html](./v3/role-2-marketing.html) |
| 3 | Sản xuất | [v3/role-3-san-xuat.html](./v3/role-3-san-xuat.html) |
| 4 | R&D | [v3/role-4-rd.html](./v3/role-4-rd.html) |
| 5 | Product Development | [v3/role-5-pd.html](./v3/role-5-pd.html) |

## Cách cập nhật ảnh chụp UAT

Ảnh chụp trong các `flow-*.md` được sinh tự động từ test suite Playwright:

```bash
cd tests/e2e
RUN_ETSY_PUBLISH=1 npm run test:wave-2-3
# Sau khi chạy: tests/e2e/artifacts/<spec-name>/*.png
```

Sao chép ảnh chụp đã chọn vào `docs/owner/business-flows/screenshots/<flow-id>/`
và cập nhật đường dẫn `![]()` trong file markdown tương ứng.

## Cập nhật site v3

Khi site owner hiện hành thay đổi:

1. Mở dự án Figma → frame tương ứng
2. Export → HTML
3. Ghi đè vào `docs/owner/business-flows/v3/<file>.html`
4. Commit chung với mô tả `[docs] chore: refresh business-flows v3 site`

## Tham chiếu chéo

- Tài liệu nghiệp vụ chi tiết: `docs/owner/FLOW_*_VN.md`
- Hướng dẫn thao tác từng bước: `docs/owner/HUONG_DAN_*_VN.md`
- Checklist UAT hiện hành: trong `docs/owner/HUONG_DAN_*_VN.md` (mục checklist của từng luồng)
- Playwright tests: `tests/e2e/tests/uat_*.spec.ts`
