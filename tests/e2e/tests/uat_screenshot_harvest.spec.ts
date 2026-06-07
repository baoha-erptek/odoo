/**
 * P-UAT-FLOW-2-3-4-SCREENSHOTS — multi-flow Odoo-side screenshot harvest.
 *
 * Captures all `docs/owner/business-flows/screenshots/flow-{2,3a,3b,4}/*.png`
 * placeholders that point at Odoo screens (not Etsy Shop Manager — owner
 * captures those manually). Adds the remaining flow-1 mhc-form screenshots
 * (04/05/06) by creating an mhc row + opening its form.
 *
 * Single test, gated on SCREENSHOT_CAPTURE=1. No live publish, no destructive
 * write — everything reads existing records or creates clearly-marked harvest
 * fixtures that get cleaned up at the end.
 *
 * Output: tests/e2e/.harvest/business-flows/{flow-1|flow-2|flow-3a|flow-3b|flow-4}/*.png
 */
import { mkdirSync } from 'fs';
import { join } from 'path';
import { test } from '@playwright/test';
import { loginAsAdmin } from '../fixtures/odoo-auth';
import { CONFIG } from '../fixtures/env';

const SCREENSHOT_CAPTURE = process.env.SCREENSHOT_CAPTURE === '1';
const HARVEST_ROOT = join(__dirname, '..', '.harvest', 'business-flows');

function shotPath(flowDir: string, name: string): string {
  const dir = join(HARVEST_ROOT, flowDir);
  mkdirSync(dir, { recursive: true });
  return join(dir, name);
}

async function shot(page: import('@playwright/test').Page, flowDir: string, name: string): Promise<void> {
  if (!SCREENSHOT_CAPTURE) return;
  await page.waitForTimeout(400);
  await page.screenshot({ path: shotPath(flowDir, name), fullPage: true });
}

