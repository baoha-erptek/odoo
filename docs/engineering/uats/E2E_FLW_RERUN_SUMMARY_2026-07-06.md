# FLW-01..07 E2E Rerun — Summary (2026-07-06)

Full main-flow gate rerun on staging `esty_odoo19` (129.150.63.207 /
https://odoo.hatafax.com) after the FLW-01..07 product-flow fixes
(merge `69a0d9c8f86`). Plan: `~/.claude/plans/check-for-master-plan-robust-curry.md`.
DB backup taken + gzip-verified before any run
(`~/backups/esty_odoo19_pre_flw_e2e_20260706.sql.gz` on staging).

## Gate results (each ×2 PASS)

| Gate | Driver | Result | FLW deltas asserted |
|---|---|---|---|
| Flow-1 publish | `scripts/e2e_flow1_publish.py` | 12/12 ×2 | FLW-02 §3b SKU write-back (`MUG-15OZ` synthesized → persisted + `etsy.listing.product` linked); FLW-07 §T cron no-op (ICP unset, inventory api-log rows unchanged) |
| Flow-2 orders | `scripts/e2e_flow2_orders.py` | 8/8 ×2 | FLW-03 §G unresolved-SKU hold: placeholder line, `production_blocked` + reason names SKU, NO auto-created product |
| Flow-3a fulfillment | `scripts/e2e_flow3a_fulfillment.py` | 10/10 ×2 | FLW-06 §5: outgoing-DO validation auto-advanced `vn_internal_production` → `shipped` (Đã Gửi) |
| Flow-3b dropship | `scripts/e2e_flow3b_dropship.py` | 10/10 ×2 | FLW-05 §W: `gift_message_body` on draft wire, NO `personalisation` key; FLW-01 §V: block UserError w/o variant codes + mapped push carries distinct `GM0249020374`/`GM0249020373`; FLW-04: WARNING logged, `METHOD_STANDARD` kept |
| Flow-4 after-sales | `scripts/e2e_flow4_aftersales.py` | 8/8 ×2 | regression (after vi.po defect fix below) |

Playwright UAT suites (`tests/e2e`, staging, workers=1):

| Suite | Result |
|---|---|
| `test:tao-san-pham` (`RUN_ETSY_PUBLISH=1`, price 19.99) | 11 passed ×2 (4 skipped by design — parity with 2026-07-04 gate) |
| `test:don-hang-etsy` | 7 passed ×2 (2 skipped by design) |
| `test:giao-hang` | 8 passed ×2 (7 skipped by design) |
| `test:hau-mai` | **N/A — spec file never existed.** `package.json` carries a scaffold-only script (ESTY-186); after-sales UI coverage is the flow-4 runner (§6 UI evidence) which passed ×2. Follow-up owner decision: author `uat_huong_dan_hau_mai.spec.ts` or drop the npm script. |

Per-flow section detail: `E2E_FLOW{1,2,3A,3B,4}_*_2026-07-06.md` in this directory.

## Defects found → fixed → gate re-run (MP006 loop)

1. **vi.po placeholders split by line wrap (PRODUCT defect, HIGH).**
   Flow-4 §2 crashed: `ValueError: unsupported format character` on
   address-change approve for every vi_VN user. Two `etsy_integration`
   vi.po msgstr entries wrapped INSIDE a named placeholder
   (`%(fields)\ns.`, `%(erro\nrs)s`). Fixed + regression test
   `test_i18n_po_placeholders` (RED verified) scanning all 3 addons'
   vi.po; ei bumped 19.0.3.22.1, deployed to staging, container
   restarted (code translations are file-cached). Commit `dfc4780d3f3`.
2. **flow3b §W/§V payload parse (runner defect).** `request_payload_summary`
   wraps the body in `{"data": ...}`; assertions parsed the wrapper.
   Wire payloads verified correct in the log rows. Commit within
   `feature/flw-e2e-rerun`.
3. **Playwright vi_VN locale drift (test-side, whole class).** The
   2026-07-05 i18n import translated attribute values ("Gốm + Chrome"),
   notebook tabs ("Tùy chọn danh sách", "Dòng xem trước"), and
   error-dialog titles ("Lỗi xác nhận") that the vi_VN personas see.
   The en-keyed page objects quick-created a DUPLICATE attribute value
   without `x_code` (broke SKU derive) and timed out on tabs/modals.
   Fixed in page objects: session-lang name resolution, no-quick-create
   guard, notice-dialog dismissal, vi title/label alternates. Staging
   residue values 64/95/96 unlinked. Commits `54ed9441d9d`, `431cb7294aa`.

## Owner actions

- **Gearment dashboard — discard 6 DRAFT orders** (never confirmed/labeled,
  no charge): `260706P-GM3MUJU-4UJ9LWCV` (S03409), `260706P-GM3MUJU-4UNJ2N1K`
  (S03410), `260706P-GM3MUJU-4VCTWB9V` (S03411), `260706P-GM3MUJU-4VH6XGC2`
  (S03412), `260706P-GM3MUJU-4VSXP3T8` (S03413), `260706P-GM3MUJU-4VX0BER4`
  (S03414).
- **Etsy Shop Manager** — flow-1 listings `4533253493`, `4533267304` were
  deactivated by §9 (PATCH state=inactive → shows `edit`); true DELETE still
  needs the ungranted `listings_d` scope. Playwright live-publish drafts are
  cleaned by `scripts/cleanup_uat_etsy_drafts.py` (cleanup phase).
- `test:hau-mai` decision (see table above).

## Test-data ref list (written BEFORE cleanup — audit anchor)

Sale orders created by this run (ids 3389–3400): S03406 (FLW-03 held —
kept for screenshot, then cleaned), S03407/S03408 (flow-3a, `sale`),
S03409–S03414 (flow-3b, cancelled by §7), S03415 (flow-4 run-1, `sale`),
S03416/S03417 (flow-4, cancelled). Chained: MOs WH/MO/00021–00027,
pickings WH/OUT/00095–00101 (00100/00101 = ESTY-249 suite orphans,
orders already unlinked by suite teardown), POs P00018–P00023 (draft,
from cancelled flow-3b orders), tickets RT00005/RT00006 (refunded),
design.file 125–135, address-change requests 24–28, products
`E2E-F1*`/`E2E-F3*`/`E2E-F3B*`/`E2E-F4*`/`UAT-TAOSP*`/`ESTY-249*`
(688 kept unarchived only for the supplierinfo screenshot), partners
`E2E-*`/`UAT-*` buyers. Email-fixture orders S03401/02/04/05 and the
run-1 held order S03403 were already removed by runner hygiene (§F/§G).

## Environment notes

- Module versions after rerun: `etsy_integration 19.0.3.22.1`,
  `multichannel_hub_fulfillment 19.0.1.0.34`, `multichannel_hub_core
  19.0.1.0.78`.
- ICPs `etsy_integration.pod_topup_quantity` and
  `gearment_confirm_enabled` were NOT set (owner decisions) — FLW-07
  verified as no-op only.
