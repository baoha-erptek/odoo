import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object for the STANDARD product.template form (v1.2 flow).
 *
 * v1.2 (HUONG_DAN_TAO_SAN_PHAM_VN.md / FLOW_TAO_SAN_PHAM_VN.md, 2026-05-28)
 * retired the two creation wizards. Products are now created via the standard
 * Odoo product form; the SKU auto-derives from categ_id + attribute_line_ids.
 *
 * Sources verified on staging mhc 19.0.1.0.60 / etsy_integration 19.0.2.24.0:
 *   - Auto-SKU onchange/create: multichannel_hub_core/models/product_template.py:239,299
 *   - Form pages (Channels/SKU Drift/Listing Tags/Options/Defaults/Extra Images):
 *     multichannel_hub_core/views/product_template_views.xml
 *   - Publish header button: etsy_integration/views/product_views.xml
 *     (button[name="action_open_etsy_publish_wizard"])
 *   - Publish wizard buttons: etsy_integration/wizards/etsy_publish_wizard_views.xml
 *     action_run_publish (full) | action_run_publish_draft_only | action_run_inventory_only
 */
export class ProductFormPage {
  readonly page: Page;
  readonly form: Locator;
  readonly nameInput: Locator;
  readonly defaultCodeInput: Locator;
  readonly categIdInput: Locator;
  readonly listPriceInput: Locator;
  readonly gearmentSkuInput: Locator;
  readonly weightInput: Locator;
  readonly saveButton: Locator;
  readonly discardButton: Locator;
  readonly publishButton: Locator;
  readonly errorModal: Locator;

  constructor(page: Page) {
    this.page = page;
    this.form = page.locator('.o_form_view').first();
    this.nameInput = page.locator('[name="name"] input, [name="name"] textarea').first();
    this.defaultCodeInput = page.locator('[name="default_code"] input').first();
    this.categIdInput = page.locator('[name="categ_id"] input').first();
    this.listPriceInput = page.locator('[name="list_price"] input').first();
    this.gearmentSkuInput = page.locator('[name="x_gearment_sku"] input').first();
    this.weightInput = page.locator('[name="weight"] input').first();
    this.saveButton = page.locator('button.o_form_button_save').first();
    this.discardButton = page.locator('button.o_form_button_cancel').first();
    this.publishButton = page.locator('button[name="action_open_etsy_publish_wizard"]').first();
    // ValidationError / UserError surface as a modal dialog over the form.
    this.errorModal = page.locator('.modal-dialog', {
      has: page.locator(
        '.modal-title:has-text("Validation Error"), .modal-title:has-text("User Error"), ' +
        '.modal-title:has-text("Invalid Operation"), .modal-title:has-text("Access Error")',
      ),
    }).locator('.modal-body');
  }

  // --- navigation ---------------------------------------------------------

  /**
   * Auto-dismiss Odoo's non-blocking "Note: The Internal Reference 'X' already
   * exists." dialog. The category-only auto-derive can yield a bare family code
   * (e.g. 'MUG') that collides with other products; the warning is informational
   * but its modal intercepts clicks. Register once per page.
   */
  async installNoteDismisser(): Promise<void> {
    const note = this.page.locator('.modal-dialog', {
      has: this.page.locator('.modal-title:has-text("Note")'),
    });
    await this.page.addLocatorHandler(note, async () => {
      await this.page.locator('.modal-footer button', { hasText: /Close|Đóng/ }).first().click();
    });
  }

  /** Open the products list and click New to get a blank product form. */
  async openNew(): Promise<void> {
    await this.installNoteDismisser();
    await this.page.goto('/odoo/inventory/products');
    await this.page.waitForSelector('.o_list_view, .o_kanban_view', { timeout: 15000 });
    const newBtn = this.page.locator(
      'button.o_list_button_add, button.o-kanban-button-new, .o_control_panel_main button:has-text("New")',
    ).first();
    await newBtn.click();
    await this.form.waitFor({ state: 'visible', timeout: 15000 });
  }

  /** Switch to a notebook page by its visible tab label. */
  async openTab(label: string | RegExp): Promise<void> {
    const tab = this.page.locator('.o_notebook .nav-link', { hasText: label }).first();
    await tab.waitFor({ state: 'visible', timeout: 8000 });
    await tab.click();
    await this.page.waitForTimeout(200); // let the page's lazy content render
  }

