# Hướng dẫn xin credentials Gearment sandbox

**Dành cho**: Chủ doanh nghiệp (owner) — người ký hợp đồng với Gearment
**Mục đích**: Lấy credentials API của môi trường sandbox (test) từ Gearment để đội dev chạy POC 3 ngày xác thực các tính năng đặt hàng, rate limit, HMAC webhook trước khi code tích hợp production.
**Thời gian thực tế**: 15–30 phút gửi email + 1–5 ngày chờ Gearment phản hồi
**Liên quan**: [MASTER_PLAN Phase 0 — Gearment sandbox POC](../../MASTER_PLAN.md), [ADR-001 Spec 004 split](../../adrs/ADR-001-spec-004-split.md), Spec 004b (Gearment adapter — sẽ tạo sau POC)

---

## Vì sao phải làm việc này?

Gearment là **đối tác fulfillment chính** — đặt hàng POD (print-on-demand) và xử lý toàn bộ khâu sản xuất + vận chuyển quốc tế. Hệ thống Odoo sẽ gọi Gearment API v3 để:

1. Tạo đơn hàng (draft) từ đơn Etsy vừa sync về
2. Lấy báo giá (quote)
3. Xác nhận đặt hàng (confirm) để Gearment bắt đầu sản xuất
4. Nhận webhook khi đơn chuyển trạng thái (produced / shipped)

**Rủi ro hiện tại**: Tài liệu Gearment API v3 rất ít công khai. Chúng ta chưa biết:
- Auth mechanism (API key / OAuth / HMAC header?)
- Rate limit thực tế (requests/second, requests/day)
- Format của HMAC signature trên webhook
- Các state hợp lệ của đơn hàng và chuyển trạng thái
- Idempotency key (để retry an toàn)

Chạy POC 3 ngày trong sandbox trước khi viết code production giúp phát hiện các bất ngờ sớm. Nếu chờ đến khi code production rồi mới test thì rủi ro rework cao.

---

## Tổng quan các bước

1. Xác định contact point phù hợp tại Gearment
2. Soạn email xin credentials sandbox (mẫu bên dưới)
3. Gửi email + theo dõi
4. Nhận credentials + lưu an toàn
5. Bàn giao cho đội dev

---

## Bước 1 — Xác định contact tại Gearment

- Nếu đã có **Account Manager** riêng ở Gearment (thường là người ký hợp đồng ban đầu): gửi thẳng cho họ
- Nếu không: gửi đến **support@gearment.com** (kèm CC cho account manager nếu có)
- Kênh phụ: Skype / Zalo của account manager (nhanh hơn nhưng phải email lại để có giấy tờ)

**Thông tin cần nắm trước khi gửi**:
- Mã khách hàng (Customer ID) tại Gearment — tra trong dashboard Gearment hoặc hợp đồng
- Số hợp đồng / tên công ty đang dùng dịch vụ
- Email/số điện thoại đăng ký với Gearment

---

## Bước 2 — Mẫu email xin credentials sandbox

Subject:

```
[API Sandbox] Yêu cầu cấp credentials sandbox cho tích hợp Odoo ERP - Customer ID [XXX]
```

Body (điều chỉnh các phần trong `{{...}}`):

```
Kính gửi team Gearment,

Công ty {{Tên công ty}} (Customer ID: {{Mã KH}}) hiện đang triển khai
hệ thống ERP nội bộ trên nền tảng Odoo 19 để tự động hoá luồng đơn hàng
từ Etsy → ERP → Gearment.

Để tích hợp API v3 của Gearment một cách an toàn, chúng tôi cần chạy
giai đoạn Proof of Concept (POC) trong môi trường sandbox trước khi đi
production. Dự kiến POC kéo dài 3 ngày, tập trung vào 4 nội dung chính:

1. Xác thực authentication mechanism (API key hoặc OAuth2)
2. Đo rate limit thực tế (requests/second và requests/day)
3. Xác thực format HMAC signature trên webhook
4. Kiểm thử idempotency key cho luồng draft → quote → confirm

Để hoàn tất POC, đề nghị Gearment cung cấp:

A. Credentials sandbox:
   - API base URL của môi trường sandbox (nếu khác production)
   - API key / Client ID + Client secret (tuỳ cơ chế Gearment đang dùng)
   - Shared secret cho HMAC webhook signing (nếu có)
   - Customer ID sandbox (nếu tách riêng với production)

B. Tài liệu:
   - API v3 reference (endpoints, request/response schemas)
   - Webhook specification (event types, payload format, retry policy)
   - Rate limit documentation (per-second, per-day, per-endpoint nếu khác nhau)
   - Danh sách state hợp lệ của đơn hàng và sơ đồ state transition

C. Webhook callback URL từ phía chúng tôi:
   - Staging:    https://staging.namco-odoo.internal/gearment/webhook
   - Production: (sẽ cung cấp sau khi provision xong)

D. Thông tin hỗ trợ:
   - Technical contact tại Gearment cho giai đoạn POC (Skype/Zalo càng tốt)
   - Kênh báo lỗi/hỏi đáp ưu tiên trong 3 ngày POC

Sau khi POC kết thúc, chúng tôi sẽ gửi lại báo cáo kết quả kèm các phản hồi
và câu hỏi kỹ thuật nếu có. Credentials production sẽ xin sau khi Gearment
duyệt báo cáo.

Mong nhận được phản hồi trong vòng 3 ngày làm việc để không ảnh hưởng
tới timeline triển khai.

Trân trọng cảm ơn,
{{Tên}} - {{Chức danh}}
{{Tên công ty}}
{{Email liên hệ}}
{{Số điện thoại}}
```

