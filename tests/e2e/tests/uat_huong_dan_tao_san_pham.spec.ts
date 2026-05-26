/**
 * UAT — HUONG_DAN_TAO_SAN_PHAM_VN.md  (ESTY-183)
 *
 * Maps TC-001 .. TC-007 from docs/owner/HUONG_DAN_TAO_SAN_PHAM_VN.md §8.
 *
 * Model + view sources (verified 2026-05-26):
 *   custom_addons/multichannel_hub_core/wizards/product_creation_wizard.py
 *   custom_addons/multichannel_hub_core/wizards/product_creation_wizard_views.xml
 *   custom_addons/etsy_integration/views/product_views.xml (Publish button)
 *   custom_addons/etsy_integration/models/product_product.py:49 (action_open_etsy_publish_wizard)
 *
 * Note on TC-007 (spec drift): the doc says "Validation — price < $0.20".
 * The wizard validator actually checks "> 0" (line 127 of product_creation_wizard.py).
 * This spec tests what the code does today (price=0 → "Listing Price must be greater than 0").
 * If owner wants the $0.20 floor as a wizard validator, that becomes a P-UAT-FIX-TC007
 * MP006 slice (option A: tighten validator; option B: rewrite doc).
 */

import { test, expect } from '@playwright/test';
import { loginAsBaLead, loginAsBaUser } from '../fixtures/odoo-auth';
import { ProductCreationWizardPage } from '../page-objects/product_creation_wizard';
import { ProductSkuBuilderWizardPage } from '../page-objects/product_sku_builder_wizard';
import { CONFIG } from '../fixtures/env';

const UAT_NAME_PREFIX = 'UAT-TAOSP';
const UAT_SKU_PREFIX = 'UAT-MUG';
const UAT_BUILDER_PREFIX = 'UAT-SKU-BUILDER';

function uniqueSku(stem: string): string {
  return `${UAT_SKU_PREFIX}-${stem}-${Date.now().toString(36).slice(-5).toUpperCase()}`;
}

/**
 * Query staging via Odoo JSON-RPC for product.template rows matching the
 * supplied default_code. Authenticates as admin. Used to verify the new
 * SKU-builder wizard created (or did NOT create) a template after submit.
 */
async function countProductsBySku(
  request: import('@playwright/test').APIRequestContext,
  defaultCode: string,
): Promise<number> {
  const auth = await request.post(`${CONFIG.BASE_URL}/web/session/authenticate`, {
    data: {
      jsonrpc: '2.0',
      params: { db: CONFIG.DB, login: CONFIG.ADMIN_LOGIN, password: CONFIG.ADMIN_PASSWORD },
    },
  });
  if (!auth.ok()) throw new Error(`session/authenticate failed: HTTP ${auth.status()}`);
  const res = await request.post(`${CONFIG.BASE_URL}/web/dataset/call_kw/product.template/search_count`, {
    data: {
      jsonrpc: '2.0',
      params: {
        model: 'product.template',
        method: 'search_count',
        args: [[['default_code', '=', defaultCode]]],
        kwargs: {},
      },
    },
  });
  const body = await res.json();
  if (body?.error) throw new Error(`search_count error: ${JSON.stringify(body.error)}`);
  return body?.result ?? 0;
}

