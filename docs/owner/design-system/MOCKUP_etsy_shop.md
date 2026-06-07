# Mockup procedure — `etsy.shop` form

> Output of `odoo-functional-mockup` skill 2026-06-07. **Process note:** Code shipped GREEN before mockup was authored (Phase 2 testing completed; Phase 2.5 XML edits done). This document captures decisions made, not spec being implemented per P-DS-2-MVP-BACKPORT precedent.

---

## Step 1 — Baseline (standard Odoo view to inherit)

| Attribute | Value |
|---|---|
| **XML ID** | `etsy_integration.etsy_shop_view_form` |
| **File** | `custom_addons/etsy_integration/views/etsy_shop_views.xml:25` |
| **Edition** | `[Custom]` — no standard Odoo equivalent (etsy.shop is a custom model in ADR-008a) |
| **Shape** | `<sheet>` + stat-button row (Orders, Authorize, Test Connection, Email Alias) + title + 2 main groups (Tier 1 essentials + Tier 3 diagnostics) + notebook with 2 tabs (Publisher Defaults, Orders) |

### No inheritance chain (custom model)

The `etsy.shop` model is entirely custom (not inheriting from `res.company` or `sale.config`). The form view was built from scratch per ADR-008a (source-switching architecture). No standard Odoo view to inherit.

### What this means for Phase 2.5

- Tier curation happens via `groups="..."` attribute on groups and fields (not via position= xpath on inherited views).
- The 3-tier model from `FORM_CURATION_GUIDE.md` is enforced by wrapping sections in groups with explicit gating.
- No risk of clashing with Odoo's inherited field visibility — all visibility is explicit from the start.

---

## Step 2 — Taste overlay

Per `taste-skill` brief inference for Odoo back-office:

| Dial | Setting | Reasoning |
|---|---|---|
| DESIGN_VARIANCE | low | B2B back-office; system administrator use only (flow where API failures need triage) |
| MOTION_INTENSITY | low | No animations; focus on clarity + scanability when API issues arise |
| VISUAL_DENSITY | high | Admin opens form only during API outages → must see health metrics + recovery state at a glance |

**Direction statement:** "When an Etsy API shop breaks, the system admin needs to **see the health state in <10 seconds**, not hunt through tabs. Tier 1 must include shop identity + active adapter (the two questions: 'which shop?' and 'which source?'). Tier 2 houses the configuration tabs (Publisher Defaults, Orders) that operate normally. Tier 3 hides the debug probe counters + auto-recovery toggle behind `base.group_no_one` to unclutter the normal view. Purple (#714B67) badge on `active_source` Selection (api = success-green, email = warning-orange) — no custom OWL, just standard `widget="badge"` + `decoration-*` attributes."

---

## Step 3 — Craft check (`od-design-craft` rules applied)

| Rule | Applied? | How |
|---|---|---|
| Anti-AI-slop typography | ✓ | Use Odoo default fonts; `.mu-mono` class on `etsy_api_shop_id` for technical id display (follows product.template precedent) |
| Color discipline | ✓ | Purple #714B67 only on active-badge + status indicators; no gradients or neon |
| State coverage — empty | ✓ | New shop form shows placeholder "e.g. 60752333" on `etsy_api_shop_id`; `active_source` defaults to 'email' |
| State coverage — error | ✓ | No explicit error UI needed; Odoo's built-in field validation covers server-side constraints |
| State coverage — admin-only | ✓ | Tier 3 group gated via `groups="base.group_no_one"` — debug fields vanish from normal user view |
| a11y — label association | ✓ | All fields auto-render `<label for=>` per standard Odoo form |
| a11y — keyboard nav | ✓ | Tab order preserved; no custom focus traps |
| a11y — contrast | ✓ | Purple #714B67 on white = 7.1:1 (AAA); badge text uses standard Odoo contrast ratios |
| Form validation patterns | ✓ | Use Odoo's `required=True` on `name` + `active_source`; server-side constraints via `_sql_constraints` |

---

## Step 4 — Diff vs mockup screen (Flow 2, "Etsy shop — API status triage")

### Tier 1 — Always visible (top of sheet)

Cap at 6 fields. Must answer: "Which shop?" + "Which source?" + "How much revenue?" + "Which currency?"

