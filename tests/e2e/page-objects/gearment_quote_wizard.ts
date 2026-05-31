import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object for the gearment.quote.wizard (Flow-3 TC-DROP-002/003).
 *
 * Sources verified on staging mhf 19.0.1.0.*:
 *   - Model: multichannel_hub_fulfillment/wizards/gearment_quote_wizard.py
 *     methods: action_confirm (push) / action_cancel (discard)
 *     ACL: _check_ba_shipping_or_raise (BA Shipping role required)
 *   - View: multichannel_hub_fulfillment/wizards/gearment_quote_wizard_views.xml
 *     fields: order_id (readonly), quote_currency, quote_total (monetary),
 *             quote_expires_at, quote_breakdown_json (raw text)
 *   - Opened from sale.order via button[name="action_open_gearment_quote_wizard"]
 *     (multichannel_hub_fulfillment/views/sale_order_views.xml:22)
 *
 * Mutation policy: `action_confirm` calls Gearment v3 POST /orders (creates a real
 * production-side order). Only invoke against UAT-2026-05-31-DROP-* seeded orders.
 */
export class GearmentQuoteWizardPage {
  readonly page: Page;
  readonly modal: Locator;
  readonly orderIdField: Locator;
  readonly quoteCurrencyField: Locator;
  readonly quoteTotalField: Locator;
  readonly quoteExpiresAtField: Locator;
  readonly quoteBreakdownField: Locator;
  readonly confirmButton: Locator;
  readonly cancelButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.modal = page.locator('.modal-dialog', {
      has: page.locator('[name="quote_breakdown_json"]'),
    }).first();
    this.orderIdField = this.modal.locator('[name="order_id"]').first();
    this.quoteCurrencyField = this.modal.locator('[name="quote_currency"]').first();
    this.quoteTotalField = this.modal.locator('[name="quote_total"]').first();
    this.quoteExpiresAtField = this.modal.locator('[name="quote_expires_at"]').first();
    this.quoteBreakdownField = this.modal.locator('[name="quote_breakdown_json"]').first();
    this.confirmButton = this.modal.locator('button[name="action_confirm"]').first();
    this.cancelButton = this.modal.locator('button[name="action_cancel"]').first();
  }

  // --- lifecycle ----------------------------------------------------------

  /** Wait for the wizard modal to render (after SO's action_open_gearment_quote_wizard). */
  async waitForOpen(): Promise<void> {
    await this.modal.waitFor({ state: 'visible', timeout: 30000 });
    // Gearment quote endpoint may take several seconds; total field hydrates last.
    await this.quoteTotalField.waitFor({ state: 'visible', timeout: 30000 });
  }

  /** Returns true if the wizard is currently visible. */
  async isOpen(): Promise<boolean> {
    return (await this.modal.count()) > 0 && (await this.modal.isVisible());
  }

  // --- read-only assertions -----------------------------------------------

  /** Returns the parsed quote_total (Float). NaN if not parseable. */
  async readQuoteTotal(): Promise<number> {
    const txt = ((await this.quoteTotalField.textContent()) ?? '').trim();
    // Monetary widget formats as "123.45 USD"; strip non-numeric except dot/comma.
    const normalized = txt.replace(/[^0-9.,-]/g, '').replace(',', '');
    return parseFloat(normalized);
  }

  /** Returns the ISO datetime string of quote_expires_at (raw display text). */
  async readQuoteExpiresAt(): Promise<string> {
    return ((await this.quoteExpiresAtField.textContent()) ?? '').trim();
  }

  /** Returns the raw breakdown JSON text. */
  async readBreakdownJson(): Promise<string> {
    const input = this.quoteBreakdownField.locator('textarea, input').first();
    if (await input.count() > 0) {
      return (await input.inputValue()).trim();
    }
    return ((await this.quoteBreakdownField.textContent()) ?? '').trim();
  }

  // --- mutating actions ---------------------------------------------------

  /**
   * Confirm the quote → triggers real Gearment POST /orders.
   * Returns the toast text. Wizard closes on success.
   */
  async confirm(): Promise<string> {
    await this.confirmButton.click();
    const toast = this.page.locator('.o_notification_body, .o_notification_content').first();
    await toast.waitFor({ state: 'visible', timeout: 60000 });
    await this.modal.waitFor({ state: 'hidden', timeout: 15000 }).catch(() => undefined);
    return ((await toast.textContent()) ?? '').trim();
  }

  /** Cancel the wizard (no side effects). */
  async cancel(): Promise<void> {
    await this.cancelButton.click();
    await this.modal.waitFor({ state: 'hidden', timeout: 8000 });
  }
}
