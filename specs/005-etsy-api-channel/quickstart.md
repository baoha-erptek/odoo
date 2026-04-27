# Quickstart: Etsy API v3 Channel Integration (with Email as Permanent Failover)

**Phase**: 1 (verification walkthrough — fresh module install on staging)
**Modules**: `etsy_channel_api` (NEW) and `etsy_channel_email` (RENAMED) per ADR-008a §5
**Date**: 2026-04-27 (Stage 4.2 refresh; supersedes 2026-04-10 quickstart)

---

## Prerequisites

1. Etsy Developer App registered with: app keystring, shared secret, callback URL `https://<staging-domain>/etsy/api/oauth/callback`.
2. Etsy app scope review **APPROVED** for: `transactions_r`, `transactions_w`, `listings_r`, `listings_w`, `shops_r`, `email_r`.
3. Staging Odoo at `129.150.63.207:8169` with DB `namco_odoo19` restored from a recent prod snapshot.
4. `multichannel_hub_core` installed (Spec 003 prerequisite).
5. Existing `etsy_integration` module installed and at the version that introduced `sync_mode` (Spec 005 v1, 2026-04-09 build).

---

## 1. Module split + install

```bash
# Pre-migrate etsy_integration → etsy_channel_email
docker exec namco_odoo19 odoo -d namco_odoo19 -i etsy_channel_email -u etsy_channel_email --stop-after-init

# Install etsy_channel_api fresh
docker exec namco_odoo19 odoo -d namco_odoo19 -i etsy_channel_api --stop-after-init
```

**Expected**:
- `ir_module_module` shows `etsy_channel_email` (no longer `etsy_integration`) and `etsy_channel_api` both installed.
- `etsy_shop` rows untouched (no data loss); `active_source` column populated from prior `sync_mode` per the migration script.
- `etsy.shop.source.change.log` has one `reason='bootstrap'` row per existing shop.

**DB verification**:
```sql
SELECT name, state FROM ir_module_module WHERE name IN ('etsy_integration', 'etsy_channel_api', 'etsy_channel_email');
SELECT id, name, sync_mode, active_source FROM etsy_shop ORDER BY id;
SELECT shop_id, from_source, to_source, reason FROM etsy_shop_source_change_log WHERE reason='bootstrap';
```

---

## 2. US1 — Etsy OAuth2 PKCE authorization (per shop)

1. Settings → **Etsy Integration → API Configuration**. Enter app keystring + shared secret on a test shop.
2. Click **Authorize Etsy**. Verify redirect to `https://www.etsy.com/oauth/connect?...code_challenge_method=S256&...`.
3. Complete the consent flow. On callback, verify:
   - `etsy_shop.etsy_access_token` populated (encrypted).
   - `etsy_shop.etsy_refresh_token` populated (encrypted).
   - `etsy_shop.etsy_access_token_expires_at` ~1 hour ahead.
   - `etsy_shop.etsy_token_scopes` contains the granted scopes.
4. Click **Test Connection**. Verify shop name and Etsy user displayed.
5. Wait until token expires (or force expiry by setting `etsy_access_token_expires_at` in the past). Trigger any API action (Test Connection). Verify token auto-refreshes.

**Pass/fail**:
- ✅ PKCE flow completes with correct `code_challenge_method=S256`
- ✅ Tokens stored encrypted with `groups='base.group_system'` ACL
- ✅ Auto-refresh works transparently

---

## 3. US2 — Direct order sync (canonical payload)

1. Set `etsy_shop.active_source='api'` on the test shop. Confirm a `manual` row appears in `etsy.shop.source.change.log`.
2. Trigger the order sync cron manually: `cron_etsy_order_sync` for that shop.
3. Verify:
   - `etsy.api.log` shows `endpoint='GET /v3/application/shops/:shop_id/receipts'`, `http_status=200`, `source='sync'`.
   - New `sale.order` rows created with `sync_source='api'`.
   - `sale.order.etsy_order_id` matches the receipt; `sale.order.channel_order_ref` matches.
   - Canonical payload field-mapping verified: `buyer_email` populated (API only), `listing_id` populated, `payment_status` reflects the receipt's status.
