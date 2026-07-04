import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object for the design.file kanban + upload wizard (MTO Flow-3 TC-MTO-002..004).
 *
 * Sources verified on staging mhc 19.0.1.0.64:
 *   - Model: multichannel_hub_core/models/design_file.py (states: pending/approved/rejected)
 *   - Kanban view: multichannel_hub_core/views/design_file_views.xml (id=design_file_kanban)
 *   - Form: button[name="action_approve"], button[name="action_reject"]
 *   - Upload wizard: multichannel_hub_core/views/design_file_upload_wizard.xml
 *   - Storage modes: 'url' (Drive link) | 'small' (filestore ≤ 10MB cap per
 *     ir.config_parameter multichannel_hub.large_file_threshold_bytes)
 *   - Search filters: filter_pending, filter_approved, filter_rejected
 *
 * Mutation policy: kanban surface is mutating (drag = state change). Only operate on
 * design.file rows linked to UAT-2026-05-31-* orders; never touch real-order rows.
 */
export class DesignFilesKanbanPage {
  readonly page: Page;
  readonly kanban: Locator;
  readonly searchInput: Locator;
  readonly pendingColumn: Locator;
  readonly approvedColumn: Locator;
  readonly rejectedColumn: Locator;

  constructor(page: Page) {
    this.page = page;
    this.kanban = page.locator('.o_kanban_view').first();
    this.searchInput = page.locator('.o_searchview_input').first();
    // group_by=state renders one column per state code; the badge header text is the state label.
    this.pendingColumn = page.locator('.o_kanban_group', { hasText: /pending|Chờ duyệt/i }).first();
    this.approvedColumn = page.locator('.o_kanban_group', { hasText: /approved|Duyệt/i }).first();
    this.rejectedColumn = page.locator('.o_kanban_group', { hasText: /rejected|Cần chỉnh/i }).first();
  }

  // --- navigation ---------------------------------------------------------

  /** Open the Design Files kanban (action_design_file). */
  async open(): Promise<void> {
    await this.page.goto('/odoo/action-multichannel_hub_core.action_design_file');
    await this.kanban.waitFor({ state: 'visible', timeout: 15000 });
    // Default action lands on kanban view per design_file_views.xml view_mode list.
    const kanbanSwitcher = this.page.locator('.o_switch_view.o_kanban, button[data-tooltip="Kanban"]').first();
    if (await kanbanSwitcher.count() > 0 && !(await this.kanban.isVisible())) {
      await kanbanSwitcher.click();
      await this.kanban.waitFor({ state: 'visible', timeout: 8000 });
    }
    // Ensure group-by-state is active (default may be flat list).
    await this._ensureGroupedByState();
  }

  /** Filter kanban to a single order's design files via free-text search. */
  async filterByOrder(orderName: string): Promise<void> {
    await this.searchInput.click();
    await this.searchInput.fill(orderName);
    await this.searchInput.press('Enter');
    await this.page.waitForTimeout(400);
  }

  // --- read-only assertions -----------------------------------------------

  /** Returns the number of cards in the named state column. */
  async readCardCount(state: 'pending' | 'approved' | 'rejected'): Promise<number> {
    const col = state === 'pending'
      ? this.pendingColumn
      : state === 'approved'
        ? this.approvedColumn
        : this.rejectedColumn;
    if (!(await col.count())) return 0;
    return await col.locator('.o_kanban_record').count();
  }

  /** Locator for a specific card by its file name (used for drag + assertions). */
  cardByName(fileName: string): Locator {
    return this.page.locator('.o_kanban_record', { hasText: fileName }).first();
  }

  /** Returns the state of the named card by inspecting its parent column header. */
  async readCardState(fileName: string): Promise<string> {
    const card = this.cardByName(fileName);
    await card.waitFor({ state: 'visible', timeout: 8000 });
    const col = card.locator('xpath=ancestor::*[contains(@class, "o_kanban_group")][1]');
    const header = col.locator('.o_column_title, .o_kanban_header_title').first();
    return ((await header.textContent()) ?? '').trim();
  }

  // --- mutating actions ---------------------------------------------------

  /** Open the form for a single design.file card. */
  async openCard(fileName: string): Promise<void> {
    await this.cardByName(fileName).click();
    await this.page.waitForSelector('.o_form_view', { timeout: 10000 });
  }

  /**
   * Approve a design.file via its form button (button[name="action_approve"]).
   * Pre-condition: card is in `pending` state and current user has BA permission.
   */
  async approveCard(fileName: string): Promise<void> {
    await this.openCard(fileName);
    await this.page.locator('button[name="action_approve"]').first().click();
    await this.page.waitForTimeout(500);
  }

