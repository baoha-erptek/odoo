# Mockup procedure — `multichannel.listing` form

> Output of `odoo-functional-mockup` skill 2026-06-07. Drives Phase 2.5 XML edits.

---

## Step 1 — Baseline

| Attribute | Value |
|---|---|
| **XML ID** | `multichannel_hub_core.view_multichannel_listing_form` |
| **File** | `custom_addons/multichannel_hub_core/views/multichannel_listing_views.xml:32` |
| **Edition** | Custom (no Odoo CE equivalent; this is a new model from ADR-013 multichannel hub) |
| **Shape** | `<header>` with state-conditional button + `widget="statusbar"` · `<sheet>` with alerts + image_1920 + title + External group + Scope group + 2 pages (Listing Basics, Video) |

**Important — already curated.** This form went through P-LIST-UX-FIXES (commit history shows R1/R2/R3 markers) which already:
- Added "Open in Etsy Shop Manager" button gated on `state == 'published'`
- Added workflow context callout + readonly indicator
- Wrapped Scope group inside "Advanced settings" outer group

Plus `etsy_integration/views/multichannel_listing_etsy_views.xml` adds 2 more pages:
- "How It's Made" (etsy taxonomy / shipping profile / who_made / when_made / is_supply)
- "Shipping & Variations" (variant Etsy property mapping)

**Total tabs after all inherits:** Listing Basics · Video · How It's Made · Shipping & Variations = 4 tabs.

---

## Step 2 — Taste overlay

Same direction as `product.template` (see [`MOCKUP_product_template.md`](./MOCKUP_product_template.md) §Step 2). DESIGN_VARIANCE=low, VISUAL_DENSITY=high, motion off. Purple #714B67 on statusbar active + active notebook tab + .mu-mono external_ref.

---

## Step 3 — Craft check

Same checklist as product.template. State coverage is **already implemented** via the P-LIST-UX-FIXES alerts (Draft → Ready → Published callout + Read-only banner). Empty state for video is handled with explanatory `<p class="text-muted">`.

| Rule | Applied? | How |
|---|---|---|
| State coverage — empty (no draft) | ✓ | Alert "Publishing workflow" explains the lifecycle |
| State coverage — read-only | ✓ | Yellow `alert alert-warning` shows when state != 'draft' |
| State coverage — published / external_ref | ✓ | "Open in Etsy Shop Manager" button gated on `state == 'published' and external_ref` |
| a11y — keyboard nav | ✓ | Standard Odoo notebook tab order |
| a11y — `<label for>` | ✓ | `<label for="title"/>` already present |

---

## Step 4 — Diff vs mockup screens 3, 5, 7 (Flow 1)

Mockup screen 3 ("Hậu trường — gói payload sắp gửi Etsy") covers the Channels tab on product.template form, NOT directly the multichannel.listing form. Skip — covered in the product.template mockup output.

Mockup screen 5 ("Form multichannel.listing tab Shipping & Variations") — directly applies.

Mockup screen 7 ("Wizard Publish to Etsy") — wizard, not this form.

### Tier 1 — Always visible (top of form)

The current curation is already strong. Tier 1 = what shows above the notebook:

| # | Field | Source | Mockup shows? | Action |
|---|---|---|---|---|
| 1 | `image_1920` | mhc base | ✓ | Keep (already there as `oe_avatar`) |
| 2 | `title` | mhc base | ✓ | Keep + readonly when state != 'draft' (already done) |
| 3 | `external_ref` (Etsy listing_id) | mhc base | ✓ "Etsy listing_id" | Keep + **add `class="mu-mono"`** |
| 4 | `last_synced_at` | mhc base | ✓ "Đã sync" | Keep readonly |
| 5 | `state` widget=statusbar | mhc base | ✓ — Draft → Ready → Published | Keep, **add purple SCSS on active step** |
| 6 | "Open in Etsy Shop Manager" button | mhc base | ✓ | Keep (already conditional on state) |

### Tier 2 — Notebook tabs (already curated; reorder for narrative)

| Order | Tab | Source | Tier 2 reason |
|---|---|---|---|
| 1 | Listing Basics (description) | mhc | Marketing copy — first thing BA edits |
| 2 | Shipping & Variations | etsy_integration | Etsy taxonomy + shipping profile (Wave 2 Esty-189/191) |
| 3 | How It's Made | etsy_integration | who_made / when_made / is_supply (Wave 2 Esty-193) |
| 4 | Video | mhc | Optional Etsy video upload (Wave 2 Esty-199) |

**Re-ordering needed?** Currently order is: Listing Basics → Video → How It's Made → Shipping & Variations. Mockup narrative flow suggests:
- Listing Basics (description) → Shipping & Variations (variant mapping) → How It's Made (Etsy required fields) → Video (optional).
- **Phase 2.5 action:** Use xpath to move "Shipping & Variations" between "Listing Basics" and "How It's Made"; move "Video" to last.

### Tier 3 — Hidden behind `groups="base.group_no_one"`

Current form has "Advanced settings" outer group containing `product_tmpl_id`, `channel_id`, `shop_ref`, `sequence`. These are technical fields BA Lead doesn't edit (they're set at create-time).

**Phase 2.5 action:** Add `groups="base.group_no_one"` on the `<group string="Advanced settings" name="scope_advanced">` group so it only shows in developer mode. Already 95 % curated via the visual grouping; adding `groups=` hides it cleanly from BA.

---

## Step 5 — Deliverables