4. Trigger a re-sync. Verify status-only update (operator-entered fields like `mp_note`, `pic_user_id` are NOT overwritten — FR-009).
5. Place an order on the live Etsy dev shop. Wait for next cron tick. Verify the order appears in Odoo within 5 min.

**Pass/fail**:
- ✅ Canonical `EtsyOrderPayload` flows through `EtsyApiAdapter → EtsyOrderIngestor → sale.order`
- ✅ Dedup by `etsy_order_id`
- ✅ Status-only update preserves operator data
- ✅ End-to-end latency ≤ 5 min

---

## 4. US3 — Tracking push to Etsy

1. Pick a synced order. Set `sale.order.fulfillment.tracking_number='9400111202555555555555'`, `shipping_carrier_id=<USPS carrier>`.
2. Trigger `cron_etsy_tracking_push`. Verify:
   - `etsy.api.log` shows `endpoint='POST /v3/application/shops/:shop_id/receipts/:receipt_id/tracking'`, `http_status=200`, `source='tracking_push'`.
   - `sale.order.etsy_tracking_push_status='pushed'`, `etsy_tracking_push_at` set.
   - The Etsy Seller Portal shows the tracking number on the order.
3. Repeat with a carrier whose `etsy_carrier_name` is `other`. Verify push uses `other` and a warning is logged in `etsy.api.log` with the unmapped name.

**Pass/fail**:
- ✅ Tracking visible on Etsy portal within 5 min
- ✅ Status field set + audit log clean

---

## 5. US5 — Rate limiting and resilience

1. Enable a load test: trigger 50 receipt-fetch calls in quick succession.
2. Verify the rate limiter throttles to ~10 req/s; `etsy.api.log` shows duration spread across ~5+ seconds.
3. Mock a 429 response. Verify the client respects the `Retry-After` header (test fixture).
4. Mock a 500 response. Verify exponential-backoff retry up to 3 attempts.
5. Mock a 403 (permanent). Verify NO retry; error logged with `http_status=403`.
6. Inspect `quota_remaining_today` on the latest log row. Verify it's tracking the API's headers.

**Pass/fail**:
- ✅ Rate limiter enforces ~10 req/s
- ✅ Retry policy honoured per error class

---

## 6. US8 — Source switching (REQ-SRC-01..04 — the new core)

### 6.a. Manual switch
1. As admin, change `etsy_shop.active_source` from `api` to `email` on the form view. Confirm:
   - A row appears in `etsy.shop.source.change.log` with `from_source='api'`, `to_source='email'`, `reason='manual'`, `actor_user_id=admin`.
   - The `etsy.shop.active_source_changed_at` is updated.

### 6.b. Auto-failover (3-failure threshold)
1. Force the API health-check to fail 3 times in a row (e.g., revoke OAuth token, then trigger `cron_etsy_health_check`).
2. After the 3rd failure:
   - `etsy_shop.active_source` flips from `api` to `email`.
   - A row appears in `etsy.shop.source.change.log` with `reason='auto-failover'`, `health_check_failures_at_change=3`.
   - HIGH severity alert raised (visible on the health dashboard tile).
3. Restart the email cron. Verify orders flow via `EtsyEmailAdapter` (via the renamed `etsy_channel_email` module) producing the same canonical payload.

### 6.c. Recovery probe (6-success threshold + auto-switch-back)
1. Repair the API token. Trigger `cron_etsy_recovery_probe` 6 consecutive times (or wait 6 hours).
2. After the 6th probe success:
   - `etsy.shop.active_source` flips back from `email` to `api`.
   - A row appears in `etsy.shop.source.change.log` with `reason='recovery-probe'`.
3. Set `etsy_shop.auto_recovery=False` on a different shop, force failover, then run probes. Verify the shop does NOT auto-switch-back (sticky override).

