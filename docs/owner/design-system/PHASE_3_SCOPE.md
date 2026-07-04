# Phase 3 — Full library + per-form curation (queued for clean session)

> Recorded 2026-06-07 per owner directive (Telegram msg after 747).
> Owner explicitly deferred this to a fresh session — do NOT dispatch from
> the current session.

## Recap of where Phase 1 + Phase 2 landed

| Phase | Slice | Status | Output |
|---|---|---|---|
| Phase 1 | P-DS-1-DESIGN-SYSTEM-DOCS | done (commit `079fe0cb47c` + BA-fix `2d21cb34899`) | `mu-design-tokens.css` + `MU_SYSTEM.md` + `FORM_CURATION_GUIDE.md` + BA audit applied |
| Phase 2 | P-DS-2-MVP-BACKPORT | done (commit `a5ae4178eb2` + `874a5169f1d`) | SCSS bundle scoped to mhc + view XML tier edits on `product.template` + `multichannel.listing` + mockup procedure docs |

## Phase 3 deliverables (3 sub-slices)

### P-DS-3a — Per-form curation for `etsy.shop`

**Why:** Flow 2 narrative (Etsy ingestion) opens `etsy.shop` form for Recovery Probe + API status checks. Currently exposes ALL config + Publisher Defaults tab + Sync Health metrics + debug probe fields on one screen. BA Lead opens this when API issues arise — clutter hurts triage speed.

**Scope:**
- Apply 3-tier model from `FORM_CURATION_GUIDE.md`:
  - Tier 1: `name`, `etsy_api_shop_id`, `active_source`, `listing_currency_id`
  - Tier 2 tabs: API Status (Recovery Probe + sync health summary), Publisher Defaults (already exists), Listing Configuration
  - Tier 3 (`groups="base.group_no_one"`): internal probe metrics, debug correlation IDs, `auto_recovery` toggle, `active_source_changed_at` audit
- Add `.mu-mono` class to `etsy_api_shop_id` + any displayed listing IDs
- Apply purple statusbar tint (`active_source` is Selection — use `widget="badge"` with decoration-*)

**Standard-Odoo-First check before dispatch:**
- All field hiding via `groups="base.group_no_one"` / `groups="base.group_system"` standard
- All badge styling via `widget="badge"` + `decoration-success/warn/danger` standard

**Effort:** 0.5–1 dev day. Mockup procedure (`odoo-functional-mockup` skill) first to produce `MOCKUP_etsy_shop.md`, then implement.

**Entry criteria:**
- Owner answers Q3 from COMPARISON doc (purple branding scope — already answered "mhc scope" but etsy.shop lives in `etsy_integration` not mhc; need to confirm: scope the SCSS to etsy.shop form via `name="etsy.shop"` selector inside the mhc bundle, OR add a small SCSS file to `etsy_integration/static/src/scss/`).
- Confirm specific Tier 3 fields (some debug fields owner may want visible to sys admins, not just devs).

### P-DS-3b — `sale.order` + `stock.picking` audit

**Why:** `FORM_CURATION_GUIDE.md` §"Áp dụng cho hiện trạng" line 181 currently says "Standard Odoo (kept as-is) — No curation needed — Odoo's default Tier model adequate". BUT mockup Flow 2 + Flow 3a show curated views (only specific columns visible). Verify whether the AS-IS forms genuinely match owner's mental model OR whether subtle curation is warranted.

**Scope:**
- Run `odoo-functional-mockup` procedure for both forms.
- If audit confirms no curation needed → close P-DS-3b with a tracker note (1-line `done — no work needed`).
- If audit surfaces a gap → produce `MOCKUP_sale_order.md` + `MOCKUP_stock_picking.md` and implement.

**Effort:** 0.5 dev day audit + variable implementation if gaps found.

### P-DS-3c — Full OWL component library (optional)

**Why:** Phase 2 deliberately avoided OWL components per Standard-Odoo-First (BA audit msg 738). The "full library" option from the COMPARISON doc remains genuinely deferred — only pursue if a future need surfaces (e.g. a custom widget that standard Odoo doesn't ship and CSS can't substitute).

**Scope:**
- DO NOT pursue speculatively. Only dispatch if a specific UX gap is identified that standard Odoo widgets cannot fill.
- If pursued: candidate components per the original (rejected) plan: `MuPill` (was rejected → use `widget="badge"`), `MuStatusBar` (was rejected → use `widget="statusbar"`), `MuBanner` (potentially useful as wrapper around Bootstrap `alert-info` for consistent styling).

**Effort:** Estimated 3-5 dev days if/when triggered. Not in current path.

## Total Phase 3 scope estimate

| Slice | Effort | Block on |
|---|---|---|
| P-DS-3a etsy.shop curation | 0.5–1 day | owner Q3 clarification + Tier 3 list confirmation |
| P-DS-3b sale.order + stock.picking audit | 0.5 day audit + variable | none |
| P-DS-3c full OWL library | deferred | specific gap surfacing |

**Total committed work:** 1–1.5 dev days for P-DS-3a + P-DS-3b. P-DS-3c remains optional.

## How to pick up in a fresh session

```
/clear
/dispatch-slice P-DS-3a
```

The dispatch-slice skill will:
1. Read tracker row P-DS-3a (added 2026-06-07)
2. Verify branch + tree clean
3. Set up tasks per the scope above
4. Spawn planner agent (sonnet) with this scope doc as input

If the clean session prefers to scope all three at once, dispatch `P-DS-3a` first, then `P-DS-3b` after that ships, and skip `P-DS-3c` until a real need surfaces.

## Anti-patterns to avoid in Phase 3

- **Don't reinvent standard widgets.** BA audit caught 5 reinventions in Phase 1; Phase 2.1 (`odoo-standard-first` skill) caught the statusbar/state_selection confusion. Run the skill BEFORE implementation.
- **Don't apply the brand-wide purple.** Owner answer A3 was "mhc scope". If P-DS-3a needs to load CSS into `etsy_integration` views, do it via a small etsy_integration SCSS file, not by broadening the mhc bundle scope.
- **Don't curate `sale.order` aggressively** without owner confirmation. P-DS-3b is an audit-first slice — confirm the gap exists before editing.
