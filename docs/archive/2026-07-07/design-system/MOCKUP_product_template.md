# Mockup procedure — `product.template` form

> Output of `odoo-functional-mockup` skill 2026-06-07. Drives Phase 2.5 XML edits.

---

## Step 1 — Baseline (standard Odoo view to inherit)

| Attribute | Value |
|---|---|
| **XML ID** | `product.product_template_form_view` |
| **File** | `addons/product/views/product_views.xml:5` |
| **Edition** | `[CE]` |
| **Shape** | `<sheet>` + 1 page "General Information" (groups: group_general, group_standard_price, internal_notes) + (Sales page invisible-by-default) + smart-button row |

### Inheritance chain (already in tree, before our backport)

| Layer | Inheriting view | What it adds |
|---|---|---|
| `[CE]` base | `product.product_template_form_view` | name, type, list_price, standard_price, categ_id, uom, description, internal_notes, company_id, smart buttons |
| `[CE]` sale | `addons/sale/views/product_template_views.xml` + `addons/sale/views/product_views.xml` | "Sales" page content (description_sale, taxes, invoicing settings) |
| `[CE]` stock | `addons/stock/views/product_views.xml` | "Inventory" page (route_ids, weight, volume, responsible_id, tracking, customer_lead_time) — **the biggest source of clutter per audit** |
| `[CE]` purchase | `addons/purchase/views/product_views.xml` | "Purchase" page (vendors, taxes, description_purchase, produce_delay) |
| `[CE]` mrp | `addons/mrp/views/...` | "Bill of Materials" smart button |
| **Custom** mhc | `custom_addons/multichannel_hub_core/views/product_template_views.xml` | **6 tabs**: Channels / SKU Drift / Listing Tags / Listing Options / Listing Defaults / Extra Images |
| **Custom** etsy | `custom_addons/etsy_integration/views/product_views.xml:11` | inherits `product.product_template_only_form_view` (sibling, not parent) — Etsy-specific overrides |

### What this means for Phase 2

- We inherit at the `mhc` level (already shipping). One more inherit doesn't add complexity.
- Most "clutter" comes from CE inherits (sale + stock + purchase + mrp). We hide them via `groups=` / `position="attributes"` on the inherited fields — not by removing the inherits.
- 6 mhc tabs are already there. We don't add/remove tabs in Phase 2; we just reorder + apply tier-based visibility.

---

## Step 2 — Taste overlay

Per `taste-skill` brief inference for Odoo back-office:

| Dial | Setting | Reasoning |
|---|---|---|
| DESIGN_VARIANCE | low | B2B back-office productivity surface; data-driven workflow |
| MOTION_INTENSITY | low | No marketing animations; transitions only on state change |
| VISUAL_DENSITY | high | BA Lead opens 50+ products/day; tight spacing > whitespace |

**Direction statement:** "Functional clarity over visual delight. Every visible field earns its place by being used in the Etsy publish narrative. The form should let a BA Lead scan-and-fill a new product in under 2 minutes. Purple (#714B67) accents only on workflow-state indicators (status bar, active tab, SKU mono badge) — everywhere else is default Odoo grey/white. No drop shadows, no gradients, no icon decoration."

---

## Step 3 — Craft check (`od-design-craft` rules applied)

| Rule | Applied? | How |
|---|---|---|
| Anti-AI-slop typography | ✓ | Use Odoo default fonts; only add `.mu-mono` for SKU/listing_id |
| Color discipline | ✓ | Purple #714B67 only on workflow-state surfaces (statusbar active step + active notebook tab); no neon |
| State coverage — empty | ✓ | New-product form shows placeholder text + auto-SKU pill = "—" |
| State coverage — loading | n/a | Odoo handles loading at view level (`.o_view_loading`) |
| State coverage — error | ✓ | Validation messages already standard via Odoo (`<field invalid />`) |
| State coverage — multi-record | n/a | This is a form view |
| State coverage — permission-denied | ✓ | Tier 3 fields hidden via `groups=` — no permission error UI needed |
| a11y — label association | ✓ | All fields keep their auto-rendered `<label for=>` |
| a11y — keyboard nav | ✓ | Tab order preserved; no custom focus traps |
| a11y — contrast | ✓ | Purple #714B67 on white = 7.1:1 (AAA); on mu-brand-50 = 4.6:1 (AA) |
| Form validation patterns | ✓ | Use Odoo's built-in `required` attribute + `@api.constrains` server-side |

