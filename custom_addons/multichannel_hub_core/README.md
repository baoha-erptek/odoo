# Multichannel Hub Core

Foundation module for the multichannel order pipeline on Odoo 19 CE.

## Purpose (per ADR-003)

Hosts the shared building blocks consumed by every channel connector and the
fulfillment layer:

- `sale.order.fulfillment` delegation mixin (P1-05 ✅, ADR-007 Direction A)
- Unified `shipping.carrier` model + 7-row seed (P1-06 ✅, ADR-005)
- `design.file` model + 3-col kanban + URL-mode + 10MB cap (P1-02a ✅)
- Order Dashboard list view + decorations + Operations menu (P1-01a ✅)
- Tracking Dashboard list + Mark-Shipped + bus.bus emit (P1-03 ✅)
- `multichannel.sync.health` observability model — planned
- Process Dashboard — planned (Spec 003 US3)
- `carrier_detector.py` service — planned (Spec 004a)
- `order.return` model + state machine — planned (Spec 004c)
- Webhook controller base, rate-limiter utility (`utils/rate_limiter.py` ✅)

## Status

Active — Phase 1 dashboards + fulfillment delegation landed. Manifest at
`19.0.1.0.5`. Content continues to land incrementally across remaining
Phase 1 slices.

## Dependencies

Odoo core only: `sale_management`, `stock`, `contacts`, `mail`. No
Enterprise dependencies (per ADR-004).

## Module relationships

```
multichannel_hub_core           <-- this module
        ^
        |
multichannel_hub_fulfillment    (Spec 004a / 004b)
        ^
        |
etsy_channel                    (Spec 001 / 005 + email failover)
        ^
        |
etsy_channel_migration          (Spec 002 — uninstallable post-cutover)
```

## References

- `specs/006-master-plan/adrs/ADR-003-module-decomposition.md`
- `specs/006-master-plan/MASTER_PLAN.md`
- `.claude/plans/006-master-plan-tracking.md` — task P0-20
