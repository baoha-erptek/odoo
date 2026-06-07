/**
 * UAT Wave 2/3 — Listings list-view bulk-action (TC-W23-BULK-01)
 *
 * Covers ESTY-197 / P-LIST-SHOP-BULK:
 *   - server action_bulk_mark_ready (Draft → Ready)
 *   - server action_bulk_reset_to_draft (Ready/Error → Draft)
 * Both registered as ir.actions.server with binding_view_types=list on
 * multichannel.listing — they appear in the Actions ⚙ dropdown.
 *
 * Strategy: pre-seed 2 fresh draft multichannel.listing rows via RPC (tagged
 * with title prefix [UAT-2026-06-07] so cleanup can find them), select both
 * in the list, run each bulk action, verify state via RPC.
 *
 * Safe — no Etsy calls, no published rows touched. Listings auto-cleanup at
 * end of test.
 *
 * Verified against staging mhc 19.0.1.0.64+ / etsy_integration 19.0.3.8.0+.
 */
import { test, expect } from '@playwright/test';
import { loginAsAdmin } from '../fixtures/odoo-auth';
import { CONFIG } from '../fixtures/env';

const TAG = '[UAT-2026-06-07]';

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

async function getEtsyChannelId(request: import('@playwright/test').APIRequestContext): Promise<number> {
  // multichannel.sales.channel — find the Etsy channel id (used as listing.channel_id).
  const ids = await rpc(request, 'multichannel.sales.channel', 'search', [[['code', '=', 'etsy']]]);
  expect(ids?.length, 'Etsy sales-channel record exists').toBeGreaterThan(0);
  return ids[0];
}

async function getAnyProductTmplId(request: import('@playwright/test').APIRequestContext): Promise<number> {
  // Pick any existing product.template to satisfy listing.product_tmpl_id FK.
  const ids = await rpc(request, 'product.template', 'search', [[['active', '=', true]]], { limit: 1 });
  expect(ids?.length, 'at least one product.template exists').toBeGreaterThan(0);
  return ids[0];
}

test.describe('UAT Wave 2/3 — Listings bulk-action (ESTY-197)', () => {
  test('TC-W23-BULK-01 — Mark Ready + Reset to Draft cycle on 2 listings', async ({ page, request }) => {
    test.setTimeout(90000);
    await loginAsAdmin(page);

    // --- pre-seed 2 draft rows ---------------------------------------------
    const channelId = await getEtsyChannelId(request);
    const tmplId = await getAnyProductTmplId(request);
    const t = Date.now().toString(36).slice(-5).toUpperCase();
    const titles = [`${TAG} bulk-row-A-${t}`, `${TAG} bulk-row-B-${t}`];

    const ids: number[] = [];
    for (const title of titles) {
      const id = await rpc(request, 'multichannel.listing', 'create', [{
        product_tmpl_id: tmplId, channel_id: channelId,
        shop_ref: 'jahandmadeart', title, state: 'draft',
      }]);
      ids.push(id);
    }
    console.log(`[BULK-01] seeded draft listing ids=${ids.join(',')} titles="${titles.join(' | ')}"`);

    // --- navigate to the Listings list view --------------------------------
    await page.goto('/odoo/action-multichannel_hub_core.action_multichannel_listing');
    await page.waitForSelector('.o_list_view', { timeout: 15000 });

    // Search for our [UAT-2026-06-07] tag to scope the list (default filter
    // shows draft+ready grouped by shop_ref; the search input is forgiving).
    const searchInput = page.locator('.o_searchview_input').first();
    await searchInput.click();
    await searchInput.fill(TAG);
    await searchInput.press('Enter');
    await page.waitForTimeout(800);

    // Two rows expected. If grouped, ungroup first.
    const ungroupBtn = page.locator('.o_searchview_facet_remove').first();
    while (await ungroupBtn.count() > 0 && /Shop|Channel|State/i.test(await page.locator('.o_searchview_facet').first().textContent() || '')) {
      await ungroupBtn.click();
      await page.waitForTimeout(200);
    }

    // Select all rows via the header checkbox.
    const headerCheckbox = page.locator('.o_list_view thead .o_list_record_selector input').first();
    await headerCheckbox.waitFor({ state: 'visible', timeout: 8000 });
    await headerCheckbox.click();
    await page.waitForTimeout(300);

    // --- Action 1: Mark Ready for Publish ----------------------------------
    const actionsBtn = page.locator('.o_cp_action_menus button:has-text("Actions"), .o_control_panel button:has-text("Actions")').first();
    await actionsBtn.waitFor({ state: 'visible', timeout: 8000 });
    await actionsBtn.click();
    const markReadyItem = page.locator('.dropdown-item, .o-dropdown--menu-item', { hasText: /Mark Ready for Publish/ }).first();
    await markReadyItem.waitFor({ state: 'visible', timeout: 5000 });
    await markReadyItem.click();
    await page.waitForTimeout(1500); // server action + notification

    // Verify via RPC.
    let rows = await rpc(request, 'multichannel.listing', 'read', [ids, ['state']]);
    expect(rows.every((r: any) => r.state === 'ready'),
      `all rows ready after bulk mark — got ${JSON.stringify(rows)}`).toBe(true);
    console.log(`[BULK-01] mark-ready PASS — ${ids.length} rows ready`);

    // --- Action 2: Reset to Draft ------------------------------------------
    await headerCheckbox.click(); // re-select (Odoo clears selection after action)
    await page.waitForTimeout(200);
    if (!(await headerCheckbox.isChecked())) await headerCheckbox.click();
    await page.waitForTimeout(200);

    await actionsBtn.click();
    const resetItem = page.locator('.dropdown-item, .o-dropdown--menu-item', { hasText: /Reset to Draft/ }).first();
    await resetItem.waitFor({ state: 'visible', timeout: 5000 });
    await resetItem.click();
    await page.waitForTimeout(1500);

    rows = await rpc(request, 'multichannel.listing', 'read', [ids, ['state']]);
    expect(rows.every((r: any) => r.state === 'draft'),
      `all rows draft after bulk reset — got ${JSON.stringify(rows)}`).toBe(true);
    console.log(`[BULK-01] reset-to-draft PASS — ${ids.length} rows back to draft`);

    // --- cleanup -----------------------------------------------------------
    await rpc(request, 'multichannel.listing', 'unlink', [ids]);
    console.log(`[BULK-01] cleanup — unlinked seeded listings`);
  });
});
