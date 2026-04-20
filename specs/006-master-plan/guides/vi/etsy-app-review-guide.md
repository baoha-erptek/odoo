# Hướng dẫn đăng ký App Etsy + xin duyệt scope (API v3)

**Dành cho**: Chủ doanh nghiệp (owner) — người sở hữu tài khoản Etsy chính
**Mục đích**: Đăng ký ứng dụng Etsy API v3 và nộp hồ sơ xin duyệt các scope cần thiết để hệ thống đồng bộ đơn hàng trực tiếp qua API (thay cho email parsing).
**Thời gian thực tế**: 30–60 phút để nộp + chờ Etsy duyệt 3–8 tuần
**Liên quan**: [ADR-008 API-first pivot](../../adrs/ADR-008-api-first-pivot.md), [Spec 005 Etsy API channel](../../../005-etsy-api-channel/spec.md)

---

## Vì sao phải làm việc này?

Hiện tại hệ thống lấy đơn hàng Etsy bằng cách đọc email (parse 43 regex khác nhau). Cách này đã sai 423 lần trên 17,659 đơn hàng hiện có — không ổn định, không lấy được email khách hàng thật, không đẩy tracking lên Etsy được.

Quyết định 2026-04-13 (ADR-008): chuyển **toàn bộ** đơn hàng mới sang sync trực tiếp qua Etsy API. Email parsing chỉ giữ cho các shop cũ trong giai đoạn chuyển tiếp (cutover 1 shop/lần, có audit log 1–2 tuần).

**Điều kiện bắt buộc để triển khai**: Etsy phải duyệt các scope của ứng dụng. Bước duyệt này là **phụ thuộc ngoài hệ thống**, mất 3–8 tuần, không tăng tốc được. Càng nộp sớm càng tốt.

---

## Tổng quan các bước

1. Đăng nhập Etsy developer portal
2. Tạo ứng dụng (App) mới — sau này dùng chung cho production
3. Ghi lại Keystring (API key) và Shared secret — KHÔNG chia sẻ
4. Nộp hồ sơ xin duyệt 6 scope chính + 1 scope tuỳ chọn
5. Mô tả rõ use case cho từng scope (quan trọng — Etsy đọc kỹ)
6. Theo dõi trạng thái hồ sơ hàng tuần
7. Khi được duyệt, gửi Keystring cho đội dev

---

## Bước 1 — Đăng nhập Etsy developer portal

- Truy cập: https://www.etsy.com/developers/
- Đăng nhập bằng **chính tài khoản Etsy chủ shop** (không dùng tài khoản phụ — app sẽ gắn vĩnh viễn với user này)
- Nếu chưa có developer profile, Etsy sẽ yêu cầu bổ sung: họ tên đầy đủ, email liên hệ, quốc gia, mô tả ngắn lý do dùng API

---

## Bước 2 — Tạo App mới

1. Bấm **Create a New App** (hoặc **Your Apps** → **Create a New App**)
2. Điền thông tin:

| Trường | Giá trị đề xuất |
|---|---|
| **App name** | `Multichannel Hub for Esty Namco` (hoặc tên nội bộ dễ nhận biết) |
| **Primary business** | Tên công ty thật (in hoá đơn, ký hợp đồng) |
| **Website URL** | URL thật của công ty hoặc trang landing của Odoo (không để `localhost`) |
| **Application description** | Xem mẫu mô tả bên dưới |
| **What best describes how you plan to use the API?** | *Internal business tool — integrate Etsy shops with internal ERP (Odoo) for order fulfilment, inventory, and tracking.* |
| **Will you use the API to transact orders or act on behalf of other Etsy sellers?** | Chọn **"Only the shops I own"** (không phải multi-tenant) |

### Mẫu App description (copy thẳng, chỉnh nếu cần)

```
Multichannel Hub is an internal Odoo-based order management system that
integrates 19 Etsy shops owned by the same company. The app will:

1. Ingest new orders (receipts) from each shop via the Etsy API v3, replacing
   our legacy email-based order parser which has reliability issues.
2. Update tracking numbers on Etsy receipts as soon as our logistics partner
   (GKE) provides the tracking code — eliminating 2+ hours/day of manual
   entry on the Etsy Seller Portal.
3. Read listing metadata to keep our internal product catalog in sync.
4. Monitor shop-level order status and payment status.

The system is strictly internal — no public-facing features, no end-user
sign-ups, no data resale. All shops are owned by our company. Current order
volume: 17,659 historical orders across 19 shops; daily new orders average
~50. Target production rollout: Q3 2026.
```

3. Bấm **Submit App**
4. Etsy hiển thị **Keystring** (API key) và **Shared secret**
5. **BẮT BUỘC**: copy cả hai giá trị, lưu vào password manager (Bitwarden/1Password). Không lưu trong Google Docs, không gửi qua chat.

