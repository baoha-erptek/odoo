# Next-session prompt — build a complete v2 owner business-flows deck

Paste the block below into a fresh session.

---

Build a **completely new, improved version** of the owner-facing business-flows deck at
`docs/owner/business-flows/v2/` (repo: `/home/odoo/odoo_dev/other_projects/odoo19_esty`, branch
`feature/006-master-plan-coding`). This is the **canonical TO-BE** owner documentation — write it
as the finished, improved product. **Do NOT** include any "what changed / kept vs improved /
before-after / diff" framing, and **do NOT** reference Jira keys, ADRs, spec IDs, module names, or
file paths in the owner-facing text (plain business language only — see memory
`feedback_end_user_docs_plain_view`). It must read like a polished product guide, not a changelog.

## Read first (inputs — synthesize, don't copy)
- `docs/analysis/uiux-improvement.html` — the approved UI/UX direction (KPI dashboard, pipeline
  kanban, unified role-aware sidebar nav, RD price-control screen, status badges, "Fulfillment"
  tab + quote recipient block, side chatter, `muk_web_*` reuse, brand `#714B67`). **Bake all of
  this in as the default design.**
- `docs/analysis/mismatch-report.html` + `docs/analysis/gap-matrix.md` — the verified state of every
  feature (so the v2 deck only promises what is real or planned, never re-promises blocked items).
- `docs/owner/business-flows/flow-1..4-*.md` + `flow-*.html`, `role-1..5-*.html`,
  `CONTRACT-v1.0.md`, `index.html` — the v1 structure to mirror and supersede (leave v1 untouched).
- `docs/analysis/screenshots/verify-2026-06-27/` — real UI screenshots if you want live anchors.
- The existing draft `docs/owner/business-flows/v2-uiux-improved/index.html` is a single-page
  reference only — the new `v2/` deck supersedes it (you may delete that draft at the end).

## Output (a complete deck under `docs/owner/business-flows/v2/`)
- `index.html` — landing: product overview + the unified role-aware navigation map + links to each
  flow and role page.
- `flow-1-tao-san-pham.html`, `flow-2-nhan-don-hang-etsy.html`, `flow-3a-giao-hang-in-noi-bo.html`,
  `flow-3b-giao-hang-gearment-dropship.html`, `flow-4-hau-mai.html` — one polished page per flow,
  each with: the goal, the step-by-step happy path, and an **improved screen mockup** (KPI band /
  kanban / curated table / form) rendered inline.
- `role-1-ba-lead.html` … `role-5-pd.html` plus an RD page — each role's landing screen + daily
  workflow, reflecting the new per-role home. (PD and RD are first-class roles in v2.)
- All HTML **self-contained** (embedded CSS, one shared design system), Vietnamese, brand `#714B67`,
  works offline by double-click.

## Design requirements
- One shared visual system (consider emitting a `DESIGN.md` via the `design-md` skill first so all
  pages share tokens). Primary `#714B67`; clean, dense-but-calm; status badges; left sidebar nav.
- Show the **unified hub** (one app, role-scoped sidebar) — not the current split Etsy/Operations
  apps. Mockups illustrate intent, not pixel specs.
- Cover the improved surfaces: KPI dashboard with saved-filter chips, pipeline kanban board,
  curated order list, design-approval kanban, Gearment/Fulfillment, after-sales, RD price control.

## Skills to use
`odoo-functional-mockup` (baseline→taste→craft→diff per screen, but emit only the final improved
deliverable), `odoo-19-ui-ux` (view/IA correctness), `design-md` (shared tokens), `visual-explainer`
/ `design-html` (render), `taste-skill` / `od-design-craft` (quality gate). Use `/browse` (gstack)
only if you need fresh screenshots — never `mcp__claude-in-chrome__*`.

## Constraints & done criteria
- Brand-new and complete: all 5 flows + all roles + index, internally consistent.
- Owner-plain language throughout; no internal codes/IDs/paths in visible text.
- v1 files in `docs/owner/business-flows/` are NOT modified.
- Serve the deck locally (e.g. `python3 -m http.server` rooted at `docs/`) and hand back the review
  link for `v2/index.html`. (ngrok egress is blocked in this environment — use the local link.)
- Commit on `feature/006-master-plan-coding` after review: `[docs] docs(business-flows): v2 owner
  deck (improved UI/UX)`. The post-commit hook only syncs `*.md` under `docs/owner/**` to Confluence,
  so `.html` pages won't auto-publish — fine.
