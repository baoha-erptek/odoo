/**
 * VIDEO USER GUIDE — Quy trình SẢN XUẤT NỘI BỘ (MTO) từ A-Z (silent, VN captions).
 *
 * Same harness as guide_flow_dropship.spec.ts: GUIDE_RECORDING=1, one test =
 * one chapter = one WebM, concat via scripts/build_guide_videos.sh into
 * docs/owner/videos/huong_dan_mto.mp4. Retake single chapters with --grep.
 *
 * LIVE side effect: chuong-02 publishes a real DRAFT listing on Etsy.
 * Off-camera fixtures mirror scripts/e2e_flow3a_fulfillment.py: mfg+MTO
 * routes + 1:1 BOM + component stock, so SO confirm auto-creates the MO
 * (standard MTO procurement) and delivery validate triggers the FLW-06
 * pipeline auto-advance to "Đã Gửi".
 * READ-ONLY: order id 3391... no — S03391 (tracking anchor) is opened
 * read-only in chuong-07; never write to it.
 */
import { test, expect } from '@playwright/test';
import { CONFIG } from '../fixtures/env';
import { ProductFormPage } from '../page-objects/product_form';
import { SaleOrderFormPage } from '../page-objects/sale_order_form';
import {
  apiLogin, callKw, showCaption, hideCaption, titleCard, pause,
  installCursorHighlight, readGuideState, writeGuideState, publishDraftOnlyGuide,
} from '../fixtures/guide-recorder';

const GUIDE = process.env.GUIDE_RECORDING === '1';
const LIVE_PRICE = 24.99;           // company USD (NOT shop VND — see dropship spec)
const ETSY_API_SHOP_ID = '60752333';
// S03340 — only staging order with tracking pushed to Etsy (READ-ONLY; the
// former MTO anchor S03391 was swept by cleanup).
const TRACKING_ANCHOR_ID = 3323;
// A public sample artwork for the approved design file (any reachable URL).
const SAMPLE_ART_URL = 'https://origin-x.geaflare.com/exproduct/avatar_1775457720_hfavt.png';

/** Confirm any transient confirmation dialog (backorder / immediate qty). */
async function confirmDialogIfAny(page: import('@playwright/test').Page): Promise<void> {
  const btn = page.locator('.modal:visible footer .btn-primary').first();
  if (await btn.isVisible().catch(() => false)) {
    await btn.click();
    await page.waitForTimeout(800);
  }
}

