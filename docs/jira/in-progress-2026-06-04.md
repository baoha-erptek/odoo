# Jira ESTY — IN PROCESS triage (2026-06-04)

Source: `project = ESTY AND status = "IN PROCESS"` on https://erptek.atlassian.net  
Pulled: 2026-06-04 (read-only, no Jira mutations performed)  
Raw JSON: `docs/jira/in-progress-2026-06-04.json`

Note: ESTY uses workflow status `IN PROCESS` (caps, not "In Progress"). All 11
tickets currently in this state belong to Bao Ha and form the **"Listing module
from Odoo to Etsy/Amazon" feedback batch** (parent doc = ESTY-187), captured
during owner's 2026-06-03 publish-from-Odoo dry-run.

Priority gate (per owner instruction this session):
1. Bugs first (Wave 1)
2. Etsy listing-feature parity (Wave 2) — ordered by Etsy "How to Create a
   Listing" article section order
3. Architectural enhancements / non-listing helpers (Wave 3)

---

## Classification table

| Jira | Owner sub-# | Type | Etsy step | Module | Proposed slice ID | Wave | Note |
|------|-------------|------|-----------|--------|-------------------|------|------|
| ESTY-188 | 6.11b | **bug** | n/a (publish action) | etsy_integration | `P-BUG-ESTY-188` | **1** | createListing 400 on `POST /v3/application/shops/60752333/listings`. Likely root cause is one of the known post-2026-02 createListing changes (personalization fields deprecated → R-PUB-PERSONALIZATION-ENDPOINTS regression OR a missing `readiness_state_id` regression OR a new mandatory field). MUST capture response body first (per `feedback_capture_response_body_before_blackbox_probe.md`). |
| ESTY-199 | 7.0 | listing-parity | video | etsy_integration | `P-LIST-VIDEO` | 2 | Etsy listing supports up to 1 video; no upload UX in current publisher. New field on `product.template` (or `etsy.listing.draft`) + `POST /shops/{shop_id}/listings/{listing_id}/videos` per Etsy API ref. |
| ESTY-189 | 7.1 | listing-parity | category (taxonomy) | etsy_integration | `P-LIST-CATEGORY` | 2 | Currently uses Odoo `product.category` (company catalog) — wrong. Must sync `taxonomy_id` from `GET /seller-taxonomy/nodes`. Cache nodes in a new `etsy.taxonomy.node` model (Standard-Odoo-First check: nothing equivalent ships in Odoo CE). |
| ESTY-191 | 7.3 | listing-parity | shipping | etsy_integration | `P-LIST-SHIPPING` | 2 | Processing time, shipping time, shipping price missing from publisher. Etsy uses `shipping_profile_id` reference. Pull profiles via `GET /shops/{shop_id}/shipping-profiles`, attach to listing draft. |
| ESTY-192 | 7.4 | listing-parity | variations (attribute matching) | etsy_integration | `P-LIST-ATTRIBUTES` | 2 | Etsy "Matching Attributes" not auto-populated from Odoo product attributes. Map `product.attribute` → Etsy `property_id` via taxonomy attribute list. Pairs with ESTY-194. |
| ESTY-193 | 7.5 | listing-parity | "how it's made" (who/what/when) | etsy_integration | `P-LIST-HOW-ITS-MADE` | 2 | Currently untested. Required Etsy fields: `who_made`, `when_made`, `is_supply`. Need defaults at shop config + per-listing override. |
| ESTY-194 | 7.6 | listing-parity | shop & product attribute config | etsy_integration / multichannel_hub_core | `P-LIST-ATTR-CONFIG` | 2 | Owner wants a config view to map shop-level + product-level attributes. Likely composes with ESTY-192. Candidate: merge into `P-LIST-ATTRIBUTES` if scope overlap exceeds 70%. Decided: keep separate (config UI vs. publish-time mapping) — both can ship same release. |
| ESTY-197 | 7.9 | listing-parity | inventory / shop scope | etsy_integration / multichannel_hub_core | `P-LIST-SHOP-BULK` | 2 | Auto-assign every published listing to its source shop; provide bulk-action ("tick N listings, update together"). Needs `etsy.listing.shop_id` already exists per ADR-013 — add list view filter + bulk-action server action. |
| ESTY-190 | 7.2 | enhancement (multichannel) | n/a (per-channel overrides) | multichannel_hub_core | `P-ENH-ESTY-190` | 3 | Per-channel/per-shop Title/Description/Image overrides. Not a standard Etsy listing field — it's a multichannel hub feature. Touches `mhc.product.channel.status` (existing) + needs override M2O on a new `mhc.product.channel.copy` model. |
| ESTY-195 | 7.7 | enhancement (FX) | n/a (currency) | multichannel_hub_core | `P-ENH-ESTY-195` | 3 | Owner wants USD/EUR/CAD/VND auto-conversion to shop's listing currency. **Standard-Odoo-First**: `res.currency.rate` + `res.currency._convert()` already exist; this slice is mostly a cron + price-display widget on `etsy.listing`. No new currency model. |
| ESTY-187 | 6.11 | **spec / architecture** | n/a | mhc / etsy_integration | `P-SPEC-LISTING-MODEL-SPLIT` | 3 | Architectural feedback proposing 3 options (A=permissions only, B=split views, C=separate `hatafa.listing` model). Owner indicates preference for **Option C**. This blocks several Wave-2 slices (architecture decision impacts where ESTY-189/192/194 fields live). Spec slice = no code; produces ADR + spec.md. Should run **BEFORE** Wave 2 lands, even though categorised as Wave 3 — flag for owner. |

**Counts**: 1 bug, 7 listing-parity, 3 enhancement/spec.

---

