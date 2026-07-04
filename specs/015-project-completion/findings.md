# Spec 015 — Findings Log

## MF-E2E-0 (2026-07-04) — "pure config fix" was actually staging re-provisioning

Expected: set one ICP → 12/12. Reality: the May-era GDrive setup died when
`esty19_odoo` was recreated on 2026-05-21 (secrets mount added). Five separate
fixes were needed:

1. **GDrive creds gone** — vanilla `odoo:19.0` image has no google libs and no
   SA json. Fix: deploy `gdrive-service-account.json` to `/odoo/esty19/secrets/`
   (root:101 640), add `GDRIVE_SERVICE_ACCOUNT_JSON` to `/odoo/esty19/.env`,
   `docker compose up -d`, `pip3 install --break-system-packages
   google-api-python-client google-auth` in the container.
   **Ceiling: pip install is lost on next container recreate** — durable fix is
   a staging Dockerfile layer (candidate item for P0-04).
2. **Folder ID recovered from `demo_esty`** ICP (`1AZRhXHHtN4rLRkT7Bt6hU-CDl7j1fwLT`,
   folder `odoo_esty` on Shared Drive `0ABK9vk_ILselUk9PVA`). Upload probe OK;
   immediate `files().delete` 404s (propagation) — one `mf-e2e-0-probe.txt`
   left in the folder.
3. **Raw-SQL ICP insert is invisible to the running server** — `get_param` is
   ormcached; runner read `''` after direct psql INSERT. Set via XML-RPC
   `set_param` instead. Never raw-SQL `ir_config_parameter` on a live server.
4. **nginx pinned the webhook to the dead demo DB** — `location = /gearment/webhook`
   sent `X-Odoo-Database: demo_esty`; dbfilter `^esty_odoo19$` rejected it →
   404 "no database selected" in 1 ms. Fixed header to `esty_odoo19`.
   Direct-port probe (`curl localhost:8169`) vs nginx probe isolated it fast.
5. **`networkidle` never fires on staging** — `workers=0` means no websocket
   worker (nginx upstream 8172 dead); browser retries keep the network busy
   forever. Replaced all runner `wait_for_load_state("networkidle")` with
   DOM + selector waits (`_settle()`). Run-1 §0 "passed" only because the
   manager login silently failed and screenshotted the login page — seeded
   `demo_*@hatafax.demo` users (users-only subset of seed-demo-esty.py) and
   the failure became visible before the fix.

Result: 12/12 PASS (`docs/engineering/uats/E2E_DEMO_DROP_SHIP_ORDERTEST2_2026-07-04.md`).
§8 note: 0/9 tracking rows matched (sample GKE file's order refs don't exist on
esty_odoo19 — wizard completes, schema validated; matching assertions belong to
MF-E2E-3a with fixture orders).

## 2026-07-04 — MF-E2E-1 flow-1 publish gate (runner 10/10 ×2, Playwright ×2)

Runner `scripts/e2e_flow1_publish.py` (new, mirrors drop-ship shape). Two REAL
product bugs surfaced by first live exercise of the activation path, both fixed
in etsy_integration **19.0.3.16.0**:

1. **`publisher.publish()` PATCHed the wrong path** — bare `listings/{id}`;
   Etsy `updateListing` only exists shop-scoped
   (`shops/{shop_id}/listings/{listing_id}`, form-urlencoded). Same defect
   family as the upload_images 404 fixed in 19.0.2.27.0. Never caught before
   because 2026-05-28 UATs were draft-only — `publish()` had zero live runs.
   Unit test now pins the shop-scoped path (test_phase2_pub_publish_orm).
2. **Per-variant `default_code` silently ignored in `push_inventory`** when a
   variant-creating axis is NOT published as an Etsy property (Material —
   materials[]-only). `combo_value_ids` carried only publishable-axis values,
   so `_variant_for_combo`'s `vids.issubset(combo)` never matched → Etsy got
   synthesized `MUG-11OZ` instead of `MUG-CR-F11`. Fix: include single-value
   non-publishable variant-creating axes in combo_ids. RED test:
   `test_variant_default_code_wins_with_nonpublishable_material_axis`.

Environment/test findings:

3. **`list_price` is COMPANY currency (USD)** — publisher converts to shop
   VND (@25400). The folkloric "E2E_LISTING_PRICE>=250000" is wrong post
   listing_currency wiring: 350000 USD → ₫8.9B → Etsy 400 `price_too_high`
   (max ₫1,257,533,727). Use ~19.99. Etsy error body names the bound.
4. **Etsy title validator rejects test-y names** — 400 `all_caps` when >3
   hyphen/space tokens start with 2 sequential capitals (`UAT-TAOSP` +
   `TC015-MUG-DISPC` = 5). uniq() suffixes now lowercase. Flaky by timestamp
   shape until fixed.
