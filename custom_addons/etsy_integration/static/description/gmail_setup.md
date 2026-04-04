# Gmail API Setup Guide

This document describes how to configure Google OAuth2 credentials so
the Etsy Integration module can read order notification emails from a
Gmail inbox.

---

## 1. Create a Google Cloud Project

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project selector in the top navigation bar and choose
   **New Project**.
3. Enter a project name (e.g., "Odoo Etsy Integration") and click
   **Create**.
4. Wait for the project to be created, then switch to it using the
   project selector.

## 2. Enable the Gmail API

1. In the Cloud Console, navigate to **APIs & Services > Library**.
2. Search for **Gmail API**.
3. Click the **Gmail API** result and press **Enable**.

## 3. Configure the OAuth Consent Screen

1. Go to **APIs & Services > OAuth consent screen**.
2. Select **External** as the user type (unless your organization uses
   Google Workspace, in which case choose **Internal**).
3. Fill in the required fields:
   - **App name**: Odoo Etsy Integration
   - **User support email**: your email address
   - **Developer contact information**: your email address
4. Click **Save and Continue**.
5. On the **Scopes** page, click **Add or Remove Scopes** and add:
   - `https://www.googleapis.com/auth/gmail.modify`
6. Click **Update**, then **Save and Continue**.
7. On the **Test users** page (External only), add the Gmail address
   that will be monitored for Etsy order emails.
8. Click **Save and Continue**, then **Back to Dashboard**.

> **Note**: While the app is in "Testing" status, only the listed test
> users can authorize. For production use, submit the app for
> verification.

## 4. Create OAuth2 Credentials

1. Go to **APIs & Services > Credentials**.
2. Click **Create Credentials > OAuth client ID**.
3. For **Application type**, select **Web application**.
4. Enter a name (e.g., "Odoo Etsy Gmail").
5. Under **Authorized redirect URIs**, add:
   ```
   https://<your-odoo-domain>/etsy/oauth/callback
   ```
   Replace `<your-odoo-domain>` with the public URL of your Odoo
   instance. For local development this is typically:
   ```
   http://localhost:8169/etsy/oauth/callback
   ```
6. Click **Create**.
7. A dialog shows your **Client ID** and **Client Secret**. Copy both
   values -- you will need them in the next step.

> **Important**: The redirect URI must match exactly what Odoo sends
> during the OAuth flow. Odoo constructs it from the `web.base.url`
> system parameter plus `/etsy/oauth/callback`.

## 5. Configure Credentials in Odoo

1. Log in to Odoo as an administrator.
2. Navigate to **Settings** and scroll down to the **Etsy Integration**
   section (or search for "Etsy" in the settings search bar).
3. Enter the following values:
   - **Gmail Client ID**: paste the Client ID from step 4.
   - **Gmail Client Secret**: paste the Client Secret from step 4.
   - **Gmail Label**: the Gmail label applied to Etsy order emails
     (default: `ordertest2`).
4. Click **Save** to persist the credentials.

## 6. Authorize Gmail (First-Time Setup)

1. After saving the credentials, click the **Authorize Gmail** button
   in the Etsy Integration settings section.
2. You will be redirected to Google's consent screen.
3. Sign in with the Gmail account that receives Etsy order emails.
4. Review the requested permissions (`gmail.modify` -- needed to read
   emails and remove the processing label after import).
5. Click **Allow**.
6. Google redirects back to Odoo. If successful, you are returned to
   the Settings page and the refresh token is stored automatically.
7. To verify the connection, click **Test Connection**. You should see
   a success notification showing the connected email address.

### Troubleshooting Authorization

- **"No refresh token received"**: This happens when Google has already
  issued a refresh token for this app. Revoke the existing grant at
  [Google Account Permissions](https://myaccount.google.com/permissions),
  then try the Authorize Gmail flow again.
- **"redirect_uri_mismatch" error**: Ensure the redirect URI in the
  Google Cloud Console matches your Odoo `web.base.url` exactly,
  including the protocol (`http` vs `https`) and port number.
- **"Access blocked" error**: The Gmail account must be listed as a
  test user in the OAuth consent screen (see step 3.7) while the app
  is in Testing status.

## 7. How Token Refresh Works

The Etsy Integration module uses a standard OAuth2 refresh token flow:

1. **Initial authorization** (step 6) obtains both an access token and
   a refresh token. Only the refresh token is stored persistently in
   Odoo's `ir.config_parameter` at key
   `etsy_integration.gmail_refresh_token`.

2. **On each API call**, the module's `GmailClient` service sends the
   refresh token to Google's token endpoint
   (`https://oauth2.googleapis.com/token`) with `grant_type=refresh_token`
   to obtain a short-lived access token.

3. **Access tokens expire** after approximately 1 hour. The module
   requests a fresh access token before each polling cycle, so
   expiration is handled transparently.

4. **Refresh tokens do not expire** under normal conditions. However,
   they can be revoked if:
   - The user manually revokes access in Google Account settings.
   - The Google Cloud project's OAuth consent screen is reset.
   - The refresh token has not been used for 6 months (for apps in
     "Testing" status with External user type).
   - Google enforces a per-user refresh token limit (currently 100 per
     client ID) and older tokens are rotated out.

5. **If the refresh token becomes invalid**, the cron job will fail to
   authenticate and log an error. To recover:
   1. Open **Settings > Etsy Integration**.
   2. Click **Authorize Gmail** to re-authorize.
   3. A new refresh token is obtained and stored automatically.

---

## Security Considerations

- Client ID and Client Secret are stored in Odoo's `ir.config_parameter`
  table (accessible only to admin users via Settings).
- The refresh token is also stored in `ir.config_parameter`. Ensure your
  database is properly secured and backed up.
- The OAuth callback endpoint (`/etsy/oauth/callback`) requires an
  authenticated Odoo user session (`auth='user'`), preventing
  unauthorized token injection.
- The `gmail.modify` scope is the minimum required to read emails and
  manage labels. It does not grant permission to send emails on behalf
  of the user.
