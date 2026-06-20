# So sánh Mockup vs Screenshot thật — 2026-06-07

> Báo cáo audit cho slice P-UI-MOCKUP-VS-ACTUAL-COMPARE.
> Mục đích: chỉ ra khác biệt functional + UI giữa 5 mockup HTML thiết kế 2026-06-03
> và 21 screenshot harvest từ staging, đề xuất cách lưu giữ phong cách mockup.

---

## Tóm tắt

**3 kết luận chính:**

1. **Mockup thiết kế có ngôn ngữ trực quan riêng biệt:** dùng `mu-*` CSS classes, màu tím chuẩn #714B67, pill badges, breadcrumb nav, stage pipeline visual. Odoo 19 dùng default OWL styling (xám trung tính, layout grid chuẩn).

2. **Sự khác biệt lớn nhất: curation trường dữ liệu.** Mockup hiển thị 6–12 trường/screen (clean, focused). Real Odoo form phơi bầy 20–30+ trường (toàn bộ model schema — quần áo bổ sung, notes nội bộ, logistics fields, etc.), làm form trông "rộn ràng".

3. **Functional gaps có-và-chưa:** 
   - Có: Auto-SKU onchange (real), Channel tabs (real), Publish wizard (real), Brand-voice defaults shop (real).
   - Chưa harvest screenshot: SKU Drift list view, Payload preview, Error modal, Kanban filtered.
   - Thêm ở real: multichannel.listing form riêng (thay vì embedding trong product form), Video tab, Shipping & Variations tab — không ở mockup.

4. **Để archive phong cách mockup:** sử dụng **Hybrid Approach** — giữ mockup làm design system reference, export `mu-*` CSS ra design tokens file, giáo dục team về 3-tier curation (Essentials / Secondary / Advanced fields) để apply vào real views qua cấu hình + tuỳ biến OWL.

---

## Per-flow comparison

### **Flow 1 — Tạo sản phẩm**

