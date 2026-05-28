# Etsy Integration — Operator Runbook (P1-10)

Production OAuth + Fernet-at-rest token encryption. Audience: deployment
operators / sysadmins. No Odoo development knowledge assumed.

---

## 1. Install production Etsy app credentials

The OAuth controller reads the Etsy app `client_id` / `client_secret`
from a JSON file on disk — **never** from the database or source code,
so credentials never enter `pg_dump` or git.

1. Create the credentials file on the Odoo host (default path
   `/opt/odoo/secrets/credentials.json`, mounted into the container):

   ```json
   {
     "client_id": "<etsy-prod-keystring>",
     "client_secret": "<etsy-prod-shared-secret>",
     "redirect_uris": {
       "https://<prod-domain>": "https://<prod-domain>/etsy/api/oauth/callback"
     }
   }
   ```

2. The `redirect_uris` map is keyed by Odoo's `web.base.url`. The
   controller auto-selects the entry matching the running instance, so
   dev / staging / prod can share one file.

3. (Optional) To use a non-default path, set the system parameter
   `etsy.oauth.credentials_path` to the absolute file path:
   **Settings → Technical → Parameters → System Parameters**.

4. File permissions: readable only by the Odoo OS user
   (`chmod 600`, owned by the container's `odoo` user).

No restart required for credential changes — the file is read per
OAuth request.

---

## 2. Verify the Fernet encryption key

OAuth tokens are stored Fernet-encrypted. The encryption key lives in
the `etsy.oauth.fernet_key` system parameter and is **generated
automatically on the first token write** (lazy init, concurrency-safe).

There is **no manual bootstrap step**. To confirm it generated:

1. After the first successful shop authorization (or first token
   refresh), check the container log for:

   ```
   odoo.addons.etsy_integration.services.fernet_crypto:
   Generated Fernet key for 'etsy.oauth.fernet_key' (one-time lazy init).
   ```

2. Confirm the parameter is populated and access-restricted:
   **Settings → Technical → Parameters → System Parameters**, search
   `etsy.oauth.fernet_key`. Only `Settings`-group (admin) users can
   read its value; non-admin reads raise an access error by design.

> **Critical — key backup.** The Fernet key is the only thing that can
> decrypt every stored OAuth token. It is stored in the database, so a
> standard `pg_dump` backup includes it. **Never** clear or overwrite
> this parameter — doing so permanently orphans all stored tokens and
> every shop must re-authorize. Key rotation is intentionally out of
> scope for this release.

---

## 3. Scope-grant drift — detect and recover

The callback hard-rejects (HTTP 400) any authorization whose granted
scopes do not exactly satisfy the approved set:

- **Required**: `transactions_r`, `transactions_w`, `listings_r`,
  `listings_w`, `shops_r`, `email_r`
- **Forbidden**: `conversations_r` (not in the approved grant)

### Symptom

A shop authorization fails with a `400` and an audit row appears under
the Etsy API log with **source = "OAuth Scope Validation"**. The audit
row names which scopes were missing or which forbidden scope leaked. It
deliberately does **not** contain the access/refresh token.

### Recovery

1. Read the audit row to see the exact missing/forbidden scope.
2. In the Etsy developer dashboard, revoke the app's existing
   authorization for that shop.
3. Confirm the Etsy app's requested scope list matches the approved
   set above (no `conversations_r`).
4. Re-run the shop authorization flow from the Etsy shop record in
   Odoo. The controller requests the correct scope string; the new
   grant should pass validation and persist encrypted tokens.

If `conversations_r` is genuinely required later, that is tracked
separately (slice **P1-MSG-SCOPE**) and needs a fresh Etsy approval —
do not work around the scope gate.

---

## 4. Re-authorizing a shop

1. Open the Etsy shop record in Odoo.
2. Trigger the OAuth authorize flow (admin/system user only — the
   `/etsy/api/oauth/authorize` route requires login).
3. Complete the Etsy consent screen.
4. On success the new tokens are Fernet-encrypted and written; the
   5-minute sync cron resumes automatically.

Existing pre-encryption (P0-14 sandbox) plaintext tokens are migrated
lazily — the next token refresh re-writes them as ciphertext with no
operator action.

---

## 5. Pilot shop cutover (`active_source` → `api`)

This is the operational flip that moves a shop off Gmail-sourced
order ingest and onto the Etsy API adapter (ADR-008a). It is run by
a system administrator. The same procedure repeats unchanged for the
additional shops in P1-13.

### 5.1 Prerequisites (check all before flipping)

1. **Production credentials installed** — §1 complete for the Etsy
   app this shop authorizes against.
2. **Fernet key present** — §2 verified (token columns store
   ciphertext).
3. **Shop is authorized** — open the Etsy shop record; if it has no
   valid OAuth tokens, click **Authorize Etsy** and complete the
   consent screen (§4). System/admin users only; the button is
   hidden for everyone else.
4. **Scope grant clean** — no scope-drift audit row outstanding for
   this shop (§3).
5. **API adapter proven** — click **Test Connection** on the shop
   record. You must see the green "Etsy API is reachable" toast. A
   "probe failed" warning means the API path is not ready — stop and
   resolve before flipping (do not flip on a failed probe).

### 5.2 The flip

1. Open the Etsy shop record as a system administrator.
2. In the **Etsy API Configuration** group (system-only), set
   **Active Source** to `api`.
3. Save the record.

The change is recorded automatically in the append-only
`etsy.shop.source.change.log` (who, when, from→to, and the health-
failure counter at the time). No manual log entry is needed.

### 5.3 Post-flip round-trip verification

1. Wait one sync cycle (the order sync cron runs every 5 minutes and
   now filters to `active_source='api'` shops).
2. Confirm new Etsy orders for this shop appear as sale orders
   (Orders tab on the shop record / Operations dashboard).
3. Spot-check one order: amounts and line items match the Etsy
   receipt.
4. Fulfil one order through the normal flow and confirm the Etsy
   tracking write-back lands — the sale order's tracking-push status
   moves to `pushed` (P1-12). This proves the full
   ingest→fulfil→track loop on the API source.

### 5.4 Rollback

If orders are missing, malformed, or the round-trip fails:

1. Re-open the shop record (system administrator).
2. Set **Active Source** back to `email`. Save.
3. Within one cron cycle, Gmail-sourced ingest resumes for this
   shop. The rollback is itself recorded in
   `etsy.shop.source.change.log`.
4. Escalate to Dev B with the failing order ids and the change-log
   rows for a post-mortem before re-attempting the cutover.

### 5.5 Additional shops (P1-13)

Repeat §5.1–§5.3 per shop. No Fernet re-initialisation is needed —
the key is global. Each shop is authorized and probed independently;
flip them one at a time and verify each round-trip before moving to
the next.
