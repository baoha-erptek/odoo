# E2E Re-Run Prep — Next Session (2026-05-12+)

> Read this BEFORE starting the next E2E run. Captures everything that changed in the 2026-05-11 autonomous session so we don't re-discover the same things.

## Where things stand

### Branch
`feature/006-master-plan-coding` head = `02264dfb5b2` (pushed). 7 commits on 2026-05-11; all green; both reviewers approved each.

### Staging
- Host `nwf-oracle` aka `129.150.63.207`, ssh as `ubuntu` with `secrets/ssh-key-2023-02-24.key`. See memory `reference_staging_ssh_deploy.md`.
- Container `esty19_odoo` is on **branch HEAD as of 2026-05-11 15:30 UTC**:
  - `multichannel_hub_core` 19.0.1.0.34 (Annex A)
  - `etsy_integration` 19.0.2.3.8 (Annex A)
  - `multichannel_hub_fulfillment` 19.0.1.0.21 (P4-01-FIX-LOG-LINKAGE-EXCEPTION-PATH)
- Database: `demo_esty`. Admin login: `admin`/`admin` over `https://odoo.hatafax.com/xmlrpc/2/object`.
- 4 ordertest2 sale.orders present (`S01359-S01362`, ids 1375-1378), all in `state='sale'` with `tracking_state='shipped'` (GKE tracking import succeeded).

### Dashboard fixes (Annex A — P1-01b-FIX-DASHBOARD-GAPS)
Live on staging:
- ✓ `order_id` column on Operations Dashboard (optional=show)
- ✓ `sale.order.line.label_status_id` is writable (inline-edit works)
- ✓ OrderCreator dual-writes channel-agnostic shadows (gift_message, processing_time, discount_code, shipping_service_label, shipping_cost on order; transaction_id, personalisation, image_url, design_link_front, design_link_back, *_manual variant labels on line)
- ⚠️ The 4 EXISTING orders (S01359-S01362) were ingested BEFORE Annex A deploy → channel-agnostic shadows are EMPTY for them. Future ingests will populate. To verify Annex A on the existing orders, either: (a) wipe + re-ingest, or (b) inspect a NEW ingest after this prep.

### Audit log durability (Defect-2026-05-11-02 fix)
`gearment.api.log` writes now use a fresh `self.env.registry.cursor()` + explicit `cr.commit()` → audit row survives outer rollback. Verified live: log id=148 captures full Gearment response body (`data.line_items: value must contain at least 1 item(s)`) for the failed S01359 push.

## Defects status (carry into next session)

| Defect | Status | Action |
|---|---|---|
| 2026-05-10-04 (GKE archive folder empty) | OPEN | Operator: set `logistics.partner.gke.gdrive_archive_folder_id` (currently `''`). Files accumulate in inbox each rerun. Schedule slice `P2-FIX-ARCHIVE-FOLDER`. |
| 2026-05-10-05 (printing_options) | RECLASSIFIED → -11-01 | Was a symptom; real cause is empty line_items. The 12 prior probe variants were misled by audit log gap. Don't probe further. |
| 2026-05-11-01 (design.file auto-create) | OPEN — **PRIORITY** | Tracker slice `P1-DESIGN-AUTO-CREATE-FROM-EMAIL` already added. Owner: planner agent. Deliverable: extend OrderCreator to seed design.file rows from parsed `design_link_front/back`. |
| 2026-05-11-02 (exception path log) | CLOSED | Fixed in commit `6ef702b5605`; deployed to staging; verified live. |
| 2026-05-11-03 (staging drift) | CLOSED | Resolved same session; staging at branch HEAD. |

## What the next E2E rerun should do

### Recommended sequence (assumes P1-DESIGN-AUTO-CREATE-FROM-EMAIL slice has landed)