### 5.a — ASCII mockup (post-backport)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Operations ▸ Listings ▸ Custom Coffee Mug 11oz · jahandmadeart       ba.lead │
├───────────────────────────────────────────────────────────────────────────────┤
│ [ Open in Etsy Shop Manager ↗ ]    ⬛ Draft  ⬛ Ready  ●Published    ⋮ Actions │
│ ───────────────────────────────────────────────────────────────────────────── │
│ ⓘ Publishing workflow: Draft (edit) → Ready (BA approve) → Published (Etsy)  │
│                                                                              │
│  ╭───────╮   Custom Coffee Mug 11oz                                          │
│  │ image │                                                                    │
│  │       │   External Reference   [4517818413]   ⌧ mono                     │
│  │       │   Last Synced At       2026-06-07 08:24                          │
│  ╰───────╯                                                                    │
│                                                                              │
│  ─── Listing Basics ─── Shipping & Variations ─── How It's Made ─── Video ── │
│                                                                              │
│  Description:                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Hand-thrown ceramic mug with chrome finish. Microwave safe.            │   │
│  │ Each piece is unique due to handcrafted nature.                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└───────────────────────────────────────────────────────────────────────────────┘

Hidden (groups="base.group_no_one"): Advanced settings group
  (product_tmpl_id, channel_id, shop_ref, sequence) — set at create-time only
```

### 5.b — XML pseudo-diff (Phase 2.5)

```xml
<!-- custom_addons/multichannel_hub_core/views/multichannel_listing_views.xml -->
<!-- ADD: groups= on Advanced settings + .mu-mono on external_ref -->

<xpath expr="//group[@name='scope_advanced']" position="attributes">
    <attribute name="groups">base.group_no_one</attribute>
</xpath>

<xpath expr="//field[@name='external_ref']" position="attributes">
    <attribute name="class">mu-mono</attribute>
</xpath>

<!-- Re-order pages: Shipping & Variations between Listing Basics and How It's Made,
     Video last. Done by xpath inside etsy_integration extension since the
     "Shipping" and "How It's Made" pages live there. -->
```

```xml
<!-- custom_addons/etsy_integration/views/multichannel_listing_etsy_views.xml -->
<!-- Re-order: keep current xpath but use `position="after"` w/ the correct anchor -->
<!-- Current:
       <xpath expr="//page[@name='marketing']" position="after">
         <page string="How It's Made" name="etsy"/>
         <page string="Shipping &amp; Variations" name="shipping_variations"/>
       </xpath>
     Desired final order: Listing Basics · Shipping & Variations · How It's Made · Video
     Solution: rewrite to insert Shipping & Variations after Listing Basics first,
     then re-anchor How It's Made after Shipping & Variations.
-->

<xpath expr="//page[@name='marketing']" position="after">
    <page string="Shipping &amp; Variations" name="shipping_variations">
        <!-- existing shipping_variations content -->
    </page>
    <page string="How It's Made" name="etsy">
        <!-- existing how-its-made content -->
    </page>
</xpath>

<!-- The mhc base form has 'video' page AFTER 'marketing'. With the above order
     we need to MOVE 'video' to after 'etsy'. Do via xpath move: -->
<xpath expr="//page[@name='video']" position="move-to-end"/>
<!-- Odoo XML position attribute "move-to-end" doesn't exist by default — use
     position="after" combined with position="move" pattern instead. -->
```

⚠ **Note on page reordering:** Odoo's XML inheritance doesn't have a clean "move tab to end" primitive. We can either:
1. **Easy path** (recommended): leave current order Listing Basics → Video → How It's Made → Shipping & Variations. The user-experience cost is minor; saves XML refactor risk.
2. **Hard path**: delete `<page name="video"/>` and re-add at end via `position="inside"`. Risk: any user customisation on the video page is lost.

**Phase 2.5 decision:** take the easy path; document re-order as Phase 3 (future) cleanup.

### 5.c — Diff against mockup (intentional vs fixable)

| Mockup element | Real Odoo after Phase 2.5 | Divergence type |
|---|---|---|
| Statusbar Draft → Ready → Published | Same (`widget="statusbar"`) — add purple tint on active step | **Match** ✓ |
| External Reference + Last Synced At at top | Same (currently in "External" group) — add `.mu-mono` to external_ref | **Match** ✓ |
| Image avatar + title at top | Same (`oe_avatar` + `<h1>`) | **Match** ✓ |
| Workflow callout (purple info banner) | Currently `alert alert-info` (blue) — could re-tint to purple via SCSS scope | **Fixable** — SCSS override on `.alert-info` within `.o_form_view[name="multichannel.listing"]` |
| Read-only warning when state != draft | Currently `alert alert-warning` (yellow) — keep yellow per craft rules | **Match** ✓ |
| 4 tabs reordered (Listing Basics · Shipping · How It's Made · Video) | Easy-path: keep Listing Basics · Video · How It's Made · Shipping (current order) | **Intentional defer** to Phase 3 |
| Advanced settings hidden | Hide via `groups="base.group_no_one"` (new in Phase 2.5) | **Fixable** ✓ |

---

## Summary for Phase 2.5 implementation

**XML edit estimate:** ~3 `<xpath>` blocks in `multichannel_hub_core/views/multichannel_listing_views.xml` (add `groups=` to scope_advanced, `.mu-mono` to external_ref, optional `.mu-mono` to listing_id columns in list view). ~6 lines added.

**SCSS edit estimate:** included in the product.template SCSS file (same `mu_tokens.scss`). Add `.o_form_view[name="multichannel.listing"] .alert-info { /* purple tint */ }` scoped override.

**Expected effort:** 0.5 dev day for multichannel.listing (form is already well-curated; we're just adding `groups=` + `class=` decorations). Combined with product.template = 1.5 dev days total form work. Plus SCSS (~0.5 day). **Total Phase 2.5 estimate: 1.5–2 dev days** — under the original 3–4 day estimate.