---

## Bước 3 — Xác định các scope cần xin duyệt

Etsy API v3 yêu cầu mỗi scope phải được duyệt riêng. Danh sách cần nộp:

| Scope | Bắt buộc? | Dùng để | Nếu bị từ chối |
|---|---|---|---|
| `transactions_r` | **Bắt buộc** | Đọc đơn hàng (receipts) | Không sync được đơn → block toàn bộ |
| `transactions_w` | **Bắt buộc** | Đẩy tracking lên Etsy | Mất tính năng push tracking (US3) — vẫn sync được đơn |
| `listings_r` | **Bắt buộc** | Đọc thông tin listing (để khớp sản phẩm) | Matching sản phẩm phải làm thủ công qua tên |
| `listings_w` | Khuyến nghị | Tạo/sửa listing từ Odoo | Mất tính năng quản lý listing (US6) |
| `shops_r` | **Bắt buộc** | Đọc thông tin shop (country, policy) | Không xác định được cấu hình shop |
| `email_r` | **Bắt buộc** | Lấy email khách hàng thật | Mất khả năng dedup khách theo email (data quality kém) |
| `conversations_r` | Tuỳ chọn | Đọc tin nhắn khách với shop | Chấp nhận, đã được đánh dấu defer trong [Spec 005 US7](../../../005-etsy-api-channel/spec.md) |

**Chiến thuật**: nộp cả 7 scope cùng lúc. Etsy có thể duyệt từng scope riêng — nếu `conversations_r` bị từ chối vẫn tiếp tục được vì đã có phương án dự phòng.

---

## Bước 4 — Nộp hồ sơ xin duyệt scope

Trong trang **Your Apps** → chọn app vừa tạo → tab **Scopes** → bấm **Request Additional Scopes**.

Với mỗi scope, Etsy yêu cầu **mô tả cụ thể use case**. Dưới đây là các mẫu đã viết sẵn — copy nguyên văn vào từng ô:

### `transactions_r` — Read orders

```
Required to ingest new orders (receipts) into our internal Odoo ERP. We
replace a legacy email-based parser that has a 2.4% failure rate on receipt
ID extraction. The API provides the canonical receipt_id, buyer email,
transaction details, shipping address, and item-level data we need to create
sale orders in Odoo for our fulfilment pipeline.
```

### `transactions_w` — Write tracking to orders

```
Required to update tracking numbers on shipped receipts. Our logistics
partner (GKE) provides the tracking code via daily Excel upload. We push
the tracking code and carrier name to the Etsy receipt as soon as it is
entered in Odoo so buyers see tracking in their Etsy purchase history
without manual entry on the Seller Portal. This saves our fulfilment team
approximately 2 hours per day.
```

### `listings_r` — Read listings

```
Required to match inbound receipts to our internal product catalog by the
Etsy listing_id. The listing_id is stable and unique, whereas the listing
title can vary (translations, seasonal renames). Reading listings also
syncs price and listing state (active/sold-out/expired) into Odoo for our
pricing audit dashboard.
```

### `listings_w` — Write listings

```
Required to create draft listings from Odoo product records and to push
on-demand price or quantity updates to Etsy. Writes are never automatic —
they are triggered by a user action in Odoo and go through a review step
before calling the API. This scope is not on the critical path; if denied
we will keep listing management manual on the Etsy portal.
```

### `shops_r` — Read shop info

```
Required to read the shop country, currency, and shipping policies for
each of our 19 shops during onboarding and reconciliation. Read-only data
used for configuration display inside Odoo.
```

### `email_r` — Read buyer email

```
Required to store the canonical buyer email on each sale order in Odoo.
This enables customer deduplication across our 17,659 historical orders
(currently 0% dedup because email parsing cannot extract buyer email from
Etsy notification emails). Email is stored only on the order record;
no marketing use, no export, no resale.
```

### `conversations_r` — Read buyer conversations (optional)

```
Required to surface buyer-shop conversations inside Odoo so customer-service
staff do not switch contexts between Etsy and Odoo. Read-only — we do not
ask for write access. If not granted, customer service continues to use
the Etsy portal directly; this does not block our core integration.
```

---

## Bước 5 — Callback URL (Redirect URI)

Etsy cần một **Redirect URI** để hoàn tất OAuth2 flow. Điền:

| Giá trị | Dùng cho |
|---|---|
| `https://staging.namco-odoo.internal/etsy/oauth/callback` | Môi trường staging (`129.150.63.207`) |
| `https://prod.namco-odoo.internal/etsy/oauth/callback` | Môi trường production (chờ bộ phận ops cung cấp domain) |

