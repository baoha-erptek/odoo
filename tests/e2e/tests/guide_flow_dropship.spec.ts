/**
 * VIDEO USER GUIDE — Quy trình DROPSHIP từ A-Z (silent, Vietnamese captions).
 *
 * Run with GUIDE_RECORDING=1 (see playwright.config.ts): 1080p, slowMo 100,
 * video always on, retries 0, 10-min chapter timeout. One test = one chapter
 * = one WebM; scripts/build_guide_videos.sh concatenates them into
 * docs/owner/videos/huong_dan_dropship.mp4. Retake a single chapter with
 * `--grep "chuong-0N"` — its DB side effects persist on staging.
 *
 * LIVE side effects (owner-approved 2026-07-06):
 *   chuong-03: real DRAFT listing on Etsy (JaHandmadeArt — VND shop, price
 *              must be >= ~5,043 VND; 250,000 like the tao-san-pham spec).
 *   chuong-05: real Gearment DRAFT order (owner discards from GM dashboard;
 *              ref recorded in artifacts/_guide_state.json).
 * READ-ONLY hard rule: order id 3322 (S03339) and id 3323 (S03340) are REAL
 * buyer orders — never write to them, never push tracking (a push could
 * notify the buyer).
 */
import { test, expect } from '@playwright/test';
import { CONFIG, UAT_ROLE_LOGINS } from '../fixtures/env';
import { loginAs } from '../fixtures/odoo-auth';
import { ProductFormPage } from '../page-objects/product_form';
import { SaleOrderFormPage } from '../page-objects/sale_order_form';
import { GearmentQuoteWizardPage } from '../page-objects/gearment_quote_wizard';
import { OperationsDashboardPage } from '../page-objects/operations_dashboard';
import {
  apiLogin, callKw, showCaption, hideCaption, titleCard, pause,
  installCursorHighlight, readGuideState, writeGuideState,
  fetchGearmentCatalogPick, publishDraftOnlyGuide,
} from '../fixtures/guide-recorder';

const GUIDE = process.env.GUIDE_RECORDING === '1';
// Listing price is sent in COMPANY currency (USD) — NOT the shop's VND
// (memory feedback_etsy_live_publish_traps): 250000 → $250k → Etsy 400.
// 19.99 is the price the 2026-07-06 FLW rerun published with.
const LIVE_PRICE = 19.99;
const REAL_ORDER_ID = 3322;         // S03339 — real Etsy receipt 3818231452 (READ-ONLY)
const TRACKING_ANCHOR_ID = 3323;    // S03340 — tracking pushed to Etsy (READ-ONLY)
const ETSY_API_SHOP_ID = '60752333';

