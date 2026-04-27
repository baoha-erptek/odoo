# Quickstart: Three Operational Dashboards, Design & Address-Change Workflows, Multi-Channel Foundation

**Phase**: 1 (verification walkthrough — fresh module install on staging)
**Module**: `multichannel_hub_core` (per ADR-003 Phase 1)
**Date**: 2026-04-27 (Stage 4.1 refresh)

---

## Prerequisites

- Odoo 19 CE running on staging (`129.150.63.207:8169`) with `namco_odoo19` DB restored from a recent prod snapshot (Spec 002 run completed: 17,659 orders normalized, `sales_channel` backfill yet to run on the staging DB).
- `multichannel_hub_core` installed; `etsy_integration` (existing module) upgraded to declare the new dependency.
- Test users created and assigned to groups: `ba_user_test` (BA group), `ba_lead_test` (BA-lead group), `mp_user_test` (Marketing group), `pd_user_test` (production-team group), `admin_test` (system).
- Test data: 1 sale order in each pipeline state (17 orders matching the seed); 1 order with a pending design file; 1 order with a pending address-change request.

---

## 1. Module install + seed data verification

```bash
docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init
```

**Expected**:
- No install errors.
- Server log shows: `multichannel_hub_core: 9 new models loaded` (`shipping.carrier`, `etsy.address.change.request`, `design.file`, `design.file.route`, `design.print.batch`, `order.pipeline`, `order.pipeline.state`, `pipeline.team`, `order.pipeline.transition.log`).
- `data/order_pipeline_seed.xml` loaded: 3 pipelines (`vn_internal_production` v1, `gearment_pod` v1, `multi_technique_hybrid` v1) with the 17 / 4 / 3 stages respectively.
- `data/shipping_carrier_seed.xml` loaded: 7 carriers.
- `data/ir_config_parameter.xml` loaded: `multichannel_hub.large_file_threshold_bytes = 10485760`.

**DB verification (Phase 1 testing)**:
```sql
SELECT code, version, transition_policy FROM order_pipeline ORDER BY code;
SELECT pipeline_id, code, sequence, is_initial, is_terminal FROM order_pipeline_state WHERE pipeline_id = (SELECT id FROM order_pipeline WHERE code='vn_internal_production' AND version=1) ORDER BY sequence;
SELECT code, name, etsy_carrier_name, gearment_carrier_name FROM shipping_carrier ORDER BY code;
```

---

## 2. US1 — Order Dashboard for BA daily triage

1. Log in as `ba_user_test`. Open menu → **Operations → Order Dashboard**.
2. Verify the list shows ≥ 17,000 rows; first page renders within 3 seconds (browser DevTools Network tab → request duration < 3000ms).
3. Verify the columns: shop, channel, order date, buyer, country, amount, discount flag, PIC, priority, MP note, design-status summary, overdue-approval marker, tracking state, product image (`image_128`).
4. Filter: `qty>=2`. Verify rows show the `decoration-info` (orange) row decoration.
5. Filter: a buyer who has placed 2+ orders in the last 7 days. Verify "duplicate buyer" decoration on both rows.
6. Find a `Push` order (or set one: `order_priority='push'`). Verify `decoration-danger` and the store-manager avatar icon.
7. Inline-edit MP note on row #1. Click away. Reload. Verify the new value persists.
8. Inline-edit PIC and priority. Open the order's chatter. Verify `mail.tracking.value` rows for both edits with old/new values and editor name.

**Pass/fail**:
- ✅ Render performance ≤ 3s
- ✅ All decorations render correctly
- ✅ Inline-edit persists
- ✅ Audit trail visible

---

## 3. US2 — Tracking Dashboard for shipping ops

1. Log in as `ba_user_test`. Open **Operations → Tracking Dashboard**.
2. Verify columns: buyer, shop, channel, tracking number, carrier, shipping date, label status, tracking state, has-pending-address-change flag, overdue-approval marker.
3. Search by tracking number (paste a known tracking string). Verify exact-match filter.
4. Select 5 rows (none with pending address change). Click **Bulk → Mark shipped**. Verify all 5 transition to `tracking_state='shipped'` atomically.
5. Select 5 rows where 1 has pending address change. Click **Bulk → Mark shipped**. Verify the 4 unblocked transition; the 1 blocked is skipped with an on-screen warning naming the order ref.
6. Click **Export to Excel**. Verify the downloaded file matches GKE import format (column order: Order ID, tracking, carrier, …).