---

## Step 4 — Diff vs mockup screen 1 (Flow 1, "Form Sản phẩm chuẩn — Auto-SKU")

### Tier 1 — Always visible (top of General Information page)

Cap at 10 fields. Must include everything in the mockup's left + right column.

| # | Field | Source | Mockup shows? | Action |
|---|---|---|---|---|
| 1 | `name` | CE base | ✓ | Keep visible |
| 2 | `categ_id` | CE base | ✓ "Danh mục" | Keep visible (drives auto-SKU) |
| 3 | `list_price` | CE base | ✓ "Giá bán (USD)" | Keep visible |
| 4 | `default_code` | CE base | ✓ "Mã SKU" + `auto` pill | Keep visible + add `class="mu-mono"` |
| 5 | `image_1920` | CE base | ✓ (implicit — top-right thumbnail) | Keep visible |
| 6 | `x_channel_applicability_ids` | mhc | ✓ "Các kênh áp dụng" | **Promote** from Channels tab into General header (mockup priority) |
| 7 | `attribute_line_ids` | CE base (Variants) | ✓ Material+Size+Color table on Biến thể tab | Keep on Variants tab (Tier 2) but show count widget on General |
| 8 | `state` (workflow) | TBD — does product.template have a state? | ✓ "Draft → Published → Archived" pipeline | **Custom field needed** — see escalation below |
| 9 | `x_sku_auto_status` | etsy_integration | ✓ "BA-edited" pill | Already exists; keep visible |
| 10 | `display_name` (computed) | CE base | ✓ Used in title | Already part of form title |

### Tier 2 — Notebook tabs (secondary, in `<notebook>`)

| Tab | Source | Content | Purpose |
|---|---|---|---|
| Channels | mhc | x_channel_applicability_ids list + per-channel sync state | Per-channel detail |
| Variants | CE base | attribute_line_ids one2many | Already there |
| Listing Defaults | mhc | Default override values | Already there |
| Listing Tags | mhc | Etsy tags | Already there |
| Personalization | custom | x_personalization_* fields | Etsy personalization opt-in |
| Override Etsy | custom | Per-product Etsy field overrides | Advanced override |
| Sales | CE sale | description_sale, taxes_id, public_description | Hide entirely if module not used; otherwise Tier 2 |
| Internal Notes | CE base | description (textarea) | Keep — useful for internal QA notes |

### Tier 3 — Hidden behind `groups=` (developer mode or sys-admin)

| Field | Where | Hide-via | Reason |
|---|---|---|---|
| `type` (Goods/Service/Combo) | CE base General | `groups="base.group_no_one"` | POD always Goods; admin doesn't toggle this per product |
| `combo_ids` | CE base General | already `invisible="type != 'combo'"` | Standard already hides; verify still works |
| `service_tracking` | CE base General | already `invisible="type != 'service'"` | Standard already hides; verify still works |
| `product_tooltip` | CE base General | `groups="base.group_no_one"` | UI hint rarely used |
| `standard_price` | CE base General | `groups="base.group_system"` | Cost is sensitive; admin only |
| `barcode` | CE base header | `groups="base.group_no_one"` | POD products aren't scanned |
| `company_id` | CE base General | already `groups="base.group_multi_company"` | Standard already hides; ok |
| **Operations group** (route_ids, MTO, dropship buy/sell) | CE sale + stock | `groups="base.group_no_one"` on the whole `<group name="operations">` | Routes/MTO config is per-module setup, not per-product editing |
| **Logistics group** (weight, volume, customer_lead_time, responsible_id) | CE stock | Keep weight + volume (Etsy uses them); hide responsible_id + customer_lead_time via `groups="base.group_no_one"` | Etsy needs physical dimensions |
| **Description blocks** (description_purchase, description_pickingin, description_pickingout) | CE base + stock | `groups="base.group_no_one"` | Internal warehouse notes, not Etsy-relevant |
| Smart buttons: Bill of Materials, Documents, Purchased, Sold Units | CE mrp + purchase + sale | already `invisible="..."` on count being 0 | Standard hides empties; OK |
| `produce_delay` | CE mrp | already gated on mrp module | OK |

