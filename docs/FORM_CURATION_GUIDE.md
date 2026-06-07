# Form Curation Guide

> Governance rule cho mọi custom form/view trong project odoo19_esty.
> Sinh ra từ audit [`COMPARISON_MOCKUP_VS_ACTUAL.md`](owner/business-flows/COMPARISON_MOCKUP_VS_ACTUAL.md) (Phase 1 của Option 3 Hybrid).

**Phiên bản:** 1.0 (2026-06-07) · **Trạng thái:** MANDATORY for new custom views.

---

## Vấn đề muốn giải quyết

Real Odoo forms hiện đang phơi bầy **20–30+ fields** mỗi screen (full ORM schema + Etsy-specific overrides). Mockup curate chỉ **6–12 fields** focus theo từng narrative scenario. Đây là nguồn gốc cảm giác "cluttered" — không phải styling, mà là field visibility.

Guide này định nghĩa **3-tier visibility model** để mỗi form vẫn dùng default Odoo styling nhưng chỉ hiển thị các fields liên quan đến vai trò user + scenario.

---

## 3-tier model

### Tier 1 — Essential (always visible)

**Tiêu chí:** field này là **must-fill** để hoàn thành use-case chính của form.

**Vị trí trong form:** General Information tab (đầu form), hoặc trong section đầu tiên không gập.

**Ví dụ trên `product.template` từ Flow 1 narrative:**
- `name` — Tên sản phẩm
- `categ_id` — Danh mục
- `list_price` — Giá bán
- `default_code` — Mã SKU (auto-generated)
- `x_channel_applicability_ids` — Các kênh áp dụng
- `image_1920` — Ảnh chính

**Số lượng đề xuất:** 6-10 fields tối đa per Tier 1 section. Nếu nhiều hơn → re-evaluate tier classification.

### Tier 2 — Secondary (in tabs / accordions)

**Tiêu chí:** field cần thiết cho **một số use-cases** nhưng không phải core happy-path. Hoặc fields theo grouping logic (Inventory, Shipping, etc.).

**Vị trí trong form:** Notebook tabs sau General, hoặc collapsed accordion sections.

**Ví dụ trên `product.template`:**
- `description_sale` (tab Sales)
- `taxes_id` (tab Sales)
- `route_ids` (tab Purchase + Inventory)
- `responsible_id` (tab Inventory)
- `x_etsy_tags` (tab Channels)
- `x_personalization_*` (tab Personalization)

**Số lượng đề xuất:** 4-8 fields per tab.

### Tier 3 — Advanced (hidden behind groups / debug)

**Tiêu chí:** field chỉ admin/system user cần. Hoặc legacy/internal/debug fields không liên quan business workflow.

**Vị trí trong form:** `groups="base.group_system"` hoặc `invisible="True"` (cho debug fields), HOẶC moved into a separate "Technical" admin form.

**Ví dụ trên `product.template`:**
- `barcode` (rarely used in dropship/POD context)
- `volume`, `weight` (chỉ relevant cho POD physical — keep visible nếu module dùng nó)
- `tracking` (lot/serial) — group_system
- `produce_delay` (manufacturing) — group_system
- `service_to_purchase` (purchase tightly coupled) — group_system
- All `x_*_internal_*` fields — group_system or invisible

**Số lượng:** không giới hạn, nhưng phải có lý do rõ ràng để là Tier 3.

---

## XML pattern

### Tier 1: default visible
```xml
<group string="General Information">
  <field name="name"/>
  <field name="categ_id"/>
  <field name="list_price"/>
  <field name="default_code"/>
</group>
```

### Tier 2: in a notebook tab
```xml
<notebook>
  <page string="Sales" name="sales">
    <group>
      <field name="description_sale"/>
      <field name="taxes_id"/>
    </group>
  </page>
  <page string="Channels" name="channels">
    <field name="x_channel_applicability_ids"/>
    <field name="x_etsy_tags"/>
  </page>
</notebook>
```

### Tier 3: behind group / invisible
```xml
<!-- Visible only to System administrators -->
<group string="Advanced" groups="base.group_system">
  <field name="tracking"/>
  <field name="produce_delay"/>
</group>

<!-- Debug field — invisible by default -->
<field name="x_internal_correlation_id" invisible="1"/>

<!-- Hidden via Studio-style attribute (per-record visibility) -->
<field name="x_legacy_sku" invisible="context.get('hide_legacy')"/>
```

---

## Mandatory cho mọi custom field/view mới

Khi viết XML view mới (hoặc thêm field vào view sẵn có), tác giả PR PHẢI:

1. **Khai báo tier trong commit message:**
   ```
   feat(P-EXAMPLE-SLICE): add x_etsy_priority field [Tier 2 — in Channels tab]
   ```

2. **Comment trong XML:**
   ```xml
   <!-- Tier 2 — Channels tab; show only when x_channel_applicability_ids includes Etsy -->
   <field name="x_etsy_priority"
          invisible="not x_channel_applicability_ids"/>
   ```