**Pass/fail**:
- ✅ Tracking lookup is instant on indexed `tracking_number`
- ✅ Bulk action is atomic per row
- ✅ Pending-address-change exclusion fires
- ✅ Export format matches GKE round-trip

---

## 4. US3 — Process Dashboard for Production (VN+US)

1. Log in as `pd_user_test`. Open **Operations → Process Dashboard**.
2. Verify columns: order date, shop, product image, product name, variant attributes, qty, personalisation, PD note, design-status, **pipeline-state column with colour chip**, production-blocked flag, block reason, PIC (PD), priority, row decorations (qty≥2, Push, Amazon), warehouse zone (VN/US).
3. Verify the pipeline-state column's chip colour matches the seed (e.g., `producing_dish` shows lime `#8BC34A`).
4. Filter: `warehouse_zone='vn'`. Verify only VN orders appear.
5. Inline-edit a row's pipeline state from `producing_dish` → `packed`. Verify:
   - The `x_pipeline_state_id` field updates.
   - A new row appears in `order.pipeline.transition.log` with `change_type='order_transition'`, `from_state_id=producing_dish`, `to_state_id=packed`.
   - Chatter shows the transition with user + timestamp.
6. Set Vietnamese as user language. Refresh the dashboard. Verify all stage labels show Vietnamese with diacritics ("Đang sản xuất", not "Dang san xuat").
7. Try inline-editing pipeline state to a non-adjacent stage (e.g., `producing_dish` → `fulfilled` directly): with `transition_policy='dag_with_admin_override'`, the move requires admin confirmation popup.

**Pass/fail**:
- ✅ Pipeline column renders with correct colours
- ✅ Transition writes audit-log row
- ✅ Vietnamese diacritics preserved
- ✅ Transition policy enforced

---

## 5. US4 — Address-Change Approval Workflow

1. Log in as `mp_user_test`. Open a non-shipped order.
2. Try to edit `partner_shipping_id` directly. Verify the form fields are read-only and a banner shows: "Bấm Yêu cầu đổi địa chỉ để cập nhật" (or English equivalent).
3. Click **Request address change**. Fill new address values + reason "Customer moved". Submit.
4. Verify:
   - `etsy.address.change.request` record created with `state='requested'`.
   - `mail.activity` posted to the `group_ba_lead` (visible in Activity inbox).
   - `sale.order.has_pending_address_change == True`.
   - The destination fields on the order form become read-only for everyone (banner persists).
5. Open the Tracking Dashboard. Try to bulk-mark-shipped including this order: verify it's excluded with warning.
6. Try a server-side write on the order with `partner_shipping_id`: verify `UserError` raised with message about pending address change.
7. Log in as `ba_lead_test`. Find the activity. Open the request form. Click **Approve**.
8. Verify:
   - `state='approved'`, `approved_by=ba_lead_test`, `approved_at` set.
   - The order's destination fields now reflect the new values.
   - Chatter on the order shows the field-by-field delta.
   - `has_pending_address_change == False`.
   - Destination fields are editable again (subject to standard ACL).

**Pass/fail**:
- ✅ Request state machine: requested → approved
- ✅ Read-only enforcement at UI + ORM
- ✅ Bulk-action exclusion fires
- ✅ Atomic apply on approve
- ✅ Audit trail complete

---

## 6. US5 — Design Files + 3-State Approval (ADR-009 lifecycle)

1. Log in as `ba_user_test` (designer). Upload a 200 KB preview file as `design.file` with `storage_mode='small'`. Verify creation.
2. Try to upload an 11 MB file: verify `ValidationError` with message about 10 MB cap.
3. Paste a GDrive shareable URL for the production-quality file. Verify:
   - `design.file` record created with `storage_mode='url'`, `file_url=<gdrive>`, `version=1`, `parent_file_id=NULL`, `state='pending'`.
   - A `design.file.route` record is auto-created targeting MP for review (per the order-confirm workflow REQ-AUT-02 / ADR-009 §4 routing).
