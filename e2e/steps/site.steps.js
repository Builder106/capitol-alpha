// @ts-check
const { createBdd } = require('playwright-bdd');
const { expect } = require('@playwright/test');

const { Given, Then } = createBdd();

Given('I am on the research report', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('h1.title')).toBeVisible({ timeout: 10_000 });
});

Then('the page title contains {string}', async ({ page }, text) => {
  await expect(page).toHaveTitle(new RegExp(text));
});

Then('the headline alpha figure is visible', async ({ page }) => {
  await expect(page.locator('.verdict-number .digits')).toContainText('2.58');
});

Then('the verdict shows statistically significant', async ({ page }) => {
  await expect(page.locator('.rating-chip--pos')).toContainText(/Stat\. Sig/i);
});

Then('the KPI panel contains {string} alpha', async ({ page }, value) => {
  await expect(page.locator('.kpi-value').first()).toContainText(value);
});

Then('the KPI panel contains {string} total trades', async ({ page }, value) => {
  await expect(page.locator('.kpi-value').filter({ hasText: value })).toBeVisible();
});

Then('all {int} exhibit figures are present', async ({ page }, count) => {
  await expect(page.locator('.fig figure img')).toHaveCount(count);
});

Then('the abstract PDF link is present', async ({ page }) => {
  await expect(page.locator('a[href="/docs/abstract.pdf"]')).toBeVisible();
});

Then('the final reflection PDF link is present', async ({ page }) => {
  await expect(page.locator('a[href="/docs/final-reflection.pdf"]')).toBeVisible();
});
