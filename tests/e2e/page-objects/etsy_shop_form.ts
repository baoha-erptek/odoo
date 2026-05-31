import { Page, Locator, expect } from '@playwright/test';

/**
 * Page Object for the etsy.shop form (Etsy → Shops).
 *
 * Sources verified on staging etsy_integration 19.0.2.30.0 / mhc 19.0.1.0.64:
 *   - View: custom_addons/etsy_integration/views/etsy_shop_views.xml (form ~25-160)
 *   - Authorize / Test Connection buttons: gated by `base.group_system` (sysadmin only)
 *   - Publisher Defaults page: gated by `multichannel_hub_core.group_ba_user` (4 ID fields
 *     individually gated by `base.group_system`)
 *   - etsy_api_shop_id is a Char (prevents XML-RPC int32 overflow; memory: reference_etsy_shop_id_mapping)
 *   - active_source toggle: `api` | `email` (memory: project_api_first_pivot)
 *
 * Mutation policy (plan: check-for-master-plan-gentle-kahn.md):
 *   - Authorize / Test Connection are READ-ONLY surfaces in pre-UAT (we assert state, never trigger).
 *   - Triggering Authorize on a live shop would rotate tokens — strictly opt-in via explicit method.
 */
export class EtsyShopFormPage {
  readonly page: Page;
  readonly form: Locator;
  readonly nameField: Locator;
  readonly etsyApiShopIdInput: Locator;
  readonly activeSourceSelect: Locator;
  readonly authorizeButton: Locator;
  readonly testConnectionButton: Locator;
  readonly defaultTaxonomyIdInput: Locator;
  readonly defaultShippingProfileIdInput: Locator;
  readonly defaultReturnPolicyIdInput: Locator;
  readonly defaultReadinessStateIdInput: Locator;
  readonly defaultWhoMadeSelect: Locator;
  readonly defaultWhenMadeSelect: Locator;

  constructor(page: Page) {
    this.page = page;
    this.form = page.locator('.o_form_view').first();
    this.nameField = page.locator('[name="name"] input').first();
    this.etsyApiShopIdInput = page.locator('[name="etsy_api_shop_id"] input').first();
    this.activeSourceSelect = page.locator('[name="active_source"] select').first();
    // Header stat-buttons: name attr is the action method; visible label is "Authorize Etsy" / "Test Connection".
    this.authorizeButton = page.locator('button[name="action_authorize_etsy"]').first();
    this.testConnectionButton = page.locator('button[name="action_test_connection"]').first();
    // Publisher Defaults inputs (Char fields — int4 overflow guard, memory: reference_etsy_createlisting_2025_readiness)
    this.defaultTaxonomyIdInput = page.locator('[name="default_taxonomy_id"] input').first();
    this.defaultShippingProfileIdInput = page.locator('[name="default_shipping_profile_id"] input').first();
    this.defaultReturnPolicyIdInput = page.locator('[name="default_return_policy_id"] input').first();
    this.defaultReadinessStateIdInput = page.locator('[name="default_readiness_state_id"] input').first();
    this.defaultWhoMadeSelect = page.locator('[name="default_who_made"] select').first();
    this.defaultWhenMadeSelect = page.locator('[name="default_when_made"] select').first();
  }

  // --- navigation ---------------------------------------------------------

  /** Open the Etsy Shops list and click into a named shop. */
  async openByName(shopName: string): Promise<void> {
    // Menu: Etsy → Shops (action_etsy_shop). Direct action URL keeps tests resilient to menu reordering.
    await this.page.goto('/odoo/action-etsy_integration.action_etsy_shop');
    await this.page.waitForSelector('.o_list_view, .o_kanban_view', { timeout: 15000 });
    const row = this.page.locator('tr.o_data_row, .o_kanban_record', { hasText: shopName }).first();
    await row.waitFor({ state: 'visible', timeout: 8000 });
    await row.click();
    await this.form.waitFor({ state: 'visible', timeout: 15000 });
  }

  /** Switch to a named notebook page on the form. */
  async openTab(label: string | RegExp): Promise<void> {
    const tab = this.page.locator('.o_notebook .nav-link', { hasText: label }).first();
    await tab.waitFor({ state: 'visible', timeout: 8000 });
    await tab.click();
    await this.page.waitForTimeout(200);
  }

  // --- read-only assertions (pre-UAT default) -----------------------------

  /** Returns the shop's stored etsy_api_shop_id. JaHandmadeArt expected: '60752333'. */
  async readEtsyApiShopId(): Promise<string> {
    await this.etsyApiShopIdInput.waitFor({ state: 'visible', timeout: 8000 });
    return (await this.etsyApiShopIdInput.inputValue()).trim();
  }

  /** Returns the shop's active_source ('api' | 'email'). */
  async readActiveSource(): Promise<string> {
    await this.activeSourceSelect.waitFor({ state: 'visible', timeout: 8000 });
    return (await this.activeSourceSelect.inputValue()).trim();
  }

  /** Returns publisher-defaults dict. Empty strings indicate falsy values. */
  async readPublisherDefaults(): Promise<{
    taxonomy: string;
    shippingProfile: string;
    returnPolicy: string;
    readinessState: string;
    whoMade: string;
    whenMade: string;
  }> {
    await this.openTab(/Publisher Defaults/);
    return {
      taxonomy: (await this.defaultTaxonomyIdInput.inputValue()).trim(),
      shippingProfile: (await this.defaultShippingProfileIdInput.inputValue()).trim(),
      returnPolicy: (await this.defaultReturnPolicyIdInput.inputValue()).trim(),
      readinessState: (await this.defaultReadinessStateIdInput.inputValue()).trim(),
      whoMade: (await this.defaultWhoMadeSelect.inputValue()).trim(),
      whenMade: (await this.defaultWhenMadeSelect.inputValue()).trim(),
    };
  }

  /** Assert the Authorize / Test Connection buttons are visible to the current user (sysadmin). */
  async assertSysadminButtonsVisible(): Promise<void> {
    await expect(this.authorizeButton).toBeVisible({ timeout: 8000 });
    await expect(this.testConnectionButton).toBeVisible({ timeout: 8000 });
  }

  // --- mutating surfaces (opt-in only) ------------------------------------

  /**
   * Trigger "Test Connection". Returns the toast/notification body text.
   * Read-only on Etsy side (GET /shops/{id}), but DO call sparingly — each call
   * spends one API rate-limit slot.
   */
  async clickTestConnection(): Promise<string> {
    await this.testConnectionButton.click();
    const toast = this.page.locator('.o_notification, .o_notification_body, .o_notification_content').first();
    await toast.waitFor({ state: 'visible', timeout: 15000 });
    return (await toast.textContent())?.trim() ?? '';
  }

  /**
   * DESTRUCTIVE: triggers OAuth round-trip (rotates tokens on success).
   * Do NOT call from pre-UAT — only from a TC explicitly testing the OAuth flow
   * with a sandbox shop the owner approved for token rotation.
   */
  async clickAuthorizeEtsy(): Promise<void> {
    await this.authorizeButton.click();
    // Etsy authorize opens a new tab — caller is responsible for handling it.
  }
}
