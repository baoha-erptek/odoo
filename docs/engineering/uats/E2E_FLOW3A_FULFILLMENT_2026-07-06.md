# MF-E2E-3a — Flow-3a giao hàng in nội bộ (2026-07-06)

- **Target**: https://odoo.hatafax.com / DB `esty_odoo19`
- **Build**: 3a0b8e7f939
- **Driver**: scripts/e2e_flow3a_fulfillment.py
- **Order**: S03408 (receipt marker 9783325667)
- **Result**: 10/10 sections PASS

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | server 19.0-20260609; routes OK (mfg+mto); gke folder 1-cY65RD…; google libs OK; marker=fd69b3; archived 0 stale product(s) | — |
| 1 | PASS | order S03408 (receipt marker 9783325667), Route-A product + 1:1 BOM + component stock seeded | — |
| 2 | PASS | MO WH/MO/00022 state=confirmed auto-created from S03408 | — |
| 3 | PASS | design.file state=approved; MO design_ready False->True after design order approval | — |
| 4 | PASS | MO state=done | — |
| 5 | PASS | DO WH/OUT/00096 state=done; FLW-06 pipeline vn_internal_production auto-advanced to 'shipped' (expect 'shipped') | — |
| 6 | PASS | generated gke_e2e_f3_fd69b3.xlsx for receipt 9783325667 + uploaded to Drive folder 1-cY65RD… | — |
| 7 | PASS | log={'id': 53, 'state': 'ok', 'source': 'gdrive', 'filename': 'gke_e2e_f3_fd69b3.xlsx', 'matched_count': 1, 'imported_count': 1, 'total_rows': 1} lines=[{'id': 198, 'state': 'imported', 'raw_tracking_number': '9400111202555560000001'}] fulfillment=[{'id': 3414, 'tracking_number': '9400111202555560000001', 'shipping_carrier_id': [1, 'USPS']}] | — |
| 8 | PASS | push={'id': 3391, 'etsy_tracking_push_status': 'failed', 'etsy_tracking_push_at': '2026-07-06 08:14:49', 'etsy_tracking_push_attempts': 1, 'etsy_tracking_push_error': 'Etsy tracking push error: 404 Client Error: Not Found for url: https://openapi.etsy.com/v3/application/shops/60752333/receipts/9783325667/tracking'} api_log=[{'id': 26201, 'http_status': 0, 'error_message': 'Etsy tracking push error: 404 Client Error: Not Found for url: https://openapi.etsy.com/v3/application/shops/60752333/receipts/9783325667/tracking'}] | — |
| 9 | PASS | evidence captured; 2 product(s) archived | docs/screenshots/2026-07-06/f3_s9_order_tracking.png |

## Notes

- §5 asserts the FLW-06 auto-advance: outgoing-picking validation moves the SO pipeline to 'shipped' (ĐÃ GỬI) — no manual state write in this runner since the 2026-07-06 rerun.
- §6 GENERATES the GKE xlsx from this run's actual order ref (closes the MF-E2E-0 residue: the static sample matched 0/9).
- §8 proves the tracking-push path to the Etsy API boundary with a synthetic receipt; a live `pushed` confirmation belongs to P1-11 (real receipts on the production shop).
- Tracking-push retry cap (`etsy_tracking_push_attempts` < 10 in the fallback cron) shipped with this gate — fixes the eternal 5-minute retry loop found in MF-E2E-2.

## Reproducing

```bash
/tmp/e2e-venv/bin/python scripts/e2e_flow3a_fulfillment.py --db esty_odoo19
```