### Custom-field escalation: workflow `state` field

**Mockup shows:** Top-of-form statusbar `Draft → Published → Archived` (stage pipeline) for the product.

**Standard Odoo:** `product.template` has NO `state` field by default. It's a configuration master, not a workflow object.

**Where workflow state actually lives:**
- `multichannel.listing.state` (Draft / Ready / Published / Error) — per-listing-per-shop
- `product.channel.status.state` (Pending / Synced / Error) — per-channel sync state

**Decision:** the statusbar in the mockup at the product.template form is **misleading**. Real workflow is per-listing, not per-product. **Don't add `state` to product.template** — instead, show a kanban-style summary widget that aggregates per-channel publish state.

**Phase 2 action:** Drop the statusbar at product.template form level. Add a small read-only computed badge `x_publish_state_summary` (Char) showing "3/5 published, 1 error" — compute from `multichannel.listing` rows. Mockup divergence documented as intentional (Standard-Odoo-First + ADR-008 separation between product master + channel listing).

---

## Step 5 — Deliverables

### 5.a — ASCII mockup (post-backport)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Sales ▸ Products ▸ Custom Coffee Mug 11oz                          ba.lead@hatafa │
├───────────────────────────────────────────────────────────────────────────────┤
│ ⓘ Draft │  3/5 published · 1 error              [ Save ] [ Discard ]  ⋮ Actions │
│ ───────────────────────────────────────────────────────────────────────── │
│                                                                              │
│  ╭─ image ────╮   Custom Coffee Mug 11oz                       [UNSAVED]    │
│  │            │                                                              │
│  │  [picture] │   Category    [ Mug                            ]            │
│  │            │   Sales Price [ 14.50  USD                     ]            │
│  ╰────────────╯   SKU         [MUG-CR-F11]  ⌧ auto                          │
│                   Channels    [ Etsy × ]  ⊕ add                              │
│                                                                              │
│  ─── Variants ── Internal Notes ── Channels ── Listing Tags ── Listing Defaults ── Override Etsy │
│                                                                              │
│  Variants:                                                                    │
│   Attribute            Value                Auto SKU segment                  │
│   Material             Ceramic + Chrome     CR                                │
│   Fluid oz             11 oz                F11                               │
│                                                                              │
└───────────────────────────────────────────────────────────────────────────────┘

Hidden (groups="base.group_no_one"): type, combo_ids, product_tooltip, barcode,
  produce_delay, route_ids, responsible_id, customer_lead_time, description_*,
  Operations & Logistics groups, Bill of Materials smart button
Hidden (groups="base.group_system"): standard_price
Hidden (groups="base.group_multi_company"): company_id (already standard)
```

### 5.b — XML pseudo-diff (Phase 2.5 implementation guide)

```xml
<!-- custom_addons/multichannel_hub_core/views/product_template_views.xml -->
<!-- ADD: Tier-3 hiding via xpath position="attributes" -->

<xpath expr="//group[@name='group_general']/field[@name='type']" position="attributes">
    <attribute name="groups">base.group_no_one</attribute>
</xpath>

<xpath expr="//field[@name='product_tooltip']" position="attributes">
    <attribute name="groups">base.group_no_one</attribute>
</xpath>

<xpath expr="//field[@name='standard_price']" position="attributes">
    <attribute name="groups">base.group_system</attribute>
</xpath>

<xpath expr="//field[@name='barcode']" position="attributes">
    <attribute name="groups">base.group_no_one</attribute>
</xpath>

<!-- Hide whole Operations group (Routes/MTO/Dropship setup) -->
<xpath expr="//group[@name='operations']" position="attributes">
    <attribute name="groups">base.group_no_one</attribute>
</xpath>

