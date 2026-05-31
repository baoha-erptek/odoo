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
    await this.openCard(fileName);
    await this.page.locator('button[name="action_reject"]').first().click();
    const modal = this.page.locator('.modal-dialog').first();
    await modal.waitFor({ state: 'visible', timeout: 10000 });
    return modal.locator('[name="rejection_reason"] textarea, [name="rejection_reason"] input').first();
  }

  // --- upload wizard ------------------------------------------------------

  /**
   * Fill the upload wizard with a Drive URL (storage_mode='url').
   * Wizard must already be open (call SaleOrderFormPage.openDesignUploadWizard first).
   */
  async fillUploadWizardWithUrl(name: string, url: string): Promise<void> {
    const modal = this.page.locator('.modal-dialog').first();
    await modal.waitFor({ state: 'visible', timeout: 8000 });
    await modal.locator('[name="name"] input').first().fill(name);
    const storageSelect = modal.locator('[name="storage_mode"] select').first();
    if (await storageSelect.count() > 0) {
      await storageSelect.selectOption('url').catch(() => storageSelect.selectOption({ label: 'URL' }));
    }
    await modal.locator('[name="file_url"] input').first().fill(url);
  }

  /**
   * Fill the upload wizard with a small filestore attachment (storage_mode='small').
   * Pass a local file path to chooseFiles().
   */
  async fillUploadWizardWithFile(name: string, localPath: string): Promise<void> {
    const modal = this.page.locator('.modal-dialog').first();
    await modal.waitFor({ state: 'visible', timeout: 8000 });
    await modal.locator('[name="name"] input').first().fill(name);
    const storageSelect = modal.locator('[name="storage_mode"] select').first();
    if (await storageSelect.count() > 0) {
      await storageSelect.selectOption('small').catch(() => storageSelect.selectOption({ label: /Small|Filestore/ }));
    }
    const fileInput = modal.locator('[name="design_file"] input[type="file"]').first();
    await fileInput.setInputFiles(localPath);
  }

  /** Confirm the upload wizard (button[name="action_upload"] or generic submit). */
  async submitUploadWizard(): Promise<string> {
    const modal = this.page.locator('.modal-dialog').first();
    const submit = modal.locator('.modal-footer button.btn-primary').first();
    await submit.click();
    // 10MB cap rejections return a UserError modal — caller may catch this branch.
    const result = this.page.locator('.o_notification_body, .modal-body').first();
    await result.waitFor({ state: 'visible', timeout: 15000 }).catch(() => undefined);
    return ((await result.textContent()) ?? '').trim();
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
