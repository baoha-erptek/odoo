/**
 * UAT — Real catalog product end-to-end (TC-R01)
 *
 * Owner-requested 2026-05-28: take a REAL product from the 2025 Product Catalog
 * (`.0temp/raw/[2025] Product Catalog.xlsx`), create it in Odoo via the genuine
 * standard-form flow with its variant attributes and MORE THAN ONE real image,
 * then publish it to Etsy (JaHandmadeArt) as a complete, sellable DRAFT.
 *
 * Differs from uat_huong_dan_tao_san_pham.spec.ts (synthetic seed data, image
 * upload skipped as headless-fragile): this uses the Black/White Apron `APF`
 * (Apparel sheet row 5) and its 2 embedded catalog photos. Multi-image upload is
 * done via JSON-RPC (Odoo lazy-renders the Extra Images grid; UI binary upload is
 * unreliable headless) — the genuine "Publish to Etsy → Run Publish Draft Only"
 * wizard then pushes main + gallery to Etsy via EtsyListingPublisher.upload_images.
 *
 * Gated behind RUN_ETSY_PUBLISH=1 (creates a real JaHandmadeArt draft — no fee,
 * not buyer-visible). JaHandmadeArt is a VND shop: set E2E_LISTING_PRICE>=250000
 * or createListing 400s "price too low".
 *
 * Verified against staging mhc 19.0.1.0.63 / etsy_integration 19.0.2.26.0.
 */
import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { test, expect } from '@playwright/test';
import { loginAsBaLead } from '../fixtures/odoo-auth';
import { ProductFormPage } from '../page-objects/product_form';
import { CONFIG } from '../fixtures/env';

const RUN_ETSY = process.env.RUN_ETSY_PUBLISH === '1';
const LIVE_PRICE = Number(process.env.E2E_LISTING_PRICE || 250000);
const ASSETS = join(__dirname, '..', 'fixtures', 'assets');

function uniq(stem: string): string {
  return `${stem}-${Date.now().toString(36).slice(-5).toUpperCase()}`;
}

function asset(name: string): string {
  // The .b64 files are pre-extracted by fixtures/extract_catalog_images.py.
  return readFileSync(join(ASSETS, name), 'utf-8').trim();
}

/** JSON-RPC helper: authenticate (admin) and call a model method. */
async function rpc(
  request: import('@playwright/test').APIRequestContext,
  model: string,
  method: string,
  args: unknown[],
  kwargs: Record<string, unknown> = {},
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

/** Poll product.channel.status (by template id) until external_ref is truthy. */
async function pollExternalRefByTmpl(
  request: import('@playwright/test').APIRequestContext,
  tmplId: number,
  timeoutMs = 20000,
): Promise<{ state: string; external_ref: string | false } | null> {
  const deadline = Date.now() + timeoutMs;
  let last: { state: string; external_ref: string | false } | null = null;
  do {
    const rows = await rpc(request, 'product.channel.status', 'search_read',
      [[['product_tmpl_id', '=', tmplId]]], { fields: ['state', 'external_ref'], limit: 1 });
    last = rows?.[0] ?? null;
    if (last?.external_ref) return last;
    await new Promise((r) => setTimeout(r, 1000));
  } while (Date.now() < deadline);
  return last;
}

test.describe('UAT Real Product — Apron APF → Etsy draft', () => {
  test('TC-R01 — real catalog apron (variants + 2 images) → publish draft to Etsy', async ({ page, request }) => {
    test.skip(!RUN_ETSY, 'Live Etsy draft publish — set RUN_ETSY_PUBLISH=1 to run.');
    // Image fixtures are gitignored (~1MB base64). Regenerate if absent:
    //   python3 fixtures/extract_catalog_images.py --sheet Apparel --row 5 --prefix apf
    test.skip(
      !existsSync(join(ASSETS, 'apf_main.b64')) || !existsSync(join(ASSETS, 'apf_extra1.b64')),
      'Catalog image assets missing — run fixtures/extract_catalog_images.py --sheet Apparel --row 5 --prefix apf',
    );
    test.setTimeout(180000);

    const name = uniq('UAT Real Apron APF');
    const f = new ProductFormPage(page);
    await loginAsBaLead(page);

    // --- create via the real standard product form -------------------------
    await f.openNew();
    await f.fillName(name);
    await f.selectCategory('Apron');                  // auto-SKU derives APR-...
    await f.addVariantAttribute('Material', 'Textile');        // drives materials[]=['Textile']
    await f.addVariantAttribute('Apparel Size', 'Medium');     // APR family is apparel-size-gated
    await f.addVariantAttribute('Color', ['Black', 'White']);  // 2 colors -> 2 variants
    await f.fillListPrice(LIVE_PRICE);
    await f.addChannel('Etsy');
    await f.fillWeight(0.40);
    // who_made / when_made / taxonomy come from the JaHandmadeArt shop defaults
    // (publisher falls back to them); no per-product Listing Defaults needed.
    await f.save();

    const sku = await f.readSku();
    console.log(`[TC-R01] created product "${name}" sku=${sku}`);

    // --- inject the 2 real catalog images via JSON-RPC ---------------------
    const tids = await rpc(request, 'product.template', 'search', [[['name', '=', name]]]);
    expect(tids?.length, 'product.template should exist after save').toBeGreaterThan(0);
    const tmplId = tids[0];

    await rpc(request, 'product.template', 'write', [[tmplId], { image_1920: asset('apf_main.b64') }]);
    await rpc(request, 'product.template', 'write', [[tmplId], {
      x_extra_image_ids: [[0, 0, { image_1920: asset('apf_extra1.b64'), sequence: 10, name: 'APF extra 1' }]],
    }]);

    // confirm Odoo side: main image present + 1 gallery row
    const [tmpl] = await rpc(request, 'product.template', 'read', [[tmplId], ['image_1920', 'x_extra_image_ids']]);
    expect(Boolean(tmpl.image_1920), 'main image_1920 set').toBeTruthy();
    expect(tmpl.x_extra_image_ids.length, 'one extra gallery image').toBe(1);

    // --- publish a DRAFT via the genuine wizard ----------------------------
    await f.publishDraftOnly('JaHandmadeArt');

    // --- verify the Etsy listing id propagated -----------------------------
    const status = await pollExternalRefByTmpl(request, tmplId);
    expect(status, 'channel.status row exists').not.toBeNull();
    expect(status!.external_ref, 'Etsy listing_id populated').toBeTruthy();
    expect(String(status!.external_ref)).toMatch(/^\d+$/);
    console.log(`[TC-R01] published Etsy draft listing_id=${status!.external_ref} (state=${status!.state})`);
    console.log(`[TC-R01] verify in Shop Manager: https://www.etsy.com/your/shops/jahandmadeart/tools/listings/drafts`);
  });
});