## Closure audit (2026-06-07)

Cross-reference of the 11 ESTY rows above against current tracker state in
`.claude/plans/006-master-plan-tracking.md`:

| Jira | Slice | Tracker state (2026-06-07) | Gate / Notes |
|------|-------|---------------------------|--------------|
| ESTY-187 | P-SPEC-LISTING-MODEL-SPLIT | `done` 2026-06-06 | ADR-013 + spec 012 landed; Wave-2 fields placed per Option C decision |
| ESTY-188 | P-BUG-ESTY-188 | `doing` (iter3 shipped to staging 2026-06-06 08:38 UTC) | **Owner-gated** — needs re-publish on JaHandmadeArt to verify 201 (not 400) |
| ESTY-189 | P-LIST-CATEGORY | `done` 2026-06-06 | Wave-2 ship |
| ESTY-190 | P-ENH-ESTY-190 | `done` 2026-06-07 | Wave-3 ship this session (commits 5da85b379c4 + 4bb3ee7d9c3 + 79d5f3a175b). Staging T901-T904 deferred to owner |
| ESTY-191 | P-LIST-SHIPPING | `done` 2026-06-06 | Wave-2 ship |
| ESTY-192 | P-LIST-ATTRIBUTES | `done` 2026-06-06 | Wave-2 ship |
| ESTY-193 | P-LIST-HOW-ITS-MADE | `done` 2026-06-06 | Wave-2 ship |
| ESTY-194 | P-LIST-ATTR-CONFIG | `done` 2026-06-06 | Wave-2 ship |
| ESTY-195 | P-ENH-ESTY-195 | `done` 2026-06-06 | Wave-3 ship (commits df6766db30a + f71701ebbc0). Staging T901-T904 deferred to owner |
| ESTY-197 | P-LIST-SHOP-BULK | `done` 2026-06-06 | Wave-2 ship |
| ESTY-199 | P-LIST-VIDEO | `done` 2026-06-06 | Wave-2 ship |

**Result**: 10 of 11 ESTY rows are `done` on `feature/006-master-plan-coding`.
The remaining row — ESTY-188 — is **owner-gated** (waiting on owner
re-publish to flip iter3 GREEN → `done`); no code action available without
owner. Jira "IN PROCESS" filter should drop to 1 ticket after owner confirms
and moves ESTY-188 to "Done" status on Atlassian.

Closures during the 2026-06-06 → 2026-06-07 window (this session window):

- 2026-06-06: ESTY-187 (P-SPEC), Wave-2 7 listing-parity rows, ESTY-195 (Wave-3)
- 2026-06-07: ESTY-190 (Wave-3) + companion close on P-DOCS-ETSY-READINESS-ASSESSMENT (tracker only, not a Jira row)

---

## Dispatch decision

Per owner instruction in this task:
- **Wave 1 (auto-dispatch)**: `P-BUG-ESTY-188`
- **Wave 2 (tracker rows only; awaits owner approval)**: `P-LIST-VIDEO`,
  `P-LIST-CATEGORY`, `P-LIST-SHIPPING`, `P-LIST-ATTRIBUTES`,
  `P-LIST-HOW-ITS-MADE`, `P-LIST-ATTR-CONFIG`, `P-LIST-SHOP-BULK`
- **Wave 3 (tracker rows only; awaits owner approval)**: `P-ENH-ESTY-190`,
  `P-ENH-ESTY-195`, `P-SPEC-LISTING-MODEL-SPLIT`

**Sequencing flag for owner**: `P-SPEC-LISTING-MODEL-SPLIT` (ESTY-187) is
technically Wave 3 in our classification but it carries an **architectural
decision** (Option C — separate `hatafa.listing` model) that influences where
the Wave-2 listing fields (`taxonomy_id`, attribute matching, who_made, video)
should live (on `product.template` vs a new model). Recommend running it as
Wave 1.5 — i.e. immediately after the ESTY-188 bug ships and before any Wave-2
slice begins.

---

## Per-slice planner references

When `/dispatch-slice` invokes the `planner` agent for any of these, the
planner MUST cite:

1. The Jira key (this doc) in the slice's `findings.md` Step-1 evidence row.
2. The relevant Etsy dev-docs corpus file under
   `~/.cache/etsy-developer-docs/` for any endpoint touched, e.g.:
   - ESTY-188 / `P-BUG-ESTY-188`:
     `documentation_tutorials_listings.md`,
     `documentation_tutorials_personalization-migration.md`,
     `documentation_tutorials_personalization_endpoint-migration.md`
   - `P-LIST-VIDEO`: `documentation_tutorials_listings.md` (video section)
   - `P-LIST-CATEGORY`: `documentation_reference.md` (taxonomy nodes section)
   - `P-LIST-SHIPPING`: `documentation_tutorials_listings.md` (shipping profile)
   - `P-LIST-ATTRIBUTES` / `P-LIST-ATTR-CONFIG`:
     `documentation_tutorials_third-variation.md`,
     `documentation_tutorials_listings.md` (matching-attributes section)
   - `P-LIST-HOW-ITS-MADE`: `documentation_tutorials_listings.md`
     (who_made/when_made/is_supply)
3. The `odoo-standard-first` decision tree before adding any new field/model
   (mandatory per CLAUDE.md).

---

## Crawl-anti-bot note

The Etsy dev-docs crawl flagged 10 pages (mostly under
`/documentation/tutorials/payments/*` and one auth tutorial) as
"anti-bot protection — minimal_text on small page". 24 pages landed cleanly,
including the listings + personalization + variations tutorials that drive
the bulk of the slices above. Re-crawling the blocked pages with a different
user-agent is a future-task chore, not a blocker for any slice in this batch.