  /**
   * Activate the first notebook page (General Information), where name/category/
   * price/Internal Reference live. Odoo 19 lazy-renders inactive pages, so
   * General-Info fields are absent from the DOM after we visit another tab —
   * always re-open before reading/filling them.
   */
  async openGeneralTab(): Promise<void> {
    const tab = this.page.locator('.o_notebook .nav-link').first();
    if (await tab.count() > 0) {
      await tab.click();
      await this.page.waitForTimeout(200);
    }
  }

  // --- basic fields -------------------------------------------------------

  async fillName(name: string): Promise<void> {
    await this.nameInput.fill(name);
  }

  async fillListPrice(price: number): Promise<void> {
    await this.openGeneralTab();
    await this.listPriceInput.fill(String(price));
    await this.listPriceInput.press('Tab');
  }

  async fillGearmentSku(sku: string): Promise<void> {
    await this.openGeneralTab();
    await this.gearmentSkuInput.fill(sku);
    await this.gearmentSkuInput.press('Tab');
  }

  async fillWeight(kg: number): Promise<void> {
    // `weight` lives on the Inventory tab (Logistics group), lazy-rendered in
    // Odoo 19 — fill before activating that tab and the locator never becomes
    // actionable (15s timeout). Open the tab and wait for visibility first.
    await this.openTab(/Inventory|Tồn kho|Logistics|Hậu cần/);
    await this.weightInput.waitFor({ state: 'visible', timeout: 8000 });
    await this.weightInput.fill(String(kg));
    await this.weightInput.press('Tab');
  }

  /** Pick a product category (Many2one autocomplete). Triggers auto-SKU onchange. */
  async selectCategory(name: string): Promise<void> {
    await this._selectMany2one(this.categIdInput, name);
    await this.page.waitForTimeout(400); // let _onchange_auto_fill_default_code settle
  }

  /** Read the (possibly auto-filled) Internal Reference / SKU. */
  async readSku(): Promise<string> {
    await this.openGeneralTab();
    await this.defaultCodeInput.waitFor({ state: 'visible', timeout: 8000 });
    return (await this.defaultCodeInput.inputValue()).trim();
  }

  /** Manually overwrite the SKU (e.g. legacy code). */
  async setSku(code: string): Promise<void> {
    await this.openGeneralTab();
    await this.defaultCodeInput.fill(code);
    await this.defaultCodeInput.press('Tab');
  }

  // --- variants (Attributes & Variants tab) ------------------------------

  /**
   * Add one attribute line with a single value. Type the FULL display name
   * from sku_attribute_seed.xml ("Ceramic + Chrome", "11 oz", "Medium") — NOT
   * the x_code abbreviation (autocomplete has no domain filter; abbreviations
   * silently pick the wrong value — see memory feedback_attribute_value_display_name_drift).
   */
  async addVariantAttribute(attributeName: string, valueName: string): Promise<void> {
    await this.openTab(/Attributes|Variants|Thuộc tính|Biến thể/);
    const linesField = this.page.locator('[name="attribute_line_ids"]').first();
    await linesField.locator('.o_field_x2many_list_row_add a').first().click();
    // The inline editable row (product.template.attribute.line) opens with
    // attribute_id (m2o) + value_ids (m2m tags, domain-filtered by attribute).
    // Scope selectors to the active row so we never touch existing rows.
    const row = this.page.locator('tr.o_selected_row');
    await row.waitFor({ state: 'visible', timeout: 8000 });
    const attrInput = row.locator('[name="attribute_id"] input');
    await attrInput.click();
    await attrInput.fill(attributeName);
    await this.page.locator('.o-autocomplete--dropdown-item', { hasText: attributeName }).first().click();
    await this.page.waitForTimeout(300); // value_ids domain re-filters on attribute pick
    const valInput = row.locator('[name="value_ids"] input');
    await valInput.click();
    await valInput.fill(valueName);
    await this.page.locator('.o-autocomplete--dropdown-item', { hasText: valueName }).first().click();
    await this.page.waitForTimeout(400); // let onchange('attribute_line_ids') re-derive SKU
  }

  // --- metadata pages -----------------------------------------------------

  async addChannel(channelName: string): Promise<void> {
    await this.openTab(/Channels|Kênh/);
    const input = this.page.locator('[name="x_channel_applicability_ids"] input').first();
    await this._selectMany2one(input, channelName);
  }

  async addTags(tags: string[]): Promise<void> {
    await this.openTab(/Listing Tags/);
    const input = this.page.locator('[name="product_tag_ids"] input').first();
    for (const t of tags) {
      await input.click();
      await input.fill(t);
      // product.tag with no_create_edit: pick an existing suggestion if present,
      // else Enter to create-on-the-fly is disabled — caller must seed tags.
      const suggestion = this.page.locator('.o-autocomplete--dropdown-item', { hasText: t }).first();
      if (await suggestion.count() > 0) {
        await suggestion.click();
      } else {
        await input.press('Enter');
      }
    }
  }

