/**
 * UAT — HUONG_DAN_TAO_SAN_PHAM_VN.md v1.2  (ESTY-183)
 *
 * v1.2 (2026-05-28) retired the creation wizards. Products are created on the
 * STANDARD product.template form; SKU auto-derives from categ_id + variants.
 * This suite maps TC-001..TC-015 from §9 of the guide onto that form.
 *
 * Verified against staging mhc 19.0.1.0.60 / etsy_integration 19.0.2.24.0.
 *
 * Live-Etsy TCs (real draft listings on JaHandmadeArt, no fee) are gated behind
 * RUN_ETSY_PUBLISH=1 so the form-only subset runs fast and offline-of-Etsy.
 *
 * Known v1.2 doc/impl drift captured inline + in docs/owner/UAT_FINDINGS_2026-05-28.md:
 *   - TC-007: the ">0" price floor was a WIZARD-only validator; the standard
 *     product.template has NO such constrains(). Price 0 saves. Etsy enforces
 *     $0.20 at push time. This TC asserts actual form behaviour (saves) and
 *     flags the drift rather than testing a check that no longer exists.
 */
import { test, expect } from '@playwright/test';
import { loginAsBaLead, loginAsBaUser } from '../fixtures/odoo-auth';
import { ProductFormPage } from '../page-objects/product_form';
import { CONFIG } from '../fixtures/env';

const RUN_ETSY = process.env.RUN_ETSY_PUBLISH === '1';
const NAME = 'UAT-TAOSP';
// JaHandmadeArt is a VND shop (Etsy min ~5,043 VND). Live-publish TCs must use a
// shop-currency-appropriate price or createListing 400s ("price too low").
// Form-only TCs use their own small values (they never publish).
const LIVE_PRICE = Number(process.env.E2E_LISTING_PRICE || 250000);

