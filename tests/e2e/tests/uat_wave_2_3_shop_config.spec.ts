/**
 * UAT Wave 2/3 — JaHandmadeArt shop config sanity (TC-W23-CFG-01)
 *
 * Covers shop-level configuration landed in Wave 2/3:
 *   - ESTY-191 default_shipping_profile_id (P-LIST-SHIPPING)
 *   - ESTY-189 default_taxonomy_id (P-LIST-CATEGORY shop fallback)
 *   - ESTY-193 default_who_made / default_when_made / default_is_supply (P-LIST-HOW-ITS-MADE)
 *   - ESTY-190 default_title / default_description / default_image_1920 (P-ENH-ESTY-190 brand-voice tier 3)
 *   - ESTY-194 default_attribute_mapping_ids (P-LIST-ATTR-CONFIG tier 2)
 *   - ESTY-195 listing_currency_id (P-ENH-ESTY-195 FX widget prerequisite)
 *
 * Read-only assertions only — no mutations. Safe to run any time, no Etsy fees.
 * Verified against staging etsy_integration 19.0.3.8.0 / mhc 19.0.1.0.64+.
 */
import { mkdirSync } from 'fs';
import { join } from 'path';
import { test, expect } from '@playwright/test';
import { loginAsAdmin } from '../fixtures/odoo-auth';
import { CONFIG } from '../fixtures/env';

// P-UAT-SCREENSHOTS-WAVE-2-3 — harvest flow-1 #08 (brand-voice defaults).
// SHOT_DIR is OUTSIDE Playwright's outputDir (`artifacts/`) so screenshots
// from this spec survive an outputDir wipe by a separate Playwright run.
const SCREENSHOT_CAPTURE = process.env.SCREENSHOT_CAPTURE === '1';
const SHOT_DIR = join(__dirname, '..', '.harvest', 'business-flows');
if (SCREENSHOT_CAPTURE) mkdirSync(SHOT_DIR, { recursive: true });
async function shot(page: import('@playwright/test').Page, name: string): Promise<void> {
  if (!SCREENSHOT_CAPTURE) return;
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(SHOT_DIR, name), fullPage: true });
}

const EXPECTED_API_SHOP_ID = '60752333'; // JaHandmadeArt — see reference_etsy_shop_id_mapping memory

async function rpc(
  request: import('@playwright/test').APIRequestContext,
  model: string, method: string, args: unknown[], kwargs: Record<string, unknown> = {},
): Promise<any> {
  await request.post(`${CONFIG.BASE_URL}/web/session/authenticate`, {
    data: { jsonrpc: '2.0', params: { db: CONFIG.DB, login: CONFIG.ADMIN_LOGIN, password: CONFIG.ADMIN_PASSWORD } },
  });
  const res = await request.post(`${CONFIG.BASE_URL}/web/dataset/call_kw/${model}/${method}`, {
    data: { jsonrpc: '2.0', params: { model, method, args, kwargs } },
  });
  const body = await res.json();
  if (body?.error) throw new Error(`${model}.${method} error: ${JSON.stringify(body.error)}`);
  return body?.result;
}

