# E2E Testing Guide — Multichannel Hub on Odoo 19

**Target environment:** `https://odoo.hatafax.com` (staging on `129.150.63.207`)
**Database:** `namco_odoo19_staging` (nightly restore from Odoo 15 prod)
**Owner:** project lead
**Tester role:** real BA / production team operator (no developer hand-holding)
**Branch under test:** `feature/006-master-plan-coding`

This guide covers every customer-facing feature shipped under Master Plan
006. Each section gives a precise click path, the data the system must
write, and a pass/fail check the tester can answer in seconds.

---

## 0. Pre-flight (10 min)

Run these once before starting the suite. Fail any of them → stop and ping
the dev team.

| Check | How | Expected |
|---|---|---|
| Site loads | `https://odoo.hatafax.com` | Odoo login page |
| HTTPS valid | Browser address bar | green padlock, no warnings |
| Login | username + password | lands on apps page |
| DB name banner | top-right user menu | shows `namco_odoo19_staging` |
| Module list | Apps → search "multichannel" | both `multichannel_hub_core` + `multichannel_hub_fulfillment` show **Installed** |
| Apps `etsy_integration` | Apps → search "etsy" | shows **Installed** |
| Operations menu visible | top bar | **Operations** menu item present |
| Etsy menu visible | top bar | **Etsy** menu item present |
| Test users exist | Settings → Users | `ba_shipping@test.local`, `ba_manager@test.local`, `prod_team@test.local`, `salesman@test.local` all active |

If any check fails, capture screenshot + log line, then escalate.

---

## 1. Master data (15 min)

### 1.1 Pipelines (route definitions)

**Goal:** confirm the 3 fulfillment pipelines + their stages are seeded
and visible.

**Path:** Operations → **Fulfillment Pipelines**

**Expected list:**

| Code | Name | Channel hint | Stages |
|---|---|---|---|
| `vn_internal_production` | Internal Production (VN) | Internal Production | 5 (Chờ File → Đang Sản Xuất → Đã Đóng Gói → Đã Gửi → Hoàn Thành) |
| `gearment_pod` | Gearment POD | Gearment Drop-Ship | 4 (Draft → Quoted → Confirmed → Shipped) |
| `multi_technique_hybrid` | Multi-Technique Hybrid | Multi-Technique Hybrid | 3 (Setup → Production → Done) |

**Click path tests:**

1. Open `vn_internal_production` form → **Stages** tab → verify 5 rows
   with one row marked **Initial = ✓** (Chờ File) and one row marked
   **Terminal = ✓** (Hoàn Thành).
2. Try to delete `vn_internal_production` from the list — Odoo must
   refuse (`is_in_use=True` because seeded sale orders reference it).
3. Operations → **Pipeline Teams** — verify 3 teams: Internal Production
   Team, Drop-Ship Liaison, QA & Release.
4. Operations → **Pipeline Transitions** — read-only audit log. Should
   contain 1 row per existing sale order with `change_type='initial'`.

**Pass:** all 3 checks succeed. **Fail:** any pipeline missing, or
delete succeeds, or transition log is empty.

### 1.2 Shipping carriers

**Path:** Settings → Technical → **Shipping Carriers** (or Operations menu
if listed)

**Expected rows (8 total):**

`usps`, `uniuni`, `yunexpress`, `4px`, `dhl_ecommerce`, `fedex_smartpost`,
`gke_local`, `other` (sequence=999, fallback).

Verify the first three have `tracking_prefix_regex` populated; `other`
has none.

### 1.3 Product → Pipeline routing

**Path:** Sales → Products → pick any storable product → form view

**Setup:** for **one** test product, set `Default Pipeline` → `gearment_pod`.

**Verify:** Sales → Quotations → create a new sale order with that
product → on the order, **Fulfillment Pipeline** field auto-resolves to
`gearment_pod`. (If you change the product to one without an override,
order falls back to the category default → ICP default → first-active.)

**Pass:** `x_pipeline_id` reflects the chosen route within 1s of saving.

---

## 2. Etsy ingest — email path (legacy fallback)

**Path:** Etsy → Email Log

**Setup:** the Gmail polling cron is **disabled** on staging (per restore
script). Trigger a manual ingest:

1. Open Etsy → **Email Log** → top-right action menu → **Reprocess
   Recent (7 days)** OR import via Excel wizard (see §2.1 below).

### 2.1 Excel ingest (import historical orders)

**Path:** Etsy → **Import Orders**

**Sample file:** ask the dev team for `tests/data/sample_50_orders.xlsx`
(50 rows, 12 carriers).

1. Upload the file.
2. Click **Preview** — wizard shows row counts: matched, unmatched,
   conflicts.
3. Click **Import** — wait until state goes to `done`.
4. Check Etsy → Orders → 50 new draft sale orders should appear with
   `sales_channel='etsy'`.

**Pass:** all 50 orders land; sale_order rows have `partner_id`,
`order_line` populated, `x_pipeline_id` resolved per product config,
`x_pipeline_state_id` set to the pipeline's initial state.