| # | Field | Source | Mockup shows? | Standard-Odoo-First | Action |
|---|---|---|---|---|---|
| 1 | `name` | custom | ✓ "Shop Name" (h1 title) | N/A — custom field | Keep visible (already in oe_title) |
| 2 | `revenue_total` | custom computed | ✓ "Total Revenue" | N/A — custom compute | Keep visible (monetary widget) |
| 3 | `listing_currency_id` | custom M2O | ✓ "Etsy Listing Currency" | N/A — custom field | Keep visible (critical for price conversion) |
| 4 | `etsy_api_shop_id` | custom Char | ✓ "Etsy Shop ID" mono badge | N/A — custom field | Keep visible + **add `class="mu-mono"`** |
| 5 | `active_source` | custom Selection | ✓ (api\|email) badge + color | `widget="badge"` + `decoration-*` are **standard Odoo** | Keep visible + **add `widget="badge"` + decoration-success/warning** |

**Standard-Odoo-First evidence:** `widget="badge"` is standard Odoo 19 (`addons/web/views/…`); `decoration-success`/`decoration-warning` are standard (`odoo/addons/web/views/…`); `class="mu-mono"` is a reusable CSS class (no custom OWL component).

### Tier 2 — Notebook tabs (secondary configuration)

| Tab | Source | Content | Purpose | Visibility |
|---|---|---|---|---|
| Publisher Defaults | custom | Etsy API defaults (taxonomy, shipping, readiness, who_made, when_made, is_supply, brand-voice, attribute mapping) | BA Lead configures per-shop overrides | Normal visibility (group_ba_user gated on sub-sections) |
| Orders | custom | One2many readonly list of sale.order rows | Admin reviews orders ingested from this shop | Normal visibility |

**Tier 2 justification:** Publisher Defaults are Tier 2 because only **during onboarding** or **after an API break** does BA Lead edit these. Tier 1 is the "is it working now?" snapshot; Tier 2 is "let me fix the config."

### Tier 3 — Hidden behind `groups="base.group_no_one"` (developer-only diagnostics)

These fields live in the "Advanced Diagnostics" group at the bottom of the sheet, wrapped in `groups="base.group_no_one"`:

| Field | Where | Hide-via | Reason | Current value in view |
|---|---|---|---|---|
| `auto_recovery` | Diagnostics group | `groups="base.group_no_one"` | Toggle—admin rarely changes; probe controls it | ✓ Already added in Phase 2 (line 92) |
| `active_source_changed_at` | Diagnostics group | `groups="base.group_no_one"` readonly | Audit timestamp — system-only | ✓ Already added in Phase 2 (line 93) |
| `health_check_consecutive_failures` | Diagnostics group | `groups="base.group_no_one"` readonly | Probe counter — debugging only | ✓ Already added in Phase 2 (line 94-95) |
| `recovery_probe_consecutive_successes` | Diagnostics group | `groups="base.group_no_one"` readonly | Probe counter — debugging only | ✓ Already added in Phase 2 (line 96-97) |

**Tier 3 justification:** These four fields are **system/diagnostic only**. Normal BA Leads should never see them. They clutter the API triage screen. System admins running `/dev/null` (debug mode) can still access them via `base.group_no_one` gate. Owner gate answers (from PHASE_3_SCOPE.md §P-DS-3a) confirmed: "4 tracker-explicit fields only; borderline fields (sync_audit_mode, etsy_oauth_token_expires_at, etsy_last_receipt_sync_at) stay Tier 2 visible — but these are NOT currently rendered in the view, so they remain absent."

### Decoration domain map (active_source Selection styling)

Badge color mapping per `widget="badge"` + `decoration-*` pattern:

| Selection value | Label | Badge color | Decoration class | Meaning |
|---|---|---|---|---|
| `'api'` | `'Etsy API'` | Green (success) | `decoration-success="active_source == 'api'"` | API source is primary; ingestion from Etsy v3 endpoints |
| `'email'` | `'Email'` | Orange (warning) | `decoration-warning="active_source == 'email'"` | Email source is primary; legacy Gmail-cron ingestion |

**Rationale:** Green = API (modern, real-time); Orange = Email (legacy, batch). No red needed; neither is an error state. Both are valid sources per ADR-008a.

---

## Step 5 — Deliverables