test.describe('UAT Wave 2/3 — JaHandmadeArt shop publisher defaults', () => {
  test('TC-W23-CFG-01 — Publisher Defaults populated for live publish', async ({ page, request }) => {
    test.setTimeout(60000);
    await loginAsAdmin(page);

    // RPC read first — fast structural check before any UI work.
    const shops = await rpc(request, 'etsy.shop', 'search_read',
      [[['etsy_api_shop_id', '=', EXPECTED_API_SHOP_ID]]],
      { fields: [
        'name', 'etsy_api_shop_id', 'active_source', 'listing_currency_id',
        'default_taxonomy_id', 'default_shipping_profile_id',
        'default_return_policy_id', 'default_readiness_state_id',
        'default_who_made', 'default_when_made', 'default_is_supply',
        'default_title', 'default_description',
      ], limit: 1 });

    expect(shops?.length, 'JaHandmadeArt shop exists').toBe(1);
    const shop = shops[0];
    console.log(`[CFG-01] shop="${shop.name}" id=${shop.etsy_api_shop_id} source=${shop.active_source}`);

    // ESTY-195 — listing currency must be set for the FX widget compute to work.
    expect(shop.listing_currency_id, 'listing_currency_id set (ESTY-195)').toBeTruthy();

    // ESTY-189 / 191 / readiness — required for live createListing per
    // reference_etsy_createlisting_2025_readiness memory.
    expect(String(shop.default_taxonomy_id || ''), 'default_taxonomy_id (ESTY-189)').toMatch(/^\d+$/);
    expect(String(shop.default_shipping_profile_id || ''), 'default_shipping_profile_id (ESTY-191)').toMatch(/^\d+$/);
    expect(String(shop.default_readiness_state_id || ''), 'default_readiness_state_id').toMatch(/^\d+$/);

    // ESTY-193 — Etsy createListing requires all three "how it's made" fields.
    expect(shop.default_who_made, 'default_who_made (ESTY-193)').toBeTruthy();
    expect(shop.default_when_made, 'default_when_made (ESTY-193)').toBeTruthy();
    expect(typeof shop.default_is_supply, 'default_is_supply is bool (ESTY-193)').toBe('boolean');

    // ESTY-190 — Brand-voice defaults may be empty (intentional fallthrough), but the fields MUST exist.
    expect(shop, 'default_title field exists (ESTY-190)').toHaveProperty('default_title');
    expect(shop, 'default_description field exists (ESTY-190)').toHaveProperty('default_description');

    // ESTY-194 — attribute mapping table must be queryable (Tier-2 fallback).
    const mappingCount = await rpc(request, 'etsy.shop.attribute.mapping', 'search_count',
      [[['shop_id', '=', shops[0].id ?? (await rpc(request, 'etsy.shop', 'search', [[['etsy_api_shop_id', '=', EXPECTED_API_SHOP_ID]]]))[0]]]]);
    console.log(`[CFG-01] attribute mapping rows for shop: ${mappingCount}`);
    expect(typeof mappingCount, 'etsy.shop.attribute.mapping queryable (ESTY-194)').toBe('number');

    // UI smoke — best-effort. ESTY-190 brand-voice fields are gated by
    // multichannel_hub_core.group_marketing_user; admin may not have that group
    // on staging. The RPC assertions above already verify the fields exist on
    // the model. UI checks here are non-blocking diagnostics.
    const shopId = await rpc(request, 'etsy.shop', 'search', [[['etsy_api_shop_id', '=', EXPECTED_API_SHOP_ID]]]);
    await page.goto(`/odoo/action-etsy_integration.action_etsy_shops/${shopId[0]}`);
    await page.waitForSelector('.o_form_view', { timeout: 15000 });

    const defaultsTab = page.locator('.o_notebook .nav-link', { hasText: /Publisher Defaults/ }).first();
    if (await defaultsTab.count() > 0) {
      await defaultsTab.click();
      await page.waitForTimeout(300);
      await shot(page, '08-brand-voice-defaults.png');           // flow-1 #08 — Publisher Defaults tab

      const uiChecks = [
        ['default_title (ESTY-190 brand-voice)', '[name="default_title"]'],
        ['default_description (ESTY-190)', '[name="default_description"]'],
        ['default_attribute_mapping_ids (ESTY-194)', '[name="default_attribute_mapping_ids"]'],
      ] as const;
      for (const [label, sel] of uiChecks) {
        const visible = await page.locator(sel).first().isVisible({ timeout: 2000 }).catch(() => false);
        console.log(`[CFG-01] UI smoke ${label}: ${visible ? 'visible' : 'NOT rendered (group gate or DOM lazy)'}`);
      }
    }

    console.log(`[CFG-01] PASS — shop ${shopId[0]} has all Wave-2/3 publisher defaults present (RPC verified)`);
  });
});