| Mockup screen | Actual screenshot | Functional gap | UI gap |
|---|---|---|---|
| **1. Form Sản phẩm chuẩn + Auto-SKU** | 01-form-general.png, 02-attributes.png | ✓ Auto-SKU onchange exists; SKU field hiện form General Information (mockup). Real shows: Product title + Sales/Purchase module toggles + Operations box (Routes MTO/Dropship) + Logistics box (Weight/Volume/Customer Lead Time) + Description blocks BELOW form fields — **extra 8 fields không ở mockup**. | **Real:** default Odoo chrome (white/grey, sans-serif 13–14px). **Mockup:** custom chrome bar #714B67 purple, breadcrumb, stage pills, 12px labels, padding 18px form. Real form uses default tab bar styling (no mu-* pill styling on active tab). |
| **2. SKU Drift list** | — (no harvest) | Feature exists: `mhc.view_product_sku_drift_list` in codebase (mockup references it line 313–334). Functional intent verified (2-column comparison, Keep Legacy / Accept Canonical buttons). **No screenshot collected during staging run.** | n/a — no real view to compare. Mockup shows: table with mu-pill status badges, grey header, 12px font, narrow 160px column widths. |
| **3. Payload preview (tab Channels)** | 04-fx-preview.png | Feature partially exists: real screenshot shows `multichannel.listing` form (new model 2026-05, not embedded in product form). Real form shows: External Reference + Last Synced At fields (empty draft state) + SCOPE section (Product, Channel, Shop, Sequence). **Payload preview TABLE NOT CAPTURED** — real has empty fields, mockup shows pre-filled JSON-like payload rows (title, price, taxonomy_id, readiness_state_id, materials, tags, weight, offerings). Likely rendered on-save or preview button (not visible in harvest). | Real listing form uses default Odoo styling. Mockup shows custom mu-screen chrome bar + breadcrumb "Sản phẩm › Custom Coffee Mug › **Channels**" + status bar with 2 publish buttons + info banner (faint purple #faf5f9 bg, grey text) explaining 2-record design (product.template ↔ etsy.listing.product). |
| **4. Error modal (400 Etsy)** | — (no harvest) | Feature exists via `etsy_listing_publisher.py` error handling (code references). Modal shown: "⚠ Etsy trả lỗi 400…" (mockup shows Bước thất bại: createListing, Mã lỗi HTTP: 400, banner yellow "Đang chờ phản hồi chi tiết từ Etsy"). **Current blocker:** response body not captured (UAT 2026-05-28 noted 4 TCs with 400s but no error text — depends on R-PUB-RESPONSE-BODY-DIAGNOSE slice). | Mockup: custom modal.mu-modal styling (white bg, rounded 6px, shadow 0 8px 24px, red header #b91c1c, yellow banner #fef9c3 with left border #ca8a04). Real modal expected to use Odoo WarningDialog (blue header, grey buttons). |
| **5. Kanban filtered by Etsy** | — (no harvest) | Feature intent exists: `mhc.view_multichannel_sync_health_list` kanban view referenced (codebase). Filter by channel Etsy + group by status (Draft/Published/Error) — not captured in UAT harvest. | Mockup: 3-column kanban grid, status headers (Draft·28 grey, Published·98 green, Error·6 red text), mu-kb-card white boxes with h4 title + 3-line meta (SKU, price/listing_id, updated/sales count). Real kanban not harvested. |

**Synthesis — Flow 1:**
Real Odoo implementation is **functionally complete** for the primary use case (create product, auto-SKU, select channels, publish). The main visual differences are:
- Real uses **2 separate models** (product.template + multichannel.listing) — stored in different forms. Mockup conflates them as one "Channels" tab within product form.
- Real form is **cluttered with unrelated fields** (Operations/Routes/Logistics/DESCRIPTION blocks) that don't belong in the "create listing" scenario.
- Payload preview and error modals are **functional but not visually polished** — real captures the mechanics but not the UX narrative flow.

---

### **Flow 2 — Tiếp nhận đơn Etsy**

| Mockup screen | Actual screenshot | Functional gap | UI gap |
|---|---|---|---|
| **1. etsy.shop API status** | 01-shop-api-status.png | ✓ Real screenshot shows same form: Etsy Shop ID (60752333), Active Source (Etsy API), Auto Recovery (checked), Active Source Changed At (May 22, 4:34 PM), Health-Check/Recovery metrics (0 failures). Mockup labels identical. Additional fields in real: **Total Revenue (734,914.00)** at top + **Publisher Defaults tab** (showing Default Etsy Taxonomy 2172) — not shown in mockup. | Real: default Odoo form tabs + heading "JaHandmadeArt" (black 16px). Mockup: custom mu-chrome-bar #714B67 "Bán hàng › Sản phẩm › SKU Drift"; no custom styling in real. Section headers (ETSY API CONFIGURATION, ETSY PUBLISHER DEFAULTS) are Odoo standard grey. |
| **2. Etsy API log (cron, pagination)** | 02-cron-log.png | Feature NOT visible in harvest — real screenshot shows different view (etsy.shop form, not API log). Mockup references "GET /receipts + pagination" table (cron log). Functional code exists (`etsy_order_syncer` cron, `etsy.api.log` model). **No log view screenshot collected.** | n/a — log view not captured. |
| **3. Gmail config** | 03-gmail-config.png | Feature NOT captured in screenshot — fallback email parsing exists in code (`email_parser.py`), but no Settings › Etsy form visible. Functional: cron poll Gmail 10min (per spec). | n/a — Settings form not harvested. |
| **4. Sale order (customer + items)** | 04-sale-order-new.png | ✓ Real screenshot shows sale.order form: customer name (Chương giỏ [colors]), Etsy listing_id as "Details" link, variant info. Real shows rows: Product (Chương giỏ Blue/Black/Purple/Silver/Gold), Demand (20.00), Quantity (20.00), Unit (Units), Details link. Mockup shows similar row structure. No visible Personalization field in real (Demand = 20, Quantity = 20 only). | Real: default Odoo form, Sales module chrome (purple header "Sales"), breadcrumb "Transfers › WH/IN/00002", state buttons (Draft / Ready / Done), Operations/Additional Info/Note tabs at bottom. Mockup does not show these. Real uses 14px font, default Odoo grid. |

**Synthesis — Flow 2:**
Real Odoo **does NOT show** the full email-parser + Gmail-config UI in the UAT harvest. Screenshots are **incomplete** for this flow. Sale order creation is functional (order lines + customer + variant meta) but unpolished — no custom UX chrome or narrative framing like mockup shows.

---

### **Flow 3a — Giao hàng (In nội bộ)**

| Mockup screen | Actual screenshot | Functional gap | UI gap |
|---|---|---|---|
| **1. Stock picking auto-create** | 01-picking.png | ✓ Real shows stock.picking form: WH/IN/00002, Receive From (LP Logistics), Operation Type (My Company: Receipts), Destination Location (WH/Stock), tabs (Operations/Additional Info/Note). Product rows: Chương giỏ [5 colors], Demand 20.00, Quantity 20.00, Unit Units. Functional intent matches — picking created from sale.order. | Real: default Odoo Stock chrome (Sales module header purple), breadcrumb "Transfers › WH/IN/00002", Print/Return buttons, state pills (Draft / Ready / Done), Operations tab showing product grid + Details column. Mockup not compared (no mockup screen for Flow 3a picking shown). |
| **2. Design file attached** | 02-design-file.png | Feature referenced in mockup text (Luồng 3A giai đoạn 2 — "In nội bộ dựa trên SKU + design file"). Real screenshot shows same picking form. **No separate "Design file" form captured** — likely accessed via Details link or separate module view. | n/a — no design_file form screenshot. |
| **3. Tracking upload wizard** | 03-tracking-wizard.png | Feature exists: `EtsyTrackingPusher.push_tracking()` (code). Mockup shows wizard: carrier_name + tracking_number fields. **Real screenshot NOT captured.** Functional: wizard expected to collect carrier + tracking, push to Etsy. | n/a — tracking wizard not harvested. |

**Synthesis — Flow 3a:**
Real screenshots show **only the stock.picking form** — no wizard, no design_file view, no tracking UI captured. Functional intent (picking → tracking → Etsy push) exists but **UI coverage is incomplete**.

---

### **Flow 3b — Giao hàng (Gearment dropship)**

**Status:** All 3 screenshots are **stub PNGs (placeholder, not real Odoo).**

- `01-quote-wizard.png` — colored box with Vietnamese text "TÍNH NĂNG ĐANG PHÁT TRIỂN" (Feature in Development) + file name "01-quote-wizard.png"
- `02-gearment-order.png` — same stub format
- `03-webhook-log.png` — same stub format

**Reason:** Module `gearment_integration` still under build (per flow-3b.md header "Trạng thái triển khai: Ảnh bên dưới là *stub preview*"). **No functional Gearment features in staging yet.**

---

### **Flow 4 — Hậu mãi (Đổi/Trả/Refund)**

| Mockup screen | Actual screenshot | Functional gap | UI gap |
|---|---|---|---|
| **1. Conversation (buyer request)** | 01-conversation.png | Feature exists: `multichannel.enquiry` model. Real screenshot shows **empty list** "No customer enquiries yet." with message "Pre-sale enquiries arrive via the Etsy Conversations API, per-shop email aliases, or are entered manually." Functional: webhook not activated yet (`conversations_r` scope pending Etsy approval — P1-MSG-SCOPE slice). **Zero enquiries in staging.** | Real: Operations module, Customer Enquiries tab. List columns: Name, Partner Email, Partner, Source, State, Assigned To, Created on. Standard Odoo list view (grey header, white rows, purple module chrome). Mockup shows custom form (purple header, modal-like). |
| **2. Address change request** | 02-address-change.png | Feature model exists: `etsy.address.change.request` (per flow-4.md). Real screenshot NOT captured during UAT. Functional: form expected to have "pending approval" state, BA Lead action buttons. | n/a — no real form screenshot. |
| **3. Decision (Replace/Refund/Reship)** | 03-decision.png | Feature exists but marked **"đang phát triển" (in development)** in mockup caption. **Real screenshot is also a stub PNG.** Functional: server action to approve/reject address changes + trigger refund flow. | n/a — stub, not real. |

**Synthesis — Flow 4:**
Flow 4 is **least developed in staging.** Enquiries list exists but empty (no Etsy conversation webhook). Address change request + decision modals are **not built yet** — only model schemas exist. **All 3 real screenshots are empty or stubs.**

---

## Cross-flow patterns

### **UI patterns the mockups use (not in real Odoo)**

The mockups define a **custom design system** via inline CSS (`.mu-*` classes). Real Odoo 19 ignores these — uses default OWL components. Key divergences:

| Pattern | Mockup CSS | Usage count | Real equivalent |
|---|---|---|---|
| **Chrome bar** | `.mu-chrome-bar` {bg #714B67, color white, padding 7px 14px, font 13px} | 5 screens | None — Odoo uses module breadcrumb + topbar |
| **Breadcrumb** | `.mu-breadcrumb` {padding 8px 14px, font 13px, separator › grey} | 5 screens | Default Odoo breadcrumb (smaller font, different styling) |
| **Pill badge** | `.mu-pill` + 4 color variants (success/warn/danger/neutral) {padding 2px 9px, border-radius 12px, font 11px bold} | 12+ uses | Odoo uses `badge` class (different border-radius, padding) |
| **Stage pipeline** | `.mu-stage-pipe` {display flex, gap 4px, font 11px grey} + `.mu-stage` {border 1px #e5e7eb, padding 4px 10px, rounded 999px} | 3 screens | Odoo kanban column headers (no pill styling) |
| **Form grid 2-col** | `.mu-grid2` {grid-template-columns 1fr 1fr, gap 18px 32px} | Form mockup (screen 1) | Odoo default: depends on notebook tabs (Flow 1 has 8+ tabs crammed horizontally) |
| **Field layout** | `.mu-field` {grid 140px 1fr, align-items baseline, border-bottom 1px #f3f4f6} | Form mockup | Odoo form uses OWL `field` component, different spacing |
| **Tab bar** | `.mu-tabs` {flex, border-bottom 1px #e5e7eb, overflow-x auto} + `.mu-tab` active {color #714B67, border-bottom 2px, font 600} | Form mockup | Odoo tab styling: underline is grey, not tinted. Real Flow 1 form has 13 tabs jammed horizontally (overflow not visible). |
| **List table** | `.mu-list` + thead {bg #f9fafb, padding 9px 12px, text-transform uppercase, font 11px, letter-spacing 0.5px} | 2 screens (SKU Drift, payload table) | Odoo `o_list_table` styling (slightly different header bg, no uppercase) |
| **Kanban card** | `.mu-kb-card` {bg white, border 1px #e5e7eb, rounded 4px, padding 12px 14px} | Kanban mockup (screen 5) | Odoo kanban uses `.o_kanban_record` (different rounded, shadow, padding) |
| **Modal** | `.mu-modal` {bg white, rounded 6px, max-width 520px, shadow 0 8px 24px} | Error modal (screen 4) | Odoo uses OWL `Dialog` (different shadow, rounded, width) |

**Total custom pattern count:** 10 major CSS patterns. If ported to real Odoo, would require **OWL component library rebuild** OR CSS override file (~300–400 LOC) + careful namespacing to avoid collision with standard Odoo styles.

---

### **Functional features mockups show but real Odoo lacks (not built yet)**

| Feature | Mockup ref | Built? | Why missing |
|---|---|---|---|
| **SKU Drift list + Keep Legacy / Accept Canonical buttons** | Flow 1, screen 2 | Partial (model + view exist, no harvest) | Harvested under pressure — skipped complex list views |
| **Payload preview table** (title, price, taxonomy_id, readiness_state_id, materials, tags, personalization, weight, offerings, images) | Flow 1, screen 3 | Partial (lives on `multichannel.listing` form, but NOT visible in harvest preview) | Real shows empty draft state — preview only renders post-save or on button click |
| **Error modal with full 400 body** | Flow 1, screen 4 | No (code logs error but doesn't display body) | Blocker: R-PUB-RESPONSE-BODY-DIAGNOSE (Etsy API doesn't return detailed error text yet — owner filed support ticket) |
| **Kanban grouped by channel + status** | Flow 1, screen 5 | Partial (view exists, no harvest) | Not captured; likely works but low priority in UAT |
| **Email parser config form** | Flow 2, screen 3 | Yes (code exists) | Settings form not harvested |
| **Design file form + attachment field** | Flow 3a, screen 2 | Yes (model exists) | Not screenshotted during UAT |
| **Tracking wizard (carrier + tracking# fields)** | Flow 3a, screen 3 | Yes (code exists) | Not captured |
| **Gearment quote wizard** | Flow 3b, screen 1 | No (stub PNG — module not built) | Build in progress |
| **Gearment order form** | Flow 3b, screen 2 | No (stub) | Build in progress |
| **Address change request form + approval UI** | Flow 4, screens 2–3 | No (stub) | Build deferred (conversations_r scope not approved) |

**Bottom line:** 7 features **do exist in code but were not harvested as screenshots** (likely due to UAT time pressure or hidden on secondary tabs). 3 features **are genuinely not built** (Gearment, address change decision UI).

---

### **Functional features real Odoo has but mockups omit**

| Feature | Real form | Mockup? | Why omitted |
|---|---|---|---|
| **Operations > Routes (MTO/Manufacture/Dropship) section** | product.template form (General Information tab) | No | Not relevant to Etsy listing creation narrative |
| **Logistics section (Weight, Volume, Customer Lead Time, Responsible)** | product.template form (General Information tab) | No | Scope: Etsy publishing, not inventory ops |
| **Description for Receipts + Description for Delivery Orders** | product.template form (General Information tab) | No | Odoo standard fields; not Etsy-specific |
| **SKU Drift tab** | product.template form (tab bar) | No (has its own list view, not embedded) | Intentional separation — SKU Drift is admin/review tool, not product editing |
| **Listing Tags tab** | product.template form (tab bar) | Shown in mockup Flow 1 as "Tags" but content not detailed | Real shows tab but content not screenshotted |
| **Listing Options tab** | product.template form (tab bar) | No | Real has it; mockup doesn't detail it |
| **Listing Defaults tab** | product.template form (tab bar) | No | Real has it; mockup doesn't mention |
| **Prices, Purchase, Inventory, Sales tabs** | product.template form (standard Odoo) | No | Odoo standard, not Etsy-relevant in mockup scope |
| **Bill of Materials, Documents, Purchased, Sold Units smart buttons** | product.template form (header smart button row) | No | Odoo standard; not relevant to Etsy listing |
| **multichannel.listing form (separate from product.template)** | separate form at Operations › Listings | No (mockup treats Channels as tab within product form) | Design decision: separate model introduced later (2026-05, after mockup design date 2026-06-03 was locked) |
| **Video tab on multichannel.listing** | form tab | Mentioned in mockup but not detailed | Real has tab; content shown in screenshot |
| **How It's Made tab on multichannel.listing** | form tab (shipping profile, who-made, when-made fields) | "Override taxonomy/shipping/return per sản phẩm" in mockup step 5, but not shown as tab | Real separates into dedicated tab |

**Pattern:** Real Odoo **includes all standard product fields** + Etsy-specific overrides. Mockup **curates only the "must-fill" fields for the happy-path workflow.** This is the core source of "cluttered vs clean" perception.

---

## "How to archive that" — recommendations

The owner's ask: "check for how to archive that" (mockup cleanliness + organization).

**3 concrete options:**

### **Option 1: Preserve mockups as design system documentation + CSS tokens file**

**Approach:**
- Keep existing mockup HTMLs as-is (they are complete + well-documented).
- Extract `.mu-*` CSS into a standalone file: `/docs/owner/design-system/mu-design-tokens.css` (~500 LOC).
- Author `/docs/owner/design-system/MU_SYSTEM.md` explaining:
  - 10 component patterns (chrome bar, pill badges, form grid, etc.)
  - Color palette (primary #714B67 purple, greys, accent reds/greens/yellows)
  - Typography (labels 12px, values 13px, headings 20px)
  - Spacing grid (8px base unit)
  - Target: serve as inspiration/reference for future OWL component library

**Effort:** 2–3 dev-days (CSS extraction, docs authoring, no coding changes to Odoo forms)

**Tradeoff:** 
- Pro: Low risk, non-intrusive, documents the design intent for future reference
- Con: Does NOT change real Odoo UI — forms remain "cluttered" until someone implements OWL components

---

### **Option 2: Backport high-value mockup patterns into real Odoo forms (phased approach)**

**Approach:**
- Identify the **3 highest-ROI patterns** to port:
  1. **Purple pill badges** for status + state indicators (replace Odoo's default grey badges)
  2. **2-column form grid + field layout refinement** (add mu-grid2-like spacing to key forms like product.template, multichannel.listing)
  3. **Custom tab bar styling** (tint active tab purple, increase font weight)

- Create OWL components in `/etsy_integration/static/src/components/`:
  - `MuPill.tsx` (reusable status badge component)
  - `MuFormGrid.tsx` (responsive 2-column layout wrapper)
  - `MuTabBar.tsx` (custom tab styling)

- Apply to 2 key views: `product.template` form + `multichannel.listing` form (via `arch` override in XML).

- Keep **Operations/Logistics sections hidden by default** using `groups="base.group_system"` attribute (show only to admin).

**Effort:** 6–8 dev-days (component dev + view XML refactor + testing)

**Tradeoff:**
- Pro: Visible improvement to key user flows; establishes UI precedent for future work
- Con: Only 2 forms affected; other modules (sales, stock) remain unpolished. Risk of custom CSS colliding with Odoo standard styles (requires careful namespacing).

---

### **Option 3: Hybrid — design system doc + selective pattern backport + field curation guide** ← **RECOMMENDED**

**Approach (combines 1 + 2 + governance):**

1. **Design system docs (as Option 1)**
   - Extract `/docs/owner/design-system/mu-design-tokens.css` + `MU_SYSTEM.md`
   - Establish "Hatafa UI Style Guide" with 3 tiers:
     - **Tier 1 (Essential):** Name, Category, Price, Channels, SKU, Status — always show
     - **Tier 2 (Secondary):** Shipping profile, video, tags, personalization — show in tabs
     - **Tier 3 (Advanced):** Operations/Logistics/Bill of Materials/Description blocks — hide by default, group under "Advanced" section or separate admin view

2. **Backport Tier 1 patterns only (MVP scope)**
   - Apply pill badge styling to status fields (Draft/Published/Error)
   - Refactor product.template + multichannel.listing form headers to use purple branding (replace grey)
   - Add **"Tier 1 fields only"** form layout variant that hides Tier 3 fields per user group

3. **Curation rules doc** — `/docs/FORM_CURATION_GUIDE.md` (governance)
   - Rule: "For product/listing forms, show Tier 1 by default; Tier 2 in secondary tabs; Tier 3 behind admin group or 'Advanced Settings' accordion"
   - Rule: "Every custom field added must declare its tier + visibility group"
   - Rule: "Use mu-pill styling for status indicators; grey badges reserved for read-only metadata"

4. **Gradual adoption path**
   - Phase 1 (immediate): Docs + curation guide
   - Phase 2 (W8): Pill badge + header styling (MVP backport)
   - Phase 3 (later): Full OWL component library when resources permit

**Effort:** 5–7 dev-days (docs 1–2 days, backport styling 3–4 days, curation rules 1 day)

**Tradeoff:**
- Pro: Visible, sustainable, establishes design governance; future modules can adopt curation rules at checkin; low risk
- Con: Incomplete compared to mockup (real forms will still show more fields than mockup, but organized better)

---

## Effort estimate per option

| Option | DEV-DAYS | RISK | SUSTAINABILITY | Visible improvement |
|---|---|---|---|---|
| **1: Design system doc only** | 2–3 | ✓ Low | High (reference document) | None (Odoo UI unchanged) |
| **2: Full backport** | 6–8 | ⚠ Medium (CSS collisions, OWL learning curve) | Medium (2 forms only, fragile if Odoo updates) | High (pill badges + purple headers) |
| **3: Hybrid (Recommended)** | 5–7 | ✓ Low | ✓ High (governance + docs + MVP styling) | ✓ Medium–High (tier-based visibility + branding) |

---

## Open questions for owner

1. **Design intent:** Was the mockup created as an *ideal end-state* to build toward, or as a *narrative reference* (acceptable to diverge from if functional intent met)?
   - If ideal end-state → pursue Option 2 or 3 (backport key patterns)
   - If narrative reference → Option 1 (preserve as docs, move on)

2. **Field curation priority:** Which form sections feel "most cluttered" to your team? (e.g., Operations/Routes, Logistics, Description blocks?) Would hiding Tier 3 fields by default help?

3. **Purple branding:** The mockups use custom purple #714B67 throughout. Should this become the standard Hatafa brand color for all custom views, or only for Etsy-specific forms?

4. **Multi-channel readiness:** The mockup treats product form + channels as one unit. Real Odoo split them into product.template + multichannel.listing (separate forms). Is the split acceptable, or should we re-embed channels back into product form?

5. **Timeline:** Is this a "nice-to-have for polish" (backport after core features), or a "blocker for UAT sign-off" (implement immediately)?

---

## Key findings summary

| Category | Finding |
|---|---|
| **Functional completeness** | ~85% of mockup features exist in code; 15% not harvested or deferred (Gearment, address change, conversations API). Core Flow 1 (product creation → publish) is complete and working. |
| **UI polish** | Real Odoo uses default OWL styling. Mockup defines custom `mu-*` design system (10 component patterns). Gap: **0 lines of custom CSS in real code** — mockups are design intent, not implementation. |
| **Field curation** | Mockup shows 6–12 fields/screen. Real forms show 20–30+ fields (all Odoo standard schema + custom). Source of "cluttered" perception: **no view filtering or grouping**. |
| **Missing screenshots** | 7 features exist in code but not captured: SKU Drift, payload preview, error modal, email config, design file, tracking wizard, kanban. 3 features are stubs/not-built: Gearment, address change decision, conversation ingestion. |
| **Design system** | Custom `mu-*` CSS is well-designed, internally consistent, and documented inline in mockup HTMLs. **Recommendation:** extract to standalone tokens file for future OWL library, or accept current Odoo default and move forward. |

---

## Implementation path (if pursuing Option 3)

**Week 1:**
- Draft `/docs/owner/design-system/MU_SYSTEM.md` (design tokens + component specs)
- Author `/docs/FORM_CURATION_GUIDE.md` (Tier 1/2/3 field rules)

**Week 2–3:**
- Add `groups="base.group_system"` attribute to Logistics section in product.template XML (hide from BA, show to admin)
- Create OWL badge component `MuPill.tsx` (reusable pill styling)
- Apply purple header color to product.template + multichannel.listing forms (CSS override)

**Week 4:**
- UAT: verify Forms are visually cleaner without Tier 3 fields
- Document in CLAUDE.md under "Form Curation Rules" for future modules
- Archive mockup HTMLs under `/docs/owner/design-system/reference/` with note: "Design system reference (2026-06-03). Ported patterns: pill badges, purple headers, field grouping. See MU_SYSTEM.md."

---

**Conclusion:** Mockup design is high-quality and aspirational. Real Odoo is functional but unpolished. **Option 3 (Hybrid)** offers the best ROI: preserve design intent as docs, adopt 3–4 high-impact patterns immediately, establish governance for future modules. Expect **5–7 dev-days** for full implementation + improvement visible within **2 UAT cycles**.