Có thể thêm nhiều URI — Etsy cho phép. Nếu chưa có domain production, tạm điền staging trước; bổ sung production sau (không cần xin duyệt lại).

**Lưu ý**: Etsy bắt buộc HTTPS. URL dạng `http://localhost` chỉ chấp nhận trong chế độ Development Mode.

---

## Bước 6 — Submit + theo dõi

1. Review lại toàn bộ form
2. Bấm **Submit for review**
3. Etsy gửi email xác nhận kèm **ticket ID** — lưu ticket ID vào file `.claude/plans/006-master-plan-tracking.md` dòng **E1**
4. Hồ sơ chuyển sang trạng thái **Pending Review**

### Theo dõi trạng thái (hàng tuần)

- Vào **Your Apps** → **Scope Requests** → xem cột Status
- Trạng thái có thể:
  - `Pending Review` — đang chờ
  - `Approved` — đã duyệt (có thể duyệt từng scope một)
  - `More Info Requested` — Etsy yêu cầu bổ sung — **trả lời trong 72 giờ** để không bị close ticket
  - `Denied` — bị từ chối (hiếm nếu mô tả use case rõ ràng)

### Nếu sau 4 tuần vẫn `Pending Review`

1. Gửi email tới `developers@etsy.com` kèm ticket ID, hỏi status
2. Nếu sau 6 tuần vẫn không có phản hồi, đăng thread trên Etsy Developer Forum (https://www.etsy.com/developers/forum) — Etsy staff thường phản hồi trong vòng 3–5 ngày trên forum
3. Nếu cần leo thang, liên hệ qua https://help.etsy.com/ với subject *"API scope review delayed more than 6 weeks — ticket ID [XXX]"*

---

## Bước 7 — Khi được duyệt

1. Email từ Etsy xác nhận các scope đã được duyệt (có thể duyệt từng scope một — kiểm tra từng dòng)
2. Thông báo cho đội dev qua kênh nội bộ — **kèm các thông tin sau**:
   - Keystring (API key) — chia sẻ qua password manager, không qua chat
   - Shared secret — tương tự
   - Danh sách scope đã được duyệt
   - Redirect URI đang active
3. Cập nhật file tracking dòng **E1**: status `done`, ngày duyệt
4. Đội dev bắt đầu **Phase 1 cutover** — xem [tracking doc P1-10, P1-11, P1-12, P1-13](../../../../.claude/plans/006-master-plan-tracking.md)

---

## Checklist nhanh (tick khi hoàn tất)

- [ ] Đăng nhập Etsy developer portal bằng tài khoản chủ shop chính
- [ ] Tạo App mới, điền đủ thông tin bắt buộc
- [ ] Copy + lưu Keystring và Shared secret vào password manager
- [ ] Nộp hồ sơ xin duyệt 7 scope (6 bắt buộc + 1 tuỳ chọn)
- [ ] Điền mô tả use case rõ ràng cho từng scope
- [ ] Thêm Redirect URI cho staging + production
- [ ] Submit + lưu ticket ID
- [ ] Cập nhật dòng E1 trong `.claude/plans/006-master-plan-tracking.md`
- [ ] Đặt lịch ping hàng tuần (thứ Hai) để check status

---

## Câu hỏi thường gặp (FAQ)

**Q: Nộp tài khoản phụ có được không?**
A: Không nên. App gắn vĩnh viễn với user tạo. Nếu tài khoản phụ bị xoá, app cũng mất.

**Q: Có cần verified business không?**
A: Không. Individual developer account là đủ.

**Q: Có phí không?**
A: Không. Etsy API v3 miễn phí, chỉ giới hạn rate limit (~10 requests/giây, ~5000 requests/ngày/shop).

**Q: Sau khi được duyệt, có cần xin lại khi thêm shop mới không?**
A: Không. Một app duyệt 1 lần, dùng cho tất cả shop mà user hiện tại sở hữu. Chỉ cần thêm OAuth authorization cho shop mới.

**Q: Nếu chỉ được duyệt 5/7 scope, có chạy được không?**
A: Có. Nếu đủ 6 scope bắt buộc (`transactions_r/w`, `listings_r`, `shops_r`, `email_r`), hệ thống chạy đầy đủ tính năng P1. Mất `listings_w` → quản lý listing thủ công. Mất `conversations_r` → đã lên kế hoạch defer.

**Q: Etsy có thể thu hồi scope đã duyệt không?**
A: Có — nếu vi phạm ToS hoặc app không hoạt động 12 tháng. Không ảnh hưởng đến use case bình thường.

---

**Khi xong bước này → chuyển sang**: [Hướng dẫn Gearment sandbox](gearment-sandbox-guide.md)
