# ADR-018 — Design Order module topology & 'Design Ready' representation

- Status: Accepted (2026-07-02)
- Ticket: ESTY-244
- Related: ADR-006 (design-file storage), ADR-009 (file lifecycle), ADR-010 (configurable order pipeline)

## Context
ESTY-244 asks to (1) split Design into an independent module with its own
document ("phiếu") and flow like sale.order/mrp.production, (2) auto-create a
design order when a sale order is confirmed (toggle, default ON), and (3) on
approval set the linked production order to "Design Ready" and attach the
approved file to it.

Two realities surfaced during planning/build that shaped the design:

1. **`design.file` is entangled with non-design shared infra in `multichannel_hub_core` (mhc).**
   `design.file` (and its wizard) import the `gdrive_uploader` service — also
   used by `multichannel_hub_fulfillment` and the catalog fetcher — and gate on
   `group_production_team`, a group used across `sale_order`, `sale_order_fulfillment`
   and `etsy_integration`. Making a new `design` module a *foundation* that mhc
   depends on (the first-draft plan) would require relocating that shared infra
   too — a cascade far beyond ESTY-244.

2. **`mrp.production.state` is a computed, stored, readonly field** (`_compute_state`).
   A `selection_add` value would render but be recomputed away on write. mhc
   already models intermediate production stages on the sale order via
   `order.pipeline.state` (`x_pipeline_state_id`), built precisely because the
   6-state MO model cannot represent them, with forward-only automatic sync at
   MO boundaries.

## Decision
- **Topology (reversed from first draft):** `design` depends on
  `multichannel_hub_core`; it sits ON TOP of mhc and freely reuses `design.file`,
  the pipeline model, and `group_production_team`. No circular dependency; no
  relocation of shared infra.
- **`design.file` is NOT physically relocated.** The `design` module extends it
  via `_inherit = 'design.file'` to add `design_order_id`. This avoids a fragile
  live-DB `ir_model_data` ownership migration and keeps design.file's internal
  `multichannel_hub_core.*` references valid. Full physical relocation of the
  legacy design-file storage code is **deferred** (a separate refactor gated by
  the shared-infra entanglement above).
- **'Design Ready' = a `design_ready` `order.pipeline.state` code** on each
  production pipeline (Option B), not a new `mrp.production.state` value. On
  `design.order` approval the linked sale order advances to `design_ready` via
  the existing `sale.order._write_pipeline_state(..., change_type='automatic')`,
  and approved files are attached to the linked mrp.production(s) as
  `ir.attachment`. Because the stage lives on the SO pipeline (one per SO), the
  "which MO gets the state when MTO makes several" problem does not arise; the
  attachment side handles 0..n MOs gracefully.

## Alternatives considered
- `design` as a foundation module (mhc depends on design): rejected — forces
  relocating gdrive_uploader + group_production_team (out of scope, high risk).
- New value on `mrp.production.state`: rejected — computed/stored field,
  upgrade-fragile, and duplicates the purpose-built pipeline-state layer.
- Boolean + button on mrp.production: viable but not a first-class stage; the
  pipeline layer already gives the visible stage the owner asked for.

## Consequences
- Delivers the design-*order* workflow (reqs 2 & 3) and an independent `design`
  module (req 1, for the order layer) at low risk.
- Legacy `design.file` views/models remain in mhc for now; a follow-up may
  relocate them once the shared infra is factored out.
- `design` must always be installed alongside mhc (declared dependency).
