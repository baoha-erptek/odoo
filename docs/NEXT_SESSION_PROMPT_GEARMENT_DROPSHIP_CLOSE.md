# NEXT SESSION — Close Defect-2026-05-10-05 (Gearment dropship live draft push)

**Branch:** `feature/006-master-plan-coding` (already pushed through commit `e508df6ac1d`).
**Goal:** Take the `printing_options` enum fix from "code-fixed, PARTIAL" to **fully closed** —
a LIVE `POST /api/v3/orders/draft` returns **200** with a real `x_gearment_outbound_ref`,
and the two dropship E2E flows pass end-to-end on staging without the mock-fallback caveat.

## Definition of done

- [ ] `scripts/e2e_flow3b_dropship.py` §3 live push → **200** (not 400), non-empty outbound_ref.
- [ ] `scripts/e2e_demo_drop_ship_ordertest2.py` §6 auto-push → **200**, quote advances
      `confirmed → quoted`.
- [ ] Both re-run **×2** (gate discipline) on staging `esty_odoo19`.
- [ ] Evidence docs refreshed (new dated files), old vendor-blocker caveats struck.
- [ ] Tracker `006-master-plan-tracking.md` Defect-2026-05-10-05 flipped **PARTIAL → DONE**;
      spec 015 MF-E2E-3b caveat removed; `findings.md` closure entry.
- [ ] DRAFT orders discarded in the Gearment dashboard afterward (never confirm/label — no charge).

## What already changed (this session)

- Root cause found via doc crawl (`docs/vendor/gearment/`, commit `ec6557c7b19`):
  `location_code` is the proto3 enum **`PRINT_LOCATION_CODE_*`**, not the bare names the 400
  quotes. The 14+ prior probes never tried the `PRINT_LOCATION_CODE_` prefix.
- Builder fixed (commit `595fb03286b`): `_PRINT_LOCATIONS_DEFAULT` →
  `('PRINT_LOCATION_CODE_FRONT','PRINT_LOCATION_CODE_BACK')`. RED→GREEN, 390 module tests green.
- **This means: do NOT re-open the "which string?" probe loop. The enum form is the answer.**
  If a 400 persists, the failure has MOVED to a different field (see Step 4).

## Preconditions (do these first, in order)

1. **Deploy the fix to staging.** The green tests were local; staging container `esty19_odoo`
   runs deployed code. Per memory `reference_staging_ssh_deploy.md`: rsync the `multichannel_hub_fulfillment`
   module to `ubuntu@129.150.63.207` (per-module, **NEVER `--delete`**), then
   `-u multichannel_hub_fulfillment --stop-after-init` and **restart the container**
   (memory `feedback_restart_container_after_stop_after_init_upgrade.md`).
   Verify: `docker exec esty19_odoo grep -n PRINT_LOCATION_CODE /opt/.../services/gearment_payload_builder.py`.
2. **Keys present:** `docker exec esty19_odoo env | grep GEARMENT` returns
   `GEARMENT_API_KEY`, `GEARMENT_API_SECRET`, `GEARMENT_WEBHOOK_HMAC_SECRET` (E2, verified live 2026-07-04).
3. **Staging DB is `esty_odoo19`** (memory `reference_staging_db_name.md` — default `demo_esty` is wrong).
4. **Sandbox host is dead** (`api.gearmentinc.com` / `api.gearment.com` = 530). This is a LIVE
   PRODUCTION draft push. Safe because it stops at DRAFT — adapter `confirm()` still raises
   `NotImplementedError`, no labeling, no charge. Clean up drafts after.

## Flows to redo

| ID | Script | Evidence (write NEW dated file) |
|----|--------|--------------------------------|
| **MF-E2E-3b** | `scripts/e2e_flow3b_dropship.py` | `docs/engineering/uats/E2E_FLOW3B_DROPSHIP_<date>.md` |
| **Demo dropship** | `scripts/e2e_demo_drop_ship_ordertest2.py` | `docs/engineering/uats/E2E_DEMO_DROP_SHIP_ORDERTEST2_<date>.md` |

Run (on staging, ×2 each):
```bash
/tmp/e2e-venv/bin/python scripts/e2e_flow3b_dropship.py --db esty_odoo19
/tmp/e2e-venv/bin/python scripts/e2e_demo_drop_ship_ordertest2.py --db esty_odoo19
```

## Step 4 — If the live draft STILL 400s (blocker moved, not returned)

The enum was the *first* wrong field. The docs (`docs/vendor/gearment/api_api.order.v1.vendororderapi.md`)
show two more likely culprits — attack in this order, **capturing the full response body each time**
(memory `feedback_capture_response_body_before_blackbox_probe.md` — print `r.text[:2000]`, durable
audit row via fresh cursor + commit; **cap at ~5 variants, do not runaway-probe**):

1. **`variant_id` vs `legacy_id`.** We send `legacy_id` derived from the Odoo SKU. Docs: draft
   line items want **`variant_id`** (GM-prefixed, e.g. `GM0002003147`) + `product_id` (e.g. `G5000`),
   resolved via `GET /api/v3/catalog/variants/stock?filter.product_ids=...&filter.variant_ids=...`.
   Our synthetic `DEMO-*` SKUs are **not catalog variants** → this is the *separate*
   **Defect-2026-05-10-02**. Pull a real dev-catalog `variant_id` first and test with it.
2. **Non-WHOLE enum values.** Only `PRINT_LOCATION_CODE_WHOLE` is doc-literal; `FRONT`/`BACK`/`POCKET`
   are inferred from the 400's allowed-list + the proven prefix. If FRONT/BACK 400 but WHOLE 200,
   switch single-design orders to `PRINT_LOCATION_CODE_WHOLE` and confirm the multi-design mapping.
3. Only if 1+2 both fail: the error body will name the next field — follow it, don't guess.

Each finding → new RED test + builder fix on `feature/006-master-plan-coding`, same RED→GREEN loop
as commit `595fb03286b`. `printing_options` string form is SETTLED — do not revisit it.

## Do NOT

- Re-probe `location_code` string encodings (14+ done, enum is the answer).
- Confirm/label any Gearment order (charges real money; `confirm()` gate must stay).
- rsync staging with `--delete`.
- Touch the QUOTE endpoint's `print_locations:["front"]` lowercase shape — that one is correct as-is.

## References

- Analysis + answered vendor questions: `docs/GEARMENT_API_REFERENCE.md` (Docs Source + Q1.1/Q1.2/Q2.1/Q4.1).
- Crawled corpus: `docs/vendor/gearment/` (raw HTML in `_raw/`, git-ignored).
- Prior evidence + blocker trail: `docs/engineering/uats/E2E_FLOW3B_DROPSHIP_2026-07-04.md:49-56`
  (validator `has_front_back_or_whole_printing_option`, request_id `1d36e400-77e8-4612-b0f7-2539b2471d76`).
- Findings: `specs/004-fulfillment-routing/findings.md` (2026-07-05 entry).
- Playbook: `.claude/plans/006-implementation-playbook.md` (9-phase loop — this is a fix slice, run it).