  async setPersonalization(opts: {
    enable: boolean;
    required?: boolean;
    charCount?: number;
    instructions?: string;
  }): Promise<void> {
    await this.openTab(/Listing Options/);
    const enableBox = this.page.locator('[name="x_is_personalizable"] input').first();
    if (opts.enable !== (await enableBox.isChecked())) await enableBox.click();
    if (!opts.enable) return;
    if (opts.required !== undefined) {
      const reqBox = this.page.locator('[name="x_personalization_required"] input').first();
      if (opts.required !== (await reqBox.isChecked())) await reqBox.click();
    }
    if (opts.charCount !== undefined) {
      const cc = this.page.locator('[name="x_personalization_char_count"] input').first();
      await cc.fill(String(opts.charCount));
      await cc.press('Tab');
    }
    if (opts.instructions !== undefined) {
      await this.page.locator('[name="x_personalization_instructions"] textarea, [name="x_personalization_instructions"] input')
        .first().fill(opts.instructions);
    }
  }

  async setListingDefaults(opts: { taxonomyId?: string; whoMade?: string; whenMade?: string }): Promise<void> {
    await this.openTab(/Listing Defaults/);
    if (opts.taxonomyId !== undefined) {
      await this.page.locator('[name="x_taxonomy_id"] input').first().fill(opts.taxonomyId);
    }
    if (opts.whoMade !== undefined) {
      await this._selectSelection('x_who_made', opts.whoMade);
    }
    if (opts.whenMade !== undefined) {
      await this._selectSelection('x_when_made', opts.whenMade);
    }
  }

  // --- save / publish -----------------------------------------------------

  async save(): Promise<void> {
    await this.saveButton.click();
    // Wait for the record to persist (breadcrumb leaves "New", dirty indicator clears).
    await expect(this.page.locator('.o_form_status_indicator_buttons .o_form_button_save'))
      .toHaveCount(0, { timeout: 10000 }).catch(() => { /* indicator variant differs across builds */ });
    await this.page.waitForTimeout(500);
  }

  /** Click save and return the validation/user-error modal text. */
  async saveExpectingError(): Promise<string> {
    await this.saveButton.click();
    await this.errorModal.waitFor({ state: 'visible', timeout: 10000 });
    return (await this.errorModal.textContent())?.trim() ?? '';
  }

  /**
   * Open the Publish wizard from the form header and run draft-only publish.
   * Requires etsy_integration >= 19.0.2.24.0 (adds the "Publish Draft Only" button).
   * Fills shop_id if the wizard opens it empty.
   */
  async publishDraftOnly(shopName = 'JaHandmadeArt'): Promise<void> {
    await this.publishButton.click();
    const modal = this.page.locator('.modal-dialog', {
      has: this.page.locator('.modal-title:has-text("Publish to Etsy")'),
    }).first();
    await modal.waitFor({ state: 'visible', timeout: 10000 });
    const shopInput = modal.locator('[name="shop_id"] input').first();
    if ((await shopInput.inputValue()).trim() === '') {
      await this._selectMany2one(shopInput, shopName);
    }
    await modal.locator('button[name="action_run_publish_draft_only"]').click();
    // Publisher hits the live Etsy API — allow generous time, then wizard closes.
    await modal.waitFor({ state: 'hidden', timeout: 60000 });
  }

  // --- internals ----------------------------------------------------------

  private async _selectMany2one(input: Locator, label: string): Promise<void> {
    await input.click();
    await input.fill(label);
    const suggestion = this.page.locator('.o-autocomplete--dropdown-item, .ui-autocomplete li')
      .filter({ hasText: label }).first();
    await suggestion.waitFor({ state: 'visible', timeout: 6000 });
    await suggestion.click();
  }

  private async _selectSelection(fieldName: string, value: string): Promise<void> {
    // Odoo 19 renders Selection as a <select> inside the field wrapper.
    const select = this.page.locator(`[name="${fieldName}"] select`).first();
    if (await select.count() > 0) {
      await select.selectOption({ label: value }).catch(async () => {
        await select.selectOption(value);
      });
      return;
    }
    // Fallback: autocomplete-style selection field.
    const input = this.page.locator(`[name="${fieldName}"] input`).first();
    await this._selectMany2one(input, value);
  }
}