5. **`channelStatus()` in the UAT spec resolved the WRONG product** —
   attribute-less Mug TCs (TC-002/TC-007) share auto-SKU `MUG`; unordered
   `search(default_code=…)[0]` returned an older sibling with empty
   external_ref. Fixed with `order: 'id desc', limit 1`. This is why publish
   TCs failed only in full-suite order and passed isolated.
6. **Owner-deactivated listings read back `state='edit'`** (not `inactive`)
   via GET /listings — runner accepts both.
7. **True listing DELETE needs `listings_d` OAuth scope** — current grant
   (transactions_r/w, listings_r/w, shops_r/w, email_r) lacks it. §9
   deactivates via PATCH state=inactive (listings_w). OWNER ITEM: add
   `listings_d` to DEFAULT_SCOPES + re-authorize, or accept manual
   Shop-Manager deletes of E2E/UAT test listings/drafts.

**SKU-drift-job decision (P-HUB-SKU-DRIFT residue)**: NO scheduled drift job
needed. The dirty-flag machinery (`x_sku_v2_status`) + canonicalise wizard
cover the BA workflow; `EtsyListingDriftReporter` is a callable read-only
service exercised on demand (runner §8 pattern: fire listing+variant sync
crons, then query). A cron would only add noise until a BA-facing report
surface exists. Revisit if catalog scale (>5k variants) or BA asks for a
scheduled report.

**Spec-flip honesty note**: only the 8 items the run actually exercised were
flipped to done (P-PUB-CLIENT/DRAFT/IMAGES/INVENTORY/PUBLISH,
P-HUB-PROD-MODEL/WIZARD/SKU-DRIFT). P-HUB-XLS-PARSE/INGEST/CRON, P-HUB-IMAGES
and P1-01b stayed `shipped*` — the flow-1 gate never touched the Excel catalog
stack or the order-line dashboard; they need their own verification step
(XLS: small dedicated runner or fold into a catalog-sync check; P1-01b: falls
out of MF-E2E-2 dashboard walk).

## 2026-07-04 — MF-E2E-2 flow-2 order receipt gate (runner 7/7 ×2, Playwright ×2)

Runner `scripts/e2e_flow2_orders.py`. Product changes (etsy_integration
**19.0.3.17.0**):

1. **Sync-health rows were missing for BOTH ingest paths** — only the
   import/migration wizards called `report_run`. Wired into
   `_cron_sync_orders` (`etsy_api_receipts_sync`) and
   `_cron_fetch_etsy_emails` (`etsy_email_fetch`, incl. the no-new-emails
   early return + Gmail auth-failure error row). 4 unit tests.
2. **`action_retry_parse` returned None** — the operator Retry button gave
   zero UI feedback (TC-004's toast assertion was hollow and only ever
   passed by accident). Now returns display_notification success/warning/info
   per outcome.

Environment/test findings:

3. **Anchor fixture drift**: S00007 → renamed S03339 (state draft→sale,
   amount re-priced 734914 VND→16.21 USD) — same receipt 3818231452;
   re-frozen `real_order_reference.json`. Re-audit by `etsy_raw_source_id`,
   not name.
4. **Bare BA role groups have NO sale.order ACL** — uat_ba_user got
   AccessError opening any SO. Production BA users are also salespeople; the
   etsy shop-scope record rule presumes a sales read grant. seed_ba_user now
   adds `sales_team.group_sale_salesman_all_leads` to BA User/Lead.
5. **`active_source` is a READONLY badge in the shop form** (owner-gated
   P-DS-3a) — the owner flow-2 doc's "admin toggles in UI" is currently a
   backend write (C-ESY-002). TC-009 tests the real mechanism (RPC write +
   badge reflects + audit rows). OWNER ITEM: align doc or add gated toggle.
6. **Pre-flight guard rows log http_status=0 by design**
   ("Shop has no etsy_api_shop_id; cannot push tracking") — TC-007 now
   accepts status-or-error. SIDE FIND: the tracking-push cron retries
   receipt 3703975562 / legacy shop id=1 every ~5 min forever — no retry
   cap. Routed to MF-E2E-3a (tracking push scope).
7. **Email-path partner dedupe**: the text-only fixture carries no
   email/address (address extraction is HTML-only), so per-order partners
   are the DESIGNED Tier-4 outcome. Partner dedupe is asserted on the API
   path (§A: re-ingest maps to existing partners, count unchanged).

## 2026-07-04 — MF-E2E-3a flow-3a fulfillment gate (runner 10/10 ×2, Playwright ×2)

Runner `scripts/e2e_flow3a_fulfillment.py`. FOUR product fixes (each
RED→GREEN unit-tested; details in evidence doc E2E_FLOW3A_FULFILLMENT):

