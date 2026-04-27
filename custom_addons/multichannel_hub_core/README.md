# Multichannel Hub Core

Foundation module for the multichannel order pipeline on Odoo 19 CE.

## Purpose (per ADR-003)

Hosts the shared building blocks consumed by every channel connector and the
fulfillment layer:

- `sale.order.fulfillment` delegation mixin (planned P1-05, ADR-007)
- Unified `shipping.carrier` model + seed (planned P1-06, ADR-005)
- `order.design.file` model + 3-state approval workflow
- `multichannel.sync.health` observability model (renamed from
  `etsy.sync.health`)
- Order / Tracking / Process dashboards (Spec 003)
- `carrier_detector.py` service
- `order.return` model + state machine
- Webhook controller base, rate-limiter utility

## Status

Scaffold only — installable as an empty module. Content lands incrementally
across Phase 1 slices.

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