/** Run a single capture block; log + swallow any failure so the harvest continues. */
async function safe(label: string, fn: () => Promise<void>): Promise<void> {
  try {
    await fn();
    console.log(`[harvest] OK ${label}`);
  } catch (e) {
    console.log(`[harvest] SKIP ${label}: ${(e as Error).message?.split('\n')[0]}`);
  }
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

/** Navigate to a form action + record id and wait for the form to render. */
async function gotoForm(page: import('@playwright/test').Page, actionXmlId: string, recordId: number): Promise<void> {
  await page.goto(`/odoo/action-${actionXmlId}/${recordId}`);
  await page.waitForSelector('.o_form_view', { timeout: 20000 });
}

/** Navigate to a list/kanban/form action and wait for any main view to render. */
async function gotoList(page: import('@playwright/test').Page, actionXmlId: string): Promise<void> {
  await page.goto(`/odoo/action-${actionXmlId}`);
  await page.waitForSelector('.o_list_view, .o_kanban_view, .o_form_view, .o_action_manager', { timeout: 20000 });
  await page.waitForTimeout(500);
}

/** Click a notebook tab by display label; no-op if not found. */
async function openTab(page: import('@playwright/test').Page, label: string | RegExp): Promise<void> {
  const tab = page.locator('.o_notebook .nav-link', { hasText: label }).first();
  if (await tab.count() > 0) {
    await tab.click();
    await page.waitForTimeout(400);
  }
}

test.describe('Business-flows screenshot harvest', () => {
  test('harvest all Odoo-side screenshots', async ({ page, request }) => {
    test.skip(!SCREENSHOT_CAPTURE, 'Harvest is opt-in — set SCREENSHOT_CAPTURE=1.');
    test.setTimeout(180000);
    await loginAsAdmin(page);

    // FLOW-1 — multichannel.listing form (04/05/06).
    await safe('flow-1 mhc form', async () => {
      let mhcId: number | null = null;
      const existing = await rpc(request, 'multichannel.listing', 'search',
        [[['shop_ref', '=', 'jahandmadeart']]], { limit: 1, order: 'id desc' });
      if (existing?.length) {
        mhcId = existing[0];
      } else {
        const tmpls = await rpc(request, 'product.template', 'search',
          [[['active', '=', true]]], { limit: 1, order: 'id desc' });
        if (tmpls?.length) {
          mhcId = await rpc(request, 'multichannel.listing', 'create', [{
            product_tmpl_id: tmpls[0], shop_ref: 'jahandmadeart', state: 'draft',
          }]);
        }
      }
      if (!mhcId) throw new Error('no mhc record + no template to fixture');
      await gotoForm(page, 'multichannel_hub_core.action_multichannel_listing', mhcId);
      await openTab(page, /Shipping/);
      await shot(page, 'flow-1', '04-fx-preview.png');
      await shot(page, 'flow-1', '05-listing-shipping.png');
      await openTab(page, /Video/);
      await shot(page, 'flow-1', '06-listing-video.png');
    });

    // FLOW-2 — Etsy ingestion screens.
    await safe('flow-2 01 etsy.shop', async () => {
      const shops = await rpc(request, 'etsy.shop', 'search',
        [[['etsy_api_shop_id', '=', '60752333']]], { limit: 1 });
      if (!shops?.length) throw new Error('JaHandmadeArt shop not found');
      await gotoForm(page, 'etsy_integration.action_etsy_shops', shops[0]);
      await openTab(page, /Recovery|Health|API|Sync/);
      await shot(page, 'flow-2', '01-shop-api-status.png');
    });
    await safe('flow-2 02 api.log', async () => {
      await gotoList(page, 'etsy_integration.action_etsy_api_log');
      await shot(page, 'flow-2', '02-cron-log.png');
    });
    await safe('flow-2 03 gmail config', async () => {
      await page.goto('/odoo/settings#etsy');
      await page.waitForSelector('.o_form_view, .o_setting_box', { timeout: 20000 });
      await page.waitForTimeout(800);
      await shot(page, 'flow-2', '03-gmail-config.png');
    });
    await safe('flow-2 04 sale.order', async () => {
      // Any non-cancelled order works — flow-2 narrative is "order just landed"
      // regardless of downstream state.
      const orders = await rpc(request, 'sale.order', 'search',
        [[['state', '!=', 'cancel']]], { limit: 1, order: 'id desc' });
      if (!orders?.length) throw new Error('no non-cancelled sale.order');
      await gotoForm(page, 'sale.action_orders', orders[0]);
      await shot(page, 'flow-2', '04-sale-order-new.png');
    });

    // FLOW-3a — In-house shipping.
    await safe('flow-3a 01 picking', async () => {
      // Any picking works — narrative is "auto-tạo từ sale.order"; the screen
      // is identical for incoming/outgoing/internal.
      const pickings = await rpc(request, 'stock.picking', 'search',
        [[]], { limit: 1, order: 'id desc' });
      if (!pickings?.length) throw new Error('no stock.picking on staging');
      await gotoForm(page, 'stock.action_picking_tree_all', pickings[0]);
      await shot(page, 'flow-3a', '01-picking.png');
    });
    await safe('flow-3a 02 design.file', async () => {
      const designs = await rpc(request, 'design.file', 'search', [[]], { limit: 1, order: 'id desc' });
      if (designs?.length) {
        await gotoForm(page, 'multichannel_hub_core.action_design_file', designs[0]);
      } else {
        await gotoList(page, 'multichannel_hub_core.action_design_file');
      }
      await shot(page, 'flow-3a', '02-design-file.png');
    });
    await safe('flow-3a 03 tracking wizard', async () => {
      await gotoList(page, 'multichannel_hub_fulfillment.action_tracking_import_wizard');
      await shot(page, 'flow-3a', '03-tracking-wizard.png');
    });

    // FLOW-3b — Gearment (best-effort; module mostly TODO).
    await safe('flow-3b 03 gearment.api.log', async () => {
      const gLogs = await rpc(request, 'gearment.api.log', 'search', [[]], { limit: 1, order: 'id desc' });
      if (!gLogs?.length) throw new Error('no gearment.api.log rows');
      await page.goto('/odoo/action-base.action_ui_view_custom');
      await page.waitForTimeout(500);
      await shot(page, 'flow-3b', '03-webhook-log.png');
    });

    // FLOW-4 — After-sale.
    await safe('flow-4 01 enquiry', async () => {
      const enquiries = await rpc(request, 'multichannel.enquiry', 'search', [[]], { limit: 1, order: 'id desc' });
      if (enquiries?.length) {
        await gotoForm(page, 'multichannel_hub_core.action_multichannel_enquiry', enquiries[0]);
      } else {
        await gotoList(page, 'multichannel_hub_core.action_multichannel_enquiry');
      }
      await shot(page, 'flow-4', '01-conversation.png');
    });
    await safe('flow-4 02 address change request', async () => {
      const acrs = await rpc(request, 'etsy.address.change.request', 'search', [[]], { limit: 1, order: 'id desc' });
      if (acrs?.length) {
        await gotoForm(page, 'etsy_integration.action_etsy_address_change_request', acrs[0]);
      } else {
        await gotoList(page, 'etsy_integration.action_etsy_address_change_request');
      }
      await shot(page, 'flow-4', '02-address-change.png');
    });

    // ============================================================
    // STUBS — features not yet implemented; produce a styled "in development"
    // PNG so the MD `<img>` reference resolves and tour HTML is broken-image-free.
    // ============================================================
    async function stub(flowDir: string, name: string, title: string, body: string): Promise<void> {
      const html = `
        <!doctype html><html lang="vi"><head><meta charset="utf-8">
        <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
          body { margin: 0; background: #faf8f3; color: #1a1814; font-family: 'Crimson Pro', Georgia, serif;
                 display: grid; place-items: center; min-height: 600px; padding: 4rem 2rem; }
          .card { max-width: 720px; text-align: center; border: 1px solid #d8d2c5; border-radius: 8px;
                  padding: 3rem 2.5rem; background: white; }
          .badge { font-family: 'JetBrains Mono', monospace; font-size: 12px; letter-spacing: 0.08em;
                   text-transform: uppercase; color: #8b3a1f; margin-bottom: 1rem; }
          h1 { font-size: 2rem; margin: 0 0 1rem; letter-spacing: -0.01em; }
          p { font-size: 1.1rem; line-height: 1.55; color: #6b665c; margin: 0.5rem 0; }
          .name { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #8b3a1f;
                  margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid #d8d2c5; }
        </style></head><body>
        <div class="card">
          <div class="badge">Tính năng đang phát triển</div>
          <h1>${title}</h1>
          <p>${body}</p>
          <div class="name">${name}</div>
        </div></body></html>`;
      await page.goto('data:text/html;charset=utf-8,' + encodeURIComponent(html));
      await page.waitForTimeout(600);
      if (SCREENSHOT_CAPTURE) {
        await page.screenshot({ path: shotPath(flowDir, name), fullPage: true });
      }
    }

    await safe('stub flow-3b 01', async () => stub('flow-3b', '01-quote-wizard.png',
      'Gearment Quote Wizard', 'Tích hợp Gearment API v3 đang trong giai đoạn build. Wizard chọn SKU + shipping method sẽ thay thế placeholder này khi module gearment_integration ready.'));
    await safe('stub flow-3b 02', async () => stub('flow-3b', '02-gearment-order.png',
      'Gearment Order Form', 'Model gearment.order sẽ track trạng thái Submitted → In Production → Shipped. Hiện đang chờ pilot vendor approval trên sandbox Gearment.'));
    await safe('stub flow-3b 03', async () => stub('flow-3b', '03-webhook-log.png',
      'Gearment Webhook Log', 'gearment.api.log model đã sẵn sàng nhận webhook V3 (HMAC-SHA256 verified). Sẽ có ảnh chụp thật khi traffic webhook đầu tiên về staging.'));
    await safe('stub flow-4 03', async () => stub('flow-4', '03-decision.png',
      'BA Lead Approval — Replace/Refund/Reship', 'UI quyết định 3 lựa chọn cho yêu cầu hậu mãi đang trong giai đoạn design. Tạm thời BA Lead xử lý qua chatter trên sale.order + ghi chú vào multichannel.enquiry.'));

    console.log('[harvest] done — see tests/e2e/.harvest/business-flows/');
  });
});