### 6.d. Same canonical payload from both adapters
1. Take a representative receipt on the dev shop. Force ingestion via API adapter; capture the canonical `EtsyOrderPayload` JSON.
2. Force the same receipt's confirmation email through the email adapter; capture its canonical payload.
3. Diff the two payloads. Required fields must match exactly. Source-specific fields (`buyer_email`, `listing_id`) MAY differ (API has them, email doesn't).

**Pass/fail**:
- ✅ Manual + auto-failover + recovery-probe transitions all logged correctly
- ✅ HIGH alert fires on auto-failover
- ✅ `auto_recovery=False` blocks switch-back
- ✅ Canonical payload parity between adapters on required fields

---

## 7. REQ-MSG-01 — Customer Message Hub (`buyer_message` ingestion)

1. Place a test order on Etsy dev shop with a buyer message ("Please ship gift-wrapped"). Wait for next sync.
2. Verify:
   - `etsy.buyer.message` row created with `(shop_id, etsy_receipt_id)`, `message='Please ship gift-wrapped'`, `is_read=False`.
   - The row's `sale_order_id` links to the newly-created `sale.order`.
3. Open the order form. Verify the "Buyer Message" tab shows the message.
4. Open the **Customer Message Hub** view (delivered by Spec 003). Verify the message appears, filterable by shop.
5. As MP, click the message. Verify `is_read=True`, `read_by_user_id=mp_user`, `read_at` set.

**Pass/fail**:
- ✅ Per-receipt buyer message ingested without extra HTTP calls
- ✅ Customer Message Hub view populated
- ✅ Read-tracking works

---

## 8. US4 — Webhook receiver (P2 — Phase 2)

1. Click **Register Webhooks** on the shop config. Verify `etsy.api.log` rows for the registration calls.
2. Place a test order on Etsy. Verify within 60 s:
   - A row appears in `etsy.webhook.event` with `signature_status='valid'`, `event_type='order_paid'`.
   - The corresponding `sale.order` exists.
3. Replay the same webhook payload (curl with same headers). Verify idempotency: no duplicate event row, no duplicate sale order.
4. Replay with tampered HMAC signature. Verify rejection: `signature_status='invalid'`, no order created.

**Pass/fail**:
- ✅ HMAC verification works
- ✅ Idempotency on replay
- ✅ Latency ≤ 60 s

---

## 9. Health dashboard tiles (per ADR-008a §6)

1. Open the health dashboard. Verify these tiles render with live values:
   - `active_source_per_shop` — table of shop name → current source
   - `auto_failover_count_7d` — count of `auto-failover` rows in `etsy.shop.source.change.log` over last 7 days
   - `time_since_last_recovery_probe_success` — for shops in failover, time since last successful probe
   - `parser_template_drift` — health metric on the email adapter (regex match-rate trend)

**Pass/fail**:
- ✅ All four tiles visible + populated
- ✅ Auto-failover count alerts on spike

---

## Cleanup

```bash
# Reset cron failures on test shop:
docker exec db psql -U odoo -d namco_odoo19 -c "
  UPDATE etsy_shop SET health_check_consecutive_failures=0, recovery_probe_consecutive_successes=0
  WHERE name = '<test_shop>';
"

# Truncate the source-change log if rerunning the test suite:
docker exec db psql -U odoo -d namco_odoo19 -c "TRUNCATE etsy_shop_source_change_log RESTART IDENTITY;"

# Re-bootstrap:
docker exec namco_odoo19 odoo -d namco_odoo19 -u etsy_channel_api --stop-after-init
```

---

## Cross-references

- spec.md US1–US8 (one quickstart section per User Story)
- data-model.md (full model definitions)
- research.md (R7 source-switching, R8 canonical payload, R9 buyer-message, R10 module-rename)
- ADR-008a v2 §1–§6, ADR-005 (carrier), ADR-001 §11 (module map)
- master plan staging note (Q10): `129.150.63.207`
