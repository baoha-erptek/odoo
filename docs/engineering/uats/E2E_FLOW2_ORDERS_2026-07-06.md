# MF-E2E-2 — Flow-2 nhận đơn hàng Etsy (2026-07-06)

- **Target**: https://odoo.hatafax.com / DB `esty_odoo19`
- **Build**: 3a0b8e7f939
- **Driver**: scripts/e2e_flow2_orders.py
- **Etsy shop**: JaHandmadeArt (60752333)
- **Result**: 8/8 sections PASS

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | server 19.0-20260609; shop id=10 source=api cursor=2025-10-13 09:18:48; cleaned 0 order(s) + 0 email log(s) | — |
| A | PASS | cursor=2025-10-13 09:18:48 health={'id': 33, 'state': 'ok', 'last_run_at': '2026-07-06 08:13:20', 'last_run_row_count': 1, 'last_run_error_count': 0} orders 30->30 partners 11->11 dupes=none | — |
| B | PASS | 2nd sync: orders 30->30 dupes=none cursor=2025-10-13 09:18:48 health_rows=1 | — |
| C | PASS | source→email change_log={'id': 30, 'from_source': 'api', 'to_source': 'email', 'reason': 'manual'} cursor 2025-10-13 09:18:48==2025-10-13 09:18:48 | docs/screenshots/2026-07-06/f2_sC_shop_email_mode.png |
| D | PASS | orders=['S03404', 'S03405'] partners={227, 228} (per-order partner = designed for address-less text emails) pipeline=[[1, 'Vietnam Internal Production'], [1, 'Vietnam Internal Production']] | docs/screenshots/2026-07-06/f2_sD_email_order.png |
| E | PASS | etsy_email_fetch health: {'id': 34, 'state': 'ok', 'last_run_at': '2026-07-06 08:13:35', 'last_run_row_count': 0, 'last_run_error_count': 0} | — |
| F | PASS | active_source restored to api; removed 2/2 fixture order(s) + 2 log(s) | — |
| G | PASS | order S03406 (id 3389) blocked=True products 177->177; cleaned 1 stale fixture(s) | docs/screenshots/2026-07-06/f2_sG_unresolved_hold.png |

## Notes

- §A/§B rewind `etsy_last_receipt_sync_at` and re-fetch REAL JaHandmadeArt receipts — dedupe (status-only re-sync) is the assertion, so `orders unchanged` is the PASS condition.
- §C/§D prove the manual fallback: source→email stops the API cursor; the email path still creates + classifies orders (fixture replay via `action_retry_parse`, semantics-equal to the Gmail cron). Partner dedupe is asserted on the API path (§A 'no new partners'); the text-only email fixture has no address/email so per-order partners are the designed Tier-4 outcome there.
- Sync-health rows for BOTH paths (`etsy_api_receipts_sync`, `etsy_email_fetch`) landed in etsy_integration 19.0.3.16.0 (report_run wired into both crons — spec 015 MF-E2E-2 criterion).
- §G asserts the FLW-03 hold (2026-07-06): API ingest with an unknown SKU books the 'Etsy Unresolved Item' placeholder, holds the order via production_blocked/block_reason, and creates NO product (the old auto-create contract is gone). The held order is kept for the screenshot harvest and removed by the run-level cleanup phase.
- Production-shop assertions deferred to P1-11 per the gate scope.

## Reproducing

```bash
/tmp/e2e-venv/bin/python scripts/e2e_flow2_orders.py --db esty_odoo19
```