function uniq(stem: string): string {
  // Lowercase on purpose: Etsy's createListing title validator rejects
  // titles where >3 hyphen/space-separated tokens start with 2 sequential
  // capitals ("all_caps" 400, seen 2026-07-04). NAME's "UAT-TAOSP" already
  // contributes 2 caps tokens; the uniq suffix must not add more.
  return `${stem}-${Date.now().toString(36).slice(-5)}`.toLowerCase();
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

async function channelStatus(
  request: import('@playwright/test').APIRequestContext,
  defaultCode: string,
): Promise<{ state: string; external_ref: string | false } | null> {
  // Newest-first: attribute-less Mug TCs (TC-002/TC-007) auto-derive the
  // same category-level SKU 'MUG', so an unordered search resolves an older
  // sibling whose channel.status has no external_ref (2026-07-04 MF-E2E-1).
  const tids = await rpc(request, 'product.template', 'search',
    [[['default_code', '=', defaultCode]]], { order: 'id desc', limit: 1 });
  if (!tids?.length) return null;
  const rows = await rpc(request, 'product.channel.status', 'search_read',
    [[['product_tmpl_id', '=', tids[0]]]], { fields: ['state', 'external_ref'], limit: 1 });
  return rows?.[0] ?? null;
}

/**
 * Poll channel.status until `external_ref` is populated. The publish RPC returns
 * before the listing id is necessarily committed/propagated to the status row, so
 * a single read races (intermittent TC-013 failure). Re-query until truthy or
 * timeout, then return the last row for assertion.
 */
async function pollExternalRef(
  request: import('@playwright/test').APIRequestContext,
  defaultCode: string,
  timeoutMs = 15000,
): Promise<{ state: string; external_ref: string | false } | null> {
  const deadline = Date.now() + timeoutMs;
  let last: { state: string; external_ref: string | false } | null = null;
  do {
    last = await channelStatus(request, defaultCode);
    if (last?.external_ref) return last;
    await new Promise((r) => setTimeout(r, 1000));
  } while (Date.now() < deadline);
  return last;
}

test.describe('ESTY-183 — HUONG_DAN_TAO_SAN_PHAM_VN v1.2 (standard form)', () => {

  test('TC-001 — Tạo Mug bằng form chuẩn; SKU tự sinh MUG-CR-F11', async ({ page }) => {
    await loginAsBaLead(page);
    const f = new ProductFormPage(page);
    await f.openNew();
    await f.fillName(`${NAME} Mug 2026 ${uniq('001')}`);
    await f.selectCategory('Mug');
    await f.addVariantAttribute('Material', 'Ceramic + Chrome');
    // "11 oz" lives on the "Fluid oz" attribute (mug SIZE-slot), not "Size".
    await f.addVariantAttribute('Fluid oz', '11 oz');
    expect(await f.readSku()).toBe('MUG-CR-F11');
    await f.fillListPrice(12.99);
    await f.addChannel('Etsy');
    await f.save();
    await f.openTab(/Channels|Kênh/);
    const list = page.locator('[name="x_sales_channel_status_ids"]');
    await expect(list).toContainText(/Etsy/i, { timeout: 8000 });
    await expect(list).toContainText(/draft|Draft|Nháp/i);
  });

  test('TC-002 — Mã SKU Gearment → chế độ Dropship', async ({ page }) => {
    await loginAsBaLead(page);
    const f = new ProductFormPage(page);
    await f.openNew();
    const gsku = `GEAR-${uniq('002')}`;
    await f.fillName(`${NAME} Dropship Mug ${gsku}`);
    await f.selectCategory('Mug');
    await f.fillListPrice(19.99);
    await f.fillGearmentSku(gsku);
    await f.addChannel('Etsy');
    await f.save();
    await expect(page.locator('[name="x_gearment_sku"] input')).toHaveValue(gsku);
  });

  test('TC-003 — SKU Drift "Keep Legacy"', async ({ page }) => {
    test.skip(true, 'Requires a seeded legacy-SKU product (x_sku_v2_status=non_canonical). ' +
      'Provided by fixtures/seed_uat_data.py; enable once seed runs in globalSetup.');
  });

  test('TC-004 — SKU Drift "Accept Canonical" (published product)', async ({ page }) => {
    test.skip(true, 'Requires a published Etsy product with legacy SKU + live inventory push. ' +
      'Seed + owner-approved live run only.');
  });

  test('TC-005 — Đăng Draft lên Etsy', async ({ page, request }) => {
    test.skip(!RUN_ETSY, 'Live Etsy draft publish — set RUN_ETSY_PUBLISH=1 to run.');
    await loginAsBaLead(page);
    const f = new ProductFormPage(page);
    await f.openNew();
    const sku = uniq('TC005-MUG');
    await f.fillName(`${NAME} Publish ${sku}`);
    await f.selectCategory('Mug');
    await f.fillListPrice(LIVE_PRICE);
    await f.addChannel('Etsy');
    await f.save();
    const code = await f.readSku();
    await f.publishDraftOnly();
    const st = await channelStatus(request, code);
    expect(st, `channel.status for ${code}`).not.toBeNull();
    expect(st!.external_ref, 'Etsy listing id present').toBeTruthy();
  });

  test('TC-006 — BA User thấy nút "Publish to Etsy"', async ({ page }) => {
    test.skip(!CONFIG.BA_USER_PASSWORD,
      'BA User seed unavailable — needs seed_ba_user.py (STAGING_ADMIN_PASSWORD).');
    await loginAsBaUser(page);
    await page.goto('/odoo/inventory/products');
    await page.waitForSelector('.o_list_view, .o_kanban_view', { timeout: 15000 });
    await page.locator('.o_list_view tbody tr.o_data_row, .o_kanban_record').first().click();
    await page.waitForSelector('.o_form_view', { timeout: 10000 });
    const btn = page.locator('button[name="action_open_etsy_publish_wizard"]');
    await expect(btn).toBeVisible();
  });

  test('TC-007 — Giá: form chuẩn KHÔNG chặn giá 0 (drift vs doc)', async ({ page }) => {
    // DRIFT: the ">0" floor lived only in the retired wizard. The standard
    // product.template has no list_price constrains; price 0 saves. Etsy
    // enforces the $0.20 floor at push. Assert actual behaviour + flag.
    await loginAsBaLead(page);
    const f = new ProductFormPage(page);
    await f.openNew();
    await f.fillName(`${NAME} ZeroPrice ${uniq('007')}`);
    await f.selectCategory('Mug');
    await f.fillListPrice(0);
    await f.addChannel('Etsy');
    await f.save();
    // No error modal; record persists with price 0.
    await expect(f.errorModal).toHaveCount(0);
    await f.openGeneralTab();
    await expect(page.locator('[name="list_price"] input')).toHaveValue(/0(\.0+)?/);
  });

  test('TC-008 — Tags: 13 ok / 14th & 21-char bị chặn', async ({ page }) => {
    test.skip(true, 'Needs >=15 pre-seeded product.tag records (field is no_create_edit). ' +
      'Enable once fixtures/seed_uat_data.py seeds uat-tag-01..15 + a 21-char tag.');
  });

  test('TC-009 — Cá nhân hoá bật+bắt buộc+256 → publish draft', async ({ page, request }) => {
    test.skip(!RUN_ETSY, 'Live Etsy draft publish — set RUN_ETSY_PUBLISH=1 to run.');
    await loginAsBaLead(page);
    const f = new ProductFormPage(page);
    await f.openNew();
    const sku = uniq('TC009-MUG');
    await f.fillName(`${NAME} Personalize ${sku}`);
    await f.selectCategory('Mug');
    await f.fillListPrice(LIVE_PRICE);
    await f.addChannel('Etsy');
    await f.setPersonalization({ enable: true, required: true, charCount: 256, instructions: 'Khắc tên lên cốc' });
    await f.save();
    const code = await f.readSku();
    await f.publishDraftOnly();
    const st = await channelStatus(request, code);
    expect(st?.external_ref, 'listing id present').toBeTruthy();
    // Etsy-side personalization field verification is manual (Shop Manager).
  });

  test('TC-010 — Cá nhân hoá char_count ngoài dải 1..1024 → lỗi', async ({ page }) => {
    await loginAsBaLead(page);
    const f = new ProductFormPage(page);
    await f.openNew();
    await f.fillName(`${NAME} CharRange ${uniq('010')}`);
    await f.selectCategory('Mug');
    await f.fillListPrice(10.0);
    await f.addChannel('Etsy');
    await f.setPersonalization({ enable: true, charCount: 0 });
    const err = await f.saveExpectingError();
    expect(err.toLowerCase()).toMatch(/between 1 and 1024|char count|từ 1 đến 1024/);
  });

  test('TC-011 — Vật liệu auto từ biến thể → publish draft', async ({ page, request }) => {
    test.skip(!RUN_ETSY, 'Live Etsy draft publish — set RUN_ETSY_PUBLISH=1 to run.');
    await loginAsBaLead(page);
    const f = new ProductFormPage(page);
    await f.openNew();
    const sku = uniq('TC011-MUG');
    await f.fillName(`${NAME} Materials ${sku}`);
    await f.selectCategory('Mug');
    await f.addVariantAttribute('Material', 'Ceramic + Chrome');
    await f.addVariantAttribute('Fluid oz', '11 oz');
    await f.fillListPrice(LIVE_PRICE);
    await f.addChannel('Etsy');
    await f.save();
    const code = await f.readSku();
    await f.publishDraftOnly();
    const st = await channelStatus(request, code);
    expect(st?.external_ref, 'listing id present').toBeTruthy();
    // Etsy-side Materials=["Ceramic","Chrome"] verified manually in Shop Manager.
  });

  test('TC-012 — Ảnh phụ (mini gallery) + thứ tự', async ({ page }) => {
    test.skip(true, 'Extra-image upload + ordering is image-binary heavy and headless-fragile; ' +
      'verified manually. Future slice P-UAT-EXTRA-IMAGES-BROWSER may automate via base64 set_field.');
  });

  test('TC-013 — Override taxonomy theo sản phẩm → publish draft', async ({ page, request }) => {
    test.skip(!RUN_ETSY, 'Live Etsy draft publish — set RUN_ETSY_PUBLISH=1 to run.');
    await loginAsBaLead(page);
    const f = new ProductFormPage(page);
    await f.openNew();
    const sku = uniq('TC013-MUG');
    await f.fillName(`${NAME} Taxonomy ${sku}`);
    await f.selectCategory('Mug');
    await f.fillListPrice(LIVE_PRICE);
    await f.addChannel('Etsy');
    await f.setListingDefaults({ taxonomyId: '1633' }); // Etsy "Mugs" taxonomy id
    await f.save();
    const code = await f.readSku();
    await f.publishDraftOnly();
    const st = await pollExternalRef(request, code);
    expect(st?.external_ref, 'listing id present').toBeTruthy();
  });

  test('TC-014 — Cân nặng + Kích thước → publish draft', async ({ page, request }) => {
    test.skip(!RUN_ETSY, 'Live Etsy draft publish — set RUN_ETSY_PUBLISH=1 to run.');
    await loginAsBaLead(page);
    const f = new ProductFormPage(page);
    await f.openNew();
    const sku = uniq('TC014-DMT');
    await f.fillName(`${NAME} Doormat ${sku}`);
    await f.selectCategory('Doormat');
    // NOTE: rectangular doormat sizing (R30X18) was wizard-only (rect_w/rect_h);
    // there is no standard '30x18' Size attribute value. This TC validates the
    // weight path + draft publish; dimension emission is verified manually.
    await f.fillListPrice(LIVE_PRICE);
    await f.fillWeight(0.35);
    await f.addChannel('Etsy');
    await f.save();
    const code = await f.readSku();
    await f.publishDraftOnly();
    const st = await pollExternalRef(request, code);
    expect(st?.external_ref, 'listing id present').toBeTruthy();
    // Etsy-side item_weight/item_length/item_width verified manually.
  });

  test('TC-015 — Thuộc tính biến thể (property_values) → publish draft', async ({ page, request }) => {
    test.skip(!RUN_ETSY, 'Live Etsy draft publish — set RUN_ETSY_PUBLISH=1 to run.');
    await loginAsBaLead(page);
    const f = new ProductFormPage(page);
    await f.openNew();
    const sku = uniq('TC015-MUG');
    await f.fillName(`${NAME} VariantProps ${sku}`);
    await f.selectCategory('Mug');
    await f.addVariantAttribute('Material', 'Ceramic + Chrome');
    await f.addVariantAttribute('Color', 'Black');
    await f.fillListPrice(LIVE_PRICE);
    await f.addChannel('Etsy');
    await f.save();
    const code = await f.readSku();
    await f.publishDraftOnly();
    const st = await channelStatus(request, code);
    expect(st?.external_ref, 'listing id present').toBeTruthy();
    // Etsy-side per-offering property_values verified manually.
  });
});
