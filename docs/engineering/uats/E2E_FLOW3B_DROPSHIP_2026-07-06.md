# MF-E2E-3b — Flow-3b Gearment dropship, LIVE API (2026-07-06)

- **Target**: https://odoo.hatafax.com / DB `esty_odoo19`
- **Build**: 3fd706c3b1f
- **Driver**: scripts/e2e_flow3b_dropship.py
- **Gearment**: LIVE api (draft-only safety contract)
- **Order**: S03413 / outbound_ref 260706P-GM3MUJU-4VSXP3T8
- **Result**: 10/10 sections PASS

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | server 19.0-20260609; pipeline OK; staging env OK; live catalog: 'Hand flag with handle' variant_id=GM0249020374; marker=536d5a; archived 0 | — |
| 1 | PASS | order S03413; POD product variant_id=GM0249020374; approved URL design (artwork=https://origin-x.geaflare.com/exproduct/…) | — |
| 2 | PASS | state=sale pipeline_state=[8, 'Confirmed'] | — |
| 3 | PASS | LIVE draft pushed (vendor validator FIXED?): outbound_ref='260706P-GM3MUJU-4VSXP3T8' — owner must discard the Gearment DRAFT | — |
| 4 | PASS | LIVE quote (POST /orders/price): {'id': 3396, 'x_gearment_outbound_state': 'quoted', 'x_gearment_outbound_ref': '260706P-GM3MUJU-4VSXP3T8', 'x_gearment_quote_total': 12.99, 'x_gearment_quote_currency': 'USD'} | — |
| W | PASS | draft http=200 gift_message_body='Happy birthday from E2E-F3B 536d5a' line_item_keys=['printing_options', 'quantity', 'variant_id'] | — |
| 5 | PASS | webhook status=200 body='{"status": "ok"}' | — |
| 6 | PASS | fulfillment=[{'id': 3419, 'tracking_number': '9400111202555560005365', 'tracking_url': 'https://tools.usps.com/go/TrackConfirmAction?tLabels=9400111202555560005365', 'gearment_last_webhook_topic': 'tracking_order_updated'}] push={'id': 3396, 'etsy_tracking_push_status': 'failed', 'etsy_tracking_push_attempts': 1, 'etsy_tracking_push_error': 'Etsy tracking push error: 404 Client Error: Not Found for url: https://openapi.etsy.com/v3/application/shops/60752333/receipts/9683325802/tracking'} | docs/screenshots/2026-07-06/f3b_s6_dropship_order.png |
| V | PASS | block UserError="Cannot push to Gearment: product 'E2E-F3B MV 536d5a (Hand flag with h) (11 oz)' has variants, but this variant has no Gearment variant code. On the product's Purchase tab, add the Gearment vendor line"; mapped push ref='260706P-GM3MUJU-4VX0BER4' err='' wire_variant_ids=['GM0249020374', 'GM0249020373'] flw04_warnings=3 | — |
| 7 | PASS | SO(s) cancelled; 2 product(s) archived. OWNER ACTION: discard Gearment DRAFT order ref(s) ['260706P-GM3MUJU-4VSXP3T8', '260706P-GM3MUJU-4VX0BER4'] in the dashboard (never confirmed/labeled by this runner). | — |

## Notes

- SAFETY: only `POST api/v3/orders/draft` + `GET orders/{ref}/price` were called live; `confirm()/labeled` (chargeable) is NEVER invoked by this runner. Owner discards the draft in the Gearment dashboard.
- Webhook leg is self-signed with the P0-18b2 HMAC scheme — closes the signature verification live (X-Connect-Signature).
- Etsy tracking push runs to the API boundary (synthetic receipt → recorded outcome); live `pushed` belongs to P1-11.
- §W (FLW-05, 2026-07-06): the draft wire carries `gift_message_body` from the order's gift message and line_items carry NO `personalisation` key (removed — not in the vendor schema). Asserted on the PII-scrubbed request_payload_summary.
- §V (FLW-01/FLW-04, 2026-07-06): multi-variant product without variant-specific Gearment codes must BLOCK the push (UserError); with per-variant supplierinfo product_code rows the draft carries DISTINCT GM variant_ids. Expedited shipping_service_label logs a WARNING but ships METHOD_STANDARD (only wire-documented method).

## Reproducing

```bash
/tmp/e2e-venv/bin/python scripts/e2e_flow3b_dropship.py --db esty_odoo19
```