1. **Tracking-push retry cap** (ei 19.0.3.18.0) — `_cron_push_tracking`
   re-picked `failed` orders forever (flow-2's 5-min loop). New
   `etsy_tracking_push_attempts` counter, cron ceiling 10, manual button
   exempt, reset on success.
2. **Carrier detection was wizard-only** (mhf 19.0.1.0.26) — the GDrive
   poller path imported trackings with `shipping_carrier_id=False`
   (apply_to_fulfillment docstring even said "we leave it None"); Etsy push
   then degraded to carrier 'other'. `detect_carriers()` now shared in
   tracking_importer.
3. **Schema compute died under web `bin_size` reads** (mhf) — form reloads
   recomputed `schema_hash/is_new_schema` with excel_file rendered as
   "12.3 KB" → silent parse failure → New Schema flag + Approve Schema
   button vanished; BA could not approve schemas in the UI at all (the
   drop-ship runner had auto-approved via RPC, masking it).
4. **No UI path to reject a design file** (mhc 19.0.1.0.76) — Rejection tab
   (holding the required rejection_reason field) was only visible when
   state=='rejected', but action_reject requires the reason BEFORE
   rejecting. Tab now visible while pending.

Env + test findings:

5. gke logistics.partner had EMPTY `gdrive_inbox_folder_id` on esty_odoo19
   — set to the owner "GKE" Shared-Drive folder (1-cY65RD…). SA access
   verified for both candidate folders.
6. Builder USPS tracking numbers were 23 digits; the carrier-seed regex
   caps at 22 (`9[0-9]{15,21}`) — detection silently failed. Prefix
   trimmed. Lesson: generated fixtures must satisfy the SEED regexes.
7. Drive immediate-deletes 404 on this Shared Drive (known MF-E2E-0 trap)
   — runner §7 keys on its own filename instead of "latest log row".
8. MO first `button_mark_done` lands on `to_close` unless raw moves are
   picked first; runner picks raw moves + double-calls.
9. Playwright drift class of the day: lazy notebook tabs (Pipeline /
   Rejection / Preview Lines), Odoo 19 `o_select_menu` replacing native
   `<select>` in dialogs, free-text search applying the FIRST facet only,
   role-gated buttons invisible to admin (production-team / BA-shipping),
   wizard field renames (`name`→`file_name`). Page-objects updated.
10. Local dev DB carries stale `design_ready` pipeline-state rows →
    3 pre-existing `test_pipeline_state_db` failures (noupdate drift,
    NOT this gate; staging clean).

## 2026-07-04 — .docs/tasks alignment + design_ready attribution correction

- `.docs/tasks/` (8 active tickets, legacy excluded) was cross-referenced
  nowhere in spec 015 — alignment table added to spec.md ("JIRA ticket
  alignment"). ESTY-205..210 (all pushed) are flow-2 surface, covered by
  MF-E2E-2 + their own ORM suites; ESTY-244 (design module split) → flow-3a;
  ESTY-246 (PO Gearment quote) → folded into MF-E2E-3b scope.
- CORRECTION to the MF-E2E-3a note above: the 3 local
  `test_pipeline_state_db` failures ("stale design_ready rows") are residue
  of the ESTY-244 WORK-IN-PROGRESS seeds on the local dev DB, not random
  noupdate drift. Re-baseline those tests when ESTY-244 lands.
- Gearment E2 keys in `.env` verified LIVE (200 on catalog) — MF-E2E-3b
  unblocked without a simulator.

## 2026-07-04 — MF-E2E-3b flow-3b Gearment gate (runner 8/8 ×2, Playwright ×2)

- **E2 keys LIVE** (owner: develop account, actual tests blessed): 200 on
  catalog. Production host in .env; sandbox host 530-dead.
- **Vendor blocker re-confirmed**: orders/draft rejects every
  printing_options shape (Defect-2026-05-10-05). 2 NEW capped probes with
  variant-level ids (legacy_variant_id 20374 / location_id 1 from live
  catalog) → identical opaque 400. STOP probing; escalate to Gearment
  support (validator `has_front_back_or_whole_printing_option`).
- **Real defect fixed** (mhf 19.0.1.0.27): webhook-triggered Etsy tracking
  push (ADR D-A PRIMARY trigger) ran under the public webhook env → 
  AccessError on sale.order.fulfillment → soft-fail on EVERY live webhook
  since P1-12 landed; only the 5-min cron ever pushed. Dispatcher now runs
  the pusher sudo (bounded; HMAC verified upstream). ORM test pins it.
- Webhook HMAC verified LIVE twice (runner §5 + TC-DROP-005) → **P0-18b2
  closes**. TC-DROP-005 needed Python-compatible PADDED base64url and the
  X-Connect-Client-Key header (controller selects secret by client key).
- Simulated draft/quote legs (documented mock fallback per the 3b exit
  criteria): `_SimAdapter` patched at the module seam in odoo shell — HTTP
  boundary only; builder + state machine real. Simulator enforces the
  documented printing_options contract so it cannot mask the regression.
- gearment.api.log rows are NOT written for verified webhooks (discovery
  mode only) — provenance lives on fulfillment
  `gearment_last_webhook_topic/at`.
