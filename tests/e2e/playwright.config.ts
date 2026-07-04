import { defineConfig, devices } from '@playwright/test';

const BASE_URL = process.env.STAGING_BASE_URL || 'https://odoo.hatafax.com';
const SCREENSHOT_CAPTURE = process.env.SCREENSHOT_CAPTURE === '1';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'reports/html', open: 'never' }],
    ['json', { outputFile: 'reports/results.json' }],
  ],
  outputDir: 'artifacts',
  globalSetup: require.resolve('./fixtures/global-setup.ts'),
  globalTeardown: require.resolve('./fixtures/global-teardown.ts'),
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: SCREENSHOT_CAPTURE ? 'on' : 'only-on-failure',
    video: SCREENSHOT_CAPTURE ? 'on' : 'retain-on-failure',
    actionTimeout: 15000,
    navigationTimeout: 30000,
    ignoreHTTPSErrors: false,
    locale: 'vi-VN',
    timezoneId: 'Asia/Ho_Chi_Minh',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  timeout: 60000,
  expect: { timeout: 10000 },
});