test.describe('HUONG_DAN VIDEO — MTO', () => {
  test.skip(!GUIDE, 'Video recording chapters — set GUIDE_RECORDING=1 to run.');

  test('chuong-01 gioi thieu va dang nhap', async ({ page }) => {
    await installCursorHighlight(page);
    await page.goto('/web/login');
    await titleCard(page,
      'Hướng dẫn quy trình Sản xuất nội bộ (MTO)',
      'Tạo sản phẩm → Đăng lên Etsy → Đơn hàng → Lệnh sản xuất → Giao hàng → Tracking');
    await showCaption(page, 'Đăng nhập vào Odoo bằng tài khoản của bạn', 3000);
    await apiLogin(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD, CONFIG.DB);
    await page.goto('/odoo');
    await showCaption(page, 'Khác với Dropship, hàng MTO do xưởng nội bộ sản xuất theo từng đơn', 4000);
    await hideCaption(page);
  });

  test('chuong-02 tao san pham mto va dang etsy', async ({ page }) => {
    await installCursorHighlight(page);
    const marker = Date.now().toString(36).slice(-5);
    const name = `video demo mto keepsake ${marker}`;
    writeGuideState({ mtoProductName: name });

    await apiLogin(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD, CONFIG.DB);
    await page.goto('/odoo');
    await showCaption(page, 'Bước 1: Tạo sản phẩm sản xuất nội bộ — vào Tồn kho → Sản phẩm');
    const f = new ProductFormPage(page);
    await f.openNew();
    await showCaption(page, 'Nhập tên sản phẩm');
    await f.fillName(name);
    await pause(page);
    await showCaption(page, 'Chọn Danh mục — SKU tự sinh như video Dropship');
    await f.selectCategory('Mug');
    await pause(page);
    await showCaption(page, 'Nhập Giá bán');
    await f.fillListPrice(LIVE_PRICE);
    await pause(page);
    await showCaption(page,
      'KHÔNG nhập mã Gearment — sản phẩm này sẽ đi theo quy trình sản xuất NỘI BỘ', 4500);
    await showCaption(page, 'Thêm kênh bán hàng Etsy');
    await f.addChannel('Etsy');
    await pause(page);
    await showCaption(page, 'Lưu sản phẩm');
    await f.save();
    await pause(page);

    // Off-camera: template id + manufacturing config (routes + BOM +
    // component stock — one-time setup normally done by the warehouse admin,
    // mirrors e2e_flow3a section_1).
    const tids = await callKw<number[]>(page, 'product.template', 'search',
      [[['name', '=', name]]], { order: 'id desc', limit: 1 });
    expect(tids.length).toBe(1);
    const variantIds = await callKw<number[]>(page, 'product.product', 'search',
      [[['product_tmpl_id', '=', tids[0]]]]);
    const mfgRoutes = await callKw<number[]>(page, 'stock.route', 'search',
      [[['rule_ids.action', '=', 'manufacture']]]);
    const mtoRoutes = await callKw<number[]>(page, 'stock.route', 'search',
      [[['name', 'ilike', 'replenish']]]);
    await callKw(page, 'product.template', 'write', [[tids[0]], {
      is_storable: true,
      route_ids: [[6, 0, [mfgRoutes[0], mtoRoutes[0]]]],
    }]);
    const compTmpl = await callKw<number>(page, 'product.template', 'create', [{
      name: `video demo mto component ${marker}`, is_storable: true, list_price: 1.0,
    }]);
    const compVariant = (await callKw<number[]>(page, 'product.product', 'search',
      [[['product_tmpl_id', '=', compTmpl]]]))[0];
    await callKw(page, 'mrp.bom', 'create', [{
      product_tmpl_id: tids[0], product_qty: 1.0, type: 'normal',
      bom_line_ids: [[0, 0, { product_id: compVariant, product_qty: 1.0 }]],
    }]);
    const wh = await callKw<Array<{ lot_stock_id: [number, string] }>>(
      page, 'stock.warehouse', 'search_read', [[]], { fields: ['lot_stock_id'], limit: 1 });
    const quant = await callKw<number>(page, 'stock.quant', 'create', [{
      product_id: compVariant, location_id: wh[0].lot_stock_id[0], inventory_quantity: 10,
    }]);
    await callKw(page, 'stock.quant', 'action_apply_inventory', [[quant]]);
    writeGuideState({
      mtoProductTmplId: tids[0], mtoVariantId: variantIds[0], mtoComponentTmplId: compTmpl,
    });
    await showCaption(page,
      '(Cấu hình sản xuất: định mức BOM + tuyến Sản xuất/MTO do quản trị kho thiết lập sẵn một lần)', 4500);

    await page.reload();
    await page.waitForSelector('.o_form_view', { timeout: 15000 });
    await showCaption(page, 'Đăng sản phẩm lên Etsy — thao tác giống video Dropship');
    await publishDraftOnlyGuide(page);
    let ref: string | false = false;
    const deadline = Date.now() + 20000;
    while (Date.now() < deadline && !ref) {
      const rows = await callKw<Array<{ external_ref: string | false }>>(
        page, 'product.channel.status', 'search_read',
        [[['product_tmpl_id', '=', tids[0]]]], { fields: ['external_ref'], limit: 1 });
      ref = rows?.[0]?.external_ref ?? false;
      if (!ref) await page.waitForTimeout(1000);
    }
    expect(ref, 'Etsy listing id').toBeTruthy();
    writeGuideState({ mtoListingRef: ref });
    await showCaption(page, `Đăng thành công — mã listing Etsy: ${ref}`, 4000);
    await hideCaption(page);
  });

  test('chuong-03 don hang va lenh san xuat tu dong', async ({ page }) => {
    const st = readGuideState();
    expect(st.mtoVariantId, 'chuong-02 must run first').toBeTruthy();
    await installCursorHighlight(page);
    await apiLogin(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD, CONFIG.DB);

    // Off-camera: demo incoming Etsy order + approved design file.
    let mtoOrderId = st.mtoOrderId as number | undefined;
    let mtoMoId = st.mtoMoId as number | undefined;
    if (!mtoOrderId) {
      const shopIds = await callKw<number[]>(page, 'etsy.shop', 'search',
        [[['etsy_api_shop_id', '=', ETSY_API_SHOP_ID]]]);
      const countryIds = await callKw<number[]>(page, 'res.country', 'search', [[['code', '=', 'US']]]);
      const partnerId = await callKw<number>(page, 'res.partner', 'create', [{
        name: `Video Demo MTO Buyer ${Date.now().toString(36).slice(-5)}`,
        street: '1 Test Lane', city: 'Austin', zip: '78701', country_id: countryIds[0],
      }]);
      const etsyOrderId = `97${Math.floor(Date.now() / 1000) % 100000000}`;
      mtoOrderId = await callKw<number>(page, 'sale.order', 'create', [{
        partner_id: partnerId,
        etsy_order_id: etsyOrderId, etsy_shop_id: shopIds[0],
        sales_channel: 'etsy', channel_order_ref: etsyOrderId,
        order_line: [[0, 0, {
          product_id: st.mtoVariantId, product_uom_qty: 1.0, price_unit: LIVE_PRICE,
        }]],
      }]);
      const lineIds = await callKw<number[]>(page, 'sale.order.line', 'search',
        [[['order_id', '=', mtoOrderId]]]);
      await callKw(page, 'design.file', 'create', [{
        name: `VIDEO-MTO-ART-${Date.now().toString(36).slice(-5)}`,
        order_line_id: lineIds[0], storage_mode: 'url',
        file_url: SAMPLE_ART_URL, state: 'approved',
      }]);
      // vn_internal_production pipeline (what the ingest assigns for MTO).
      const pipeIds = await callKw<number[]>(page, 'order.pipeline', 'search',
        [[['code', '=', 'vn_internal_production']]]);
      const pendingIds = await callKw<number[]>(page, 'order.pipeline.state', 'search',
        [[['pipeline_id', '=', pipeIds[0]], ['code', '=', 'pending_file']]]);
      await callKw(page, 'sale.order', 'write',
        [[mtoOrderId], { x_pipeline_id: pipeIds[0], x_pipeline_state_id: pendingIds[0] }],
        { context: { bypass_pipeline_state_guard: true } });
      await callKw(page, 'sale.order', 'action_confirm', [[mtoOrderId]]);
      const nameRow = await callKw<Array<{ name: string }>>(page, 'sale.order', 'read',
        [[mtoOrderId], ['name']]);
      // MTO procurement auto-creates the MO (mirror flow3a section_2).
      const deadline = Date.now() + 60000;
      while (Date.now() < deadline && !mtoMoId) {
        const mos = await callKw<number[]>(page, 'mrp.production', 'search',
          [[['origin', '=', nameRow[0].name]]]);
        mtoMoId = mos[0];
        if (!mtoMoId) await page.waitForTimeout(2000);
      }
      expect(mtoMoId, 'MO auto-created by MTO procurement').toBeTruthy();
      writeGuideState({ mtoOrderId, mtoOrderName: nameRow[0].name, mtoMoId });
    }

    // On-camera: the order as the team sees it.
    const so = new SaleOrderFormPage(page);
    await so.openById(mtoOrderId);
    await showCaption(page,
      'Bước 2: Đơn Etsy đổ về — sản phẩm KHÔNG có mã Gearment nên đi tuyến sản xuất nội bộ');
    await showCaption(page, 'Trạng thái quy trình bắt đầu ở "Chờ File" (chờ file thiết kế)', 4000);
    await pause(page);
    await so.openTab(/Design Files|Tệp thiết kế/);
    await showCaption(page, 'File thiết kế đã tải lên và được DUYỆT trên dòng đơn', 4000);
    await pause(page);
    await so.openTab(/Pipeline/);
    await showCaption(page, 'Thẻ Pipeline theo dõi từng bước của đơn trong xưởng', 3500);
    await showCaption(page,
      'Khi xác nhận đơn, Odoo TỰ tạo Lệnh sản xuất (MO) nhờ tuyến MTO + định mức BOM', 4500);
    await hideCaption(page);
  });

  test('chuong-04 hoan tat lenh san xuat', async ({ page }) => {
    const st = readGuideState();
    expect(st.mtoMoId, 'chuong-03 must run first').toBeTruthy();
    await installCursorHighlight(page);
    await apiLogin(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD, CONFIG.DB);

    await page.goto(`/odoo/action-mrp.mrp_production_action/${st.mtoMoId}`);
    await page.waitForSelector('.o_form_view', { timeout: 20000 });
    await showCaption(page, 'Bước 3: Lệnh sản xuất (MO) do Odoo tự tạo từ đơn hàng');
    await showCaption(page, 'Xưởng sản xuất theo file thiết kế đã duyệt', 3000);
    await pause(page);

    // Off-camera: fill produced qty (UI equivalent: the qty widget).
    await callKw(page, 'mrp.production', 'write', [[st.mtoMoId], { qty_producing: 1.0 }]);
    await page.reload();
    await page.waitForSelector('.o_form_view', { timeout: 20000 });
    await showCaption(page, 'Sản xuất xong — nhấn "Hoàn tất" để đóng lệnh sản xuất');
    await page.locator('button[name="button_mark_done"]').first().click();
    await page.waitForTimeout(2000);
    await confirmDialogIfAny(page); // backorder / immediate production dialogs
    await page.waitForTimeout(1500);
    await confirmDialogIfAny(page);

    // Verify done state via RPC (badge text is locale-dependent).
    const deadline = Date.now() + 30000;
    let moState = '';
    while (Date.now() < deadline && moState !== 'done') {
      const rows = await callKw<Array<{ state: string }>>(page, 'mrp.production', 'read',
        [[st.mtoMoId], ['state']]);
      moState = rows[0].state;
      if (moState !== 'done') await page.waitForTimeout(1500);
    }
    expect(moState, 'MO done').toBe('done');
    await showCaption(page, 'Lệnh sản xuất hoàn tất — thành phẩm đã nhập kho', 4000);
    await hideCaption(page);
  });

  test('chuong-05 giao hang va tu dong sang Da Gui', async ({ page }) => {
    const st = readGuideState();
    expect(st.mtoOrderName, 'chuong-03 must run first').toBeTruthy();
    await installCursorHighlight(page);
    await apiLogin(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD, CONFIG.DB);

    // Off-camera: locate the outgoing delivery for the SO.
    let pickingId = st.mtoPickingId as number | undefined;
    if (!pickingId) {
      const picks = await callKw<Array<{ id: number; name: string }>>(
        page, 'stock.picking', 'search_read',
        [[['origin', '=', st.mtoOrderName], ['picking_type_id.code', '=', 'outgoing']]],
        { fields: ['name'], limit: 1 });
      expect(picks.length, 'outgoing delivery exists').toBeGreaterThan(0);
      pickingId = picks[0].id;
      await callKw(page, 'stock.picking', 'action_assign', [[pickingId]]);
      writeGuideState({ mtoPickingId: pickingId });
    }

    await page.goto(`/odoo/action-stock.action_picking_tree_all/${pickingId}`);
    await page.waitForSelector('.o_form_view', { timeout: 20000 });
    await showCaption(page, 'Bước 4: Phiếu giao hàng cho khách — hàng đã sẵn sàng xuất kho');
    await pause(page);
    await showCaption(page, 'Nhấn "Xác nhận" để hoàn tất giao hàng');
    await page.locator('button[name="button_validate"]').first().click();
    await page.waitForTimeout(2000);
    await confirmDialogIfAny(page);
    await page.waitForTimeout(1500);
    await confirmDialogIfAny(page);

    // FLW-06: delivery validate on a vn_internal_production order
    // auto-advances the pipeline to 'shipped' (Đã Gửi).
    const deadline = Date.now() + 30000;
    let stateName = '';
    while (Date.now() < deadline) {
      const rows = await callKw<Array<{ x_pipeline_state_id: [number, string] | false }>>(
        page, 'sale.order', 'read', [[st.mtoOrderId], ['x_pipeline_state_id']]);
      stateName = rows[0].x_pipeline_state_id ? rows[0].x_pipeline_state_id[1] : '';
      if (/Gửi|Ship/i.test(stateName)) break;
      await page.waitForTimeout(1500);
    }
    expect(stateName, 'pipeline auto-advanced to shipped').toMatch(/Gửi|Ship/i);

    const so = new SaleOrderFormPage(page);
    await so.openById(st.mtoOrderId as number);
    await showCaption(page,
      `Giao hàng xong — trạng thái quy trình TỰ ĐỘNG chuyển sang "${stateName}"`, 5000);
    await hideCaption(page);
  });

  test('chuong-06 tracking va ket thuc', async ({ page }) => {
    await installCursorHighlight(page);
    await apiLogin(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD, CONFIG.DB);
    await page.goto('/odoo');
    await showCaption(page,
      'Bước 5: Mã vận đơn từ đối tác vận chuyển được nhập về Odoo (file Excel GKE) và đẩy lên Etsy');

    // READ-ONLY anchor: an order already shipped with tracking pushed.
    const so = new SaleOrderFormPage(page);
    await so.openById(TRACKING_ANCHOR_ID);
    await showCaption(page, 'Đơn này đã có mã vận đơn và trạng thái "Đã Gửi"', 4000);
    await pause(page);
    await so.openTab(/Etsy/);
    await showCaption(page,
      'Tracking đồng bộ lên Etsy để khách theo dõi — giống bước cuối của video Dropship', 4500);
    await titleCard(page,
      'Hoàn tất quy trình Sản xuất nội bộ',
      'Sản phẩm → Etsy → Đơn hàng → Lệnh sản xuất → Giao hàng → Tracking về Etsy');
  });
});
