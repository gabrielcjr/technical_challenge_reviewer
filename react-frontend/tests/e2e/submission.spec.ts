import { test, expect } from '@playwright/test';

test.describe('Challenge and Submission Flow', () => {
  test('should create a new challenge', async ({ page }) => {
    await page.goto('/challenges/new');

    const uniqueTitle = `E2E Test Challenge ${Date.now()}`;
    
    // Fill out the form
    await page.fill('input#title', uniqueTitle);
    await page.fill('textarea#description', 'This is an E2E test challenge description that is longer than 20 characters.');
    
    // Submit
    await page.click('button[type="submit"]');

    // Should redirect to dashboard and show the new challenge
    await expect(page).toHaveURL('/');
    await expect(page.locator(`text=${uniqueTitle}`)).toBeVisible();
  });

  test('should submit code against a custom challenge', async ({ page }) => {
    await page.goto('/submissions/new');

    const uniqueUser = `E2EUser-${Date.now()}`;
    
    // Fill out the form
    await page.fill('input#userName', uniqueUser);
    await page.fill('input#githubRepoUrl', 'https://github.com/octocat/Hello-World');
    
    // Select custom instructions
    await page.click('label[for="useCustom"]');
    
    // Fill custom instructions
    await page.fill('textarea', 'Evaluate this custom E2E challenge submission. Must be at least 20 chars.');

    // Submit
    await page.click('button[type="submit"]');

    // Should redirect to submission details page
    await expect(page).toHaveURL(/.*\/submissions\/[0-9a-fA-F-]{36}/);
    
    // Verify the user name is visible on the details page
    await expect(page.locator('h1')).toContainText(uniqueUser);
    
    // Verify status is displayed
    await expect(page.getByText('pending', { exact: true }).or(page.getByText('processing', { exact: true }))).toBeVisible();
  });
});
