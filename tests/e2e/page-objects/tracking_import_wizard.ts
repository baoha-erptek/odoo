import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object for tracking.import.wizard (Flow-3 TC-MTO-005 / TC-MTO-006).
 *
 * Sources verified on staging mhf 19.0.1.0.*:
 *   - Model: multichannel_hub_fulfillment/wizards/tracking_import_wizard.py
 *     state machine: draft → previewed → done
 *   - View: multichannel_hub_fulfillment/views/tracking_import_views.xml:142
 *   - Action: action_tracking_import_wizard (menu "Tracking Import")
 *   - Buttons gated by groups:
 *       action_preview          → group_ba_shipping
 *       action_approve_schema   → group_ba_manager (only for new schema fingerprint)
 *       action_import           → group_ba_shipping (only after preview, not new schema)
 *       action_cancel           → always (until state='done')
 *
 * Mutation policy: action_import writes tracking.import.log + advances sale.order
 * tracking_number / state. Test only against UAT-2026-05-31-MTO-* orders.
 */
export class TrackingImportWizardPage {
  readonly page: Page;
  readonly modal: Locator;
  readonly excelFileInput: Locator;
  readonly schemaHashField: Locator;
  readonly isNewSchemaField: Locator;
  readonly previewLogIdField: Locator;
  readonly headerDiffPage: Locator;
  readonly previewLinesList: Locator;
  readonly previewButton: Locator;
  readonly approveSchemaButton: Locator;
  readonly importButton: Locator;
  readonly cancelButton: Locator;
  readonly errorModal: Locator;

  constructor(page: Page) {
    this.page = page;
    this.modal = page.locator('.modal-dialog', {
      has: page.locator('[name="excel_file"], [name="schema_hash"]'),
    }).first();
    this.excelFileInput = this.modal.locator('[name="excel_file"] input[type="file"]').first();
    this.schemaHashField = this.modal.locator('[name="schema_hash"]').first();
    this.isNewSchemaField = this.modal.locator('[name="is_new_schema"] input').first();
    this.previewLogIdField = this.modal.locator('[name="preview_log_id"]').first();
    this.headerDiffPage = this.modal.locator('[name="header_diff_html"]').first();
    this.previewLinesList = this.modal.locator('[name="preview_line_ids"]').first();
    this.previewButton = this.modal.locator('button[name="action_preview"]').first();
    this.approveSchemaButton = this.modal.locator('button[name="action_approve_schema"]').first();
    this.importButton = this.modal.locator('button[name="action_import"]').first();
    this.cancelButton = this.modal.locator('button[name="action_cancel"]').first();
    this.errorModal = page.locator('.modal-dialog', {
      has: page.locator(
        '.modal-title:has-text("Validation Error"), .modal-title:has-text("User Error"), ' +
        '.modal-title:has-text("Warning")',
      ),
    }).locator('.modal-body');
  }

  // --- navigation ---------------------------------------------------------

  /** Open the wizard via its act_window action XML ID. */
  async open(): Promise<void> {
    await this.page.goto('/odoo/action-multichannel_hub_fulfillment.action_tracking_import_wizard');
    await this.modal.waitFor({ state: 'visible', timeout: 15000 });
  }

  // --- happy path ---------------------------------------------------------

  /** Stage 1 (draft): attach the Excel file. */
  async attachExcel(localPath: string): Promise<void> {
    await this.excelFileInput.setInputFiles(localPath);
    // The form auto-stores filename; no further action needed before preview.
    await this.page.waitForTimeout(300);
  }

  /** Stage 2: click Preview → wizard transitions to 'previewed' (or errors). */
  async clickPreview(): Promise<void> {
    await this.previewButton.click();
    // Either the wizard re-renders with preview lines, or the error modal opens.
    await Promise.race([
      this.previewLinesList.waitFor({ state: 'visible', timeout: 30000 }),
      this.errorModal.waitFor({ state: 'visible', timeout: 30000 }),
    ]);
  }

  /**
   * Stage 2.5: if `is_new_schema` is true, a BA Manager must approve the schema
   * before import unlocks. Returns true if approval was needed and performed.
   */
  async approveNewSchemaIfNeeded(): Promise<boolean> {
    if (await this.approveSchemaButton.count() === 0) return false;
    if (!(await this.approveSchemaButton.isVisible().catch(() => false))) return false;
    await this.approveSchemaButton.click();
    await this.page.waitForTimeout(500);
    return true;
  }

  /** Stage 3: click Import → wizard transitions to 'done' and writes tracking. */
  async clickImport(): Promise<void> {
    await this.importButton.click();
    // Done state shows "Close" button (special=cancel) instead of action buttons.
    const closeBtn = this.modal.locator('.modal-footer button', { hasText: /^Close$/ }).first();
    await closeBtn.waitFor({ state: 'visible', timeout: 30000 });
  }

  /** Cancel/close the wizard without import. */
  async cancel(): Promise<void> {
    const btn = this.cancelButton.or(this.modal.locator('.modal-footer button', { hasText: /Cancel|Close/ }).first());
    await btn.click();
    await this.modal.waitFor({ state: 'hidden', timeout: 8000 }).catch(() => undefined);
  }

  // --- assertions ---------------------------------------------------------

  /** Returns the displayed schema_hash (empty until preview completes). */
  async readSchemaHash(): Promise<string> {
    const input = this.schemaHashField.locator('input').first();
    if (await input.count() > 0) return (await input.inputValue()).trim();
    return ((await this.schemaHashField.textContent()) ?? '').trim();
  }

  /** Returns true if the wizard flagged the upload as a new schema fingerprint. */
  async isNewSchema(): Promise<boolean> {
    if (await this.isNewSchemaField.count() === 0) return false;
    return await this.isNewSchemaField.isChecked().catch(() => false);
  }

  /** Returns the number of preview lines rendered after Preview. */
  async readPreviewLineCount(): Promise<number> {
    return await this.previewLinesList.locator('tr.o_data_row').count();
  }

  /** Returns the text of the validation/user-error modal (after Preview fails). */
  async readErrorModalText(): Promise<string> {
    await this.errorModal.waitFor({ state: 'visible', timeout: 4000 });
    return ((await this.errorModal.textContent()) ?? '').trim();
  }
}
