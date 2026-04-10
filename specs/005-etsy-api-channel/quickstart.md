# Quickstart: Etsy API v3 Channel Integration

**Feature**: 005-etsy-api-channel | **Date**: 2026-04-10

## Prerequisites

1. Etsy Developer Account registered at https://www.etsy.com/developers/your-apps
2. Etsy application created with callback URL: `https://<your-odoo-domain>/etsy/api/oauth/callback`
3. Application keystring and shared secret noted
4. Docker environment running (`docker compose up -d`)
5. Existing `etsy_integration` module installed and working (email-based pipeline)

## Setup Steps

### 1. Configure Etsy API Credentials

1. Navigate to **Settings > Etsy Integration**
2. In the **Etsy API Configuration** section:
   - Enter the **API Key** (application keystring)
   - Enter the **Shared Secret**
3. Click **Save**

### 2. Authorize Etsy Shop

1. Open **Etsy > Shops** and select the shop to connect
2. Click **Authorize Etsy API**
3. Browser redirects to Etsy consent page
4. Approve the requested permissions (transactions, listings, shops, email)
5. On success, the shop form displays:
   - Connected Etsy user name
   - Etsy numeric shop ID
   - Token expiry countdown
6. Click **Test Connection** to verify

### 3. Set Sync Mode

1. On the shop form, set **Sync Mode**:
   - **Email Only** -- keep current email-based pipeline (default for existing shops)
   - **Dual** -- run both email and API sync with deduplication (recommended for transition)
   - **API Only** -- use only API sync (after dual mode proves reliable)
2. Click **Save**

### 4. Configure Carrier Mapping (for Tracking Push)

1. Navigate to **Etsy > Configuration > Carrier Mapping**
2. Review pre-populated mappings (USPS, FedEx, UPS, DHL)
3. Add custom mappings if needed (e.g., your logistics partner's carrier name -> Etsy carrier name)

### 5. Configure Webhooks (Optional, for Real-Time Events)

1. Go to Etsy Developer Portal > Your App > Webhook Portal
2. Click **+Add Endpoint**
3. Enter callback URL: `https://<your-odoo-domain>/etsy/webhook/callback`
4. Select events: `order.paid`, `order.shipped`, `order.canceled`, `order.delivered`
5. Copy the webhook signing secret
6. In Odoo, open the shop form and paste the **Webhook Secret**

### 6. Verify Order Sync

1. Wait for the next API sync cron run (every 5 minutes) or trigger manually:
   - **Etsy > Shops > [Shop] > Sync Orders Now**
2. Check **Etsy > API Logs** for successful API calls
3. Verify new orders appear in **Sales > Orders** with sync source "API"

### 7. Verify Tracking Push

1. Open an Etsy sale order with a tracking number
2. Click **Push Tracking to Etsy** (or wait for the tracking push cron)
3. Verify tracking push status changes to "Pushed"
4. Confirm on Etsy Seller Portal that tracking is visible

## Scheduled Actions

After setup, these crons run automatically:

| Action | Interval | Description |
|--------|----------|-------------|
| Etsy: API Order Sync | 5 min | Fetches new/updated receipts from Etsy |
| Etsy: Push Tracking | 5 min | Pushes pending tracking numbers to Etsy |
| Etsy: Listing Sync | 60 min | Pulls listing state updates from Etsy |
| Etsy: Cleanup API Logs | 1 day | Removes logs older than retention period |

## Troubleshooting

### Token Refresh Failed
- Check **Etsy > API Logs** for 401 errors
- If refresh token expired (>90 days), re-authorize: Shop > Authorize Etsy API
- System auto-falls back to email sync if in dual mode

### Rate Limit Exceeded
- Check **Etsy > API Logs** for 429 errors
- System auto-waits and retries based on `retry-after` header
- If persistent, increase sync interval in Settings

### Tracking Push Failed
- Open the sale order, check **Tracking Push Error** field
- Common issue: carrier name not recognized by Etsy
- Fix: add/update carrier mapping in **Etsy > Configuration > Carrier Mapping**
- Click **Retry Tracking Push**

### Webhook Events Not Arriving
- Verify server is accessible from internet (Etsy must reach your callback URL)
- Check **Etsy > Webhook Events** for received events
- If no events, verify webhook registration in Etsy Developer Portal
- Webhooks are optional -- cron sync continues regardless

## Development Setup

For local development with webhooks:

1. Use a tunnel service (e.g., ngrok) to expose local Odoo:
   ```
   ngrok http 8169
   ```
2. Use the ngrok URL as the webhook callback in Etsy Developer Portal
3. Set the OAuth callback URL to the ngrok URL as well

For testing without webhooks, cron-based sync works with any local setup.