3. **Cập nhật `docs/FORM_CURATION_GUIDE.md` examples** nếu thêm pattern mới (PR review check).

---

## Audit checklist cho existing custom views

Nếu refactor existing view, run qua checklist này:

- [ ] **Đếm visible Tier 1 fields:** nếu > 10, đẩy thấp tier xuống.
- [ ] **Operations/Logistics blocks:** trên `product.template` có thực sự cần ở Tier 1 cho POD/dropship workflow không? Nếu không → group="base.group_system" hoặc đẩy vào tab Inventory.
- [ ] **Description blocks:** "Description for Receipts" + "Description for Delivery Orders" — nếu module dropship không in tài liệu nội bộ này, đẩy vào tab Sales hoặc invisible.
- [ ] **Smart buttons:** "Bill of Materials" / "Documents" / "Purchased" / "Sold Units" — chỉ smart button nào liên quan đến core workflow giữ ở header. Còn lại → invisible hoặc behind group.
- [ ] **Notebook tabs:** "Prices" / "Purchase" / "Inventory" / "Sales" trên `product.template` — nếu module chỉ dùng Etsy/Channels tab, ẩn các tab kia.

---

## Anti-patterns cần tránh

### ❌ "Add field, fix tier later"
Thêm field mà không khai báo tier trong commit → field rơi vào Tier 1 default → cluttering tăng dần. **PR reviewer reject.**

### ❌ "Tier 1 — vì user hỏi field này 1 lần"
Tier 1 dành cho field **bắt buộc cho core workflow**, không phải field "có thể hữu ích". Field "có thể hữu ích" = Tier 2.

### ❌ "Tier 3 = invisible"
Tier 3 = behind group OR invisible với lý do rõ ràng. Nếu admin/system user vẫn cần edit → group; nếu KHÔNG AI cần edit thủ công → invisible OR xoá field.

### ❌ "Custom view cho mỗi role"
Đừng tạo 3 form views (BA / BA Lead / Admin) cho cùng 1 model. Dùng `groups="..."` trên field/section thay vì duplicate view.

---

## Liên kết

- **Audit gốc:** [COMPARISON_MOCKUP_VS_ACTUAL.md](owner/business-flows/COMPARISON_MOCKUP_VS_ACTUAL.md) — nguồn gốc tại sao có guide này.
- **Design system:** [MU_SYSTEM.md](owner/design-system/MU_SYSTEM.md) — styling rules (phối hợp với curation rules ở đây).
- **Mockup references:** [`docs/owner/business-flows/flow-*.html`](owner/business-flows/) — ví dụ cách curate fields theo narrative.
- **Standard-Odoo-First rule:** trước khi thêm bất kỳ field nào, grep `addons/` xem standard có chưa. Xem CLAUDE.md §"Standard-Odoo-First (MANDATORY)".

---

## Áp dụng cho hiện trạng

Per audit recommendations, các target ưu tiên backport (Phase 2 entry):

| Form | Hiện trạng (Tier hỗn loạn) | Sau curation |
|---|---|---|
| `product.template` (Flow 1) | All Odoo standard + Etsy fields ở Tier 1 (~22 fields) | Tier 1: 6 (name, categ, price, SKU, channels, image) + Tier 2 tabs (Channels/Personalization/Tags) + Tier 3 group_system (Manufacturing/Routes/Internal logistics) |
| `multichannel.listing` (Flow 1) | All Etsy fields phẳng | Tier 1: external_ref + state + image preview + title; Tier 2 tabs (Shipping & Variations / Video / How It's Made / Override Etsy) |
| `etsy.shop` (Flow 2) — **shipped P-DS-3a** | All shop config flattened, no Tier separation; `etsy_api_shop_id`/`active_source` hidden inside `groups="base.group_system"` group | **Tier 1**: name (oe_title), revenue_total, listing_currency_id, etsy_api_shop_id (`.mu-mono`), active_source (`widget="badge"` decoration-success on `api` / decoration-warning on `email`); **Tier 2** notebook tabs unchanged (Publisher Defaults + Orders); **Tier 3** `groups="base.group_no_one"` "Advanced Diagnostics" group (auto_recovery, active_source_changed_at, health_check_consecutive_failures, recovery_probe_consecutive_successes). Borderline fields (sync_audit_mode, etsy_oauth_token_expires_at, etsy_last_receipt_sync_at) remain absent from the view per owner gate 2026-06-07 — adding them is scope expansion. Mockup at `docs/owner/design-system/MOCKUP_etsy_shop.md`. |
| `sale.order` (Flow 2) | Standard Odoo (kept as-is) | No curation needed — Odoo's default Tier model adequate |
| `stock.picking` (Flow 3a) | Standard Odoo (kept as-is) | No curation needed |

Mỗi target = 1 PR slice riêng (e.g. `P-CURATION-PRODUCT-TEMPLATE`, `P-CURATION-MULTICHANNEL-LISTING`). Estimate: 0.5–1 day per slice.
