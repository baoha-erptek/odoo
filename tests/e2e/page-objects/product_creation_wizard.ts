import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object for product.creation.wizard.
 *
 * Model source: custom_addons/multichannel_hub_core/wizards/product_creation_wizard.py
 * View action xmlid: multichannel_hub_core.action_product_creation_wizard
 * FR-017 gate: multichannel_hub_core.group_ba_user
 */
export class ProductCreationWizardPage {
  readonly page: Page;
  readonly form: Locator;
  readonly nameInput: Locator;
  readonly defaultCodeInput: Locator;
  readonly categIdInput: Locator;
  readonly listingPriceInput: Locator;
  readonly shippingPriceInput: Locator;
  readonly gearmentSkuInput: Locator;
  readonly channelTagInput: Locator;
  readonly createButton: Locator;
  readonly cancelButton: Locator;
  readonly notification: Locator;

  constructor(page: Page) {
    this.page = page;
    this.form = page.locator('.o_form_view').first();
    this.nameInput = page.locator('[name="name"] input, [name="name"] textarea').first();
    this.defaultCodeInput = page.locator('[name="default_code"] input').first();
    this.categIdInput = page.locator('[name="categ_id"] input').first();
    this.listingPriceInput = page.locator('[name="x_listing_price"] input').first();
    this.shippingPriceInput = page.locator('[name="x_shipping_price_internal"] input').first();
    this.gearmentSkuInput = page.locator('[name="x_gearment_sku"] input').first();
    this.channelTagInput = page.locator('[name="x_channel_applicability_ids"] input').first();
    this.createButton = page.locator('button[name="action_create"], button.btn-primary:has-text("Create")').first();
    this.cancelButton = page.locator('button.o_form_button_cancel, button:has-text("Cancel")').first();
    // Odoo 19 UserError appears as a NEW modal dialog with a "Close" button
    // stacked OVER the wizard's own modal. Target the modal whose title is the
    // exception-class name ("Invalid Operation" / "Validation Error" / "User Error").
    this.notification = page.locator('.modal-dialog', {
      has: page.locator('.modal-title:has-text("Invalid Operation"), .modal-title:has-text("Validation Error"), .modal-title:has-text("User Error")'),
    }).locator('.modal-body');
  }

  /** Open the wizard via the URL action. */
  async open(): Promise<void> {
    await this.page.goto('/odoo/action-multichannel_hub_core.action_product_creation_wizard');
    await this.form.waitFor({ state: 'visible', timeout: 15000 });
  }

  async fillBasics(opts: {
    name: string;
    defaultCode?: string;
    categName?: string;
    listingPrice: number;
    shippingPrice: number;
    gearmentSku?: string;
    channels?: string[];
  }): Promise<void> {
    await this.nameInput.fill(opts.name);
    if (opts.defaultCode !== undefined) {
      await this.defaultCodeInput.fill(opts.defaultCode);
    }
    if (opts.categName) {
      await this.selectCategory(opts.categName);
    }
    await this.listingPriceInput.fill(String(opts.listingPrice));
    await this.shippingPriceInput.fill(String(opts.shippingPrice));
    if (opts.gearmentSku) {
      await this.gearmentSkuInput.fill(opts.gearmentSku);
    }
    for (const ch of opts.channels ?? []) {
      await this.addChannel(ch);
    }
  }

  /** Click an autocomplete (Many2one) suggestion. */
  async selectCategory(name: string): Promise<void> {
    await this.categIdInput.click();
    await this.categIdInput.fill(name);
    const suggestion = this.page.locator('.o-autocomplete--dropdown-item, .ui-autocomplete li')
      .filter({ hasText: name }).first();
    await suggestion.waitFor({ state: 'visible', timeout: 5000 });
    await suggestion.click();
  }

  async addChannel(channelName: string): Promise<void> {
    await this.channelTagInput.click();
    await this.channelTagInput.fill(channelName);
    const suggestion = this.page.locator('.o-autocomplete--dropdown-item, .ui-autocomplete li')
      .filter({ hasText: channelName }).first();
    await suggestion.waitFor({ state: 'visible', timeout: 5000 });
    await suggestion.click();
  }

  async submit(): Promise<void> {
    await this.createButton.click();
  }

  async submitExpectingError(): Promise<string> {
    await this.createButton.click();
    await this.notification.waitFor({ state: 'visible', timeout: 10000 });
    const text = await this.notification.textContent();
    return text?.trim() ?? '';
  }
}