test.describe('HUONG_DAN VIDEO — dropship', () => {
  test.skip(!GUIDE, 'Video recording chapters — set GUIDE_RECORDING=1 to run.');

  test('chuong-01 gioi thieu va dang nhap', async ({ page }) => {
    await installCursorHighlight(page);
    await page.goto('/web/login');
    await titleCard(page,
      'Hướng dẫn quy trình Dropship',
      'Tạo sản phẩm → Đăng lên Etsy → Đơn hàng → Gearment → Tracking');
    await showCaption(page, 'Bước 1: Đăng nhập vào Odoo bằng tài khoản của bạn');
    await loginAs(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD);
    await pause(page);
    await showCaption(page, 'Đăng nhập thành công — đây là màn hình chính của Odoo', 3500);
    await hideCaption(page);
  });

  test('chuong-02 tao san pham dropship', async ({ page }) => {
    await installCursorHighlight(page);
    // Off-camera: pick a REAL Gearment catalog variant so the product is
    // quotable in chuong-05 (template x_gearment_sku = GM variant_id).
    const pick = await fetchGearmentCatalogPick();
    const marker = Date.now().toString(36).slice(-5); // lowercase — Etsy all_caps 400
    const name = `video demo dropship mug ${marker}`;
    writeGuideState({ gmVariantId: pick.variantId, gmArtworkUrl: pick.artworkUrl, productName: name });

    await apiLogin(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD, CONFIG.DB);
    await page.goto('/odoo');
    await showCaption(page, 'Bước 2: Vào menu Tồn kho → Sản phẩm để tạo sản phẩm mới');
    const f = new ProductFormPage(page);
    await f.openNew();
    await showCaption(page, 'Nhấn nút Mới — form sản phẩm chuẩn của Odoo hiện ra');

    await showCaption(page, 'Nhập tên sản phẩm (tên này sẽ là tiêu đề listing trên Etsy)');
    await f.fillName(name);
    await pause(page);

    await showCaption(page, 'Chọn Danh mục sản phẩm — mã SKU sẽ tự sinh theo danh mục');
    await f.selectCategory('Mug');
    await pause(page);
    const sku = await f.readSku();
    await showCaption(page, `Mã nội bộ (SKU) đã tự sinh: ${sku}`, 3000);

    await showCaption(page, 'Nhập Giá bán — giá này sẽ là giá niêm yết trên Etsy');
    await f.fillListPrice(LIVE_PRICE);
    await pause(page);

    await showCaption(page,
      'Nhập Mã SKU Gearment — có mã này, đơn hàng sẽ đi theo quy trình Dropship qua Gearment');
    await f.fillGearmentSku(pick.variantId);
    await pause(page);

    await showCaption(page, 'Thêm kênh bán hàng Etsy ở thẻ Kênh');
    await f.addChannel('Etsy');
    await pause(page);

    await showCaption(page, 'Nhấn Lưu — sản phẩm đã sẵn sàng để đăng lên Etsy');
    await f.save();
    await pause(page);

    // Off-camera: remember the template id for the next chapters.
    const tids = await callKw<number[]>(page, 'product.template', 'search',
      [[['name', '=', name]]], { order: 'id desc', limit: 1 });
    expect(tids.length).toBe(1);
    const variantIds = await callKw<number[]>(page, 'product.product', 'search',
      [[['product_tmpl_id', '=', tids[0]]]]);
    writeGuideState({ productTmplId: tids[0], productVariantId: variantIds[0], productSku: sku });

    await f.openTab(/Channels|Kênh/);
    await showCaption(page, 'Trạng thái kênh Etsy hiện là Nháp (Draft) — chưa đăng', 3500);
    await hideCaption(page);
  });

  test('chuong-03 dang san pham len etsy', async ({ page }) => {
    const st = readGuideState();
    expect(st.productTmplId, 'chuong-02 must run first').toBeTruthy();
    await installCursorHighlight(page);
    await apiLogin(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD, CONFIG.DB);
    await page.goto(`/odoo/inventory/products/${st.productTmplId}`);
    await page.waitForSelector('.o_form_view', { timeout: 15000 });
    await showCaption(page, 'Bước 3: Mở lại sản phẩm vừa tạo để đăng lên Etsy');

    const f = new ProductFormPage(page);
    await showCaption(page, 'Nhấn nút "Publish to Etsy" trên đầu form');
    await publishDraftOnlyGuide(page);
    await showCaption(page, 'Odoo đang gọi Etsy API... listing nháp đang được tạo', 3000);

    // Off-camera: poll channel.status for the listing id (publish RPC returns
    // before the status row commits — same race as tao-san-pham TC-013).
    let ref: string | false = false;
    const deadline = Date.now() + 20000;
    while (Date.now() < deadline && !ref) {
      const rows = await callKw<Array<{ external_ref: string | false }>>(
        page, 'product.channel.status', 'search_read',
        [[['product_tmpl_id', '=', st.productTmplId]]],
        { fields: ['external_ref', 'state'], limit: 1 });
      ref = rows?.[0]?.external_ref ?? false;
      if (!ref) await page.waitForTimeout(1000);
    }
    expect(ref, 'Etsy listing id in channel.status').toBeTruthy();
    writeGuideState({ etsyListingRef: ref });

    await page.reload();
    await page.waitForSelector('.o_form_view', { timeout: 15000 });
    await f.openTab(/Channels|Kênh/);
    await showCaption(page, `Đăng thành công — mã listing Etsy: ${ref}`, 4000);
    await showCaption(page, 'Trạng thái kênh chuyển từ Nháp sang Đã đăng', 3000);
    await hideCaption(page);
  });

  test('chuong-04 don hang etsy thuc te', async ({ page }) => {
    await installCursorHighlight(page);
    await apiLogin(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD, CONFIG.DB);
    await page.goto('/odoo');
    await showCaption(page,
      'Bước 4: Khi khách đặt hàng trên Etsy, đơn tự động đổ về Odoo (đồng bộ API mỗi 10 phút)');

    const so = new SaleOrderFormPage(page);
    await so.openById(REAL_ORDER_ID); // READ-ONLY — real buyer order
    await showCaption(page, 'Đây là một đơn hàng Etsy THẬT đã đồng bộ về Odoo', 3500);
    await showCaption(page, 'Thông tin khách mua, sản phẩm và giá lấy nguyên từ Etsy', 3500);
    await pause(page);

    await so.openTab(/Etsy/);
    await showCaption(page, 'Thẻ Etsy: mã đơn Etsy, trạng thái receipt, phí và thuế của sàn', 4000);
    await pause(page, 2500);
    await showCaption(page, 'Lời nhắn của khách mua cũng được giữ lại trên đơn', 3500);
    await hideCaption(page);
  });

  test('chuong-05 gearment fulfillment (LIVE draft)', async ({ page }) => {
    const st = readGuideState();
    expect(st.productVariantId, 'chuong-02 must run first').toBeTruthy();
    await installCursorHighlight(page);

    // ---- Off-camera fixture (admin): make the demo product a REAL dropship
    // product (Dropship route + Gearment vendor row pinned to the variant,
    // product_code = GM variant_id per FLW-01), then a demo "incoming Etsy
    // order". SO confirm lets standard procurement create the dropship PO.
    await apiLogin(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD, CONFIG.DB);
    let dropOrderId = st.dropOrderId as number | undefined;
    let dropPoId = st.dropPoId as number | undefined;
    if (!dropOrderId) {
      const vendorRef = await callKw<[string, number]>(page, 'ir.model.data',
        'check_object_reference', ['multichannel_hub_fulfillment', 'partner_gearment_vendor']);
      const dropRouteIds = await callKw<number[]>(page, 'stock.route', 'search',
        [[['name', 'ilike', 'dropship']]]);
      await callKw(page, 'product.template', 'write', [[st.productTmplId], {
        route_ids: [[6, 0, [dropRouteIds[0]]]],
        seller_ids: [[0, 0, {
          partner_id: vendorRef[1], product_id: st.productVariantId,
          product_code: st.gmVariantId, min_qty: 0, price: 5.0,
        }]],
      }]);
      const shopIds = await callKw<number[]>(page, 'etsy.shop', 'search',
        [[['etsy_api_shop_id', '=', ETSY_API_SHOP_ID]]]);
      const countryIds = await callKw<number[]>(page, 'res.country', 'search', [[['code', '=', 'US']]]);
      const stateIds = await callKw<number[]>(page, 'res.country.state', 'search',
        [[['country_id', '=', countryIds[0]], ['code', '=', 'TX']]]);
      const partnerId = await callKw<number>(page, 'res.partner', 'create', [{
        name: `Video Demo Buyer ${Date.now().toString(36).slice(-5)}`,
        street: '100 Congress Ave', city: 'Austin', zip: '78701',
        country_id: countryIds[0], state_id: stateIds[0] || false,
        phone: '+1 512 555 0100',
      }]);
      const etsyOrderId = `96${Math.floor(Date.now() / 1000) % 100000000}`;
      dropOrderId = await callKw<number>(page, 'sale.order', 'create', [{
        partner_id: partnerId,
        etsy_order_id: etsyOrderId,
        etsy_shop_id: shopIds[0],
        // Ingest service sets these; the Gearment buttons are gated on
        // sales_channel == 'etsy' (default is 'other').
        sales_channel: 'etsy',
        channel_order_ref: etsyOrderId,
        order_line: [[0, 0, {
          product_id: st.productVariantId, product_uom_qty: 1.0, price_unit: 20.0,
        }]],
      }]);
      const lineIds = await callKw<number[]>(page, 'sale.order.line', 'search',
        [[['order_id', '=', dropOrderId]]]);
      // Approved URL design → payload builder emits printing_options; without
      // it the Gearment draft push 400s ("must include at least one printing option").
      await callKw(page, 'design.file', 'create', [{
        name: `VIDEO-ART-${Date.now().toString(36).slice(-5)}`,
        order_line_id: lineIds[0], storage_mode: 'url',
        file_url: st.gmArtworkUrl, state: 'approved',
      }]);
      await callKw(page, 'sale.order', 'action_confirm', [[dropOrderId]]);
      const nameRow = await callKw<Array<{ name: string }>>(page, 'sale.order', 'read',
        [[dropOrderId], ['name']]);
      // Standard dropship procurement creates the PO on SO confirm.
      const deadline = Date.now() + 30000;
      while (Date.now() < deadline && !dropPoId) {
        const poIds = await callKw<number[]>(page, 'purchase.order', 'search',
          [[['origin', '=', nameRow[0].name]]]);
        dropPoId = poIds[0];
        if (!dropPoId) await page.waitForTimeout(1500);
      }
      expect(dropPoId, 'dropship PO auto-created on SO confirm').toBeTruthy();
      writeGuideState({ dropOrderId, dropOrderName: nameRow[0].name, dropPoId });
    }

    // ---- On-camera as BA Shipping (Gearment buttons are role-gated).
    await apiLogin(page, UAT_ROLE_LOGINS.BA_SHIPPING, CONFIG.BA_SHIPPING_PASSWORD, CONFIG.DB);
    const so = new SaleOrderFormPage(page);
    await so.openById(dropOrderId);
    await showCaption(page,
      'Bước 5: Đơn dropship (sản phẩm có mã Gearment) — nhân viên vận chuyển xử lý');
    await showCaption(page, 'File thiết kế đã được duyệt trên dòng đơn hàng', 3000);

    // Two-step UI flow: "Request Gearment Quote" fetches the live quote
    // (state draft→quoted), then "Review Quote" opens the review wizard.
    await showCaption(page, 'Nhấn "Yêu cầu báo giá Gearment" để lấy giá sản xuất + vận chuyển');
    await page.locator('button[name="action_get_gearment_quote"]').first().click();
    const reviewBtn = page.locator('button[name="action_open_gearment_quote_wizard"]').first();
    await reviewBtn.waitFor({ state: 'visible', timeout: 60000 }); // live /orders/price
    await showCaption(page, 'Đã nhận báo giá — nhấn "Xem báo giá" để xem chi tiết', 3500);
    await reviewBtn.click();
    const wiz = new GearmentQuoteWizardPage(page);
    await wiz.waitForOpen();
    const total = await wiz.readQuoteTotal();
    await showCaption(page, `Gearment báo giá trực tiếp: ${total} USD (gồm phí in + ship)`, 4500);
    await showCaption(page,
      'Lưu ý: nút Xác nhận trong cửa sổ này GỬI SẢN XUẤT và TÍNH PHÍ — chủ shop bật riêng khi vận hành thật', 5000);
    // Close WITHOUT confirming (confirm = chargeable production).
    await page.locator('.modal:visible .btn-close').first().click();
    await page.waitForTimeout(500);

    // The draft push (no charge) fires on the dropship PO confirm.
    await showCaption(page, 'Odoo đã tự tạo Đơn mua hàng dropship tới nhà cung cấp Gearment', 4000);
    await page.goto(`/odoo/purchase/${dropPoId}`);
    await page.waitForSelector('.o_form_view', { timeout: 15000 });
    await showCaption(page, 'Đây là đơn mua hàng (PO) gắn với nhà cung cấp Gearment', 3500);
    await showCaption(page, 'Nhấn "Xác nhận đơn hàng" — Odoo đẩy đơn NHÁP sang Gearment (chưa tính phí)');
    await page.locator('button[name="button_confirm"]').first().click();
    // Push is synchronous inside button_confirm — wait for the state chip.
    await page.waitForTimeout(3000);
    const deadline2 = Date.now() + 60000;
    let gmRef = '';
    while (Date.now() < deadline2 && !gmRef) {
      const rows = await callKw<Array<{ x_gearment_outbound_ref: string | false }>>(
        page, 'sale.order', 'read', [[dropOrderId], ['x_gearment_outbound_ref']]);
      gmRef = (rows[0].x_gearment_outbound_ref || '') as string;
      if (!gmRef) await page.waitForTimeout(2000);
    }
    expect(gmRef, 'Gearment draft ref on SO').toBeTruthy();
    writeGuideState({ gearmentDraftRef: gmRef });

    await so.openById(dropOrderId);
    await showCaption(page, `Đẩy thành công — mã đơn phía Gearment: ${gmRef}`, 4500);
    await showCaption(page,
      'Gearment giữ đơn ở dạng NHÁP; khi chủ shop xác nhận sản xuất, Gearment sẽ in và gửi thẳng cho khách', 5000);
    await hideCaption(page);
    console.log(`[guide] Gearment DRAFT ref (owner: discard from GM dashboard): ${gmRef}`);
  });

  test('chuong-06 tracking dong bo ve etsy', async ({ page }) => {
    await installCursorHighlight(page);
    await apiLogin(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD, CONFIG.DB);
    await page.goto('/odoo');
    await showCaption(page,
      'Bước 6: Khi Gearment gửi hàng, mã vận đơn tự động cập nhật về Odoo qua webhook');

    // READ-ONLY anchor: S03340 already has tracking pushed to Etsy. We only
    // SHOW the synced state — never re-push on a real buyer order.
    const so = new SaleOrderFormPage(page);
    await so.openById(TRACKING_ANCHOR_ID);
    await showCaption(page, 'Đơn này đã có mã vận đơn do hệ thống tự nhận về', 3500);
    await pause(page);
    await so.openTab(/Etsy/);
    await showCaption(page,
      'Trạng thái "Đã đẩy tracking lên Etsy" — khách mua nhận được thông báo giao hàng trên Etsy', 4500);
    await showCaption(page,
      'Việc đẩy tracking chạy tự động; nút đẩy thủ công chỉ dùng khi đồng bộ lỗi', 4000);
    await hideCaption(page);
  });

  test('chuong-07 dashboard va ket thuc', async ({ page }) => {
    await installCursorHighlight(page);
    await apiLogin(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD, CONFIG.DB);
    const dash = new OperationsDashboardPage(page);
    await dash.open();
    await showCaption(page,
      'Toàn bộ đơn hàng các kênh được theo dõi tập trung tại bảng điều khiển Vận hành', 4500);
    await pause(page, 2000);
    await titleCard(page,
      'Hoàn tất quy trình Dropship',
      'Sản phẩm → Etsy → Đơn hàng → Gearment sản xuất & gửi → Tracking về Etsy');
  });
});
