# MF-E2E-3a — Flow-3a giao hàng in nội bộ (2026-07-04)

- **Target**: https://odoo.hatafax.com / DB `esty_odoo19`
- **Build**: e274da24474
- **Driver**: scripts/e2e_flow3a_fulfillment.py
- **Order**: S03359 (receipt marker 9783174365)
- **Result**: 10/10 sections PASS

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | server 19.0-20260609; routes OK (mfg+mto); gke folder 1-cY65RD…; google libs OK; marker=bc1d21; archived 0 stale product(s) | — |
| 1 | PASS | order S03359 (receipt marker 9783174365), Route-A product + 1:1 BOM + component stock seeded | — |
| 2 | PASS | MO WH/MO/00007 state=confirmed auto-created from S03359 | — |
| 3 | PASS | design.file state=approved | — |
| 4 | PASS | MO state=done | — |
| 5 | PASS | DO WH/OUT/00085 state=done | — |
| 6 | PASS | generated gke_e2e_f3_bc1d21.xlsx for receipt 9783174365 + uploaded to Drive folder 1-cY65RD… | — |
| 7 | PASS | log={'id': 11, 'state': 'ok', 'source': 'gdrive', 'filename': 'gke_e2e_f3_bc1d21.xlsx', 'matched_count': 1, 'imported_count': 1, 'total_rows': 1} lines=[{'id': 39, 'state': 'imported', 'raw_tracking_number': '9400111202555560000001'}] fulfillment=[{'id': 3361, 'tracking_number': '9400111202555560000001', 'shipping_carrier_id': [1, 'USPS']}] | — |
| 8 | PASS | push={'id': 3342, 'etsy_tracking_push_status': 'failed', 'etsy_tracking_push_at': '2026-07-04 14:13:06', 'etsy_tracking_push_attempts': 1, 'etsy_tracking_push_error': 'Etsy tracking push error: 404 Client Error: Not Found for url: https://openapi.etsy.com/v3/application/shops/60752333/receipts/9783174365/tracking'} api_log=[{'id': 24986, 'http_status': 0, 'error_message': 'Etsy tracking push error: 404 Client Error: Not Found for url: https://openapi.etsy.com/v3/application/shops/60752333/receipts/9783174365/tracking'}] | — |
| 9 | PASS | evidence captured; 2 product(s) archived | docs/screenshots/2026-07-04/f3_s9_order_tracking.png |

## Notes

- §6 GENERATES the GKE xlsx from this run's actual order ref (closes the MF-E2E-0 residue: the static sample matched 0/9).
- §8 proves the tracking-push path to the Etsy API boundary with a synthetic receipt; a live `pushed` confirmation belongs to P1-11 (real receipts on the production shop).
- Tracking-push retry cap (`etsy_tracking_push_attempts` < 10 in the fallback cron) shipped with this gate — fixes the eternal 5-minute retry loop found in MF-E2E-2.

## Reproducing

```bash
/tmp/e2e-venv/bin/python scripts/e2e_flow3a_fulfillment.py --db esty_odoo19
```

## Gate summary (MF-E2E-3a exit criteria)

- Runner **10/10 PASS ×2 consecutive**: Route-A order → MO auto-created →
  design approve → MO done → DO validated → GENERATED GKE xlsx (real order
  refs — closes the MF-E2E-0 "0/9 matched" residue) → GDrive inbox → poller
  import → carrier auto-detected (USPS) → Etsy push flags set end-to-end.
- Playwright `uat_huong_dan_giao_hang.spec.ts`: **7 passed ×2, 0 failed**
  (7 documented skips: Gearment-gated TC-DROP-002..005 → MF-E2E-3b; TC-DROP
  fixtures without quote state; TC-ETSY-PUSH on non-etsy fixtures).
- Product fixes shipped:
  1. `etsy_integration 19.0.3.18.0` — tracking-push retry cap
     (`etsy_tracking_push_attempts` + cron ceiling 10; kills the eternal
     5-minute retry loop found in MF-E2E-2). 3 unit tests.
  2. `multichannel_hub_fulfillment 19.0.1.0.26` — carrier detection now
     runs on the programmatic import path (GDrive poller imported
     trackings with NO carrier before; wizard-only detection). 1 unit test.
     Also: schema compute survives web `bin_size` reads (New Schema flag +
     Approve Schema button used to vanish from the wizard UI). 1 unit test.
  3. `multichannel_hub_core 19.0.1.0.76` — Rejection tab visible while
     PENDING (operator had NO UI path to reject: reason field only
     appeared after the state it gates).
- Env provisioning: gke logistics.partner `gdrive_inbox_folder_id` set to
  the owner "GKE" Drive folder (was empty on esty_odoo19).
- Test-infra: builder USPS tracking trimmed to 22 digits (seed regex cap);
  6 Playwright selector/flow drifts fixed (lazy tabs ×3, o_select_menu,
  facet-scoped searches ×2, wizard field renames, confirm dialog,
  role-gated logins).
- Local full regression: 1945/1948 pass; 3 pre-existing failures in
  `test_pipeline_state_db` (stale `design_ready` seed rows in the local dev
  DB — noupdate drift, unrelated to this gate; staging unaffected).
- Honest scope note: §8 proves the push path to the Etsy API boundary
  (synthetic receipt → recorded 404 + flags + audit row); a live `pushed`
  needs a real receipt on the production shop (P1-11).