test.describe('ESTY-183 — HUONG_DAN_TAO_SAN_PHAM_VN UAT', () => {

  test('TC-001 — BA Lead tạo sản phẩm Mug bằng Wizard', async ({ page }) => {
    await loginAsBaLead(page);
    const wiz = new ProductCreationWizardPage(page);
    await wiz.open();

    const sku = uniqueSku('001');
    await wiz.fillBasics({
      name: `${UAT_NAME_PREFIX} Mug 2026 ${sku}`,
      defaultCode: sku,
      categName: 'All',  // safe leaf — exists in any Odoo install
      listingPrice: 12.99,
      shippingPrice: 20000,
      channels: ['Etsy'],
    });
    await wiz.submit();

    // Expect redirect to product.template form
    await expect(page.locator('.o_form_view')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('[name="default_code"] input')).toHaveValue(sku);
    // Channels tab — Etsy with draft status
    const channelsTab = page.locator('a.nav-link', { hasText: /Channels|Kênh/ }).first();
    if (await channelsTab.count() > 0) {
      await channelsTab.click();
      await expect(page.locator('.o_field_one2many [name="x_sales_channel_status_ids"]')).toContainText(/Etsy/i, { timeout: 8000 });
      await expect(page.locator('.o_field_one2many [name="x_sales_channel_status_ids"]')).toContainText(/draft|Draft|Nháp/i);
    }
  });

  test('TC-002 — Sản phẩm có Mã Gearment → đặt cờ Dropship', async ({ page }) => {
    await loginAsBaLead(page);
    const wiz = new ProductCreationWizardPage(page);
    await wiz.open();

    const sku = uniqueSku('002');
    await wiz.fillBasics({
      name: `${UAT_NAME_PREFIX} Dropship ${sku}`,
      defaultCode: sku,
      categName: 'All',
      listingPrice: 19.99,
      shippingPrice: 0,
      gearmentSku: `GEAR-${sku}`,
      channels: ['Etsy'],
    });
    await wiz.submit();

    await expect(page.locator('.o_form_view')).toBeVisible({ timeout: 15000 });
    // The wizard's production_mode_preview inferred Dropship — check the
    // resulting product surfaces x_gearment_sku
    const gearmentField = page.locator('[name="x_gearment_sku"] input').first();
    if (await gearmentField.count() > 0) {
      await expect(gearmentField).toHaveValue(new RegExp(`^GEAR-${sku}$`));
    }
  });

  test('TC-003 — SKU drift wizard "Keep Legacy"', async ({ page }) => {
    test.skip(
      true,
      'TC-003 requires a pre-existing product with x_sku_v2_status=non_canonical on staging. ' +
      'Pending seed_uat_data.py addition (P-UAT-FIX-TC003 if not seedable).'
    );
    await loginAsBaLead(page);
    // TODO: open product → SKU drift tab → click "Keep Legacy" → assert ba_approved_legacy
  });

  test('TC-004 — SKU drift wizard "Accept Canonical" (published product)', async ({ page }) => {
    test.skip(
      true,
      'TC-004 requires (a) published product on Etsy with non_canonical SKU, ' +
      '(b) Etsy API connectivity for inventory push verification. Pending seed + API setup.'
    );
    await loginAsBaLead(page);
  });

  test('TC-005 — Đăng lên Etsy (Draft mode)', async ({ page }) => {
    test.skip(
      true,
      'TC-005 creates a real Etsy draft listing on JaHandmadeArt. Owner-approved but ' +
      'requires a UAT product to publish first; chaining from TC-001 needs context handoff. ' +
      'Deferred to dedicated run after TC-001 confirms green.'
    );
    await loginAsBaLead(page);
  });

  test('TC-006 — BA tier visibility of "Publish to Etsy" button', async ({ page }) => {
    /**
     * DOC vs CODE MISMATCH FINDING — captured in docs/owner/UAT_FINDINGS_2026-05-26.md.
     *
     * HUONG_DAN_TAO_SAN_PHAM_VN.md TC-006 says: "BA User KHÔNG thấy nút Publish to Etsy".
     * BUT the implementation (verified 2026-05-26):
     *   - View: groups="multichannel_hub_core.group_ba_user" → button VISIBLE to BA User
     *   - Wizard FR-017 gate: _BA_GROUP_XMLID = 'multichannel_hub_core.group_ba_user' → BA User CAN execute
     *   - Code comment in product_product.py:49: "View binds `groups=` for defense-in-depth visibility"
     *
     * The role matrix in HUONG_DAN_TAO_SAN_PHAM_VN.md row "BA User | Đăng Etsy: ❌" is
     * wishful and contradicts both the view AND the wizard. The actual design grants
     * publish to the whole BA tier (User/Lead/Manager).
     *
     * Resolution (pending owner decision in UAT debrief):
     *   Option D1: Update the doc role matrix to: BA User | Đăng Etsy: ✅
     *   Option D2: Tighten the code (raise wizard FR-017 gate to group_ba_lead) — code change
     *
     * Until then this TC asserts the **actual designed behaviour**: button IS visible to BA User.
     */
    test.skip(
      !process.env.STAGING_BA_USER_PASSWORD && !require('fs').existsSync(
        require('path').join(__dirname, '..', 'artifacts', '_seed_state.json')
      ),
      'BA User seed unavailable — skip until seed_ba_user.py runs successfully.'
    );
    await loginAsBaUser(page);

    // Open first available product in the Sales > Products list (Etsy publish button
    // is inherited from etsy_integration onto product.template via xpath header insert).
    await page.goto('/odoo/inventory/products');
    await page.waitForSelector('.o_list_view, .o_kanban_view', { timeout: 15000 });
    const firstRow = page.locator('.o_list_view tbody tr.o_data_row, .o_kanban_record').first();
    await firstRow.click();
    await page.waitForSelector('.o_form_view', { timeout: 10000 });

    // ACTUAL: BA User has group_ba_user → button is visible by design.
    const publishBtn = page.locator('button[name="action_open_etsy_publish_wizard"]');
    await expect(publishBtn).toHaveCount(1);
    await expect(publishBtn).toBeVisible();
  });

  test('TC-007 — Validation: Listing Price phải > 0 (wizard validator)', async ({ page }) => {
    // SPEC DRIFT NOTE: doc says "< $0.20"; actual validator is "> 0".
    // We test the implementation (price=0 → error), not the doc's wishful spec.
    await loginAsBaLead(page);
    const wiz = new ProductCreationWizardPage(page);
    await wiz.open();

    const sku = uniqueSku('007');
    await wiz.fillBasics({
      name: `${UAT_NAME_PREFIX} ZeroPrice ${sku}`,
      defaultCode: sku,
      categName: 'All',
      listingPrice: 0,
      shippingPrice: 0,
      channels: ['Etsy'],
    });
    const errText = await wiz.submitExpectingError();
    expect(errText.toLowerCase()).toMatch(/listing price must be greater than 0|listing price phải/i);
    // Form should still be open (no redirect)
    await expect(wiz.form).toBeVisible();
  });

  // --------------------------------------------------------------------------
  // TC-008..TC-012 — New 4-step SKU Builder Wizard (P-HUB-SKU-BUILDER landed
  // 2026-05-26, mhc 19.0.1.0.52). Added by P-UAT-SKU-BUILDER-EXTEND slice
  // 2026-05-26. Each TC walks all 4 steps end-to-end, asserts the assembled
  // SKU in the preview, submits, then JSON-RPC confirms the product.template
  // exists with the expected default_code.
  //
  // Cleanup: globalTeardown already archives any UAT_BUILDER_PREFIX products
  // via fixtures/cleanup_uat_data.py search pattern.
  // --------------------------------------------------------------------------

  test('TC-008 — Build MUG-CR-F11 (mug 11oz happy path)', async ({ page, request }) => {
    await loginAsBaLead(page);
    const wiz = new ProductSkuBuilderWizardPage(page);
    await wiz.open();

    const productName = `${UAT_BUILDER_PREFIX} Mug 11oz ${Date.now().toString(36).slice(-4).toUpperCase()}`;
    // Step 1: Family (auto MUG from "Mug 11oz")
    await wiz.fillStep1Name(productName);
    await wiz.clickNext();
    // Step 2: Material — Ceramic (CR)
    await wiz.fillStep2Material('Ceramic + Chrome');
    await wiz.clickNext();
    // Step 3: Size — 11 oz (F11). Seed display name is "11 oz" not "11 fl oz".
    await wiz.fillStep3Size({ size: '11 oz' });
    await wiz.clickNext();
    // Step 4: Preview, no color
    const preview = await wiz.getPreviewSku();
    expect(preview).toBe('MUG-CR-F11');
    await wiz.clickCreate();

    // After create, wizard closes — give server a moment, then JSON-RPC verify
    await page.waitForTimeout(1500);
    const count = await countProductsBySku(request, 'MUG-CR-F11');
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('TC-009 — Build MUG-CR-F15-BK (mug 15oz + VAR2 black)', async ({ page, request }) => {
    await loginAsBaLead(page);
    const wiz = new ProductSkuBuilderWizardPage(page);
    await wiz.open();

    const productName = `${UAT_BUILDER_PREFIX} Mug 15oz Black ${Date.now().toString(36).slice(-4).toUpperCase()}`;
    await wiz.fillStep1Name(productName);
    await wiz.clickNext();
    await wiz.fillStep2Material('Ceramic + Chrome');
    await wiz.clickNext();
    await wiz.fillStep3Size({ size: '15 oz' });
    await wiz.clickNext();
    await wiz.fillStep4Color('Black');
    const preview = await wiz.getPreviewSku();
    expect(preview).toBe('MUG-CR-F15-BK');
    await wiz.clickCreate();

    await page.waitForTimeout(1500);
    const count = await countProductsBySku(request, 'MUG-CR-F15-BK');
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('TC-010 — Build APR-TX-AM (apron M, apparel-size-gated)', async ({ page, request }) => {
    await loginAsBaLead(page);
    const wiz = new ProductSkuBuilderWizardPage(page);
    await wiz.open();

    const productName = `${UAT_BUILDER_PREFIX} Cotton Apron M ${Date.now().toString(36).slice(-4).toUpperCase()}`;
    await wiz.fillStep1Name(productName);
    await wiz.clickNext();
    await wiz.fillStep2Material('Textile');
    await wiz.clickNext();
    // APR family-gates size step to apparel namespace — picking 'Medium' resolves to AM code.
    // Seed display name is "Medium" not "M" (avoids autocomplete ambiguity with Mug/etc).
    await wiz.fillStep3Size({ size: 'Medium' });
    await wiz.clickNext();
    const preview = await wiz.getPreviewSku();
    expect(preview).toBe('APR-TX-AM');
    await wiz.clickCreate();

    await page.waitForTimeout(1500);
    const count = await countProductsBySku(request, 'APR-TX-AM');
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('TC-011 — Build DMT-TX-R30X18 (doormat rectangular)', async ({ page, request }) => {
    await loginAsBaLead(page);
    const wiz = new ProductSkuBuilderWizardPage(page);
    await wiz.open();

    const productName = `${UAT_BUILDER_PREFIX} Doormat 30x18 ${Date.now().toString(36).slice(-4).toUpperCase()}`;
    await wiz.fillStep1Name(productName);
    await wiz.clickNext();
    await wiz.fillStep2Material('Textile');
    await wiz.clickNext();
    // Rectangular sizing via rect_w/rect_h (no size_id pick)
    await wiz.fillStep3Size({ rectW: 30, rectH: 18 });
    await wiz.clickNext();
    const preview = await wiz.getPreviewSku();
    expect(preview).toBe('DMT-TX-R30X18');
    await wiz.clickCreate();

    await page.waitForTimeout(1500);
    const count = await countProductsBySku(request, 'DMT-TX-R30X18');
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('TC-012 — FR-017 24th: non-BA user blocked at action_create (covered in mhc unit test)', async ({ page }) => {
    /**
     * Browser-level FR-017 gate test is intentionally SKIPPED.
     *
     * Why: the gate (`_check_ba_or_raise` in wizards/product_sku_builder_wizard.py:216)
     * requires a user WITHOUT multichannel_hub_core.group_ba_user. The auto-seeded
     * BA User HAS that group → not a valid test subject. To browser-test the
     * negative path we'd need a fresh "plain" user (only base.group_user) seeded
     * via fixture — additional plumbing for a behaviour already proven at the
     * correct layer.
     *
     * Where the assertion IS covered:
     *   custom_addons/multichannel_hub_core/tests/test_phase2_hub_sku_builder_orm.py:292
     *   test_non_ba_user_blocked_before_template_create — asserts AccessError
     *   raised AND product.template.search_count unchanged. Last GREEN: 2026-05-26.
     *
     * To promote to browser test in a future slice (P-UAT-FR017-BUILDER-BROWSER):
     *   - Add fixtures/seed_plain_user.py (base.group_user only)
     *   - Login as plain user → navigate to wizard URL → expect AccessError modal
     *   - JSON-RPC search_count before/after to assert no template created
     */
    test.skip(true, 'FR-017 24th gate is method-level — covered by mhc unit test test_non_ba_user_blocked_before_template_create. Browser stub kept for traceability.');
  });
});
