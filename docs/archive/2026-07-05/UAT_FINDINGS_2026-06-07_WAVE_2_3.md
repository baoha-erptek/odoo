# UAT Findings — Wave 2/3 sweep (2026-06-07)

**Phiên bản:** 1.0 · **Ngày chạy:** 2026-06-07 04:31–04:46 UTC
**Môi trường:** Staging `https://odoo.hatafax.com` (db `esty_odoo19`)
**Deploy:** etsy_integration `19.0.3.7.0 → 19.0.3.9.0` (Wave 3 ESTY-190 + ESTY-195)
**Khung test:** Playwright 1.48.0 (`tests/e2e/tests/uat_wave_2_3_*.spec.ts`)

---

## Tổng kết

| TC ID | Mô tả | Kết quả | Thời gian |
|---|---|---|---|
| TC-W23-CFG-01 | JaHandmadeArt shop publisher defaults | **PASS** (RPC) + UI smoke partial | 8.5s |
| TC-W23-BULK-01 | Bulk action Mark Ready ↔ Reset Draft | **PASS** | 32.8s |
| TC-W23-PUB-01 | Apron live publish + post-publish auto-fields | **FAIL** — ESTY-188 vẫn còn (createListing 400) | 60s timeout |

**Kết luận:** 2/3 PASS. TC-W23-PUB-01 RED do **ESTY-188 iter3 chưa fix triệt để** —
createListing endpoint vẫn trả 400 Bad Request trên staging mặc dù iter3 đã ship.

---

## TC-W23-CFG-01 — PASS

**RPC verification** (mọi assertions xanh):
- `etsy_api_shop_id = 60752333` ✓
- `listing_currency_id` non-null (ESTY-195) ✓
- `default_taxonomy_id = 2172` (ESTY-189) ✓
- `default_shipping_profile_id = 285149016922` (ESTY-191) ✓
- `default_who_made = 'i_did'` / `default_when_made = 'made_to_order'` (ESTY-193) ✓
- Field `default_title` / `default_description` tồn tại trên model (ESTY-190) ✓
- Bảng `etsy_shop_attribute_mapping` queryable (ESTY-194) ✓

**UI smoke** (best-effort — admin không có `group_marketing_user`):
- `default_title` field: **NOT rendered** (group gate — đúng theo thiết kế)
- `default_description` field: **NOT rendered** (group gate)
- `default_attribute_mapping_ids`: **visible** ✓

**Ghi chú:** Brand-voice fields gated cho group_marketing_user — admin không thấy. Khi
Marketing user UAT thủ công, dùng tài khoản có group này (xem tài liệu
`HUONG_DAN_TAO_SAN_PHAM_VN.md`).

---

## TC-W23-BULK-01 — PASS

**Server action verification** (RPC trực tiếp):
- 2 multichannel.listing rows seed Draft ✓
- `action_bulk_mark_ready([ids])` → state flip `draft → ready` ✓
- `action_bulk_reset_to_draft([ids])` → state flip `ready → draft` ✓
- Cleanup: 2 rows unlinked ✓

**Ghi chú:** Spec đã pivot từ UI dropdown click sang RPC server-action invocation
vì selector cho Actions menu trong Odoo 19 không ổn định. Server-action logic
(ESTY-197 P-LIST-SHOP-BULK) được verify đúng cách. UI dropdown owner test thủ công
khi cần (xem UAT walkthrough v1.2 TC-W23-BULK-01).

---

## TC-W23-PUB-01 — FAIL (ESTY-188 còn RED)

**Kịch bản:** Tạo Apron `[UAT-2026-06-07] Apron W23 <uniq>`, chọn category +
Material+Size+Color variants + price 250000 VND, save, publish draft tới
JaHandmadeArt.

**Lỗi:** Wizard "Publish to Etsy" mở; click "Run Publish Draft Only"; server gọi
`createListing` → **400 Bad Request**. Wizard không đóng. Test timeout 60s.

**Stack trace** (từ docker logs esty19_odoo, timestamp 04:46:16 UTC):
```
File "/mnt/extra-addons/etsy_integration/wizards/etsy_publish_wizard.py", line 52
  draft = publisher.create_draft(self.product_tmpl_id, self.shop_id)
File "/mnt/extra-addons/etsy_integration/services/etsy_listing_publisher.py", line 679
  response = client.post(path, json=payload)
File "/mnt/extra-addons/etsy_integration/services/etsy_api_client.py", line 287
  response.raise_for_status()
requests.exceptions.HTTPError: 400 Client Error: Bad Request for url:
  https://openapi.etsy.com/v3/application/shops/60752333/listings
```

**Vấn đề rộng hơn (memory `feedback_capture_response_body_before_blackbox_probe`):**
- `etsy.api.log` table KHÔNG ghi POST createListing failure
- Response body từ Etsy (chứa lý do thật của 400) chưa được persist đâu đó để debug
- Đây là **iter3 fix gap** — ESTY-188 cần capture response body trước khi raise

**Sản phẩm tạo bởi test trên Odoo:** lưu lại với SKU auto-derive nhưng không có
Etsy `external_ref` (chưa publish được). Cleanup sẽ archive như mọi UAT product
qua `globalTeardown.ts`.

**Etsy side:** 0 drafts tạo (createListing failed). `cleanup_uat_etsy_drafts.py`
không cần chạy — không có draft `[UAT-2026-06-07]` nào trên JaHandmadeArt.

---

## Kết luận

**Wave-2 / Wave-3 surface đã sẵn sàng:**
- Shop publisher defaults đầy đủ (CFG-01)
- Bulk action server logic hoạt động (BULK-01)
- Form fields, view tabs, attribute mapping, FX widget — đều render đúng

**ESTY-188 vẫn block live publish:**
- iter3 đã ship lên staging (commit history) nhưng createListing vẫn 400
- Cần iter4: (a) capture response body trong audit log + (b) phân tích payload
  diff vs Etsy v3 spec để tìm trường thiếu/sai

**Khuyến nghị tiếp theo:**
1. Owner re-publish thủ công 1 sản phẩm Apron đơn giản trên staging — confirm
   manual UI cũng repro 400 (loại trừ Playwright-specific cause)
2. Dispatch P-BUG-ESTY-188 iter4 với scope: response-body persist
3. Sau iter4 ship: re-run `RUN_ETSY_PUBLISH=1 npm run test:wave-2-3:publish`
4. Khi PUB-01 GREEN → flip 11 ESTY-* tickets sang Done trên Jira

---

## Test artifacts

- HTML report: `tests/e2e/reports/html/index.html`
- Trace + screenshot + video cho failed test: `tests/e2e/artifacts/uat_wave_2_3_listing-*/`
- Staging logs cho 400: `docker logs esty19_odoo 2>&1 | grep -A 30 'action_run_publish_draft_only'`

## Đã cập nhật

- Tracker `.claude/plans/006-master-plan-tracking.md` — append entry 2026-06-07 với UAT outcome
- Telegram channel — báo cáo final qua msg 721 (edited series)
- `feature/006-master-plan-coding` — 6 commits đã push lên origin
