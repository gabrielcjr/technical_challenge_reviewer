import { test, expect } from '@playwright/test';

test.describe('Dashboard Page', () => {
  test('should load the dashboard successfully', async ({ page }) => {
    await page.goto('/');

    // Check title
    await expect(page).toHaveTitle(/ChallengeReviewer/i);

    // Wait for data to load
    await expect(page.getByRole('heading', { name: 'Challenges' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Recent Submissions' })).toBeVisible();

    // Verify navigation links
    await expect(page.getByRole('link', { name: 'New Challenge', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Submit Code', exact: true })).toBeVisible();
  });

  test('should navigate to new challenge form', async ({ page }) => {
    await page.goto('/');
    
    // Click on New Challenge link in navbar
    await page.getByRole('link', { name: 'New Challenge', exact: true }).click();
    
    // Check URL and page content
    await expect(page).toHaveURL(/.*\/challenges\/new/);
    await expect(page.locator('h1')).toContainText('Create New Challenge');
  });

  test('should navigate to submit code form', async ({ page }) => {
    await page.goto('/');
    
    // Click on Submit Code link in navbar
    await page.getByRole('link', { name: 'Submit Code', exact: true }).click();
    
    // Check URL and page content
    await expect(page).toHaveURL(/.*\/submissions\/new/);
    await expect(page.locator('h1')).toContainText('Submit Code');
  });
});
