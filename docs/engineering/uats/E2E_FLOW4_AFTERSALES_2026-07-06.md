# MF-E2E-4 — Flow-4 Hậu mãi after-sales (2026-07-06)

- **Target**: https://odoo.hatafax.com / DB `esty_odoo19`
- **Build**: dfc4780d3f3
- **Driver**: scripts/e2e_flow4_aftersales.py
- **Order**: S03417 (receipt marker 9783326283)
- **Result**: 8/8 sections PASS

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | server 19.0-20260609; BA-Lead group OK; shop OK; MTO route OK; marker=21c8a5; archived 0 stale product(s) | — |
| 1 | PASS | order S03417 (receipt 9783326283); product + component + stock seeded; partner created | — |
| 2 | PASS | request approved by [28, 'UAT BA Lead (auto-seeded)']; SO partner_shipping_id=[243, 'E2E-F4 Buyer 21c8a5 (new addr)'] | — |
| 3 | PASS | request rejected: state=rejected | — |
| 4 | PASS | second MO 27 created and completed; second tracking 9400111202555568648 recorded; push attempts=1 | — |
| 5 | PASS | ticket RT00006 state machine: draft→approved→refunded (non-BA-Lead approve blocked); final state=refunded | — |
| 6 | PASS | UI evidence captured: 2 screenshot(s) | docs/screenshots/2026-07-06/f4_s6_ticket_form.png |
| 7 | PASS | 2 product(s) archived; order cancelled | — |

## Notes

- §2 tests address-change approval workflow (create → approve → applied to SO).
- §3 tests negative path (reject with reason; role gating).
- §4 creates second MO for reprint scenario (replacement fulfillment).
- §5 tests ticket state machine (draft → approved → refunded) with BA-Lead-only role gating.
- Etsy refund is manual (no API for this flow); ticket tracks the decision for audit trail.

## Reproducing

```bash
/tmp/e2e-venv/bin/python scripts/e2e_flow4_aftersales.py --db esty_odoo19
```
