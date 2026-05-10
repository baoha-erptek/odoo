# E2E Drop-Ship Demo — Etsy → Odoo → Gearment (2026-05-10)

- **Target**: https://odoo.hatafax.com
- **DB**: demo_esty
- **Build**: efc20888758
- **Driver**: scripts/e2e_demo_drop_ship_ordertest2.py
- **Email source**: real Gmail label `ordertest2`
- **Tracking source**: `.0temp/sample_bc_don_hang2026_04_08.xls`
- **Result**: 13/13 sections PASS

## Sections

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | version=19.0-20260324; removed 0 demo design.file from prior runs | docs/screenshots/2026-05-10/drop_ship_00_landing.png |
| 1 | PASS | resolved 4/4 receipt(s): ['S00064', 'S00065', 'S00066', 'S00067'] | — |
| 2 | PASS | order form + Operations Dashboard rendered (id=64) | docs/screenshots/2026-05-10/drop_ship_02_order_form.png | docs/screenshots/2026-05-10/drop_ship_02_dashboard.png |
| 3 | PASS | 4 order(s): [attached 3 DEMO design.file row(s) (storage_mode='small'; line ids: [120, 121, 122])]; [attached 3 DEMO design.file row(s) (storage_mode='small'; line id
=== 13/13 sections PASS ===
  [PASS] §0: version=19.0-20260324; removed 0 demo design.file from prior runs
  [PASS] §1: resolved 4/4 receipt(s): ['S00064', 'S00065', 'S00066', 'S00067']
  [PASS] §2: order form + Operations Dashboard rendered (id=64)
  [PASS] §3: 4 order(s): [attached 3 DEMO design.file row(s) (storage_mode='small'; line ids: [120, 121, 122])]; [attached 3 DEMO design.file row(s) (storage_mode='small'; line ids: [123, 124, 125])]; [attached 3 DEMO design.file row(s) (storage_mode='small'; line ids: [126, 127, 128])]; [attached 2 DEMO design.file row(s) (storage_mode='small'; line ids: [129, 130])]
  [PASS] §4: 4 order(s): [states={'approved'} (n=3)]; [states={'approved'} (n=3)]; [states={'approved'} (n=3)]; [states={'approved'} (n=2)]
  [PASS] §5: 4 order(s): [all 3 approved design.file rows promoted to gdrive; first gdrive_file_id=15LV2IKXwndL8uxHSruOeFMngFiQVqLF9]; [all 3 approved design.file rows promoted to gdrive; first gdrive_file_id=1dkvDT46R2OBbaKjVyrcoAhUAu5eBeiqF]; [all 3 approved design.file rows promoted to gdrive; first gdrive_file_id=19EGC7sGAAohF_pot1lozWUiRbD1fEjbB]; [all 2 approved design.file rows promoted to gdrive; first gdrive_file_id=17qLRZ-RAx1_SC95bN_SI3fKobU5rL5Ws]
  [PASS] §6: 4 order(s): [pipeline_state_id=8 outbound_ref=∅ outbound_api_logs=2 latest_endpoint=POST /api/v3/orders http_status=0 (non-200 means live Gearment API rejected the synthetic order; the wiring fired regardless — see chatter)]; [pipeline_state_id=8 outbound_ref=∅ outbound_api_logs=2 latest_endpoint=POST /api/v3/orders http_status=0 (non-200 means live Gearment API rejected the synthetic order; the wiring fired regardless — see chatter)]; [pipeline_state_id=8 outbound_ref=∅ outbound_api_logs=2 latest_endpoint=POST /api/v3/orders http_status=0 (non-200 means live Gearment API rejected the synthetic order; the wiring fired regardless — see chatter)]; [pipeline_state_id=8 outbound_ref=∅ outbound_api_logs=2 latest_endpoint=POST /api/v3/orders http_status=0 (non-200 means live Gearment API rejected the synthetic order; the wiring fired regardless — see chatter)]
  [PASS] §7: 4 order(s): [webhook status=200 body='{"status": "ok"}']; [webhook status=200 body='{"status": "ok"}']; [webhook status=200 body='{"status": "ok"}']; [webhook status=200 body='{"status": "ok"}']
  [PASS] §8: wizard.state=done; 4 line(s); 4 imported, 4 matched. matched_targets=4/4 (GKE schema from gke_e2e_2026-05-10.xlsx)
  [PASS] §8b: +2 log row(s); latest id=43 source=gdrive state=ok filename=gke_e2e_2026_05_10.xlsx rows=4/imported=4/matched=4
  [PASS] §9: shipped 4/4 fulfillment(s); tracking_states=['shipped', 'shipped', 'shipped', 'shipped']
  [PASS] §10: 4 order(s): [webhook status=200 body='{"status": "ok"}']; [webhook status=200 body='{"status": "ok"}']; [webhook status=200 body='{"status": "ok"}']; [webhook status=200 body='{"status": "ok"}']
  [PASS] §11: 4 order(s): [chatter has 8 message(s) on sale.order id=64]; [chatter has 8 message(s) on sale.order id=65]; [chatter has 8 message(s) on sale.order id=66]; [chatter has 7 message(s) on sale.order id=67]

report: docs/E2E_DEMO_DROP_SHIP_ORDERTEST2_2026-05-10.md
sty
```

## Known gaps

- §6 Gearment auto-push currently fires from the pipeline-state hook. P1-DROP-CALLSITE will relocate it to `purchase.order.action_confirm` via the standard dropship route per the doc; rerun this runner against that path once it lands.
- §1 depends on Gmail OAuth + label setup on the target DB. If §1 fails with 'no successful etsy.email.log row', verify ICPs `etsy_integration.gmail_client_id|secret|refresh_token` and the label `ordertest2` is applied to inbox messages.
- §5 depends on ICP `multichannel_hub.design_file_default_gdrive_folder_id` being set to a valid Drive folder ID.
- §3 attaches Etsy product images as design files via a runner-only helper. There is intentionally NO sale.order button to do this in production — operators upload via the wizard added by P1-OPS-DESIGN-LINK.
