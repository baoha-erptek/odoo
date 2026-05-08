# Findings — Spec 004a Tracking Import

Surprises, drift, and decisions discovered during slice execution. Append-only.

---

## P2-03 — Process Dashboard "Đã sản xuất" stock-move hook (2026-05-08, Phase 1 dispatch)

### Spec drift vs implementation

Spec language pre-dates the multichannel_hub_core fulfillment-delegation mixin landing. The mixin model (`sale.order.fulfillment` in `multichannel_hub_core/models/sale_order_fulfillment.py`) settled on field names that diverge from spec wording. **Code is the source of truth** — adjust spec language going forward; do not rename code to match stale spec.

| Spec (FR-016..FR-020) | Actual code |
|---|---|
| `production_stage` field | `fulfillment_status` Selection |
| Stage value `da_san_xuat` | Selection value `'produced'` |
| Resolves locations from `warehouse_id` (M2O) | `warehouse_zone` Selection (`'vn'`/`'us'`) — **logical** zone, not a stock.location M2O |
| Final-state list: `shipped`/`done`/`cancel` | `'shipped'`/`'delivered'`/`'cancelled'` |

### Decisions taken under run-to-completion

The dispatch-slice planner output left three open questions. Per memory `feedback_dispatch_run_to_completion.md`, in-slice choices take recommended options unless they qualify as STOP (contradicting ADRs / missing preconditions / data-destroying ambiguity). None did. Decisions:

1. **Warehouse_zone → stock-location resolution**: ICP-driven mapping. ICP key `multichannel_hub_fulfillment.production_locations` stores a JSON object `{"vn": {"src": "<xmlid>", "dst": "<xmlid>"}, "us": {...}}`. Hook reads ICP, resolves locations via `env.ref(xmlid, raise_if_not_found=False)`. Missing entry or unresolved xmlid → fail-open path per FR-018 (log to `etsy.sync.health` + skip; no UserError, no stage-change block).

2. **Idempotency marker**: New `purpose` Char field on `stock.move` (extension in `multichannel_hub_fulfillment/models/stock_move.py`). UNIQUE `(order_id, purpose)` enforced via `_sql_constraints` mirrored in `init()` raw SQL with `pg_constraint IF NOT EXISTS` pre-check (per memory `project_sql_constraints_drift.md` template — 7th confirmation). Specific marker value: `'production_completion'`. The hook tries `create()` and catches `psycopg2.IntegrityError` for race-condition idempotency under concurrent BA writes.

3. **sync.health model name**: `etsy.sync.health` (matches P2-01/P2-02 precedent in `services/tracking_importer.py:198`). The ADR-003 rename to `multichannel.sync.health` and the convention noted in `multichannel_hub_core/CLAUDE.md` are intent-only — the rename has not been executed. Use the current name; future P0-11 (`multichannel.sync.health` model + dashboard tile) will rename.

### Open question deferred to Phase 3

- **Does Odoo 19 `stock.move.create()` auto-confirm via picking-type defaults?** If yes, fail-open path needs explicit `_action_cancel()` to undo a partially-created move. Discover during Phase 3 GREEN by inspecting `stock.move._action_confirm` triggers; document outcome here.

### Pattern reuse (memory-tagged)

- Drift-mirror template for `_sql_constraints` + `init()` raw SQL: 7th use (after design_file, design_file_route, etsy_message_dedupe, multichannel_enquiry_etsy, P2-01 tracking_import_log, P2-01 tracking_import_line). Canonical template lives in `multichannel_hub_core/models/design_file.py`.
- FR-017 pattern (defense-in-depth `write()` override) does NOT apply to P2-03 directly — the hook fires AS PART OF a write() commit, not independently. But the existing `sale.order.fulfillment.write()` override (lines 179–211) already includes the address-change guard, which the hook inherits transitively.