### 2.2 Etsy API ingest (sandbox)

If E1 (Etsy app scope review) is approved:

**Path:** Etsy → **Shops** → pick a shop → action **Sync via API
(sandbox)**.

Otherwise: skip this section, ingest stays on email path.

---

## 3. Order Dashboard (operator entry point)

**Path:** Operations → **Order Dashboard**

**Expected columns:** Channel, Order Ref, Customer, Qty, Pipeline,
Pipeline State, Duplicate Buyer, Overdue Approval, Stuck-Route Badge,
Date.

**Filters to verify:**

- **Sales Channel = Etsy** → only Etsy-sourced orders.
- **Duplicate Buyer = Yes** → orders where the same partner placed
  another non-cancel order in trailing 7 days.
- **Pipeline = Gearment POD** → only `gearment_pod`-routed orders.

**Decoration tests:**

- Row with `qty_total ≥ 2` → bold/colored.
- Row with `is_duplicate_buyer=True` → red badge.
- Row with `stuck_route_badge=True` → orange badge (any
  design.file.route in `pending`/`failed` state for ≥2h).

**Pass:** decorations render correctly + filters work.

---

## 4. Design Files

### 4.1 Upload (production team)

**Login:** `prod_team@test.local`

**Path:** open any draft sale order → **Design Files** tab → action
**Upload Design**

1. Click **Upload Design**.
2. Pick a small PNG/JPG (<10 MB). Wizard shows preview thumbnail.
3. Submit → file is uploaded to GDrive (background) AND a thumbnail is
   stored in the Odoo filestore. Form refreshes — design.file row shows
   `state='approved'`, `gdrive_url` populated, `preview_url` set.

**Pass:** thumbnail visible inline; clicking the GDrive URL opens the
real file in a new tab.

### 4.2 File over the cap

