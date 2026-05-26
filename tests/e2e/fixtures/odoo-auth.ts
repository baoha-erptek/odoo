import { Page, expect } from '@playwright/test';
import { CONFIG } from './env';

/**
 * Login to Odoo via the standard /web/login form.
 *
 * Selectors source: .claude/agents/e2e-runner.md "Odoo Login" section.
 * Database selector field appears only when the server hosts multiple DBs;
 * we fill it defensively (no-op if hidden).
 */
export async function loginAs(
  page: Page,
  login: string,
  password: string,
): Promise<void> {
  if (!login || !password) {
    throw new Error(`loginAs: missing login or password (login=${login || '<empty>'})`);
  }
  await page.goto('/web/login');
  // Database field — only present in multi-DB mode
  const dbField = page.locator('input[name="db"]');
  if (await dbField.count() > 0 && await dbField.isVisible()) {
    await dbField.fill(CONFIG.DB);
  }
  await page.locator('input[name="login"]').fill(login);
  await page.locator('input[name="password"]').fill(password);
  await page.locator('button[type="submit"]').click();
  // Wait for the post-login app shell (any of: home menu, app launcher, web URL)
  await page.waitForURL(/\/odoo|\/web/, { timeout: 30000 });
  // Odoo 19 renders BOTH <header class="o_navbar"> AND <nav class="o_main_navbar">;
  // pick whichever appears first.
  await expect(page.locator('nav.o_main_navbar, header.o_navbar').first()).toBeVisible({ timeout: 15000 });
}

export async function loginAsBaLead(page: Page): Promise<void> {
  return loginAs(page, CONFIG.BA_LEAD_LOGIN, CONFIG.BA_LEAD_PASSWORD);
}

export async function loginAsBaUser(page: Page): Promise<void> {
  return loginAs(page, CONFIG.BA_USER_LOGIN, CONFIG.BA_USER_PASSWORD);
}

export async function loginAsAdmin(page: Page): Promise<void> {
  return loginAs(page, CONFIG.ADMIN_LOGIN, CONFIG.ADMIN_PASSWORD);
}
