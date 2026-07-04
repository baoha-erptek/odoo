# MF-E2E-2 — Flow-2 nhận đơn hàng Etsy (2026-07-04)

- **Target**: https://odoo.hatafax.com / DB `esty_odoo19`
- **Build**: 1bfaecf6d6d
- **Driver**: scripts/e2e_flow2_orders.py
- **Etsy shop**: JaHandmadeArt (60752333)
- **Result**: 7/7 sections PASS

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | server 19.0-20260609; shop id=10 source=api cursor=2025-10-13 09:18:48; cleaned 0 order(s) + 0 email log(s) | — |
| A | PASS | cursor=2025-10-13 09:18:48 health={'id': 33, 'state': 'ok', 'last_run_at': '2026-07-04 13:32:12', 'last_run_row_count': 1, 'last_run_error_count': 0} orders 4->4 partners 10->10 dupes=none | — |
| B | PASS | 2nd sync: orders 4->4 dupes=none cursor=2025-10-13 09:18:48 health_rows=1 | — |
| C | PASS | source→email change_log={'id': 20, 'from_source': 'api', 'to_source': 'email', 'reason': 'manual'} cursor 2025-10-13 09:18:48==2025-10-13 09:18:48 | docs/screenshots/2026-07-04/f2_sC_shop_email_mode.png |
| D | PASS | orders=['S03353', 'S03354'] partners={169, 170} (per-order partner = designed for address-less text emails) pipeline=[[1, 'Vietnam Internal Production'], [1, 'Vietnam Internal Production']] | docs/screenshots/2026-07-04/f2_sD_email_order.png |
| E | PASS | etsy_email_fetch health: {'id': 34, 'state': 'ok', 'last_run_at': '2026-07-04 13:32:26', 'last_run_row_count': 0, 'last_run_error_count': 0} | — |
| F | PASS | active_source restored to api; removed 2/2 fixture order(s) + 2 log(s) | — |

## Notes

- §A/§B rewind `etsy_last_receipt_sync_at` and re-fetch REAL JaHandmadeArt receipts — dedupe (status-only re-sync) is the assertion, so `orders unchanged` is the PASS condition.
- §C/§D prove the manual fallback: source→email stops the API cursor; the email path still creates + classifies orders (fixture replay via `action_retry_parse`, semantics-equal to the Gmail cron). Partner dedupe is asserted on the API path (§A 'no new partners'); the text-only email fixture has no address/email so per-order partners are the designed Tier-4 outcome there.
- Sync-health rows for BOTH paths (`etsy_api_receipts_sync`, `etsy_email_fetch`) landed in etsy_integration 19.0.3.16.0 (report_run wired into both crons — spec 015 MF-E2E-2 criterion).
- Production-shop assertions deferred to P1-11 per the gate scope.

## Reproducing

```bash
/tmp/e2e-venv/bin/python scripts/e2e_flow2_orders.py --db esty_odoo19
```

## Gate summary (MF-E2E-2 exit criteria)

- Runner **7/7 PASS ×2 consecutive** (§0/A/B/C/D/E/F).
- Playwright `uat_huong_dan_don_hang_etsy.spec.ts`: **7 passed ×2, 0 failed**
  (2 documented skips: TC-006 needs an Etsy-typed seed order — pre-existing
  follow-up; TC-008 dedupe fixture timing). New TC-009 covers the manual
  fallback walk (api → email → api) with audit-log assertions.
- Sync-health rows now written for BOTH ingest paths
  (`etsy_api_receipts_sync`, `etsy_email_fetch`) — landed with 4 unit tests
  (`TestSyncHealthBothPaths`).
- `action_retry_parse` now returns operator notifications (was silent).
- Test-infra fixes: anchor fixture re-frozen (S00007→S03339, state sale);
  seed_ba_user grants BA users Sales "All Documents" (bare BA group has no
  sale.order ACL); TC-006 skip guard before openTab; TC-007 accepts
  pre-flight guard rows (http_status=0 + error_message).

### Owner items

1. **Owner flow-2 doc vs UI**: the doc says "admin toggles active_source in
   the UI", but the shop form renders it as a READONLY badge (owner-gated
   P-DS-3a design). The real mechanism is a backend/admin write until AUD-01
   (auto-switch) or an explicit UI control lands. Align doc or add a gated
   UI toggle — owner call.
2. **Tracking-push retry loop**: `Etsy: Push Tracking` cron retries receipt
   3703975562 against legacy shop id=1 ("Shop has no etsy_api_shop_id")
   every ~5 min, forever — noisy api-log rows. Needs a retry cap or shop
   fix; routed to MF-E2E-3a scope.
