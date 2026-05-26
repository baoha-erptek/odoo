# Feature Gaps — SKU Grammar v2

**Phiên bản:** 1.0 · **Ngày:** 2026-05-26 · **Đối tượng:** Architect + Dev team
**Status:** ENGINEERING PLANNING — không phải tài liệu cho end-user
**Reference contract:** [`.0temp/deliverables/A3_grammar_v2_frozen.md`](../../.0temp/deliverables/A3_grammar_v2_frozen.md) (frozen 2026-04-14)
**MP006 tracker rows:** Phase 3b — `P-HUB-DESIGN-CODE-REGISTRY` → `P-HUB-SKU-BUILDER` → `P-HUB-V2-VALIDATE-ON-CREATE` → `P-HUB-MISSING-INFO-WIZARD`

---

## 1. Tóm tắt

SKU Grammar v2 đã được spec hoá (frozen `A3_grammar_v2_frozen.md` 2026-04-14) định nghĩa định dạng:

```
<FAM3>-<MAT2>-<SIZE>-<DSGN>[-<VAR2>]
Ví dụ: MUG-CR-F11-D0001, RDS-CE-SQ-D0002, APP-TX-AM-D0003-BK
```

Implementation hiện tại (verified `custom_addons/multichannel_hub_core/` 2026-05-26) chỉ thực hiện được phần **gợi ý FAM3** (3 ký tự đầu). Bốn cấu phần còn lại (registry DSGN, builder wizard, validator, missing-info handler) **chưa được build**.

Hệ quả: `product.creation.wizard.action_create()` chấp nhận bất kỳ chuỗi SKU nào, không transform, không validate. Catalog Excel `.0temp/raw/[2025] Product Catalog.xlsx` hiện đang 100% legacy SKU (`MUG-1`, `TAT1`, `APR1`, `SQR1`…) — sample 6 dòng đầu mỗi sheet xác nhận không một SKU nào match grammar v2.

Doc này inventory 4 gap cụ thể + đề xuất 4 slice MP006 để đóng từng gap. Ưu tiên trước khi tiếp tục UAT / mở rộng sang Phase 4.

---

## 2. Gap inventory

### Gap 1 — Không có registry `sku.design.code`

**Tham chiếu spec:** A3 §2:
> "**DSGN registry (resolves R3 HIGH):** `sku.design.code` table with auto-sequence. No alpha mnemonics — `D0001`, `D0002`, ... Eliminates HRT-vs-HART collision vector. Human-readable design name stored as a separate `design.label` field alongside the code."

**Hiện trạng:** `grep -rn "sku.design.code\|sku_design_code" custom_addons/multichannel_hub_core/` → **zero matches**. Không có model, không có sequence, không có migration backfill.

**Hệ quả:**
- Không có cách phát mã `D####` tự động cho sản phẩm mới.
- Không có cách map ngược legacy SKU → design code chuẩn.
- Mọi cố gắng tạo full v2 SKU đều phải nội suy hoặc fake `D####`.

### Gap 2 — Không có wizard đa bước build SKU v2

**Tham chiếu spec:** A3 §2 + §4 (SIZE namespace per family).

**Hiện trạng:** chỉ có `product.creation.wizard` 6 trường (flat form: name/sku/category/price/shipping/channels) và `product.sku.canonicalise.wizard` (post-creation, per-product drift fix với 2 nút Keep Legacy / Accept Canonical).

**Hệ quả:**
- BA gõ free-text SKU vào trường `default_code`, không có guidance.
- Không có UI để chọn family / material / size / design id step-by-step.
- "Mã chuẩn v2" mặc định mà các doc khác nhắc đến (FLOW_TAO_SAN_PHAM_VN, HUONG_DAN_TAO_SAN_PHAM_VN) hiện không có cách nào tạo được trong app.

### Gap 3 — Không có validator chặn SKU sai grammar v2 khi create

**Tham chiếu code:** `custom_addons/multichannel_hub_core/wizards/product_creation_wizard.py` lines 118-158.

