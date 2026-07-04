---
name: Hatafa Etsy ERP — Design Tokens
version: 1.0.0
updated: 2026-06-20
status: canonical
derived_from: docs/owner/design-system/mu-design-tokens.css
applied_in: custom_addons/multichannel_hub_core/static/src/scss/mu_tokens.scss
lint: "npx --yes @google/design.md lint docs/design/HATAFA.design.md"
---

# Hatafa Etsy ERP — Design Tokens

Single machine-readable token source for the "Màn hình Odoo" mockups and their Odoo backport.
Authored in the Google `@google/design.md` format so the palette can be WCAG-lint-checked
(`npx --yes @google/design.md lint …`). Supersedes the hand-CSS in
`docs/owner/design-system/mu-design-tokens.css` as the **source of truth** going forward; that
CSS file stays as the rendered reference and the SCSS bundle (`mu_tokens.scss`) is the runtime
subset actually loaded by Odoo.

**Adoption principle (TFV pattern):** every visual element maps to a real Odoo widget/class.
No new OWL components — tokens are applied as scoped SCSS overrides. See the component map below.

## Colors

### Brand

| Token | Hex | Use |
|---|---|---|
| `primary` | `#714B67` | Headers, primary buttons, active tab/stage, mono code color |
| `primaryTint` | `#FAF5F9` | Mono badge bg, active-stage tint, info callout bg |
| `primary100` | `#F4E8F0` | Info callout hover |
| `primary200` | `#E4CEE0` | Info callout border (faint purple) |
| `primaryContrast` | `#FFFFFF` | Text on primary |

### Neutrals

| Token | Hex | Use |
|---|---|---|
| `ink` | `#1A1A1A` | Body text |
| `inkStrong` | `#111827` | Headings, form titles |
| `inkSoft` | `#1F2937` | List rows, field values |
| `textMuted` | `#6B7280` | Labels, captions |
| `textMutedStrong` | `#4B5563` | Breadcrumb |
| `textMutedSoft` | `#9CA3AF` | Placeholders |
| `border` | `#E5E7EB` | Borders, dividers |
| `borderSoft` | `#F3F4F6` | Field-row dividers |
| `surface` | `#FFFFFF` | Cards, sections, modals |
| `surfaceAlt` | `#FAFAFA` | Page background |
| `surfaceSunken` | `#F9FAFB` | Table header, status bar |

### Status (paired surface/text — AA contrast)

| Status | Surface | Text | Tokens |
|---|---|---|---|
| Success | `#DCFCE7` | `#15803D` | `successSurface` / `success` |
| Warning | `#FEF3C7` | `#B45309` | `warningSurface` / `warning` |
| Danger | `#FEE2E2` | `#B91C1C` | `dangerSurface` / `danger` |
| Info | `#DBEAFE` | `#1D4ED8` | `infoSurface` / `info` |
| Neutral | `#F3F4F6` | `#4B5563` | `neutralSurface` / `neutral` |

> Lint target: every surface/text pair above must clear WCAG AA (4.5:1) for badge text.

## Typography

| Token | Px | Use |
|---|---|---|
| `size-xs` | 11 | Pill labels, smart-button counts, uppercase column headers |
| `size-sm` | 12 | Field labels, captions, meta |
| `size-md` | 13 | Body, field values, breadcrumb, status bar |
| `size-lg` | 14 | List headers, modal header |
| `size-xl` | 16 | Topbar heading |
| `size-2xl` | 18 | Section h3 |
| `size-3xl` | 20 | Form title |
| `size-4xl` | 26 | Page hero |

- `font-body`: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- `font-mono`: `"SF Mono", Menlo, Consolas, monospace` (SKU / listing_id / taxonomy_id)
- Weights: 400 / 500 / 600 / 700.

## Spacing & radii

- Scale: 6 / 8 / 10 / 12 / 14 / 18 / 22 / 28 / 32 px.
- Radii: 3 (buttons) · 4 (cards) · 6 (modals) · 10 (sections) · 12 (hero) · 999 (pills).

## Component map — mockup element → Odoo idiom (the achievability contract)

This is the bridge that makes "mockup intent" buildable in standard Odoo. Each row is how a
`mu-*` mockup element is delivered without custom components.

| Mockup element | Odoo idiom | Token applied | Shipped |
|---|---|---|---|
| Chrome bar / breadcrumb | `nav.o_main_navbar` / `.o_breadcrumb` | — (keep default) | n/a |
| Pill badge (4 colors) | `widget="badge"` + `decoration-success/warning/danger/info` | status pairs | partial |
| Status pipeline (Draft→Published→Archived) | `widget="statusbar"` in `<header>` | `primary` active tint | yes (listing) |
| Active notebook tab | `<notebook>` `.nav-link.active` | `primary` bottom border | yes (3 forms) |
| Mono code (SKU/id) | `<field class="mu-mono"/>` | `primaryTint` bg, `primary` text | yes |
| 2-col field grid | `<group>`/`<group>` | spacing scale | n/a (default) |
| List table | `<list>` view | header tints | refine |
| Kanban cards | `<kanban>` grouped | card tokens | refine |
| Error modal | OWL `Dialog` / `WarningDialog` | `danger` header | n/a (standard) |
| Inline banner | `<div class="alert alert-info/warning">` | `primaryTint` / `warningSurface` | yes (listing) |

## Curation (field tiers)

Per `docs/FORM_CURATION_GUIDE.md`:
- **Tier 1** — always visible (Name, Category, Price, Channels, SKU, Status).
- **Tier 2** — secondary tabs (shipping profile, video, tags, personalization).
- **Tier 3** — `groups="base.group_no_one"` (Routes/MTO, logistics, debug/diagnostic fields).

## Anti-slop rules

- No gradients, no glassmorphism, no motion.
- Status never signalled by colour alone — always text + surface.
- Right-align numerics (`font-variant-numeric: tabular-nums`).
- Every token maps to a real Odoo record/field/action; Vietnamese-first labels.

## SCSS scope discipline

Brand overrides stay scoped to `multichannel.*` forms via `.o_form_view[name="…"]` selectors
in `mu_tokens.scss` (mhc bundle). Etsy-only forms (`etsy.shop`) get a sibling file in
`etsy_integration/static/src/scss/` if needed — **do not** broaden to brand-wide (owner A3,
`PHASE_3_SCOPE.md`).
