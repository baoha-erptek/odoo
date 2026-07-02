# Design Orders (`design`)

ESTY-244. Promotes design work into a first-class document — `design.order`
("phiếu design") — with its own number, statusbar and chatter, parallel to
`sale.order` / `mrp.production`.

## What it does
- **Auto-create (toggle, default ON):** confirming a `sale.order` creates one
  `design.order` and links the order's existing `design.file` rows to it.
  Toggle: Settings → Sales → *Design Orders*, or the
  `design.auto_create_on_confirm` system parameter.
- **Approve ('Duyệt'):** on `design.order.action_approve()` the linked sale
  order advances to the `design_ready` pipeline stage (via
  `order.pipeline.state`) and every approved `design.file` is attached to the
  linked `mrp.production`(s) as `ir.attachment`.
- **Backfill:** on install, `post_init_hook` creates `design.order` rows from
  existing `design.file` data (idempotent; state inferred from child files).

## Topology (see ADR-018)
`design` **depends on `multichannel_hub_core`** and sits on top of it. It does
not relocate `design.file` (which stays in mhc) — it extends it with
`design_order_id`. 'Design Ready' is a pipeline-state code, not an
`mrp.production.state` value (that field is computed/stored).

## Models
- `design.order` — the document (1:1 with `sale.order`).
- `design.file` (`_inherit`) — adds `design_order_id`.
- `sale.order` (`_inherit`) — `design_order_ids` + auto-create on confirm.
- `res.config.settings` (`_inherit`) — the toggle.

## Tests
`--test-tags design` (Phase 1 DB + Phase 2 ORM).

## Deferred
Physical relocation of the legacy `design.file` storage code + views out of mhc
(gated by shared-infra entanglement: `gdrive_uploader`, `group_production_team`).
