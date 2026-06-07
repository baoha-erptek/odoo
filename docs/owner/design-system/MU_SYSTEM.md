# Mu Design System — Hatafa UI Reference

> Hệ thiết kế của Hatafa (mockup → real Odoo backport).
> Trích từ 5 mockup HTML trong `docs/owner/business-flows/` (designed 2026-06-03).
> Tokens canonical: [`mu-design-tokens.css`](./mu-design-tokens.css).

**Phiên bản:** 1.0 (2026-06-07) · **Trạng thái:** Reference (Phase 1 của Option 3 Hybrid)

---

## Tại sao có file này

Báo cáo [`COMPARISON_MOCKUP_VS_ACTUAL.md`](../business-flows/COMPARISON_MOCKUP_VS_ACTUAL.md) xác định:
- Mockup dùng ngôn ngữ trực quan riêng (`.mu-*` classes, purple #714B67, pill badges, stage pipeline) — sạch + có hệ thống.
- Real Odoo dùng default OWL — không có một dòng custom CSS nào.

Mu Design System là tiếp cận **archive trước, adopt sau**:
1. Lưu CSS gốc + docs về 10 patterns ở đây (Phase 1 — file này).
2. Backport 3-4 patterns ROI cao nhất vào OWL components (Phase 2).
3. Mở rộng full library khi resource cho phép (Phase 3).

---

## Color palette

### Brand (purple)
| Token | Hex | Dùng cho |
|---|---|---|
| `--mu-brand` | `#714B67` | Headers, primary buttons, active tab/stage, mono SKU color |
| `--mu-brand-50` | `#faf5f9` | Background mono SKU pill, active stage tint, info callout |
| `--mu-brand-100` | `#f4e8f0` | Hover state cho info callout |
| `--mu-brand-200` | `#e4cee0` | Border cho info callout (faint purple) |

### Neutrals (greys)
| Token | Hex | Dùng cho |
|---|---|---|
| `--mu-ink` | `#1a1a1a` | Body text default |
| `--mu-ink-strong` | `#111827` | h2, h3 headings, form titles |
| `--mu-ink-soft` | `#1f2937` | List rows, form field values |
| `--mu-muted` | `#6b7280` | Field labels, captions, secondary text |
| `--mu-muted-strong` | `#4b5563` | Breadcrumb text |
| `--mu-muted-soft` | `#9ca3af` | Placeholders ("—", "không dùng") |
| `--mu-rule` | `#e5e7eb` | Borders, section dividers |
| `--mu-rule-soft` | `#f3f4f6` | Field-level dividers (in form rows) |
| `--mu-bg-page` | `#fafafa` | Page background |
| `--mu-bg-surface` | `#ffffff` | Cards, sections, modals |
| `--mu-bg-sunken` | `#f9fafb` | Table headers, status bar |

### Status (paired bg/fg)
| Status | Background | Foreground | Token |
|---|---|---|---|
| Success | `#dcfce7` | `#15803d` | `--mu-success-bg/fg` |
| Warning | `#fef3c7` | `#b45309` | `--mu-warn-bg/fg` |
| Danger | `#fee2e2` | `#b91c1c` | `--mu-danger-bg/fg` |
| Info | `#dbeafe` | `#1d4ed8` | `--mu-info-bg/fg` |
| Neutral | `#f3f4f6` | `#4b5563` | `--mu-neutral-bg/fg` |

---

## Typography scale

| Size | Px | Token | Dùng cho |
|---|---|---|---|
| 2xs | 11 | `--mu-size-xs` | Pill labels, smart-button counts, uppercase column headers |
| xs | 12 | `--mu-size-sm` | Field labels, captions, meta lines, table cells phụ |
| sm | 13 | `--mu-size-md` | Body, form field values, breadcrumb, status bar |
| md | 14 | `--mu-size-lg` | Modal header, đôi khi status indicators |
| lg | 16 | `--mu-size-xl` | Topbar heading |
| xl | 18 | `--mu-size-2xl` | Section h3 (numbered) |
| 2xl | 20 | `--mu-size-3xl` | Form titles (mu-form-title) |
| 3xl | 26 | `--mu-size-4xl` | Page hero h2 |

**Font families:**
- Sans: system stack (San Francisco / Segoe UI / Roboto)
- Mono: `"SF Mono", Menlo, Consolas, monospace` — dành cho SKU, listing_id, taxonomy_id

**Weights:** 400 regular · 500 medium · 600 semibold · 700 bold.

---

## Spacing grid

Base unit = 2 px multiples. Common tokens:
| Token | Px | Dùng cho |
|---|---|---|
| `--mu-space-1` | 6 | Gap nhỏ trong stage pipe |
| `--mu-space-2` | 8 | Button group gap, pill margin |
| `--mu-space-3` | 10 | Banner padding |
| `--mu-space-4` | 12 | List cell padding, modal head padding |
| `--mu-space-5` | 14 | Chrome bar gap, modal body padding |
| `--mu-space-6` | 18 | Form padding, modal body padding-x |
| `--mu-space-7` | 22 | Mockup screen margin-bottom |
| `--mu-space-8` | 28 | Page container padding-x |
| `--mu-space-9` | 32 | Hero padding-x |

**Radii:** 3 (buttons) · 4 (cards) · 6 (modals) · 10 (sections) · 12 (page hero) · 999 (pills).

---

## 10 Component Patterns

### 1. Chrome bar
Top navigation bar simulating Odoo's app header.

```html
<div class="mu-chrome-bar">
  <span class="mu-app">Bán hàng</span>
  <span class="mu-menu">Sản phẩm › Sản phẩm</span>
  <span class="mu-spacer"></span>
  <span class="mu-user">ba.lead@hatafa</span>
</div>
```

- Background: `--mu-brand` (purple)
- Text: white + 85% opacity for menu/user
- Use as the top frame of every mockup screen

### 2. Breadcrumb
Path navigation under chrome bar.

```html
<div class="mu-breadcrumb">
  Sản phẩm<span class="mu-sep">›</span>
  Custom Coffee Mug 11oz<span class="mu-sep">›</span>
  <strong>Channels</strong>
</div>
```

- White background, grey separators, ink-soft current page
- Always shows the user's location in app navigation

### 3. Status bar
Action button row + state pipeline indicator.

```html
<div class="mu-statusbar">
  <button class="mu-btn">Discard</button>
  <button class="mu-btn mu-btn-primary">Save</button>
  <button class="mu-btn">Publish Draft Only</button>
  <button class="mu-btn">Publish to Etsy</button>
  <div class="mu-stage-pipe">
    <span class="mu-stage active">Draft</span>
    <span>›</span>
    <span class="mu-stage">Published</span>
    <span>›</span>
    <span class="mu-stage">Archived</span>
  </div>
</div>
```

- Background: subtle sunken grey
- Stage pipeline on the right shows current workflow state
- Active stage gets purple border + tint

### 4. Form layout (2-column grid)
Curated field grid (Tier 1 fields only — see [FORM_CURATION_GUIDE](../../FORM_CURATION_GUIDE.md)).

```html
<div class="mu-form">
  <div class="mu-form-title">Custom Coffee Mug 11oz
    <span class="mu-pill mu-pill-warn">UNSAVED</span>
  </div>
  <div class="mu-grid2">
    <div>
      <div class="mu-field">
        <div class="mu-field-label">Tên sản phẩm</div>
        <div class="mu-field-value">Custom Coffee Mug 11oz</div>
      </div>
      ...
    </div>
    <div>
      <div class="mu-field">
        <div class="mu-field-label">Mã SKU</div>
        <div class="mu-field-value">
          <span class="mu-mono">MUG-CR-F11</span>
          <span class="mu-pill mu-pill-success">auto</span>
        </div>
      </div>
      ...
    </div>
  </div>
</div>
```

- 140 px label column + flexible value column
- 18 px / 32 px gap (row/col)
- Each field row has bottom border in --mu-rule-soft
- Stacks to 1 column under 760 px

### 5. Pill badges
Status indicators in 4 colors.

```html
<span class="mu-pill mu-pill-success">Published</span>
<span class="mu-pill mu-pill-warn">UNSAVED</span>
<span class="mu-pill mu-pill-danger">Error</span>
<span class="mu-pill mu-pill-neutral">Draft</span>
```

- Always 11 px, semibold, 12 px corner radius
- Inline-block, fits naturally in titles, list cells, field values
- Use beside SKU mono token (`auto`, `BA-edited`)

### 6. Mono token
SKU / listing_id / taxonomy_id values get the purple mono treatment.

```html
<span class="mu-mono">MUG-CR-F11</span>
<span class="mu-mono">2172</span>
```

- Font: SF Mono / Menlo
- Background: --mu-brand-50 (tinted purple)
- Color: --mu-brand (purple), semibold
- Use anywhere a code/id appears — signals "this is data Odoo generated, not user-editable"

### 7. Tabs
Horizontal tab bar (notebook style).

```html
<div class="mu-tabs">
  <span class="mu-tab">Mô tả</span>
  <span class="mu-tab active">Biến thể</span>
  <span class="mu-tab">Channels</span>
  <span class="mu-tab">Cá nhân hoá</span>
  <span class="mu-tab">Override Etsy</span>
</div>
```

- 1 px bottom border across the row
- Active tab gets a 2 px purple bottom border + semibold purple text
- Inactive tabs: muted grey
- Horizontal scroll on overflow

### 8. List table
Curated list view (replaces Odoo `tree` view when used in mockups).

```html
<table class="mu-list">
  <thead>
    <tr>
      <th>Thuộc tính</th>
      <th>Giá trị</th>
      <th>Auto SKU segment</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Chất liệu</td>
      <td>Ceramic + Chrome</td>
      <td class="mu-mono">CR</td>
    </tr>
  </tbody>
</table>
```

- Header: uppercase, semibold, 11 px, letter-spacing 0.4 px, grey
- Body: 13 px, ink-soft, 1 px row dividers
- Last row has no bottom border
- Combine with `.mu-text-danger` for error highlights

### 9. Kanban cards
Card-based grouping (replaces Odoo kanban view in mockups).

```html
<div class="mu-kanban">
  <div class="mu-kb-card">
    <h4>Custom Coffee Mug 11oz</h4>
    <div class="mu-kb-meta">
      SKU <b>MUG-CR-F11</b><br>
      <b>$14.50</b> · 11 sales<br>
      Updated 2 days ago
    </div>
  </div>
  ...
</div>
```

- Responsive: minmax(220 px, 1 fr) — auto-fills available width
- Card: white surface, 1 px rule border, 4 px radius
- 13 px card title (semibold) + 12 px meta lines

### 10. Modal (danger / confirmation)
Error dialog used for Etsy 400 / 401 / validation errors.

```html
<div class="mu-modal-overlay">
  <div class="mu-modal">
    <div class="mu-modal-head">⚠ Etsy trả lỗi 400 — không thể publish</div>
    <div class="mu-modal-body">
      <p>Bước thất bại: createListing</p>
      <p>Mã lỗi HTTP: 400</p>
      <div class="mu-modal-banner">
        Đang chờ phản hồi chi tiết từ Etsy. Xem etsy_response_body
        để có nội dung lỗi đầy đủ.
      </div>
    </div>
    <div class="mu-modal-foot">
      <button class="mu-btn">Đóng</button>
      <button class="mu-btn mu-btn-primary">Mở etsy.api.log</button>
    </div>
  </div>
</div>
```

- Overlay: 60 % opacity purple-ink (`rgba(31,19,32,0.6)`)
- Head: danger tint background + danger fg + danger rule border
- Banner inside body: warning yellow with left border
- Foot: sunken grey background, button group right-aligned

---

## Bonus pattern: standalone warning banner

```html
<div class="mu-banner">
  Cảnh báo: shop chưa cấu hình default taxonomy_id —
  publish sẽ dùng giá trị product-level.
</div>
```

- Warning yellow background + left border
- Use INSIDE form sections to flag missing config / soft errors that don't block

---

## Iconography

Mockups dùng emoji + unicode arrows làm icons:
- `›` separator (breadcrumb, stage pipe)
- `☐` checkbox unchecked
- `✓` / `✗` status
- `⚠` warning header
- `🛈` info header (optional)

Backport plan dùng Font Awesome 5 (đã có sẵn trong Odoo 19):
- `fa-circle` cho stage indicator
- `fa-exclamation-triangle` cho warning
- `fa-times-circle` cho error
- `fa-check-circle` cho success

---

## Khi backport vào OWL — convention (revised 2026-06-07 per BA audit)

**⚠ Important — Standard-Odoo-First applied:** Phase 2 = **CSS overrides + view XML only**.
**NO new OWL components.** BA review identified that what we initially planned as
`MuPill` / `MuStatusBar` are already shipped by Odoo 19 CE — we just need to style them.

| Mockup pattern | Standard Odoo equivalent | Phase 2 action |
|---|---|---|
| Chrome bar | `nav.o_main_navbar` | Skip — keep default |
| Breadcrumb | `.o_breadcrumb` (auto-rendered) | Skip — keep default |
| Status bar (buttons + stage pipe) | `<header>` + `<button class="oe_highlight"/>` + `<field widget="state_selection"/>` | CSS override only — apply purple `.mu-stage` tint to active state |
| Form grid | `<group>` + `<group string=""/>` | CSS override only — `.mu-grid2` class on outer `<sheet>` div |
| Pill badge (4 colors) | `<field widget="badge"/>` (Selection field) + `decoration-success/warning/danger/info` | **No `MuPill` component.** Use standard `widget="badge"`; add `.mu-pill-*` CSS overrides for tone tuning |
| Stage pipeline (Draft → Published → Archived) | `<field widget="state_selection"/>` inside `<header>` | **No `MuStatusBar` component.** Standard widget exists; add `.mu-stage` CSS overrides |
| Mono token (SKU / listing_id) | `<field/>` + `class="mu-mono"` | CSS-only refinement |
| Tabs | `<notebook>` + `<page>` (Odoo standard arch) | **No `MuTabs` component.** Apply `.mu-tabs`/`.mu-tab.active` CSS to existing `.o_notebook .nav-tabs` |
| List table | `<list>` view (Odoo standard) | CSS refinement on `.o_list_view` |
| Kanban cards | `<kanban>` view (Odoo standard) | CSS refinement on `.o_kanban_record` |
| Modal (error 400) | `WarningDialog` / Odoo's standard modals | CSS override on `.modal-header` for danger color |
| Banner | `<div class="alert alert-warning"/>` (Bootstrap, ships with Odoo) | CSS override only |

**Revised Phase 2 MVP scope (CSS-only, no JS components):**
1. SCSS bundle override loading the design tokens (target: `etsy_integration/static/src/scss/mu_tokens.scss`)
2. CSS overrides for `.mu-pill-*` (decoration colors), `.mu-stage` (active state), `.mu-mono` (SKU styling), `.mu-tabs` (active tab purple tint)
3. View XML changes on `product.template` + `multichannel.listing` to add `groups=`/`invisible=` per Tier 3 rules + wrap key fields with `class="mu-mono"`

**Estimated effort:** 3–4 dev days (vs prior 5-7 day estimate — dropped because no OWL components).

---

## Phase 1 deliverables checklist

- [x] `mu-design-tokens.css` — all 10 patterns extracted from mockups, organized into 15 sections.
- [x] `MU_SYSTEM.md` — this doc.
- [x] `FORM_CURATION_GUIDE.md` — Tier 1/2/3 rules (BA-confirmed all standard Odoo mechanisms).
- [x] BA audit (Standard-Odoo-First) — 5 reinventions identified, all addressed by revised backport table above.

## Phase 2 entry-criteria

**A. BA confirmations needed (Telegram-actionable, before kickoff):**
1. Confirm Phase 2 scope = **CSS + view XML only**, no new OWL components (per BA audit + revised backport table above).
2. Confirm targets = `product.template` + `multichannel.listing` MVP.
3. Confirm purple branding = backend bundle CSS override (not standalone).

**B. Owner Q1-Q5 from COMPARISON doc** (less blocking now since BA audit clarified some):
1. Q1 Mockup intent (ideal vs reference) — answer guides whether to refine more mockup styles into CSS later.
2. Q2 Field section priority for hiding — needed for Tier 3 `groups=` decisions on `product.template`.
3. Q3 Purple branding scope — needed for SCSS variable injection scope.
4. Q4 mhc form split — design decision, low Phase 2 impact.
5. Q5 Timeline urgency — affects sprint planning.

## Phase 2 skill sequence (per BA inventory)

1. **odoo-standard-first** — Re-validate the revised plan before any code (~20 min).
2. **odoo-functional-mockup** — Walk the 2 target forms (product.template + multichannel.listing) through baseline → taste → craft → diff (~90 min).
3. **od-design-craft + codebase-graph** (parallel) — Craft validates token consistency; graph traces form inheritance to avoid view-conflict regressions (~75 min total).
4. **taste-skill** (optional, post-MVP) — Anti-slop final pass.
5. **design-review** (post-MVP) — Quality gate after code lands.

Skills explicitly SKIPPED: frontend-design, design-consultation, design-shotgun, ascii-ui-mockup-generator, frontend-patterns, design-html (BA reasoning in tracker row P-DS-1-DESIGN-SYSTEM-DOCS).

---

## Reference mockups

Frozen design intent — these stay as-is for inspiration:

- [Flow 1 — Tạo sản phẩm](../business-flows/flow-1-tao-san-pham.html)
- [Flow 2 — Tiếp nhận đơn Etsy](../business-flows/flow-2-nhan-don-hang-etsy.html)
- [Flow 3a — Giao hàng nội bộ](../business-flows/flow-3a-giao-hang-in-noi-bo.html)
- [Flow 3b — Gearment dropship](../business-flows/flow-3b-giao-hang-gearment-dropship.html)
- [Flow 4 — Hậu mãi](../business-flows/flow-4-hau-mai.html)

Source CSS extraction is now at [`mu-design-tokens.css`](./mu-design-tokens.css) — single source of truth.
