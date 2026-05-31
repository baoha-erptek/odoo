import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object for the sale.order form.
 *
 * Composes inherited views from:
 *   - multichannel_hub_core/views/sale_order_form.xml — Design Files tab + smart button
 *     (`action_open_design_files`, `action_open_design_file_upload_wizard`).
 *   - etsy_integration/views/sale_order_views.xml — Etsy tab + buttons:
 *       button[name="action_request_address_change"]  (BA → BA Lead approval flow)
 *       button[name="action_push_tracking_to_etsy"]   (post-tracking outbound push)
 *
 * `x_pipeline_state_id` (multichannel_hub_core/models/sale_order.py:129) is mutated via
 * `_write_pipeline_state()` per FR-017 defense-in-depth. We never write directly; pipeline
 * advances in UAT happen through the Operations dashboard bulk-action surface (see
 * OperationsDashboardPage.runBulkAction).
 *
 * Mutation policy:
 *   - readPipelineState, readField, readChatterMessages, openTab — read-only.
 *   - clickPushTrackingToEtsy, clickRequestAddressChange — mutating; only call against
 *     UAT-2026-05-31-* seeded orders, never against real S00007.
 */
export class SaleOrderFormPage {
  readonly page: Page;
  readonly form: Locator;
  readonly breadcrumb: Locator;
  readonly pipelineStateField: Locator;
  readonly hasPendingAddressChange: Locator;
  readonly requestAddressChangeButton: Locator;
  readonly pushTrackingButton: Locator;
  readonly openDesignFilesSmartButton: Locator;
  readonly openDesignUploadButton: Locator;
  readonly chatterInput: Locator;
  readonly chatterSendButton: Locator;
  readonly errorModal: Locator;

  constructor(page: Page) {
    this.page = page;
    this.form = page.locator('.o_form_view').first();
    this.breadcrumb = page.locator('.o_breadcrumb, .o_control_panel_breadcrumbs').first();
    this.pipelineStateField = page.locator('[name="x_pipeline_state_id"]').first();
    this.hasPendingAddressChange = page.locator('[name="has_pending_address_change"] input').first();
    this.requestAddressChangeButton = page.locator('button[name="action_request_address_change"]').first();
    this.pushTrackingButton = page.locator('button[name="action_push_tracking_to_etsy"]').first();
    this.openDesignFilesSmartButton = page.locator('button[name="action_open_design_files"]').first();
    this.openDesignUploadButton = page.locator('button[name="action_open_design_file_upload_wizard"]').first();
    // Chatter: Odoo 19 mail.chatter component
    this.chatterInput = page.locator('.o-mail-Composer-input, .o_ChatterComposer textarea').first();
    this.chatterSendButton = page.locator('.o-mail-Composer-send, button:has-text("Send")').first();
    this.errorModal = page.locator('.modal-dialog', {
      has: page.locator(
        '.modal-title:has-text("Validation Error"), .modal-title:has-text("User Error"), ' +
        '.modal-title:has-text("Access Error"), .modal-title:has-text("Warning")',
      ),
    }).locator('.modal-body');
  }

  // --- navigation ---------------------------------------------------------

  /** Open the SO list and click the row whose breadcrumb name matches (e.g. "S00007"). */
  async openByName(orderName: string): Promise<void> {
    await this.page.goto('/odoo/sales');
    await this.page.waitForSelector('.o_list_view, .o_kanban_view', { timeout: 15000 });
    // Search by name to dodge pagination on large staging DBs.
    const search = this.page.locator('.o_searchview_input').first();
    await search.click();
    await search.fill(orderName);
    await search.press('Enter');
    await this.page.waitForTimeout(500);
    const row = this.page.locator('tr.o_data_row, .o_kanban_record', { hasText: orderName }).first();
    await row.waitFor({ state: 'visible', timeout: 8000 });
    await row.click();
    await this.form.waitFor({ state: 'visible', timeout: 15000 });
  }

  /** Open the SO form directly by database id (cheaper than search). */
  async openById(orderId: number): Promise<void> {
    await this.page.goto(`/odoo/sales/${orderId}`);
    await this.form.waitFor({ state: 'visible', timeout: 15000 });
  }

  /** Switch to a notebook page by visible label (lazy-render safe: openTab + waitFor). */
  async openTab(label: string | RegExp): Promise<void> {
    const tab = this.page.locator('.o_notebook .nav-link', { hasText: label }).first();
    await tab.waitFor({ state: 'visible', timeout: 8000 });
    await tab.click();
    await this.page.waitForTimeout(250); // lazy-rendered tab content
  }