Try uploading a 50 MB file → wizard shows **ValidationError** ("File
exceeds 10 MB cap"). No row is created.

### 4.3 Routing on order confirm

**Login:** `salesman@test.local`

1. Open a draft sale order with at least one approved design file.
2. Click **Confirm**.
3. Refresh — order's chatter shows "Design routing in progress".
4. Process Dashboard → the relevant route row should appear in
   `pending` or `routed` state.

**Pass:** route row is created within 5s of confirm; chatter alert
posted; design file's `route_ids` list grows by 1.

---

## 5. Tracking Import wizard (P2-01) — key new feature

### 5.1 Approve a new schema (BA Manager)

**Login:** `ba_manager@test.local`

**Path:** Operations → Tracking Import → **Import GKE Excel**

1. Upload a GKE Excel file with the **standard header row**
   (`ORDER NUMBER`, `TRACKING`, `CARRIER`, `DATE`, `WEIGHT`, `NOTES`).
2. Click **Preview**. Wizard shows:
   - Schema hash (64-char SHA-256).
   - **New Schema = ✓** (first time on this layout).
   - Header diff panel showing the 6 column names.
   - Lines table with raw values + match status.
3. Click **Approve Schema**. The hash is appended to the ICP whitelist.
4. Click **Import**. Lines transition `matched → imported`. Log row
   transitions `pending → processing → ok` (or `warning` if any
   `unmatched`/`conflict`).

**Pass:** matched orders' `sale.order.fulfillment` rows now have
`tracking_number` + `shipping_date` populated; **DO NOT** overwrite
already-set `shipping_carrier_id` (Spec 004a US2 AC).

### 5.2 BA Shipping cannot approve schemas

**Login:** `ba_shipping@test.local`

1. Re-upload a different file with shuffled headers.
2. Click **Preview** → New Schema = ✓.
3. The **Approve Schema** button must be **invisible**.
4. Try **Import** anyway → wizard raises ValidationError ("Schema
   fingerprint not approved").

**Pass:** RPC bypass blocked at both the action-method gate AND the view
button visibility.

### 5.3 Carrier auto-detection (P2-02)

After Preview in §5.1, inspect the **Lines** tab on the import log:

- USPS-format tracking (22 digits starting with `9`) → `Detected
  Carrier = USPS`, `Needs Review = ✗`.
- UniUni `UUS...` → `UniUni`, no review.
- YunExpress `YT...` → `YunExpress`, no review.
- Anything else (e.g., a 4PX code) → `Detected Carrier = Other`,
  `Needs Review = ✓`.

### 5.4 Bulk re-detect

1. Select all rows on the Lines tab where `Needs Review = ✓`.
2. Action menu → **Re-detect Carriers**.
3. Rows refresh; if you've added a new regex to a carrier in master data
   between imports, those rows now match the new carrier. Order's
   existing `shipping_carrier_id` is **not** changed (advisory only).

**Pass:** non-BA-shipping user calling the action gets AccessError.

### 5.5 Idempotency

Re-upload the same Excel file → Preview shows the same row count;
**Import** writes 0 new fulfillment rows (all rows skip on
`(log_id, source_row_hash)` UNIQUE).

### 5.6 File-size cap

Upload a >10 MB Excel → ValidationError before parsing.

---

## 6. Tracking Dashboard

**Path:** Operations → **Tracking Dashboard**

After §5 imports complete, verify:

- Newly imported orders show with `tracking_state='shipped'`.
- Bulk-action **Mark Shipped** works on selected rows.
- An order whose partner has `has_pending_address_change=True` is
  **excluded** from Mark Shipped (FR-017 silent-skip + sticky warning).
- Search by tracking number works (case-insensitive).

---

## 7. Process Dashboard

**Path:** Operations → **Process Dashboard**

For each order, the row shows: order ref, partner, qty, design files,
stuck-route badge, current pipeline stage, owning team. Filter by team
to see what each PD owner has on their plate.

---

## 8. Pipeline state machine (P1-PIPELINE-FULL)

### 8.1 Direct-write defense (FR-017)

This is a developer test, but the BA can verify via UI:

1. Open any sale order in Developer Mode.
2. Use the action menu → **Update Field** → set `x_pipeline_state_id`
   to a different state of the same pipeline.
3. **Expected:** ValidationError — "Direct writes to 'Pipeline State'
   are not allowed. Use sale.order._write_pipeline_state(...)".

### 8.2 Cross-pipeline rejection

Open a sale order on `vn_internal_production`. From a developer console
(`Settings → Technical → Console`), run:

```python
order = env['sale.order'].browse(<id>)
gearment_state = env.ref('multichannel_hub_core.state_gearment_draft')
order._write_pipeline_state(gearment_state)
```

**Expected:** ValidationError — "State 'Draft' belongs to pipeline
'Gearment POD', not the order's pipeline 'Internal Production (VN)'".

### 8.3 Audit log

Operations → **Pipeline Transitions** → recent transitions show 1 row
per state change with `from_state_id`, `to_state_id`, `change_type`,
`user_id`, `timestamp`. Filter by `sale_order_id` to get a single
order's full state history.

---

## 9. Gearment outbound (manual probe — adapter only)

Adapter is wired but **state-machine integration to P4-01 is pending**.
Smoke test:

1. Settings → Technical → Models → `gearment.api.log` → action **Test
   Connection** (or run from console).
2. Verify a row appears in `gearment.api.log` with non-empty `latency_ms`,
   PII-scrubbed `request_payload`, and a recognizable response code.

**Skip** push-an-actual-order until P4-01 lands.

---

## 10. Webhook (P0-18b2 — partial)

**Status:** webhook controller code is **not yet deployed**. This
section will become live once owner registers the webhook in the
Gearment dashboard and the dev team lands the controller.

When live:

1. Trigger a Gearment status change in their dashboard.
2. Watch `tail -f /var/log/odoo19/odoo.log | grep gearment` on staging.
3. Expect a `POST /gearment/webhook` log line + a new
   `gearment.api.log` row with `direction='inbound'`.

---

## 11. Pass / fail summary template

Copy/paste into the test-run notes:

```
RUN  : ____________________ (timestamp + tester name)
BUILD: feature/006-master-plan-coding @ <commit hash>

§0 pre-flight       : PASS / FAIL
§1 master data      : PASS / FAIL (notes:                                   )
§2 etsy ingest      : PASS / FAIL
§3 order dashboard  : PASS / FAIL
§4 design files     : PASS / FAIL
§5 tracking import  : PASS / FAIL
§6 tracking dashb.  : PASS / FAIL
§7 process dashb.   : PASS / FAIL
§8 pipeline FSM     : PASS / FAIL
§9 gearment probe   : PASS / FAIL / SKIP
§10 webhook         : SKIP (P0-18b2 not deployed)

Critical bugs found : ____
Cosmetic issues     : ____
Sign-off            : Y / N
```

---

## 12. Known limitations / not-yet-shipped

- **P0-18b2 webhook controller** — owner must register endpoint in
  Gearment dashboard first; controller code lands after first inbound
  POST is inspected.
- **P2-03 Process Dashboard stock-move hook** — not yet shipped; PD
  remains read-only for inventory.
- **P2-04 import-log replay UI** — not yet shipped; failures are
  visible in log but cannot yet be re-driven from a button.
- **P2-06 GDrive polling cron** — not yet shipped; logistics partners
  must drop the GKE Excel manually via the wizard.
- **P4-01 Gearment outbound full state machine** — not yet shipped;
  adapter is a stub that logs but does not transition orders.
- **Etsy production OAuth (P1-10..13)** — waiting on Etsy app scope
  review (E1 dependency); ingest stays on email path until approved.

---

## 13. Reporting bugs

For each defect, capture:

1. URL bar (full path) at the moment of the failure.
2. Tester user (login).
3. Expected vs actual (from this guide's pass criteria).
4. Browser-console error if any.
5. Server log slice: `docker logs --since 30s namco_odoo19 | tail -100`
   on the staging host.

Post in Telegram with the `#e2e-staging` tag (or whatever the team
agreed). Bugs blocking sign-off → tag `BLOCKER`. Cosmetic → tag `NIT`.