4. Log in as `pd_user_test`. Open the kanban view. Verify 3 columns: "Chờ duyệt" / "Duyệt" / "Cần chỉnh lại". Drag the file from "Chờ duyệt" to "Cần chỉnh lại". Enter rejection reason. Verify the file's `state='rejected'`, `rejection_reason` set.
5. Log back in as the designer. Re-upload a corrected GDrive URL. Verify:
   - A NEW `design.file` record is created with `parent_file_id=rejected_one.id`, `version=2`, `state='pending'`.
   - The original rejected record is preserved (immutable).
6. Drag the new file to "Duyệt". Verify `state='approved'`, `approved_by`, `approved_at` set.
7. Open the order. Verify `sale.order.line.design_status='approved'` (rolled-up).
8. Run wizard `design.print.batch.create_for_order(orders=order_ids, layout='a4_2x2')`. Verify a `cached_pdf_id` is generated (an `ir.attachment` row with PDF mimetype). Download the PDF — verify A4 layout with 4-up imposition.

**Pass/fail**:
- ✅ Storage-mode enforcement (size guard at both `@api.constrains` and `ir.attachment.create`)
- ✅ Immutable history via `parent_file_id` chain
- ✅ Rolled-up design_status on `sale.order.line`
- ✅ Bulk-print wizard generates PDF
- ✅ PDF cache TTL: re-run > 24h re-generates; ≤ 24h returns cached

---

## 7. US6 — Multi-Channel Foundation

1. Run the post-install migration:
   ```bash
   docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init
   ```
   The hook `multichannel_hub_core/data/migrations/19.0.1.0.0_post.py` should run.
2. Verify all 17,659 historical Etsy orders have `sales_channel='etsy'` and `channel_order_ref=etsy_order_id`:
   ```sql
   SELECT COUNT(*) FROM sale_order WHERE sales_channel IS NULL;     -- expect 0
   SELECT COUNT(*) FROM sale_order WHERE channel_order_ref IS NULL AND sales_channel='etsy';   -- expect 0
   ```
3. Re-run the migration. Verify it's a no-op (idempotency): `UPDATE sale_order SET … WHERE sales_channel IS NULL` affects 0 rows.
4. Manually create a test order with `sales_channel='amazon'`. Open the Order Dashboard. Filter by Channel = Amazon. Verify only the test order shows. Verify the row has `decoration-warning` (Amazon variant).
5. On all 3 dashboards, group-by Channel works.

**Pass/fail**:
- ✅ Backfill complete
- ✅ Backfill idempotent
- ✅ Channel filter + group-by + decoration

---

## 8. US7 — Audit + Vietnamese UI cross-cutting

1. Make tracked-field edits on at least 5 different model rows. Open chatter. Verify `mail.tracking.value` rows present with old/new values + editor name.
2. Switch user language to Vietnamese (`User → Preferences → Language → Tiếng Việt`).
3. Reload the 3 dashboards. Verify EVERY label, button, kanban column title, error message, and selection value is translated to Vietnamese with correct diacritics.
4. Run i18n coverage test:
   ```bash
   docker exec namco_odoo19 python3 -m odoo.tests.loader multichannel_hub_core.tests.test_i18n_coverage
   ```
   Expected: PASS (100% coverage).
5. Round-trip test: import an Excel with "Đĩa tim mới" → save product → export Excel → reopen → verify diacritic preserved (no mojibake).

**Pass/fail**:
- ✅ Every tracked field produces chatter entry
- ✅ Vietnamese coverage at 100%
- ✅ UTF-8 round-trip clean

---

## Cleanup

```bash
# If staging needs reset between runs:
docker exec db psql -U odoo -d namco_odoo19 -c "TRUNCATE order_pipeline_transition_log, design_file_route, design_print_batch RESTART IDENTITY CASCADE;"
# Reseed:
docker exec namco_odoo19 odoo -d namco_odoo19 -u multichannel_hub_core --stop-after-init
```

---

## Cross-references

- spec.md US1–US7 (one quickstart section per User Story; matches the spec.md "Independent Test" sections)
- data-model.md (full model definitions)
- ADR-009 (file lifecycle), ADR-010 (configurable pipeline), ADR-012 (GDrive)
- master-plan staging note (Q10): `129.150.63.207`
