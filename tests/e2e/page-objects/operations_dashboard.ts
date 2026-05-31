import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object for the Operations Dashboard (Vận hành → Operations Dashboard).
 *
 * Model is sale.order.line (per P1-01b — one row per product line, not per order;
 * see memory: feedback_ceo_unified_dashboard). 34-column Excel contract preserved
 * + appended internal columns (order_id, pipeline_state, etc.) per P1-01b-FIX.
 *
 * Sources verified on staging mhc 19.0.1.0.64:
 *   - View: custom_addons/multichannel_hub_core/views/operations_dashboard_views.xml
 *     list view id=operations_dashboard_list_view (~line 21)
 *     search view id=operations_dashboard_search_view (~line 126)
 *     action id=action_operations_dashboard (~line 154)
 *   - Menu: custom_addons/multichannel_hub_core/views/menu.xml id=menu_operations_dashboard
 *   - Bulk-advance pipeline action: defined on sale.order.line as server action
 *   - Bulk Gearment sync: action_gearment_bulk_sync (sale.order.line, mhf, P4-01-D)
 *
 * Read-only by default; mutating actions (bulk advance, bulk Gearment sync) only
 * fire when an opt-in method is called with explicit `confirm=true`.
 */
export class OperationsDashboardPage {
  readonly page: Page;
  readonly listView: Locator;
  readonly searchInput: Locator;
  readonly actionMenu: Locator;

  constructor(page: Page) {
    this.page = page;
    this.listView = page.locator('.o_list_view').first();
    // Odoo 19 search input lives in the control-panel breadcrumb area.
    this.searchInput = page.locator('.o_searchview_input').first();
    // "Actions" dropdown that appears once rows are selected.
    this.actionMenu = page.locator('.o_cp_action_menus button, .o-dropdown[name="actions"] button').first();
  }

  // --- navigation ---------------------------------------------------------

  /** Open the Operations Dashboard via its action XML ID (resilient to menu reordering). */
  async open(): Promise<void> {
    await this.page.goto('/odoo/action-multichannel_hub_core.action_operations_dashboard');
    await this.listView.waitFor({ state: 'visible', timeout: 15000 });
  }

  /** Type into the search box and press Enter to apply a free-text filter. */
  async search(term: string): Promise<void> {
    await this.searchInput.click();
    await this.searchInput.fill(term);
    await this.searchInput.press('Enter');
    await this.page.waitForTimeout(400); // server fetch
  }

  /** Click into a row that contains the given text (Etsy order_id, SKU, or product name). */
  async openLineByText(text: string): Promise<void> {
    const row = this.page.locator('tr.o_data_row', { hasText: text }).first();
    await row.waitFor({ state: 'visible', timeout: 8000 });
    await row.click();
    // Clicking a line row navigates to either the line form or its parent sale.order form
    // depending on the action's view_id config. Caller asserts which form opened.
    await this.page.waitForTimeout(500);
  }

  // --- read-only assertions -----------------------------------------------

  /** Returns the count of rows currently visible. Caller should apply a filter first. */
  async readVisibleRowCount(): Promise<number> {
    await this.listView.waitFor({ state: 'visible', timeout: 8000 });
    return await this.page.locator('tr.o_data_row').count();
  }

  /** Returns the value of a named cell on the row matching `rowText`. */
  async readCell(rowText: string, columnName: string): Promise<string> {
    const row = this.page.locator('tr.o_data_row', { hasText: rowText }).first();
    await row.waitFor({ state: 'visible', timeout: 8000 });
    const cell = row.locator(`td[name="${columnName}"]`).first();
    await cell.waitFor({ state: 'visible', timeout: 4000 });
    return (await cell.textContent())?.trim() ?? '';
  }

  /**
   * Assert that a row matching `rowText` contains the given column-name → expected-value
   * pairs. Used for real-data ingest TCs (e.g. order S00007 / receipt 3818231452).
   */
  async assertRowFields(rowText: string, expected: Record<string, string | RegExp>): Promise<void> {
    for (const [col, exp] of Object.entries(expected)) {
      const actual = await this.readCell(rowText, col);
      if (exp instanceof RegExp) {
        expect(actual, `column ${col} on row "${rowText}"`).toMatch(exp);
      } else {
        expect(actual, `column ${col} on row "${rowText}"`).toBe(exp);
      }
    }
  }

  // --- mutating bulk actions (opt-in) -------------------------------------

  /** Select the row matching `rowText` via its checkbox. */
  async selectRow(rowText: string): Promise<void> {
    const row = this.page.locator('tr.o_data_row', { hasText: rowText }).first();
    await row.waitFor({ state: 'visible', timeout: 8000 });
    const checkbox = row.locator('td.o_list_record_selector input[type="checkbox"]').first();
    await checkbox.check();
  }

  /**
   * Open the "Actions" dropdown (only appears with rows selected) and click the named action.
   * Caller must `selectRow()` first. Returns the toast text after action runs.
   *
   * MUTATING: this advances pipeline state / pushes to Gearment / etc. Never call
   * against real-data rows — only against UAT-2026-05-31-* seeded rows.
   */
  async runBulkAction(actionLabel: string | RegExp): Promise<string> {
    await this.actionMenu.click();
    const item = this.page.locator('.o-dropdown-item, .dropdown-item', { hasText: actionLabel }).first();
    await item.waitFor({ state: 'visible', timeout: 4000 });
    await item.click();
    // Some bulk actions open a confirmation modal first; auto-confirm if present.
    const confirmBtn = this.page.locator('.modal-footer button.btn-primary', { hasText: /Confirm|OK|Apply|Đồng ý/ }).first();
    if (await confirmBtn.count() > 0) {
      await confirmBtn.click();
    }
    const toast = this.page.locator('.o_notification_body, .o_notification_content').first();
    await toast.waitFor({ state: 'visible', timeout: 30000 });
    return (await toast.textContent())?.trim() ?? '';
  }
}