**Hiện trạng:** `_validate()` chỉ check:
- `name` non-empty
- `default_code` non-empty
- `categ_id` set
- `x_listing_price > 0`
- `x_shipping_price_internal >= 0`
- `>= 1` channel

Không có check nào parse `default_code` theo regex v2.

**Hệ quả:** Drift trên catalog tích lũy không bị chặn ở source — phải dùng canonicalise wizard sau khi product đã tạo + đã sync sang Etsy (rủi ro: lệch SKU giữa Odoo và Etsy cho đến khi BA xử lý từng cái).

### Gap 4 — Không có flow xử lý khi tên sản phẩm thiếu key info

**Tham chiếu spec:** A3 §4 (SIZE encoding namespace per family).

**Hiện trạng:** `evaluate(name)` trả về `(suggested_sku, family_code)` chỉ ở mức FAM3. Nếu tên sản phẩm "Color Changing Beverage (GM)" không có `mug` token → match MSC family fallback, không có flow nào hỏi BA bổ sung thông tin.

**Hệ quả:**
- Nhiều product Drinkware sample có thể rơi vào MSC mặc dù bản chất là mug.
- Không có flow hỏi BA "loại sản phẩm gốc là gì?" để override family classifier.
- Không có flow yêu cầu BA điền oz/dimension/shape cho sản phẩm mà tên không nêu.

---

## 3. Đề xuất slice (đã thêm MP006 tracker Phase 3b)

### P-HUB-DESIGN-CODE-REGISTRY

| Field | Value |
|---|---|
| **Mục tiêu** | Build model `sku.design.code` + auto-sequence + sibling `design.label` Char field theo A3 §2 |
| **Files** | `custom_addons/multichannel_hub_core/models/sku_design_code.py` (NEW), `data/ir_sequence.xml` (NEW), `security/ir.model.access.csv` (add 3 rows: BA User R, BA Lead R/W, BA Manager R/W/D), `migrations/19.0.X.Y.Z/post-backfill-design-codes.py` (backfill existing products) |
| **Migration policy** | Existing products without v2 SKU → assign `D9000+` UAT-reserved range OR `D####` based on `create_date` order (decision pending architect). |
| **ACL** | `BA User: R`, `BA Lead: R/W` (manual registration of net-new designs), `BA Manager: R/W/D`. |
| **Tests** | Phase 1: row count after migration matches product count + UNIQUE on code. Phase 2: auto-sequence increments without gaps; design.label searchable; ACL gates write at BA Lead level. |
| **Dependencies** | None (foundational). |
| **LOC estimate** | ~180 (model 50 + sequence 10 + ACL 5 + migration 80 + tests 40). |

### P-HUB-SKU-BUILDER

| Field | Value |
|---|---|
| **Mục tiêu** | Wizard mới `product.sku.builder.wizard` đa bước thay thế (hoặc augment) `product.creation.wizard`: Step 1 pick family (auto from name) → Step 2 confirm material (family default + override) → Step 3 enter size (oz/dimension/shape per A3 §4 namespace) → Step 4 pick design from registry hoặc "Create New Design" sub-wizard → Step 5 preview full SKU → Step 6 confirm + create product. |
| **Files** | `custom_addons/multichannel_hub_core/wizards/product_sku_builder_wizard.py` (NEW ~200 LOC), `wizards/product_sku_builder_wizard_views.xml` (NEW), update menu xml to add "Tạo sản phẩm — SKU v2" entry parallel to existing wizard. |
| **FR-017 gate** | Method-top check at `multichannel_hub_core.group_ba_user` (continuing 23+ confirmation pattern). |
| **Decision pending** | Replace `product.creation.wizard` outright OR keep both (legacy fallback + new builder)? Architect call: probably keep both for one sprint then sunset legacy. |
| **Dependencies** | P-HUB-DESIGN-CODE-REGISTRY ✓ (needs registry to populate Step 4). |
| **LOC estimate** | ~280 (wizard 200 + views 60 + tests 20 deferred to tdd-guide). |

