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
