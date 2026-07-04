# ADR-018: Gearment quote cost-binding on the dropship PO (reuse + order-level allocation)

- **Status**: Accepted
- **Date**: 2026-07-02
- **Ticket**: ESTY-246
- **Module**: `multichannel_hub_fulfillment`
- **Related**: ADR-010 (hybrid dropship + MTO), FR-017 (write-level defense-in-depth)

## Context
ESTY-246 asks for a "Request Gearment Quote" function on the **dropship purchase order** so
the operator can pull the Gearment price. The owner's driver is **tracking Gearment cost
spend**. The quote-fetch capability already exists on `sale.order`
(`action_get_gearment_quote` → `GearmentApiAdapter.get_quote`), which stores the quote on
`x_gearment_quote_*` fields for the fulfillment-confirm handshake (P4-01-C).

A Gearment quote is **order-level** (`get_quote(reference_id)` returns `order_sub_total`,
`order_shipping_fee`, `order_tax`, `order_discount`, `order_handle_fee`,
`order_gift_message_fee`, `order_fee`, `order_total`) — there are no per-item prices. A single
dropship PO can aggregate lines from multiple source SOs (`_get_source_sale_orders()` returns a
recordset).

## Decision
1. **Bind the quote to PO cost, do not mirror quote fields.** The action writes item cost to the
   standard `purchase.order.line.price_unit` and adds one **"Gearment shipping & fees"** service
   line (seeded `product_gearment_fees`) per source SO carrying `order_total - order_sub_total`.
   The PO total then equals the Gearment cost, and **standard Purchase reporting + vendor bills
   grouped by the Gearment vendor** track spend. No custom `x_gearment_quote_*` mirror fields; a
   single `x_gearment_quote_breakdown_json` Text field holds the audit trail.
2. **Reuse the fetch.** The action calls the existing `GearmentApiAdapter.get_quote`; it does not
   duplicate quote-parse logic.
3. **Per-SO iteration.** Iterate `_get_source_sale_orders()` (mirroring the existing
   `button_confirm` push loop); each PO line traces to its SO via `sale_line_id.order_id`.
4. **Order-level → per-line allocation.** Split `order_sub_total` across a SO's product lines
   proportional to current subtotal (fallback: quantity), with the rounding residual placed on the
   largest line so the summed item cost equals `order_sub_total` exactly and the PO total matches
   `order_total` to the cent.
5. **Access: FR-017 gate then sudo.** Gate on `purchase.group_purchase_user` OR
   `group_ba_shipping` (owner: either team may request) BEFORE any write, then `sudo()` the
   reads/writes (shipping users lack `purchase.order.line` write and cross-model SO read).
6. **Re-request overwrites.** Delete prior fee lines and overwrite `price_unit`, post an
   old→new-total chatter note. Existing-quote expiry does not block.

## Alternatives considered
- **Mirror `x_gearment_quote_*` onto `purchase.order`** — duplicates SO logic and diverges; no
  benefit over binding to standard `price_unit`. Rejected.
- **Custom Gearment spend model/dashboard** — standard Purchase reporting already delivers
  vendor-spend-by-period. Rejected (Standard-Odoo-First).
- **Display-only quote (wizard preview, no cost write)** — fails the cost-tracking driver.
  Rejected.
- **Reject multi-SO POs** — unnecessary; per-SO iteration handles it cleanly. Rejected.

## Consequences
- Allocation is order-level/proportional (Gearment returns no per-item price); acceptable and the
  PO total is exact to the cent.
- The fee line needs a seeded `service` product (`product_gearment_fees`, `noupdate="1"`); a DB
  predating the seed needs a module update to load it.
- Re-request must delete prior fee lines before recreating (idempotency); covered by tests.
- `sudo()` after the group gate follows the module's FR-017 pattern; security-reviewed clean.
