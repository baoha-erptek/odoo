# UAT Findings — 2026-05-26

**Người chạy:** Playwright UAT script (tests/e2e/)
**Môi trường:** `https://odoo.hatafax.com` · DB `esty_odoo19`
**Phạm vi:** ESTY-183 — `HUONG_DAN_TAO_SAN_PHAM_VN.md` TC-001..TC-007
**Status:** Findings open, awaiting owner decisions

---

## Tổng kết Pass/Fail

| TC | Mô tả | Result | Note |
|---|---|---|---|
| TC-001 | BA Lead tạo SP Mug bằng Wizard | ✅ Pass | Product 19 archived after run |
| TC-002 | SP có Mã Gearment → Dropship | ✅ Pass | Product 18 archived after run |
| TC-003 | SKU drift "Keep Legacy" | ⏸ Skip | Cần seed product non_canonical trước |
| TC-004 | SKU drift "Accept Canonical" + Etsy push | ⏸ Skip | Cần product đã publish Etsy + sandbox shop |
| TC-005 | Đăng SP lên Etsy (Draft) | ⏸ Skip | Tạo Etsy listing thực — chạy riêng |
| TC-006 | BA User & Publish button | ⚠️ **Finding** | Xem Finding F1 dưới |
| TC-007 | Validator giá > 0 | ✅ Pass | Modal "Listing Price must be greater than 0" |

**Net:** 3/7 Pass (TC-001/002/007), 3/7 Skip (TC-003/004/005), 1/7 cần quyết định owner (TC-006).

---

## Finding F1 — Doc-vs-Code mismatch: BA User vs nút "Publish to Etsy"

### Triệu chứng

Khi đăng nhập tài khoản `uat_ba_user@hatafax.demo` (chỉ có group `multichannel_hub_core.group_ba_user`) và mở form sản phẩm bất kỳ → nút **"Publish to Etsy"** **hiện** trên header form.

HUONG_DAN_TAO_SAN_PHAM_VN.md TC-006 mong đợi: **không hiện** + nếu cố gọi URL thì AccessError.

### Điều tra

1. **View** (`custom_addons/etsy_integration/views/product_views.xml:25-26`):
   ```xml
   <button name="action_open_etsy_publish_wizard" type="object"
           string="Publish to Etsy" class="oe_highlight"
           groups="multichannel_hub_core.group_ba_user"/>
   ```
   `groups="..."` nghĩa là: chỉ hiển thị cho user thuộc group đó. BA User **là** thành viên của `group_ba_user` → button **hiện**.

2. **Wizard FR-017 gate** (`custom_addons/etsy_integration/wizards/etsy_publish_wizard.py:17`):
   ```python
   _BA_GROUP_XMLID = 'multichannel_hub_core.group_ba_user'
   ```
   Method `_check_ba_or_raise()` kiểm tra membership ở `group_ba_user` — BA User pass gate này.

3. **Comment code** (`custom_addons/etsy_integration/models/product_product.py:50-53`):
   > "The wizard itself carries the FR-017 method-top gate; this action is only a UI entry point. View binds `groups=` for defense-in-depth visibility."

   Cả view và wizard đều thống nhất: **BA User được phép publish Etsy**.

4. **Role matrix trong doc** (HUONG_DAN_TAO_SAN_PHAM_VN.md §2):
   | Vai trò | Tạo SP | Đăng Etsy | Sửa SKU | Xoá SP |
   | BA User | ✅ | ❌ | ❌ | ❌ |
   | BA Lead | ✅ | ✅ | ✅ | ❌ |

   Doc nói BA User **không** publish được — ngược với code.

### Kết luận

Doc và code mâu thuẫn. Code có **23 lần xác nhận pattern FR-017 với `group_ba_user`** (xem auto-memory `feedback_fr017_write_defense_in_depth.md`) — pattern rất nhất quán. Khả năng cao là **doc viết sai** (wishful), không phải code lỗi.

### Quyết định cần owner duyệt

| Option | Hành động | Phạm vi |
|---|---|---|
| **D1 (recommended)** | Cập nhật HUONG_DAN_TAO_SAN_PHAM_VN.md role matrix: BA User Đăng Etsy = ✅ | Doc-only change, không cần MP006 slice |
| **D2** | Thắt chặt code: nâng FR-017 gate từ `group_ba_user` lên `group_ba_lead`; nâng view `groups=` cũng | MP006 slice `P-UAT-FIX-TC006`; chạm 4 chỗ (2 module: mhc + etsy_integration); rủi ro side-effect lên các method khác đang dùng cùng pattern |

**Đề xuất D1** vì code design có ý đồ rõ (defense-in-depth comment + 23 lần confirmation pattern); doc là tài liệu mới hơn (viết ngày 2026-05-26) trong khi code đã consolidate qua nhiều slice.

---

## Finding F2 — TC-007 spec drift (đã giải quyết trong test)

HUONG_DAN_TAO_SAN_PHAM_VN.md TC-007 mong đợi: "Validation — giá USD < 0.20 → thông báo 'Giá Etsy tối thiểu $0.20'".

Actual validator (`product_creation_wizard.py:127`):
```python
if rec.x_listing_price <= 0:
    raise UserError(_("Listing Price must be greater than 0."))
```

Validator chỉ check `> 0`, không phải `>= 0.20`. Etsy's $0.20 minimum được enforce ở **push step** chứ không ở wizard step.

Spec drift tương tự F1 (doc wishful) nhưng đã được xử lý trong test: TC-007 hiện test với `price=0` (actual behaviour) thay vì `price=0.10`.

**Đề xuất:** cập nhật HUONG_DAN TC-007 text từ "$0.20 minimum" → "Listing Price phải > 0" cho khớp implementation. Hoặc thêm slice `P-UAT-FIX-TC007` để tăng validator lên >= 0.20.

---

## Finding F3 — TC-003/004/005 cần seed UAT data trước

Để chạy:
- TC-003 cần 1 sản phẩm có `x_sku_v2_status='non_canonical'`
- TC-004 cần thêm: sản phẩm đó đã publish Etsy + có Etsy listing_id
- TC-005 cần: 1 sản phẩm sẵn sàng publish + đồng ý tạo Etsy draft thực

**Đề xuất:** thêm `fixtures/seed_uat_data.py` để tạo 1 sản phẩm non_canonical SKU (cho TC-003) + 1 sản phẩm đã có listing (cho TC-004) — chạy trong `globalSetup` sau `seed_ba_user.py`. TC-005 vẫn cần owner approval trước khi chạy lần đầu vì tạo Etsy listing thực.

---

## Kế hoạch tiếp theo (sau khi owner quyết)

1. **F1 — D1 hoặc D2?** → áp dụng quyết định.
2. **F2 — sửa doc hay tăng validator?** → áp dụng.
3. **F3 — owner approve TC-005 chạy live?** → seed data + run.
4. Sau đó UAT TC-001..007 đầy đủ → đính HTML report vào ESTY-183 → chuyển trạng thái Done.
5. Tiếp tục ESTY-184/185/186 với cùng pattern.
