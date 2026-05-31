import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object for etsy.address.change.request (Flow-2 TC-006).
 *
 * Sources verified on staging etsy_integration 19.0.2.30.0:
 *   - Model: etsy.address.change.request (states: pending/approved/rejected)
 *   - View: etsy_integration/views/etsy_address_change_request_views.xml
 *   - Form buttons:
 *       action_approve  → group_address_lead (BA Lead)
 *       action_reject   → group_address_lead
 *   - SO entry point: button[name="action_request_address_change"] on sale.order
 *     (BA role; visible only when `is_etsy_order=True` and no pending request).
 *
 * Workflow (per HUONG_DAN_DON_HANG_ETSY_VN TC-006):
 *   1. BA on sale.order clicks "Yêu cầu đổi địa chỉ" → opens this form pre-filled
 *      with `order_id`, `requested_by`, `reason`, `new_values` (JSON of partner fields).
 *   2. BA Lead opens the request from menu → reviews → Approve or Reject.
 *   3. On approve: partner address is updated atomically.
 *   4. On reject: BA must rework / contact buyer; original address kept.
 *
 * Mutation policy: clickApprove + clickReject are mutating. Only operate against
 * UAT-2026-05-31-ADDR-* seeded requests.
 */
export class AddressChangeRequestFormPage {
  readonly page: Page;
  readonly form: Locator;
  readonly stateBadge: Locator;
  readonly orderIdField: Locator;
  readonly requestedByField: Locator;
  readonly reasonField: Locator;
  readonly newValuesField: Locator;
  readonly rejectionReasonField: Locator;
  readonly approveButton: Locator;
  readonly rejectButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.form = page.locator('.o_form_view').first();
    this.stateBadge = page.locator('[name="state"]').first();
    this.orderIdField = page.locator('[name="order_id"]').first();
    this.requestedByField = page.locator('[name="requested_by"]').first();
    this.reasonField = page.locator('[name="reason"]').first();
    this.newValuesField = page.locator('[name="new_values"]').first();
    this.rejectionReasonField = page.locator('[name="rejection_reason"]').first();
    this.approveButton = page.locator('button[name="action_approve"]').first();
    this.rejectButton = page.locator('button[name="action_reject"]').first();
  }

  // --- navigation ---------------------------------------------------------

  /** Open the Address Change Requests list and click into a row matching the order name. */
  async openByOrderName(orderName: string): Promise<void> {
    await this.page.goto('/odoo/action-etsy_integration.action_etsy_address_change_request');
    await this.page.waitForSelector('.o_list_view', { timeout: 15000 });
    const row = this.page.locator('tr.o_data_row', { hasText: orderName }).first();
    await row.waitFor({ state: 'visible', timeout: 8000 });
    await row.click();
    await this.form.waitFor({ state: 'visible', timeout: 15000 });
  }

  /** Open by request id (cheaper). */
  async openById(requestId: number): Promise<void> {
    await this.page.goto(`/odoo/action-etsy_integration.action_etsy_address_change_request/${requestId}`);
    await this.form.waitFor({ state: 'visible', timeout: 15000 });
  }

  // --- read-only assertions -----------------------------------------------

  /** Returns the current state ('pending' | 'approved' | 'rejected'). */
  async readState(): Promise<string> {
    await this.stateBadge.waitFor({ state: 'visible', timeout: 8000 });
    return ((await this.stateBadge.textContent()) ?? '').trim().toLowerCase();
  }

  /** Returns the linked sale.order display name. */
  async readOrderName(): Promise<string> {
    const input = this.orderIdField.locator('input').first();
    if (await input.count() > 0) return (await input.inputValue()).trim();
    return ((await this.orderIdField.textContent()) ?? '').trim();
  }

  /** Returns the reason text (BA's stated cause for the change). */
  async readReason(): Promise<string> {
    const ta = this.reasonField.locator('textarea, input').first();
    if (await ta.count() > 0) return (await ta.inputValue()).trim();
    return ((await this.reasonField.textContent()) ?? '').trim();
  }

  /** Returns the raw new_values JSON string. */
  async readNewValues(): Promise<string> {
    const ta = this.newValuesField.locator('textarea, input').first();
    if (await ta.count() > 0) return (await ta.inputValue()).trim();
    return ((await this.newValuesField.textContent()) ?? '').trim();
  }

  // --- mutating actions ---------------------------------------------------

  /** BA Lead approves the request → partner address gets updated. */
  async clickApprove(): Promise<void> {
    await this.approveButton.waitFor({ state: 'visible', timeout: 8000 });
    await this.approveButton.click();
    await this.page.waitForTimeout(500);
  }

  /**
   * BA Lead rejects with a reason. The form requires `rejection_reason` to be set
   * before Reject succeeds (server-side @api.constrains).
   */
  async clickReject(rejectionReason: string): Promise<void> {
    // The rejection_reason field is only writable while state=pending; fill first.
    const ta = this.rejectionReasonField.locator('textarea, input').first();
    await ta.fill(rejectionReason);
    await this.rejectButton.click();
    await this.page.waitForTimeout(500);
  }
}