<!-- Hide responsible_id + customer_lead_time inside Logistics; keep weight + volume -->
<xpath expr="//field[@name='responsible_id']" position="attributes">
    <attribute name="groups">base.group_no_one</attribute>
</xpath>

<xpath expr="//field[@name='customer_lead_time']" position="attributes">
    <attribute name="groups">base.group_no_one</attribute>
</xpath>

<!-- Hide description_purchase / description_pickingin / description_pickingout -->
<xpath expr="//field[@name='description_purchase']" position="attributes">
    <attribute name="groups">base.group_no_one</attribute>
</xpath>

<xpath expr="//field[@name='description_pickingin']" position="attributes">
    <attribute name="groups">base.group_no_one</attribute>
</xpath>

<xpath expr="//field[@name='description_pickingout']" position="attributes">
    <attribute name="groups">base.group_no_one</attribute>
</xpath>

<!-- Promote x_channel_applicability_ids into General Information header -->
<xpath expr="//group[@name='group_standard_price']/field[@name='categ_id']" position="after">
    <field name="x_channel_applicability_ids" widget="many2many_tags"
           options="{'no_create': True}"/>
</xpath>

<!-- Add .mu-mono class to default_code wherever it appears -->
<xpath expr="//field[@name='default_code']" position="attributes">
    <attribute name="class">mu-mono</attribute>
</xpath>

<!-- Add computed x_publish_state_summary badge near save buttons (header) -->
<!-- (requires field definition in models/product_template.py — see model PR) -->
<xpath expr="//header" position="inside">
    <field name="x_publish_state_summary" widget="badge"
           decoration-success="x_publish_state_summary == 'all_published'"
           decoration-info="x_publish_state_summary == 'draft'"
           decoration-warning="x_publish_state_summary == 'partial'"
           decoration-danger="x_publish_state_summary == 'error'"/>
</xpath>
```

### 5.c — Diff against mockup (intentional vs fixable divergence)

| Mockup element | Real Odoo after Phase 2.5 | Divergence type |
|---|---|---|
| Top stage pipeline "Draft → Published → Archived" | Badge "3/5 published, 1 error" instead | **Intentional** — Standard-Odoo-First + ADR-008 (workflow lives in multichannel.listing) |
| Chrome bar "Bán hàng › Sản phẩm › Sản phẩm" | Odoo default breadcrumb | **Intentional** — keep default Odoo navbar |
| Form title with "UNSAVED" yellow pill | Odoo's default "Modified" indicator (light grey "Unsaved Changes") | **Fixable** — could add `widget="modified_state"` if exists, otherwise leave |
| 2-column field layout in General | Achievable via `<group><group>...</group><group>...</group></group>` — already used by standard `group_general` + `group_standard_price` | **Match** — no change needed |
| Variants tab table with "Auto SKU segment" column | Already in `mhc.view_product_sku_drift_list` reachable from kanban menu; not on this form tab | **Intentional** — keep separate (per ADR-013) |
| Purple Etsy pill on "Các kênh áp dụng" row | `widget="many2many_tags"` with color_field — needs `color` field on `x_channel_applicability_ids` to source colors per channel | **Fixable** — add color mapping in mhc model (separate slice if scope grows) |

---

## Summary for Phase 2.5 implementation

**XML edit estimate:** ~15 `<xpath>` blocks in `multichannel_hub_core/views/product_template_views.xml`. ~30 lines added.

**Model edit estimate:** 1 new computed field `x_publish_state_summary` on `product.template` (Char, compute from `multichannel.listing` aggregates). ~15 LOC.

**SCSS edit estimate:** ~50 LOC for `.mu-mono` styling + `.o_statusbar_status .btn-primary` purple tint + `.o_notebook .nav-link.active` purple bottom-border. New file `multichannel_hub_core/static/src/scss/mu_tokens.scss`.

**Manifest:** add `'web.assets_backend': ['multichannel_hub_core/static/src/scss/mu_tokens.scss']` to mhc manifest's assets dict.

**Expected effort:** 1 dev day total for product.template form (vs prior estimate 1.5-2 days — clarified scope drops the OWL component work).