### P-HUB-V2-VALIDATE-ON-CREATE

| Field | Value |
|---|---|
| **Mục tiêu** | Add `_validate()` check trong `product.creation.wizard` (legacy) AND `product.sku.builder.wizard` (new): parse `default_code` theo regex v2 `^[A-Z]{3}-[A-Z]{2}-(SQ|HT|OV|LSQ|WV|AR|BW|RD|S\d+|F\d+|A[A-Z]+|R\d+X\d+)-D\d{4}(-[A-Z]{2})?$`. Soft-warn vs hard-fail — owner ADR amendment required. |
| **Backwards-compat** | Legacy SKUs (e.g. `MUG-1`) handled via opt-out flag `x_sku_v2_status='ba_approved_legacy'` — wizard accepts them but logs warning. Operator can later run canonicalise wizard to migrate. |
| **Files** | `custom_addons/multichannel_hub_core/services/sku_grammar_v2.py` (add `validate_v2_format(sku) -> bool`), `wizards/product_creation_wizard.py` line 132+ (add check), `wizards/product_sku_builder_wizard.py` (same check at submit). |
| **Tests** | Phase 2: valid v2 SKU passes; valid legacy with `ba_approved_legacy` passes with warning; invalid (e.g. `mug-xx`) raises UserError (hard-fail mode) or only logs (soft mode). |
| **Dependencies** | P-HUB-DESIGN-CODE-REGISTRY ✓ (otherwise validator has no way to confirm DSGN exists). |
| **LOC estimate** | ~80 (validator helper 30 + 2 wizard hooks 20 + tests 30). |

### P-HUB-MISSING-INFO-WIZARD

| Field | Value |
|---|---|
| **Mục tiêu** | Khi SKU builder wizard (Step 3 enter SIZE) hit case không thể infer size từ name (e.g. "Color Changing Beverage" — không có "11oz" trong name), surface a "Resolve missing info" sub-step cho BA bổ sung attribute on-the-fly. Tự propagate lên `product.template` attribute storage (per A3 §8 attribute taxonomy: Material/Shape/Size/Fluid oz/Apparel size). |
| **Triggers** | (a) Step 1 family classifier return MSC + BA confirm sản phẩm ko phải MSC → wizard cho BA override family thủ công; (b) Step 3 size parser fail → wizard hỏi oz/dim/shape; (c) Step 4 registry miss + BA chưa muốn tạo design code mới → cho phép skip với cảnh báo. |
| **Files** | `custom_addons/multichannel_hub_core/wizards/product_sku_builder_wizard.py` (extend with conditional sub-step logic), `views/product_sku_builder_wizard_views.xml` (conditional `<group attrs="{'invisible': [('needs_resolve','=',False)]}"/>` panels). |
| **Dependencies** | P-HUB-SKU-BUILDER ✓ (extends its Step 1/3/4 flow). |
| **LOC estimate** | ~120 (sub-step logic 80 + view conditionals 30 + tests 10). |

---

## 4. Build order + decision points

```
P-HUB-DESIGN-CODE-REGISTRY   (foundational, no deps)
            ↓
P-HUB-SKU-BUILDER            (consumer of registry)
       /         \
       ↓          ↓
P-HUB-V2-      P-HUB-MISSING-
VALIDATE-      INFO-WIZARD
ON-CREATE
```

**Có thể chạy song song:** P-HUB-V2-VALIDATE-ON-CREATE và P-HUB-MISSING-INFO-WIZARD đều phụ thuộc P-HUB-SKU-BUILDER nhưng độc lập với nhau.

### Decision points cần owner duyệt trước khi dispatch

