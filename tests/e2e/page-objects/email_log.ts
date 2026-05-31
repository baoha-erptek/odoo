import { Page, Locator } from '@playwright/test';

/**
 * Page Object for etsy.email.log (Flow-2 TC-004/005/008).
 *
 * Sources verified on staging etsy_integration 19.0.2.30.0:
 *   - Model: etsy.email.log (parse_status: success|failed|skipped)
 *   - List/form/search: etsy_integration/views/etsy_email_log_views.xml
 *   - Form button: action_retry_parse → re-runs services/email_parser on raw_body
 *   - Search filters: filter_all/filter_success/filter_failed/filter_skipped
 *
 * Read-only by default. action_retry_parse is mutating (re-creates / updates the
 * linked sale.order) — only call against synthetic UAT-2026-05-31-* email-log rows.
 */
export class EmailLogPage {
  readonly page: Page;
  readonly listView: Locator;
  readonly form: Locator;
  readonly searchInput: Locator;
  readonly retryParseButton: Locator;
  readonly viewOrderButton: Locator;
  readonly errorMessageField: Locator;
  readonly parseStatusBadge: Locator;
  readonly saleOrderIdField: Locator;

  constructor(page: Page) {
    this.page = page;
    this.listView = page.locator('.o_list_view').first();
    this.form = page.locator('.o_form_view').first();
    this.searchInput = page.locator('.o_searchview_input').first();
    this.retryParseButton = page.locator('button[name="action_retry_parse"]').first();
    this.viewOrderButton = page.locator('button[name="action_view_order"]').first();
    this.errorMessageField = page.locator('[name="error_message"]').first();
    this.parseStatusBadge = page.locator('[name="parse_status"]').first();
    this.saleOrderIdField = page.locator('[name="sale_order_id"]').first();
  }

  // --- navigation ---------------------------------------------------------

  /** Open the Email Log list. Menu under Etsy. */
  async openList(): Promise<void> {
    await this.page.goto('/odoo/action-etsy_integration.action_etsy_email_log');
    await this.listView.waitFor({ state: 'visible', timeout: 15000 });
  }

  /** Apply a named search filter (Success | Failed | Skipped | All). */
  async applyFilter(label: string | RegExp): Promise<void> {
    // Open the search-bar filter dropdown
    const filterBtn = this.page.locator('button:has-text("Filters"), button:has-text("Bộ lọc")').first();
    if (await filterBtn.count() > 0) {
      await filterBtn.click();
      const item = this.page.locator('.o_menu_item, .dropdown-item', { hasText: label }).first();
      if (await item.count() > 0) {
        await item.click();
        await this.page.waitForTimeout(300);
        return;
      }
    }
    // Fallback: free-text search
    await this.searchInput.click();
    await this.searchInput.fill(typeof label === 'string' ? label : '');
    await this.searchInput.press('Enter');
    await this.page.waitForTimeout(300);
  }

  /** Search the list by Gmail message ID or subject. */
  async search(term: string): Promise<void> {
    await this.searchInput.click();
    await this.searchInput.fill(term);
    await this.searchInput.press('Enter');
    await this.page.waitForTimeout(300);
  }

  /** Open a single log row matching the given text. */
  async openLogByText(text: string): Promise<void> {
    const row = this.page.locator('tr.o_data_row', { hasText: text }).first();
    await row.waitFor({ state: 'visible', timeout: 8000 });
    await row.click();
    await this.form.waitFor({ state: 'visible', timeout: 15000 });
  }

  // --- read-only assertions -----------------------------------------------

  /** Returns the number of rows currently visible in the list. */
  async readRowCount(): Promise<number> {
    return await this.page.locator('tr.o_data_row').count();
  }

  /** Returns the parse_status badge text for the currently open log form. */
  async readParseStatus(): Promise<string> {
    await this.parseStatusBadge.waitFor({ state: 'visible', timeout: 8000 });
    return ((await this.parseStatusBadge.textContent()) ?? '').trim().toLowerCase();
  }

  /** Returns the error_message text (empty if parse succeeded). */
  async readErrorMessage(): Promise<string> {
    if (await this.errorMessageField.count() === 0) return '';
    return ((await this.errorMessageField.textContent()) ?? '').trim();
  }

  /** Returns the linked sale_order_id display name (empty if no link). */
  async readSaleOrderName(): Promise<string> {
    if (await this.saleOrderIdField.count() === 0) return '';
    const input = this.saleOrderIdField.locator('input').first();
    if (await input.count() > 0) return (await input.inputValue()).trim();
    return ((await this.saleOrderIdField.textContent()) ?? '').trim();
  }

  // --- mutating actions ---------------------------------------------------

  /**
   * Click Retry Parse. Re-runs the parser; on success, creates/links the sale.order
   * and flips parse_status to 'success'. Returns toast text.
   */
  async clickRetryParse(): Promise<string> {
    await this.retryParseButton.waitFor({ state: 'visible', timeout: 8000 });
    await this.retryParseButton.click();
    const toast = this.page.locator('.o_notification_body, .o_notification_content').first();
    await toast.waitFor({ state: 'visible', timeout: 15000 });
    return ((await toast.textContent()) ?? '').trim();
  }
}
