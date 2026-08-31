const {defineConfig, devices} = require('@playwright/test');
module.exports = defineConfig({testDir:'./tests/e2e', timeout:30000, fullyParallel:true, retries:1,
  use:{baseURL:'http://127.0.0.1:8011', trace:'retain-on-failure'},
  projects:[{name:'chromium-desktop',use:{...devices['Desktop Chrome']}},{name:'chromium-mobile',use:{...devices['Pixel 7']}}]});