  /**
   * Reject a design.file via its form button (button[name="action_reject"]).
   * Opens the rejection-reason wizard; caller must fill `reason` then submit.
   * Returns the rejection-reason locator for the caller to fill.
   */
  async clickRejectAndAwaitReasonWizard(fileName: string): Promise<Locator> {
    // Current flow (2026-07-04): there is NO reason wizard — action_reject
    // reads `rejection_reason` from the record and raises a ValidationError
    // when empty. The UI walk is: fill the form's rejection_reason field,
    // then click Reject. Return the FORM field locator; the caller fills it
    // and then presses the Reject button we leave un-clicked here.
    await this.openCard(fileName);
    // rejection_reason lives in the lazy-rendered "Rejection" notebook tab.
    const tab = this.page.locator('.o_notebook .nav-link', { hasText: /Rejection/ }).first();
    await tab.waitFor({ state: 'visible', timeout: 10000 });
    await tab.click();
    await this.page.waitForTimeout(300);
    const field = this.page.locator(
      '[name="rejection_reason"] textarea, [name="rejection_reason"] input').first();
    await field.waitFor({ state: 'visible', timeout: 10000 });
    return field;
  }

  /** Click the form's Reject button (call after filling rejection_reason).
   * The button carries a static confirm="..." dialog — acknowledge it. */
  async clickRejectOnForm(): Promise<void> {
    await this.page.locator('button[name="action_reject"]').first().click();
    const confirmOk = this.page.locator('.modal-dialog .btn-primary', { hasText: /^Ok$/ }).first();
    if (await confirmOk.count() > 0) {
      await confirmOk.click();
    }
    await this.page.waitForTimeout(800);
  }

  // --- upload wizard ------------------------------------------------------

  /**
   * Fill the upload wizard with a Drive URL (storage_mode='url').
   * Wizard must already be open (call SaleOrderFormPage.openDesignUploadWizard first).
   */
  async fillUploadWizardWithUrl(name: string, url: string): Promise<void> {
    const modal = this.page.locator('.modal-dialog').first();
    await modal.waitFor({ state: 'visible', timeout: 8000 });
    // Wizard fields (2026-07-04): file_name (NOT name); file_url only
    // renders after storage_mode='url' is selected.
    // Odoo 19 renders this selection as an o_select_menu (SelectMenu OWL
    // component), not a native <select> — click the toggler, pick the item.
    const storageSelect = modal.locator('[name="storage_mode"] select').first();
    if (await storageSelect.count() > 0) {
      await storageSelect.selectOption('url').catch(() => storageSelect.selectOption({ label: 'URL' }));
    } else {
      await modal.locator('[name="storage_mode"] .o_select_menu_toggler').first().click();
      await this.page.locator('.o_select_menu_item, .o-dropdown--menu .dropdown-item')
        .filter({ hasText: /^URL$/ }).first().click();
    }
    await modal.locator('[name="file_name"] input').first().fill(name);
    await modal.locator('[name="file_url"] input, [name="file_url"] textarea').first().fill(url);
  }

  /**
   * Fill the upload wizard with a small filestore attachment (storage_mode='small').
   * Pass a local file path to chooseFiles().
   */
  async fillUploadWizardWithFile(name: string, localPath: string): Promise<void> {
    const modal = this.page.locator('.modal-dialog').first();
    await modal.waitFor({ state: 'visible', timeout: 8000 });
    // Wizard fields (2026-07-04): file_name (NOT name); storage_mode is an
    // o_select_menu, defaulting to Small — only switch if needed; the binary
    // field is file_blob.
    await modal.locator('[name="file_name"] input').first().fill(name);
    const fileInput = modal.locator(
      '[name="file_blob"] input[type="file"], [name="design_file"] input[type="file"]').first();
    await fileInput.setInputFiles(localPath);
  }

  /** Confirm the upload wizard (button[name="action_upload"] or generic submit). */
  async submitUploadWizard(): Promise<string> {
    const modal = this.page.locator('.modal-dialog').first();
    const wizardBody = (await modal.locator('.modal-body').first().textContent()) ?? '';
    const submit = modal.locator('.modal-footer button.btn-primary').first();
    await submit.click();
    // Poll for a REAL outcome — the wizard's own .modal-body matches
    // immediately and races big uploads (12MB cap TC, 2026-07-04). Outcomes:
    // toast notification, a NEW/changed dialog (UserError), or wizard close.
    const deadline = Date.now() + 60_000;
    while (Date.now() < deadline) {
      const toast = this.page.locator('.o_notification_body, .o_notification_content').first();
      if (await toast.isVisible().catch(() => false)) {
        return ((await toast.textContent()) ?? '').trim();
      }
      const dialogs = this.page.locator('.modal-dialog:visible .modal-body');
      const n = await dialogs.count();
      for (let i = 0; i < n; i++) {
        const text = ((await dialogs.nth(i).textContent()) ?? '').trim();
        if (text && text !== wizardBody.trim()) return text;
      }
      if (n === 0) return 'uploaded'; // wizard closed, no error
      await this.page.waitForTimeout(1000);
    }
    return '';
  }

  // --- internals ----------------------------------------------------------

  private async _ensureGroupedByState(): Promise<void> {
    if (await this.pendingColumn.count() > 0 || await this.approvedColumn.count() > 0) return;
    // Activate the "Status" group-by filter from the search panel.
    const groupBtn = this.page.locator('button:has-text("Group By"), button:has-text("Nhóm theo")').first();
    if (await groupBtn.count() > 0) {
      await groupBtn.click();
      const groupItem = this.page.locator('.o_menu_item, .dropdown-item', { hasText: /Status|Trạng thái/ }).first();
      if (await groupItem.count() > 0) {
        await groupItem.click();
        await this.page.waitForTimeout(400);
      }
    }
  }
}