1. **Pre-flight** — re-confirm staging is at branch HEAD; check ICPs (Gmail OAuth, GDrive folders, GKE inbox).
2. **Wipe** — `DEMO_ADMIN_PASSWORD=admin python3 scripts/cleanup_demo_esty_orders.py` (wipes 4 orders + cascade).
3. **Re-ingest** — XML-RPC trigger of cron id=25 (`Etsy: Fetch Order Emails`). Expect 4 new sale.orders.
4. **Verify Annex A on the FRESH ingest** — confirm `gift_message`, `processing_time`, `discount_code`, `shipping_service_label`, `shipping_cost` populated on order; `transaction_id`, `personalisation`, `image_url`, `design_link_*`, `*_manual` populated on lines.
5. **Verify P1-DESIGN-AUTO-CREATE-FROM-EMAIL** — `design.file` row count ≥1 per non-shipping line with parsed design link; state=pending.
6. **Image cron** — XML-RPC trigger of cron id=36; verify `product.template.image_1920` populated for non-shipping templates.
7. **Operator approves design files** — via wizard OR XML-RPC `design.file.write({'state': 'approved'})`. Required before Gearment push.
8. **Push Gearment** — `sale.order.action_push_to_gearment([id])` per order. **Now expected to succeed** (no more empty line_items). If still 4xx, the new audit log row will carry the real reason — do NOT regress to printing_options blackbox probing.
9. **Build GKE workbook** — `docker exec namco_odoo19 python3 /tmp/build_gke.py --out /tmp/gke_e2e.xlsx --receipts <ids> --upload-to-drive --service-account /tmp/sa.json` (use the local container; the dev box's Python has broken OpenSSL).
10. **GKE poll cron** — XML-RPC trigger; verify tracking.import.line rows + propagation to sale.order.tracking_number + tracking_state='shipped'.
11. **Defect intake** — open `docs/E2E_DEFECTS_2026-05-12.md`; populate any new findings using the established template.

### Single-command shortcuts that work

```bash
# SSH key
SSHKEY=/home/odoo/odoo_dev/other_projects/odoo19_esty/secrets/ssh-key-2023-02-24.key
SSHOPTS="-i $SSHKEY -o StrictHostKeyChecking=no -o IdentitiesOnly=yes"

# Deploy diff (per-module rsync, NEVER --delete)
for m in multichannel_hub_core etsy_integration multichannel_hub_fulfillment; do
  rsync -az --no-perms --no-owner --no-group --exclude '__pycache__' --exclude '*.pyc' \
    -e "ssh $SSHOPTS" \
    /home/odoo/odoo_dev/other_projects/odoo19_esty/custom_addons/$m/ \
    ubuntu@129.150.63.207:/odoo/esty19/custom_addons/$m/
done

# Module update + restart (restart needed for Python field metadata changes)
ssh $SSHOPTS ubuntu@129.150.63.207 \
  "sudo docker exec esty19_odoo odoo -d demo_esty -u multichannel_hub_core,etsy_integration,multichannel_hub_fulfillment --stop-after-init --no-http --http-port 9999 && sudo docker restart esty19_odoo"

# Wipe + re-ingest
DEMO_ADMIN_PASSWORD=admin python3 scripts/cleanup_demo_esty_orders.py
python3 -c "
import xmlrpc.client; c=xmlrpc.client.ServerProxy('https://odoo.hatafax.com/xmlrpc/2/common', allow_none=True); uid=c.authenticate('demo_esty','admin','admin',{})
m=xmlrpc.client.ServerProxy('https://odoo.hatafax.com/xmlrpc/2/object', allow_none=True)
m.execute_kw('demo_esty',uid,'admin','ir.cron','method_direct_trigger',[[25]])
print('triggered')
"
```

## Things that hurt last time (read these so we don't repeat)

1. **Annex A field readonly attribute looked unchanged after module update** — needed `docker restart esty19_odoo` to refresh the Python class metadata. Module `-u` updates view archs + ACL CSV but NOT the in-memory field definitions.
2. **Local Python OpenSSL broken** — pip install fails with `AttributeError: module 'lib' has no attribute 'X509_V_FLAG_NOTIFY_POLICY'`. Workaround: install + run inside `namco_odoo19` container.
3. **`docker cp` files into container are owned 0:0** — must `docker exec -u root ... chown odoo:odoo` before scripts can write to the dest path.
4. **gearment.api.log was empty after every failed push** — Defect-11-02; fixed but worth knowing for any future audit-log-on-error pattern. Always use `self.env.registry.cursor()` + explicit commit for failure-path logs.
5. **The `printing_options` lead was a red herring for ~24h** — captured in memory `feedback_fix_observability_before_chasing_symptoms.md`. Don't re-open that thread; the real issue was always empty line_items.
6. **GDrive archive folder is empty** — every rerun adds a new file to the inbox. Either (a) operator sets `gdrive_archive_folder_id` on logistics.partner.gke, or (b) operator manually deletes old files between runs.
7. **rsync `--delete` once destroyed mhf on staging** — never use it. Use per-module rsync without delete; orphan files we don't need are OK.

## Files / docs to read for context

| Doc | Why |
|---|---|
| `docs/E2E_DEFECTS_2026-05-11.md` | The 6 defects (1 medium open, 1 priority open, 3 closed, 1 carry-forward) and final triage decisions |
| `docs/GEARMENT_API_REFERENCE.md` | 798-line reference doc for v3 API; section 10 has the open questions to send to Gearment support |
| `docs/GEARMENT_SUPPORT_EMAIL_DRAFT.md` | Pre-built email draft (3 questions) — sandbox / idempotency / schema |
| `~/.claude/plans/quirky-shimmying-charm.md` | Prior plan file (Annex A + Annex B + Phase 0-6) |
| `~/.claude/projects/-home-odoo-odoo-dev-other-projects-odoo19-esty/memory/reference_staging_ssh_deploy.md` | SSH deploy mechanics (this session's discovery) |
| `~/.claude/projects/-home-odoo-odoo-dev-other-projects-odoo19-esty/memory/feedback_fix_observability_before_chasing_symptoms.md` | The Defect-05 RCA lesson |
| `.claude/plans/006-master-plan-tracking.md` "E2E Defects in Flight" | Single source of truth for defect routing |

## What NOT to do

- Don't re-attempt printing_options variant probing for Defect-05; it was a red herring.
- Don't try to rsync from local without the SSH key path above.
- Don't push Gearment for orders that have 0 design files — payload will reject. Either approve a design file via the upload wizard first, OR wait for `P1-DESIGN-AUTO-CREATE-FROM-EMAIL` to land.
- Don't use rsync `--delete`. Memory `feedback_session_start_working_tree_check.md` documents the 2026-05-09 staging clobber.
- Don't write directly to `gearment.api.log` from within a transaction that might roll back — use the fresh-cursor pattern (now standard in `gearment_adapter._log_call`).

## Telegram routing for autonomous runs

DM owner via Telegram bot: chat_id `1013317517` (or `8560005895`). See memory `reference_telegram_routing.md`. Group `-5233783589` is a different project — do NOT use it.