---

## Bước 3 — Gửi email + theo dõi

1. Gửi email theo template trên
2. Lưu ngày gửi vào file `.claude/plans/006-master-plan-tracking.md` dòng **E2**
3. Nếu sau 3 ngày làm việc chưa có phản hồi:
   - Ping qua Skype/Zalo account manager
   - Nhắc nhở bằng reply "up" lịch sự lên email cũ
4. Nếu sau 5 ngày làm việc vẫn không phản hồi:
   - Leo thang lên account manager cấp cao hơn hoặc CEO Gearment nếu đã từng tiếp xúc
   - Ghi chú vào tracking doc để master plan biết rủi ro trễ Phase 0

---

## Bước 4 — Khi nhận được credentials

Gearment sẽ gửi credentials qua **một trong các kênh sau** (theo thứ tự ưu tiên an toàn):

1. **Email mã hoá / password-protected ZIP** — tốt nhất
2. **Link 1lần (one-time secret)** — OK
3. **Email thông thường** — không an toàn nhưng thường gặp
4. **Skype/Zalo** — không an toàn, yêu cầu họ gửi lại qua email để có giấy tờ

### Phải làm ngay khi nhận:

1. **Copy credentials vào password manager** (Bitwarden/1Password) dưới entry `Gearment Sandbox`
2. **Xoá email/tin nhắn gốc** chứa credentials sau khi đã lưu an toàn
3. **Không** copy vào Google Docs / Slack / Notion / Telegram
4. **Không** commit vào Git (kể cả file `.env` — đội dev sẽ inject qua Odoo config parameter, không qua repo)

### Thông tin bàn giao cho đội dev

Gửi qua kênh nội bộ có mã hoá (1Password shared vault / Bitwarden send). Kèm các mục:

- [ ] API base URL sandbox
- [ ] API key / Client ID + Client secret
- [ ] Shared secret cho HMAC webhook
- [ ] Customer ID sandbox
- [ ] URL tài liệu API reference
- [ ] URL webhook specification
- [ ] Tên + contact của technical contact tại Gearment
- [ ] Link share toàn bộ tài liệu Gearment gửi kèm

---

## Bước 5 — POC timeline

Sau khi bàn giao, đội dev sẽ chạy POC theo lịch:

| Ngày | Nội dung POC |
|---|---|
| 1 | Auth flow + "hello world" API call, xác nhận credentials hoạt động |
| 2 | Tạo draft + quote + confirm một đơn test, đo thời gian xử lý + rate limit |
| 3 | Đăng ký webhook, gửi event giả, verify HMAC signature, test retry |

Báo cáo POC sẽ được ghi vào `specs/006-master-plan/agent-reports/gearment-poc-report.md` (tạo khi POC kết thúc). Kết quả POC quyết định scope cụ thể của [Spec 004b](../../../004-fulfillment-routing/) — nếu phát hiện rủi ro nghiêm trọng (ví dụ API không có idempotency), có thể cần thay đổi thiết kế Gearment adapter.

---

## Checklist nhanh (tick khi hoàn tất)

- [ ] Xác định contact point tại Gearment (account manager / support email)
- [ ] Kiểm tra lại Customer ID + tên công ty đang dùng dịch vụ
- [ ] Gửi email theo template — ghi ngày gửi vào tracking doc E2
- [ ] Theo dõi sau 3 ngày làm việc; leo thang nếu cần
- [ ] Nhận credentials — lưu password manager, xoá bản gốc
- [ ] Bàn giao credentials + tài liệu cho đội dev qua kênh mã hoá
- [ ] Cập nhật tracking doc E2 status `done`, ngày nhận credentials
- [ ] Đội dev xác nhận đã đủ input → khởi động POC 3 ngày

---

## Câu hỏi thường gặp (FAQ)

**Q: Gearment không có môi trường sandbox riêng thì sao?**
A: Hỏi thẳng: "Nếu Gearment không có sandbox riêng, có thể cung cấp một test customer ID với đơn hàng mock (không thực sự in/ship) để POC không? Hoặc một chính sách cho phép cancel đơn test trong 24h không bị tính phí?" — Nhiều nhà cung cấp POD có workaround dạng này.

**Q: Bị từ chối cấp sandbox — chỉ có production thì sao?**
A: Ghi rủi ro vào MASTER_PLAN §5 và thảo luận với đội dev. Có thể phải chạy POC trên 1–2 đơn production nhỏ giá thấp, chấp nhận rủi ro in thật. Ghi rõ trong tracking doc E2.

**Q: Nếu Gearment thay đổi API giữa POC và production cutover?**
A: Xin cam kết stability (ví dụ "không breaking change trong 6 tháng tới") trong email trao đổi. Lưu email làm bằng chứng. Nếu Gearment có versioning (v3, v4), yêu cầu được pin v3.

**Q: POC có mất phí không?**
A: Sandbox thường miễn phí. Nhưng xác nhận trước khi gửi đơn test — một số nhà cung cấp tính phí hoặc trừ vào deposit.

**Q: Thời gian 3 ngày POC có đủ không?**
A: Đủ cho scope hiện tại (auth + đơn đơn giản + 1 webhook). Nếu POC phát hiện vấn đề lớn, có thể xin thêm 2 ngày — đội dev sẽ cập nhật tracking doc nếu cần.

---

**Khi đã có cả credentials Etsy (đã duyệt scope) và Gearment sandbox → bắt đầu Phase 0 code**: xem [execution tracker P0-14 → P0-18](../../../../.claude/plans/006-master-plan-tracking.md).
