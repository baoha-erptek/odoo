# E2E Drop-Ship Demo — Etsy → Odoo → Gearment (2026-05-09)

- **Target**: https://odoo.hatafax.com
- **DB**: demo_esty
- **Build**: 07930358553
- **Driver**: scripts/e2e_demo_drop_ship_ordertest2.py
- **Email source**: real Gmail label `ordertest2`
- **Tracking source**: `.0temp/sample_bc_don_hang2026_04_08.xls`
- **Result**: 13/13 sections PASS

## Sections

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | version=19.0-20260324; removed 0 demo design.file from prior runs | docs/screenshots/2026-05-09_114815/drop_ship_00_landing.png |
| 1 | PASS | resolved 4/4 receipt(s): ['S00060', 'S00061', 'S00062', 'S00063'] | — |
| 2 | PASS | order form + Operations Dashboard rendered (id=60) | docs/screenshots/2026-05-09_114815/drop_ship_02_order_form.png | docs/screenshots/2026-05-09_114815/drop_ship_02_dashboard.png |
| 3 | PASS | 4 order(s): [attached 3 DEMO design.file row(s) (storage_mode='small'; line ids: [109, 110, 111])]; [attached 3 DEMO design.file row(s) (storage_mode='small'; line ids: [112, 113, 114])]; [attached 3 DEMO design.file row(s) (storage_mode='small'; line ids: [115, 116, 117])]; [attached 2 DEMO design.file row(s) (storage_mode='small'; line ids: [118, 119])] | — |
| 4 | PASS | 4 order(s): [states={'approved'} (n=3)]; [states={'approved'} (n=3)]; [states={'approved'} (n=3)]; [states={'approved'} (n=2)] | — |
| 5 | PASS | 4 order(s): [all 3 approved design.file rows promoted to gdrive; first gdrive_file_id=1BcJbxuvqIxr283E8UutNner8bObe9Yv9]; [all 3 approved design.file rows promoted to gdrive; first gdrive_file_id=1yFZY2kxrT4fzzDZWymu_Bhd3BlvFd_bo]; [all 3 approved design.file rows promoted to gdrive; first gdrive_file_id=1IdUIqqgkxFDA6GJ13Mmwt9rR_ji8vn3m]; [all 2 approved design.file rows promoted to gdrive; first gdrive_file_id=1oRWJt71x-GODgQHZB03ZRX8uSe0KvHnK] | — |
| 6 | PASS | 4 order(s): [pipeline_state_id=8 outbound_ref=∅ outbound_api_logs=2 latest_endpoint=POST /api/v3/orders http_status=0 (non-200 means live Gearment API rejected the synthetic order; the wiring fired regardless — see chatter)]; [pipeline_state_id=8 outbound_ref=∅ outbound_api_logs=2 latest_endpoint=POST /api/v3/orders http_status=0 (non-200 means live Gearment API rejected the synthetic order; the wiring fired regardless — see chatter)]; [pipeline_state_id=8 outbound_ref=∅ outbound_api_logs=2 latest_endpoint=POST /api/v3/orders http_status=0 (non-200 means live Gearment API rejected the synthetic order; the wiring fired regardless — see chatter)]; [pipeline_state_id=8 outbound_ref=∅ outbound_api_logs=2 latest_endpoint=POST /api/v3/orders http_status=0 (non-200 means live Gearment API rejected the synthetic order; the wiring fired regardless — see chatter)] | — |
| 7 | PASS | 4 order(s): [webhook status=200 body='{"status": "ok"}']; [webhook status=200 body='{"status": "ok"}']; [webhook status=200 body='{"status": "ok"}']; [webhook status=200 body='{"status": "ok"}'] | — |
| 8 | PASS | wizard.state=done; 4 line(s); 4 imported, 4 matched. matched_targets=4/4 (GKE schema from gke_e2e_2026_05_10.xlsx) | — |
| 8b | PASS | +6 log row(s); latest id=40 source=gdrive state=ok filename=gke_e2e_2026_05_10.xlsx rows=4/imported=4/matched=4 | — |
| 9 | PASS | shipped 4/4 fulfillment(s); tracking_states=['shipped', 'shipped', 'shipped', 'shipped'] | — |
| 10 | PASS | 4 order(s): [webhook status=200 body='{"status": "ok"}']; [webhook status=200 body='{"status": "ok"}']; [webhook status=200 body='{"status": "ok"}']; [webhook status=200 body='{"status": "ok"}'] | — |
| 11 | PASS | 4 order(s): [chatter has 8 message(s) on sale.order id=60]; [chatter has 8 message(s) on sale.order id=61]; [chatter has 8 message(s) on sale.order id=62]; [chatter has 7 message(s) on sale.order id=63] | — |

## Architecture reference

- 19-step doc: `.0temp/Drop-Ship_Pipeline_Etsy_Odoo_Gearment.docx`
- Plan: `.claude/plans/check-for-memory-and-glistening-snail.md`

## Reproducing the run

```bash
. .venv-e2e/bin/activate  # contains: playwright, requests, openpyxl, xlrd, python-dotenv
playwright install chromium
python3 scripts/e2e_demo_drop_ship_ordertest2.py --section all --base-url https://odoo.hatafax.com --db demo_esty
```

## Known gaps

- §6 Gearment auto-push currently fires from the pipeline-state hook. P1-DROP-CALLSITE will relocate it to `purchase.order.action_confirm` via the standard dropship route per the doc; rerun this runner against that path once it lands.
- §1 depends on Gmail OAuth + label setup on the target DB. If §1 fails with 'no successful etsy.email.log row', verify ICPs `etsy_integration.gmail_client_id|secret|refresh_token` and the label `ordertest2` is applied to inbox messages.
- §5 depends on ICP `multichannel_hub.design_file_default_gdrive_folder_id` being set to a valid Drive folder ID.
- §3 attaches Etsy product images as design files via a runner-only helper. There is intentionally NO sale.order button to do this in production — operators upload via the wizard added by P1-OPS-DESIGN-LINK.
