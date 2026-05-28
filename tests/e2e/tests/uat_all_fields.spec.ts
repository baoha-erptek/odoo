/**
 * UAT Round 2 — Full Etsy listing-field coverage (TC-ALL-01, TC-ALL-02)
 *
 * Owner-requested 2026-05-28: exercise EVERY attribute Etsy's create-listing
 * flow supports, verified against the LIVE Etsy draft (not just Odoo state).
 * The verification engine is fixtures/verify_etsy_listing.py (server-side Etsy
 * readback); this spec creates + publishes the products it inspects.
 *
 * Coverage is split across two products to keep each SKU canonical and each
 * Etsy listing within the 2-variation limit:
 *   TC-ALL-01 (Apron): title, description, price, qty, who/when, taxonomy,
 *     tags, materials, weight, personalization, 2 images, and 2 real Etsy
 *     VARIATIONS (Color Black/White — dynamic axis materialized by Slice B).
 *   TC-ALL-02 (Doormat): item_length/width/HEIGHT via a 3D rect Size
 *     "R30X18X2" (Slice A).
 *
 * Gated behind RUN_ETSY_PUBLISH=1 (real JaHandmadeArt drafts, no fee). VND shop:
 * E2E_LISTING_PRICE>=250000. Verified against mhc 19.0.1.0.64 / etsy 19.0.2.29.0.
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
  return readFileSync(join(ASSETS, name), 'utf-8').trim();
}

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

async function tmplIdByName(request: import('@playwright/test').APIRequestContext, name: string): Promise<number> {
  const ids = await rpc(request, 'product.template', 'search', [[['name', '=', name]]]);
  expect(ids?.length, `product.template ${name} exists`).toBeGreaterThan(0);
  return ids[0];
}

async function injectImages(
  request: import('@playwright/test').APIRequestContext, tmplId: number, main: string, extras: string[],
): Promise<void> {
  await rpc(request, 'product.template', 'write', [[tmplId], { image_1920: main }]);
  if (extras.length) {
    await rpc(request, 'product.template', 'write', [[tmplId], {
      x_extra_image_ids: extras.map((b64, i) => [0, 0, { image_1920: b64, sequence: (i + 1) * 10 }]),
    }]);
  }
}

async function pollExternalRef(
  request: import('@playwright/test').APIRequestContext, tmplId: number, timeoutMs = 20000,
): Promise<string> {
  const deadline = Date.now() + timeoutMs;
  do {
    const rows = await rpc(request, 'product.channel.status', 'search_read',
      [[['product_tmpl_id', '=', tmplId]]], { fields: ['external_ref'], limit: 1 });
    if (rows?.[0]?.external_ref) return String(rows[0].external_ref);
    await new Promise((r) => setTimeout(r, 1000));
  } while (Date.now() < deadline);
  throw new Error('external_ref not populated within timeout');
}

test.describe('UAT Round 2 — full Etsy field coverage', () => {
  test.beforeEach(() => {
    test.skip(!RUN_ETSY, 'Live Etsy draft publish — set RUN_ETSY_PUBLISH=1 to run.');
    test.skip(
      !existsSync(join(ASSETS, 'apf_main.b64')) || !existsSync(join(ASSETS, 'apf_extra1.b64')),
      'Image assets missing — run fixtures/extract_catalog_images.py --sheet Apparel --row 5 --prefix apf',
    );
  });

  test('TC-ALL-01 — Apron: variations + materials + personalization + 2 images', async ({ page, request }) => {
    test.setTimeout(180000);
    const name = uniq('UAT AllFields Apron');
    const f = new ProductFormPage(page);
    await loginAsBaLead(page);

    await f.openNew();
    await f.fillName(name);
    await f.selectCategory('Apron');
    await f.addVariantAttribute('Material', 'Textile');           // -> materials[]
    await f.addVariantAttribute('Apparel Size', 'Medium');        // fixed property
    await f.addVariantAttribute('Color', ['Black', 'White']);     // 2 Etsy variations
    await f.fillListPrice(LIVE_PRICE);
    await f.addChannel('Etsy');
    await f.fillWeight(0.40);
    await f.addTags(['uat-tag-01', 'uat-tag-02', 'uat-tag-03']);
    await f.setPersonalization({ enable: true, required: true, charCount: 120, instructions: 'Name to print' });
    await f.save();

    const tmplId = await tmplIdByName(request, name);
    await injectImages(request, tmplId, asset('apf_main.b64'), [asset('apf_extra1.b64')]);
    await f.publishDraftOnly('JaHandmadeArt');

    const ref = await pollExternalRef(request, tmplId);
    expect(ref).toMatch(/^\d+$/);
    console.log(`[TC-ALL-01] name="${name}" listing_id=${ref}`);
  });

  test('TC-ALL-02 — Doormat: item dimensions + height (R30X18X2)', async ({ page, request }) => {
    test.setTimeout(180000);
    const name = uniq('UAT AllFields Doormat');
    const f = new ProductFormPage(page);
    await loginAsBaLead(page);

    await f.openNew();
    await f.fillName(name);
    await f.selectCategory('Doormat');
    await f.addVariantAttribute('Material', 'Textile');
    await f.addVariantAttribute('Size', 'R30X18X2');              // -> length/width/height
    await f.fillListPrice(LIVE_PRICE);
    await f.addChannel('Etsy');
    await f.fillWeight(0.50);
    await f.save();

    const tmplId = await tmplIdByName(request, name);
    await injectImages(request, tmplId, asset('apf_main.b64'), []);
    await f.publishDraftOnly('JaHandmadeArt');

    const ref = await pollExternalRef(request, tmplId);
    expect(ref).toMatch(/^\d+$/);
    console.log(`[TC-ALL-02] name="${name}" listing_id=${ref}`);
  });
});
