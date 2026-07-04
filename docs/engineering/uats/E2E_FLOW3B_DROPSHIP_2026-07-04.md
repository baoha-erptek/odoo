# MF-E2E-3b — Flow-3b Gearment dropship, LIVE API (2026-07-04)

- **Target**: https://odoo.hatafax.com / DB `esty_odoo19`
- **Build**: 33aad0d9bce
- **Driver**: scripts/e2e_flow3b_dropship.py
- **Gearment**: LIVE api (draft-only safety contract)
- **Order**: S03363 / outbound_ref SIM-GM-a83bf5
- **Result**: 8/8 sections PASS

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | server 19.0-20260609; pipeline OK; staging env OK; live catalog: 'Hand flag with handle' legacy_id=249; marker=a83bf5; archived 0 | — |
| 1 | PASS | order S03363; POD product legacy_id=249; approved URL design (artwork=https://origin-x.geaflare.com/exproduct/…) | — |
| 2 | PASS | state=sale pipeline_state=[8, 'Confirmed'] | — |
| 3 | PASS | LIVE: vendor 400 handled gracefully (UserError='requests.exceptions.HTTPError: 400 Client Error: Bad Request for url: https://apiv2.gearment.com/integration-handler/api/v3/orders/draft'; validator audited=True). SIMULATED push+quote: ref='SIM-GM-a83bf5' state='quoted'  | — |
| 4 | PASS | quote state (simulated HTTP, real state machine): {'id': 3346, 'x_gearment_outbound_state': 'quoted', 'x_gearment_outbound_ref': 'SIM-GM-a83bf5', 'x_gearment_quote_total': 14.94} | — |
| 5 | PASS | webhook status=200 body='{"status": "ok"}' | — |
| 6 | PASS | fulfillment=[{'id': 3365, 'tracking_number': '9400111202555560008357', 'tracking_url': 'https://tools.usps.com/go/TrackConfirmAction?tLabels=9400111202555560008357', 'gearment_last_webhook_topic': 'tracking_order_updated'}] push={'id': 3346, 'etsy_tracking_push_status': 'failed', 'etsy_tracking_push_attempts': 1, 'etsy_tracking_push_error': 'Etsy tracking push error: 404 Client Error: Not Found for url: https://openapi.etsy.com/v3/application/shops/60752333/receipts/9683180489/tracking'} | docs/screenshots/2026-07-04/f3b_s6_dropship_order.png |
| 7 | PASS | SO cancelled; 1 product(s) archived. OWNER ACTION: discard Gearment DRAFT order ref='SIM-GM-a83bf5' in the dashboard (never confirmed/labeled by this runner). | — |

## Notes

- SAFETY: only `POST api/v3/orders/draft` + `GET orders/{ref}/price` were called live; `confirm()/labeled` (chargeable) is NEVER invoked by this runner. Owner discards the draft in the Gearment dashboard.
- Webhook leg is self-signed with the P0-18b2 HMAC scheme — closes the signature verification live (X-Connect-Signature).
- Etsy tracking push runs to the API boundary (synthetic receipt → recorded outcome); live `pushed` belongs to P1-11.

## Reproducing

```bash
/tmp/e2e-venv/bin/python scripts/e2e_flow3b_dropship.py --db esty_odoo19
```

## Gate summary (MF-E2E-3b exit criteria)

- Runner **8/8 PASS ×2 consecutive**. LIVE legs: catalog fetch, vendor-400
  handling (validator name audited in gearment.api.log), HMAC-verified
  webhook (X-Connect-Signature, 200), Etsy tracking push to the API
  boundary. SIMULATED legs (documented mock fallback per exit criteria —
  sandbox host 530-dead): orders/draft + price at the HTTP boundary only;
  builder, model writes, and the outbound state machine are the real code.
- Playwright `uat_huong_dan_giao_hang.spec.ts` **8 passed ×2** with
  GEARMENT env (TC-DROP-001 state-aware button, TC-DROP-005 live HMAC
  webhook green after padding + client-key fixes; TC-DROP-002/003 carry
  documented vendor-blocked skips).
- Product fix (mhf 19.0.1.0.27): webhook-triggered Etsy push ran in the
  PUBLIC env and died on the fulfillment ACL — the ADR D-A PRIMARY trigger
  had never worked from a live webhook (every push silently deferred to
  the 5-min cron). Now sudo'd (bounded, HMAC-verified upstream) + ORM test.
- **VENDOR BLOCKER (unchanged)**: Gearment production validator rejects
  every known `printing_options` shape (Defect-2026-05-10-05).
  Re-confirmed 2026-07-04 with NEW variant-level ids
  (legacy_variant_id/location_id from the live catalog) — identical
  opaque 400. Sandbox host (api.gearmentinc.com) is 530-dead. No OpenAPI
  spec discoverable. OWNER ACTION: escalate to Gearment support with
  request_id `1d36e400-77e8-4612-b0f7-2539b2471d76` (today's rejection)
  and the validator name `has_front_back_or_whole_printing_option`.
  Until answered, live dropship order push cannot go to production.
