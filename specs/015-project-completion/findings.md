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