  // --- read-only assertions -----------------------------------------------

  /** Returns the current pipeline state's display name (e.g. "Chờ File"). Empty if unset. */
  async readPipelineState(): Promise<string> {
    await this.pipelineStateField.waitFor({ state: 'visible', timeout: 8000 });
    const input = this.pipelineStateField.locator('input').first();
    if (await input.count() > 0) {
      return (await input.inputValue()).trim();
    }
    return (await this.pipelineStateField.textContent())?.trim() ?? '';
  }

  /** Returns the value of a named field (works for inputs and read-only spans). */
  async readField(fieldName: string): Promise<string> {
    const field = this.page.locator(`[name="${fieldName}"]`).first();
    await field.waitFor({ state: 'visible', timeout: 8000 });
    const input = field.locator('input, textarea').first();
    if (await input.count() > 0) {
      const val = await input.inputValue().catch(() => '');
      if (val) return val.trim();
    }
    return (await field.textContent())?.trim() ?? '';
  }

  /** Returns true if a notebook tab with the given label is present. */
  async hasTab(label: string | RegExp): Promise<boolean> {
    const tab = this.page.locator('.o_notebook .nav-link', { hasText: label }).first();
    return (await tab.count()) > 0;
  }

  /**
   * Returns the visible text of the last N chatter messages (newest first). Useful
   * for asserting "Address change requested" / "Tracking pushed" trail.
   */
  async readChatterMessages(limit = 5): Promise<string[]> {
    const messages = this.page.locator('.o-mail-Message-content, .o_Message_content');
    const count = Math.min(await messages.count(), limit);
    const out: string[] = [];
    for (let i = 0; i < count; i += 1) {
      out.push(((await messages.nth(i).textContent()) ?? '').trim());
    }
    return out;
  }

  // --- design files ------------------------------------------------------

  /** Click the "Design Files" smart button (opens the kanban filtered by this order). */
  async openDesignFiles(): Promise<void> {
    await this.openDesignFilesSmartButton.click();
    await this.page.waitForSelector('.o_kanban_view, .o_list_view', { timeout: 10000 });
  }

  /** Open the design-file upload wizard pre-bound to this order. */
  async openDesignUploadWizard(): Promise<void> {
    await this.openTab(/Design Files|Tệp thiết kế/);
    await this.openDesignUploadButton.waitFor({ state: 'visible', timeout: 8000 });
    await this.openDesignUploadButton.click();
    const modal = this.page.locator('.modal-dialog').first();
    await modal.waitFor({ state: 'visible', timeout: 10000 });
  }

  // --- mutating actions (opt-in; never on real-data orders) --------------

  /**
   * Click "Yêu cầu đổi địa chỉ" → opens address-change wizard.
   * Pre-condition: order is BA-owned AND `has_pending_address_change == False`
   * (button hidden otherwise — see etsy_integration sale_order_views.xml).
   */
  async clickRequestAddressChange(): Promise<void> {
    await this.requestAddressChangeButton.waitFor({ state: 'visible', timeout: 8000 });
    await this.requestAddressChangeButton.click();
    const modal = this.page.locator('.modal-dialog').first();
    await modal.waitFor({ state: 'visible', timeout: 10000 });
  }

  /**
   * Click "Push Tracking to Etsy" → triggers EtsyTrackingPusher for this order.
   * MUTATING + outbound API call. Pre-conditions:
   *   - `tracking_number` is set
   *   - `etsy_tracking_push_status` != 'pushed'
   * Returns the toast text emitted by the action.
   */
  async clickPushTrackingToEtsy(): Promise<string> {
    await this.openTab(/Etsy/);
    await this.pushTrackingButton.waitFor({ state: 'visible', timeout: 8000 });
    await this.pushTrackingButton.click();
    const toast = this.page.locator('.o_notification_body, .o_notification_content').first();
    await toast.waitFor({ state: 'visible', timeout: 30000 });
    return (await toast.textContent())?.trim() ?? '';
  }

  /** Send a chatter message (e.g. seeding a buyer reply or operator note). */
  async sendChatterMessage(body: string): Promise<void> {
    // Some screens hide the composer behind a "Send message" button.
    const opener = this.page.locator('.o-mail-Chatter-sendMessage, button:has-text("Send message")').first();
    if (await opener.count() > 0 && !(await this.chatterInput.isVisible().catch(() => false))) {
      await opener.click();
    }
    await this.chatterInput.waitFor({ state: 'visible', timeout: 8000 });
    await this.chatterInput.fill(body);
    await this.chatterSendButton.click();
    await this.page.waitForTimeout(500);
  }
}
