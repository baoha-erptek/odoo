# MF-E2E-3b — Flow-3b Gearment dropship, LIVE API (2026-07-05)

- **Target**: https://odoo.hatafax.com / DB `esty_odoo19`
- **Build**: cd529987e7f
- **Driver**: scripts/e2e_flow3b_dropship.py
- **Gearment**: LIVE api (draft-only safety contract)
- **Order**: S03369 / outbound_ref 260705P-GM3MUJU-Z9Y83RVD
- **Result**: 8/8 sections PASS

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | server 19.0-20260609; pipeline OK; staging env OK; live catalog: 'Hand flag with handle' variant_id=GM0249020374; marker=399047; archived 0 | — |
| 1 | PASS | order S03369; POD product variant_id=GM0249020374; approved URL design (artwork=https://origin-x.geaflare.com/exproduct/…) | — |
| 2 | PASS | state=sale pipeline_state=[8, 'Confirmed'] | — |
| 3 | PASS | LIVE draft pushed (vendor validator FIXED?): outbound_ref='260705P-GM3MUJU-Z9Y83RVD' — owner must discard the Gearment DRAFT | — |
| 4 | PASS | LIVE quote (POST /orders/price): {'id': 3352, 'x_gearment_outbound_state': 'quoted', 'x_gearment_outbound_ref': '260705P-GM3MUJU-Z9Y83RVD', 'x_gearment_quote_total': 12.99, 'x_gearment_quote_currency': 'USD'} | — |
| 5 | PASS | webhook status=200 body='{"status": "ok"}' | — |
| 6 | PASS | fulfillment=[{'id': 3371, 'tracking_number': '9400111202555560003990', 'tracking_url': 'https://tools.usps.com/go/TrackConfirmAction?tLabels=9400111202555560003990', 'gearment_last_webhook_topic': 'tracking_order_updated'}] push={'id': 3352, 'etsy_tracking_push_status': 'failed', 'etsy_tracking_push_attempts': 1, 'etsy_tracking_push_error': 'Etsy tracking push error: 404 Client Error: Not Found for url: https://openapi.etsy.com/v3/application/shops/60752333/receipts/9683224563/tracking'} | docs/screenshots/2026-07-05/f3b_s6_dropship_order.png |
| 7 | PASS | SO cancelled; 1 product(s) archived. OWNER ACTION: discard Gearment DRAFT order ref='260705P-GM3MUJU-Z9Y83RVD' in the dashboard (never confirmed/labeled by this runner). | — |

## Notes

- SAFETY: only `POST api/v3/orders/draft` + `GET orders/{ref}/price` were called live; `confirm()/labeled` (chargeable) is NEVER invoked by this runner. Owner discards the draft in the Gearment dashboard.
- Webhook leg is self-signed with the P0-18b2 HMAC scheme — closes the signature verification live (X-Connect-Signature).
- Etsy tracking push runs to the API boundary (synthetic receipt → recorded outcome); live `pushed` belongs to P1-11.

## Reproducing

```bash
/tmp/e2e-venv/bin/python scripts/e2e_flow3b_dropship.py --db esty_odoo19
```
