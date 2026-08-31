const {defineConfig, devices} = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 30000,
  fullyParallel: true,
  retries: 1,
  failOnFlakyTests: true,
  use: {
    baseURL: 'http://127.0.0.1:8011',
    trace: 'retain-on-failure',
    // Full Chromium's new headless mode; the separate legacy shell crashed in mobile context setup.
    channel: 'chromium',
  },
  projects: [
    {name: 'chromium-desktop', use: {...devices['Desktop Chrome']}},
    {name: 'chromium-mobile', use: {...devices['Pixel 7']}},
  ],
});