### 5.a — ASCII mockup (post-backport)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Setup ▸ Etsy Integration ▸ Etsy Shops                          system@hatafa │
├───────────────────────────────────────────────────────────────────────────────┤
│ [ Orders ]  [ Authorize Etsy ]  [ Test Connection ]  [ Email Alias ]          │
│ ───────────────────────────────────────────────────────────────────────────── │
│                                                                              │
│  JaHandmadeArt Shop                                                          │
│                                                                              │
│  ╭─ ID ────╮   Total Revenue       $ 12,450 USD                              │
│  │ avatar  │   Listing Currency    [ United States Dollar        ]            │
│  ╰────────╯                                                                    │
│                                                                              │
│                     Etsy API Identity                                         │
│                     Etsy Shop ID      [60752333]  ⌧ mono                      │
│                     Active Source     ● Etsy API  (success-green badge)        │
│                                                                              │
│  [ Advanced Diagnostics ] (visible to system/dev only, collapsed by default)  │
│                                                                              │
│  ─── Publisher Defaults ── Orders ──                                          │
│                                                                              │
│  Etsy Publisher Defaults (BA User group only):                                │
│    Default Taxonomy ID        [ 1522263...                     ]  (system)     │
│    Default Shipping Profile   [ 285149...                     ]  (system)     │
│    Default Return Policy      [ 123456...                     ]  (system)     │
│    Default Who Made           [ I did                         ]               │
│    Default When Made          [ made_to_order                 ]               │
│    Default Is Supply          [ ☐ ]                                           │
│                                                                              │
│  Shop Brand-Voice Defaults (Marketing User group only):                       │
│    Default Title              [ Handmade Ceramics by JaHandmadeArt ]          │
│    Default Description        [ Each piece is hand-thrown...                 │
│    Default Image              [ [preview thumbnail]          ]                │
│                                                                              │
│  Etsy Publisher Unit Preferences (system only):                               │
│    Weight Unit                [ oz / g ]                                       │
│    Dimensions Unit            [ cm / in ]                                      │
│                                                                              │
│  Attribute mapping priority:                                                  │
│    Per-listing rows → Shop defaults → Product global                          │
│                                                                              │
│  [Edit attribute mapping table...]                                            │
│                                                                              │
│  Orders:                                                                       │
│    [readonly list of sale.order with name / partner / date / amount / state]  │
│                                                                              │
└───────────────────────────────────────────────────────────────────────────────┘

Hidden (groups="base.group_no_one"): Advanced Diagnostics group
  (auto_recovery, active_source_changed_at, health_check_consecutive_failures,
   recovery_probe_consecutive_successes) — visible to developers/sys-admins only
```

### 5.b — XML pseudo-diff (Phase 2.5 implementation summary — ALREADY SHIPPED)

**Status:** Code is already GREEN. The below recap shows what was implemented.

```xml
<!-- custom_addons/etsy_integration/views/etsy_shop_views.xml -->
<!-- Phase 2.5 edits (lines 67-98) already in place: -->

<!-- Tier 1 group (visible to all etsy.shop readers): -->
<group>  <!-- Line 70 -->
  <group>
    <field name="revenue_total" widget="monetary"/>
    <field name="listing_currency_id"/>
  </group>
  <group string="Etsy API Identity">  <!-- Line 76 -->
    <field name="etsy_api_shop_id"
           class="mu-mono"
           placeholder="e.g. 60752333"/>
    <field name="active_source"
           widget="badge"
           decoration-success="active_source == 'api'"
           decoration-warning="active_source == 'email'"/>
  </group>
</group>

<!-- Tier 3 group (hidden behind base.group_no_one): -->
<group string="Advanced Diagnostics"
       groups="base.group_no_one">  <!-- Line 90-91 -->
  <field name="auto_recovery"/>
  <field name="active_source_changed_at" readonly="1"/>
  <field name="health_check_consecutive_failures" readonly="1"/>
  <field name="recovery_probe_consecutive_successes" readonly="1"/>
</group>

<!-- Tier 2 tabs (Publisher Defaults, Orders) unchanged from pre-edit baseline. -->
```

**SCSS edit summary:** Extend `multichannel_hub_core/static/src/scss/mu_tokens.scss` with form-scoped purple tint rule:

```scss
/* Add to mu_tokens.scss: */
.o_form_view[name="etsy.shop"] .o_notebook .nav-link.active {
    border-bottom-color: #714B67;  /* purple active-tab indicator */
}
```

**Manifest:** mhc manifest already declares the SCSS asset; no additional entry needed.

### 5.c — Diff against mockup (intentional vs fixable divergence)

| Mockup element | Real Odoo after Phase 2.5 | Divergence type |
|---|---|---|
| Shop avatar (top-left circle) | Not present (standard Odoo form doesn't auto-render avatar for custom models) | **Intentional skip** — no Custom Image field on etsy.shop; low priority |
| "Advanced Diagnostics" group collapsed by default | Groups don't collapse; they're always expanded unless field is `invisible` | **Intentional defer** — collapsible sections require custom OWL component; Phase 3 enhancement if UX audit identifies it |
| Tier 3 group only visible in developer mode | Visible to anyone in `base.group_no_one` (includes system admins + developers; doesn't require literal "developer mode" toggle) | **Acceptable** — `base.group_no_one` is the Odoo pattern for admin-only fields; owner confirmed |
| Badge color (green for API, orange for email) | ✓ Implemented via `decoration-success`/`decoration-warning` on the Selection field | **Match** ✓ — standard Odoo widget behavior |
| Mono font on `etsy_api_shop_id` | ✓ Implemented via `class="mu-mono"` | **Match** ✓ — CSS class (no OWL component) |
| Active-tab purple border on Publisher Defaults tab | ✓ Scoped SCSS rule in `mu_tokens.scss` applied to `.o_form_view[name="etsy.shop"]` | **Match** ✓ — standard SCSS override |

---

## Process note — Code-before-mockup

**Why the timing?** Per P-DS-2-MVP-BACKPORT precedent, slice P-DS-3a ran Phase 2 (TDD + implementation) first, then Phase 2.5 (mockup + design validation) second. This is atypical but justified:

1. **Tier model is stable:** `FORM_CURATION_GUIDE.md` was already published and locked. No ambiguity about which fields go where.
2. **Implementation is simple:** 1 group wrapper + 4 field declarations. Low risk of scope creep.
3. **Tests validate shape:** Phase 2 test suite checks that Tier 3 fields are indeed hidden when `groups="base.group_no_one"` is applied (UI-layer test, not unit).
4. **Owner gate locked:** Owner answers to entry-criteria questions (Q3: SCSS scope, Tier 3 list) were provided before coding started.

**Result:** Mockup documents *decisions made*, not *spec being implemented*. This is acceptable per P-DS-2-MVP-BACKPORT (commit `874a5169f1d`) which followed the same pattern.

---

## Summary for Phase 2.5 closure

**XML edit estimate:** ✓ Done (lines 67-98 in etsy_shop_views.xml). ~30 LOC added.

**Model edit estimate:** ✓ Done (fields already defined in models/etsy_shop.py lines 241-259). No new fields; only visibility tier applied via view grouping.

**SCSS edit estimate:** ✓ Done (mu_tokens.scss extended with form-scoped selector). ~4 LOC added.

**Test coverage:** ✓ Phase 2 test suite validates Tier 1 visible + Tier 3 hidden behavior via ORM-level field access control.

**Expected effort:** 0.5 dev day total for etsy.shop curation (simpler than product.template at 1 day, and multichannel.listing at 0.5 day, due to no field reordering or complex inheritance).

---

## Standard-Odoo-First evidence

All view attributes used are standard Odoo 19:

| Feature | Source | Standard? |
|---|---|---|
| `groups="base.group_no_one"` | Odoo core ACL pattern | ✓ Standard in all Odoo versions |
| `widget="badge"` | `odoo/addons/web/views/…` | ✓ Standard since Odoo 14 |
| `decoration-success` / `decoration-warning` | `odoo/addons/web/views/…` | ✓ Standard since Odoo 12 |
| `widget="monetary"` | Standard currency formatter | ✓ Standard in all Odoo versions |
| `class="mu-mono"` | Custom CSS class (CSS-only, no component) | ✓ No OWL component required |
| `.o_form_view[name="etsy.shop"]` SCSS selector | Standard form-view styling pattern | ✓ Standard Odoo SCSS pattern |

**Conclusion:** No custom OWL components. No reinvented widgets. This form uses only standard Odoo 19 form elements + CSS styling.
