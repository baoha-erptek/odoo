import { defineConfig, devices } from '@playwright/test';

const BASE_URL = process.env.STAGING_BASE_URL || 'https://odoo.hatafax.com';
const SCREENSHOT_CAPTURE = process.env.SCREENSHOT_CAPTURE === '1';
// Video user-guide recording mode (guide_flow_*.spec.ts): 1080p, slowMo,
// always-on video, no retries (a retry would splice junk into the recording).
const GUIDE_RECORDING = process.env.GUIDE_RECORDING === '1';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: GUIDE_RECORDING ? 0 : (process.env.CI ? 2 : 1),
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
    video: GUIDE_RECORDING
      ? { mode: 'on', size: { width: 1920, height: 1080 } }
      : (SCREENSHOT_CAPTURE ? 'on' : 'retain-on-failure'),
    ...(GUIDE_RECORDING
      ? { viewport: { width: 1920, height: 1080 }, launchOptions: { slowMo: 100 } }
      : {}),
    actionTimeout: 15000,
    navigationTimeout: 30000,
    ignoreHTTPSErrors: false,
    locale: 'vi-VN',
    timezoneId: 'Asia/Ho_Chi_Minh',
  },
  projects: [
    {
      name: 'chromium',
      // devices[] pins viewport 1280x720 — guide recording must override it
      // AFTER the spread or the 1080p video letterboxes around a 720p page.
      use: {
        ...devices['Desktop Chrome'],
        ...(GUIDE_RECORDING ? { viewport: { width: 1920, height: 1080 } } : {}),
      },
    },
  ],
  // Guide chapters run at teaching pace with live vendor calls — allow 10 min.
  timeout: GUIDE_RECORDING ? 600000 : 60000,
  expect: { timeout: 10000 },
});
