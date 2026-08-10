import { test, expect } from '@playwright/test';

test.describe('Evaluation Display', () => {
  test('should display the evaluation score and result', async ({ page }) => {
    // We can use a longer timeout for this test as the evaluation takes time
    test.setTimeout(60000);

    await page.goto('/submissions/new');

    const uniqueUser = `EvalTestUser-${Date.now()}`;
    
    // Fill out the form with a known repo
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
    
    // Wait for the AI Evaluation Report header to become visible
    // This implies status changed to 'approved' or 'rejected'
    await expect(page.locator('text=AI Evaluation Report')).toBeVisible({ timeout: 45000 });

    // Verify Candidate Approved or Candidate Rejected is visible
    await expect(page.locator('text=Candidate').first()).toBeVisible();

    // Verify Overall Feedback and Detailed Reasoning headers are displayed
    await expect(page.locator('text=Overall Feedback')).toBeVisible();
    await expect(page.locator('text=Detailed Reasoning')).toBeVisible();
  });
});
