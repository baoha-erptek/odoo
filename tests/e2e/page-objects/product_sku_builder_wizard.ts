import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object for product.sku.builder.wizard (4-step BA-gated SKU builder).
 *
 * Model source: custom_addons/multichannel_hub_core/wizards/product_sku_builder_wizard.py
 * View source : custom_addons/multichannel_hub_core/wizards/product_sku_builder_wizard_views.xml
 * View action xmlid: multichannel_hub_core.action_product_sku_builder_wizard
 * FR-017 gate: multichannel_hub_core.group_ba_user (method-top in action_create)
 *
 * Step layout:
 *   1. Family — product_name, family_id_auto (readonly), family_id
 *   2. Material — material_id
 *   3. Size — size_id OR rect_w / rect_h (family-gated namespace)
 *   4. Preview — var2_color_id (optional), preview_sku (readonly)
 */
export class ProductSkuBuilderWizardPage {
  readonly page: Page;
  readonly form: Locator;
  readonly statusbar: Locator;

  // Step 1
  readonly productNameInput: Locator;
  readonly familyIdAutoText: Locator;
  readonly familyIdInput: Locator;

  // Step 2
  readonly materialIdInput: Locator;

  // Step 3
  readonly sizeIdInput: Locator;
  readonly rectWInput: Locator;
  readonly rectHInput: Locator;

  // Step 4
  readonly var2ColorIdInput: Locator;
  readonly previewSkuField: Locator;

  // Footer
  readonly nextButton: Locator;
  readonly prevButton: Locator;
  readonly createButton: Locator;
  readonly cancelButton: Locator;
  readonly errorModal: Locator;

  constructor(page: Page) {
    this.page = page;
    this.form = page.locator('.o_form_view').first();
    this.statusbar = page.locator('.o_statusbar_status').first();

    this.productNameInput = page.locator('[name="product_name"] input, [name="product_name"] textarea').first();
    this.familyIdAutoText = page.locator('[name="family_id_auto"]').first();
    this.familyIdInput = page.locator('[name="family_id"] input').first();

    this.materialIdInput = page.locator('[name="material_id"] input').first();

    this.sizeIdInput = page.locator('[name="size_id"] input').first();
    this.rectWInput = page.locator('[name="rect_w"] input').first();
    this.rectHInput = page.locator('[name="rect_h"] input').first();

    this.var2ColorIdInput = page.locator('[name="var2_color_id"] input').first();
    this.previewSkuField = page.locator('[name="preview_sku"]').first();

    this.nextButton = page.locator('button[name="action_next"]').first();
    this.prevButton = page.locator('button[name="action_prev"]').first();
    this.createButton = page.locator('button[name="action_create"]').first();
    this.cancelButton = page.locator('button.o_form_button_cancel, button:has-text("Cancel")').first();

    // Odoo 19 AccessError / UserError surface as a modal stacked above the wizard.
    this.errorModal = page.locator('.modal-dialog', {
      has: page.locator('.modal-title:has-text("Access Error"), .modal-title:has-text("User Error"), .modal-title:has-text("Validation Error"), .modal-title:has-text("Invalid Operation")'),
    }).locator('.modal-body');
  }

  async open(): Promise<void> {
    await this.page.goto('/odoo/action-multichannel_hub_core.action_product_sku_builder_wizard');
    await this.form.waitFor({ state: 'visible', timeout: 15000 });
  }

  // --- Step 1
  async fillStep1Name(name: string): Promise<void> {
    await this.productNameInput.fill(name);
    // onchange fires on blur — click off to trigger _onchange_product_name_default_family
    await this.productNameInput.press('Tab');
  }

  /** Read the auto-suggested family code (badge text). */
  async getAutoSuggestedFamilyCode(): Promise<string> {
    const t = (await this.familyIdAutoText.textContent()) ?? '';
    return t.trim();
  }

  /** Override the auto-suggested family by typing its name/code. */
  async overrideFamily(query: string): Promise<void> {
    await this.familyIdInput.click();
    await this.familyIdInput.fill('');
    await this.familyIdInput.fill(query);
    await this._pickAutocomplete(query);
  }

  // --- Step 2
  async fillStep2Material(query: string): Promise<void> {
    await this.materialIdInput.click();
    await this.materialIdInput.fill(query);
    await this._pickAutocomplete(query);
  }

  // --- Step 3
  async fillStep3Size(opts: { size?: string; rectW?: number; rectH?: number }): Promise<void> {
    if (opts.size) {
      await this.sizeIdInput.click();
      await this.sizeIdInput.fill(opts.size);
      await this._pickAutocomplete(opts.size);
    }
    if (opts.rectW !== undefined) {
      await this.rectWInput.fill(String(opts.rectW));
    }
    if (opts.rectH !== undefined) {
      await this.rectHInput.fill(String(opts.rectH));
      // Blur to commit value
      await this.rectHInput.press('Tab');
    }
  }

  // --- Step 4
  async fillStep4Color(query: string): Promise<void> {
    await this.var2ColorIdInput.click();
    await this.var2ColorIdInput.fill(query);
    await this._pickAutocomplete(query);
    // Blur so the m2o write + preview_sku compute settle before the next read.
    await this.var2ColorIdInput.press('Tab');
    await this.page.waitForTimeout(300);
  }

  async getPreviewSku(): Promise<string> {
    const t = (await this.previewSkuField.textContent()) ?? '';
    // Field is readonly Char — Odoo renders text into a span
    return t.trim();
  }

  // --- Navigation
  async clickNext(): Promise<void> {
    await this.nextButton.click();
    // Wait for status transition (next step's invisible="step != 'N'" group reveals)
    await this.page.waitForTimeout(400);
  }

  async clickPrev(): Promise<void> {
    await this.prevButton.click();
    await this.page.waitForTimeout(400);
  }

  async clickCreate(): Promise<void> {
    await this.createButton.click();
  }

  /** Click Create and capture the error-modal text. */
  async clickCreateExpectingError(): Promise<string> {
    await this.createButton.click();
    await this.errorModal.waitFor({ state: 'visible', timeout: 10000 });
    const text = (await this.errorModal.textContent()) ?? '';
    return text.trim();
  }

  // --- Internals
  private async _pickAutocomplete(label: string): Promise<void> {
    const suggestion = this.page.locator('.o-autocomplete--dropdown-item, .ui-autocomplete li')
      .filter({ hasText: label })
      .first();
    await suggestion.waitFor({ state: 'visible', timeout: 5000 });
    await suggestion.click();
  }

  // --- Convenience: navigate to a specific step from the current step
  async goToStep(target: 1 | 2 | 3 | 4): Promise<void> {
    for (let i = 0; i < 5; i++) {
      const current = await this._currentStep();
      if (current === target) return;
      if (current < target) {
        await this.clickNext();
      } else {
        await this.clickPrev();
      }
    }
  }

  private async _currentStep(): Promise<number> {
    // Statusbar renders <button class="o_arrow_button" data-value="N"> for each option,
    // with the active one marked via .o_arrow_button_current or aria-current
    const active = this.statusbar.locator('.o_arrow_button_current, [aria-current="true"]').first();
    const v = (await active.getAttribute('data-value')) ?? '1';
    return parseInt(v, 10) || 1;
  }
}
