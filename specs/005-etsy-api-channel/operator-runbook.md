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