| # | Decision | Default đề xuất |
|---|---|---|
| D-V2-1 | Backfill DSGN cho existing products: `D9000+` reserved range hay `D####` theo `create_date`? | `D####` theo create_date (mã sạch, không lãng phí dải) |
| D-V2-2 | Validator mode khi hit non-v2 SKU: hard-fail (UserError) hay soft-warn (logger.warning + cho qua)? | Soft-warn (giữ backwards-compat với legacy SKU đã import từ Excel) |
| D-V2-3 | `product.sku.builder.wizard` thay thế `product.creation.wizard` outright hay coexist 1 sprint? | Coexist 1 sprint, sunset legacy sau owner UAT pass |
| D-V2-4 | Family classifier override (Gap 4 case a) — cho BA chọn 22 family bằng dropdown hay typeahead? | Dropdown (22 lựa chọn ít, không cần search) |
| D-V2-5 | Khi sản xuất phát hiện design mới (during MTO fulfillment), tạo design code TRƯỚC khi product được create hay lúc nào? | Tại bước tạo product (Step 4 wizard) — đảm bảo SKU full trước khi sản phẩm publish. Design label có thể update sau. |

---

## 5. Out of scope cho 4 slice trên

- **UI hiển thị full v2 SKU breakdown trên form sản phẩm** (FAM3/MAT2/SIZE/DSGN tách thành 4 read-only Char). Lý do: cosmetic; defer cho sau khi 4 slice core ship.
- **Bulk re-canonicalise toàn bộ catalog từ Excel `[2025] Product Catalog.xlsx`** sang v2. Lý do: scope lớn, cần spec riêng (`P-HUB-BULK-CANONICALISE` future).
- **Integration với Etsy outbound publish để push v2 SKU update lên Etsy khi BA canonicalise**. Đã có hook trong existing `EtsyInventoryPusher` — chỉ cần wire khi P-HUB-V2-VALIDATE-ON-CREATE ship; tạo slice nhỏ `P-HUB-V2-ETSY-SYNC` follow-up.
- **Migration backfill cho sản phẩm Etsy đã publish (legacy SKU đang sync với Etsy)** — phức tạp hơn vì cần coordinate với Etsy listing update; tách thành slice riêng `P-HUB-LEGACY-ETSY-RECANONICAL` sau P-HUB-V2-VALIDATE-ON-CREATE.

---

## 6. UAT impact

UAT trên ESTY-183 (HUONG_DAN_TAO_SAN_PHAM_VN.md) đã pause 2026-05-26 vì gap inventory này (xem MP006 tracker D7). Cụ thể:
- TC-001/002 (Wizard create) — pass với current implementation, nhưng không exercise grammar v2 (vì wizard không enforce).
- TC-008 đề xuất (grammar v2 conformance) — premature; cần 4 slice trên trước khi test có ý nghĩa.

UAT resume sau khi `P-HUB-V2-VALIDATE-ON-CREATE` merge. Lúc đó:
- TC-001/002 sẽ test full builder wizard flow (thay vì legacy creation wizard).
- TC-008 sẽ assert created `product.template.default_code` parses v2 regex.
- Per-sheet drift audit từ Excel catalog trở thành findings cho `P-HUB-BULK-CANONICALISE` follow-up spec.

ESTY-183/184/185/186 stay JIRA `In Progress` với pause comment trong khi 4 slice trên dispatch.

---

## 7. Cross-references

- Spec frozen: [`.0temp/deliverables/A3_grammar_v2_frozen.md`](../../.0temp/deliverables/A3_grammar_v2_frozen.md)
- Current sku_grammar_v2 service: `custom_addons/multichannel_hub_core/services/sku_grammar_v2.py`
- Current creation wizard: `custom_addons/multichannel_hub_core/wizards/product_creation_wizard.py`
- Current canonicalise wizard: `custom_addons/multichannel_hub_core/wizards/product_sku_canonicalise_wizard.py`
- MP006 tracker rows: `.claude/plans/006-master-plan-tracking.md` Phase 3b §3b sub-table
- ADR-014 (central product hub): `specs/006-master-plan/adrs/ADR-014-central-product-hub.md`
- UAT findings 2026-05-26: `docs/owner/UAT_FINDINGS_2026-05-26.md`
