# E2E Drop-Ship Demo — Etsy → Odoo → Gearment (2026-07-05)

- **Target**: https://odoo.hatafax.com
- **DB**: esty_odoo19
- **Build**: bc7758cc172
- **Driver**: scripts/e2e_demo_drop_ship_ordertest2.py
- **Email source**: real Gmail label `ordertest2`
- **Tracking source**: `.0temp/sample_bc_don_hang2026_04_08.xls`
- **Result**: 11/12 sections PASS

## Sections

| § | Result | Note | Screenshot |
|---|---|---|---|
| 0 | PASS | version=19.0-20260609; removed 3 demo design.file from prior runs | docs/screenshots/2026-07-05/drop_ship_00_landing.png |
| 1 | PASS | FALLBACK to existing demo order S03344 (Gmail OAuth not provisioned — no fresh email logs in last 2h). partner=Kiersten Ruedy | — |
| 2 | PASS | order form + Operations Dashboard rendered (id=3327) | docs/screenshots/2026-07-05/drop_ship_02_order_form.png | docs/screenshots/2026-07-05/drop_ship_02_dashboard.png |
| 3 | PASS | 1 order(s): [attached 3 DEMO design.file row(s) (storage_mode='small'; line ids: [3394, 3395, 3396])] | — |
| 4 | PASS | 1 order(s): [states={'approved'} (n=3)] | — |
| 5 | PASS | 1 order(s): [all 3 approved design.file rows promoted to gdrive; first gdrive_file_id=1pbavmcAgKW4F_7VcN1TfMIH4SDm_rj1D] | — |
| 6 | PASS | 1 order(s): [pipeline_state_id=8 outbound_ref=260705P-GM3MUJU-YN2J6PPP outbound_state=quoted quote_total=31.0 USD outbound_api_logs=3 latest_http=200] | — |
| 7 | PASS | 1 order(s): [webhook status=200 body='{"status": "ok"}'] | — |
| 8 | FAIL | sample file missing: /home/odoo/odoo_dev/other_projects/odoo19_esty/.0temp/sample_bc_don_hang2026_04_08.xls | — |
| 9 | PASS | shipped 1/1 fulfillment(s); tracking_states=['shipped'] | — |
| 10 | PASS | 1 order(s): [webhook status=200 body='{"status": "ok"}'] | — |
| 11 | PASS | 1 order(s): [chatter has 18 message(s) on sale.order id=3327] | — |

## Architecture reference

- 19-step doc: `.0temp/Drop-Ship_Pipeline_Etsy_Odoo_Gearment.docx`
- Plan: `.claude/plans/check-for-memory-and-glistening-snail.md`

## Reproducing the run

```bash
. .venv-e2e/bin/activate  # contains: playwright, requests, openpyxl, xlrd, python-dotenv
playwright install chromium
python3 scripts/e2e_demo_drop_ship_ordertest2.py --section all --base-url https://odoo.hatafax.com --db esty_odoo19
```

## Known gaps

- §6 Gearment auto-push currently fires from the pipeline-state hook. P1-DROP-CALLSITE will relocate it to `purchase.order.action_confirm` via the standard dropship route per the doc; rerun this runner against that path once it lands.
- §1 depends on Gmail OAuth + label setup on the target DB. If §1 fails with 'no successful etsy.email.log row', verify ICPs `etsy_integration.gmail_client_id|secret|refresh_token` and the label `ordertest2` is applied to inbox messages.
- §5 depends on ICP `multichannel_hub.design_file_default_gdrive_folder_id` being set to a valid Drive folder ID.
- §3 attaches Etsy product images as design files via a runner-only helper. There is intentionally NO sale.order button to do this in production — operators upload via the wizard added by P1-OPS-DESIGN-LINK.
