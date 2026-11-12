// @ts-check
const { createBdd } = require('playwright-bdd');
const { expect } = require('@playwright/test');

const { Given, When, Then } = createBdd();

Given('I am on the research site', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('h1.question')).toBeVisible({ timeout: 10_000 });
});

Given('I open a page that does not exist', async ({ page }) => {
  await page.goto('/404.html');
});

When('I open the index', async ({ page }) => {
  await page.getByRole('button', { name: /index of event days/i }).click();
  await expect(page.locator('#index')).toBeVisible();
});

Then('the page title contains {string}', async ({ page }, text) => {
  await expect(page).toHaveTitle(new RegExp(text));
});

Then('the question asks whether members beat the market', async ({ page }) => {
  await expect(page.locator('h1.question')).toContainText('beat the market');
});

Then('the answer starts with {string}', async ({ page }, text) => {
  await expect(page.locator('.unit--question .answer')).toHaveText(new RegExp(`^${text.replace('.', '\\.')}`));
});

Then('the primary result shows {string} alpha a year', async ({ page }, value) => {
  await expect(page.locator('#day-62 .result dd').first()).toContainText(value);
});

Then('the primary result shows a p-value of {string}', async ({ page }, value) => {
  await expect(page.locator('#day-62 .result dd').nth(2)).toHaveText(value);
});

Then('the plot draws the mean abnormal return line and its band', async ({ page }) => {
  const paths = page.locator('.plot g[clip-path] path');
  await expect(paths).toHaveCount(2);
  for (const index of [0, 1]) {
    await expect(paths.nth(index)).toHaveAttribute('d', /^M[\d.]+,[\d.]+L/);
  }
});

Then('the robustness table has {int} checks', async ({ page }, count) => {
  await expect(page.locator('.checks tbody tr')).toHaveCount(count);
});

Then('the robustness chart draws {int} intervals', async ({ page }, count) => {
  await expect(page.locator('.forest__chart circle')).toHaveCount(count);
});

Then('the index links to {string}', async ({ page }, hash) => {
  await expect(page.locator(`#index a[href="${hash}"]`)).toBeVisible();
});

Then('the abstract PDF link is present', async ({ page }) => {
  await expect(page.locator('a[href="/docs/abstract.pdf"]')).toBeVisible();
});

Then('the final reflection PDF link is present', async ({ page }) => {
  await expect(page.locator('a[href="/docs/final-reflection.pdf"]').first()).toBeVisible();
});

Then('the 404 page links back to the start', async ({ page }) => {
  await expect(page.locator('h1')).toContainText('off the axis');
  await expect(page.locator('main a[href="/"]')).toBeVisible();
});
