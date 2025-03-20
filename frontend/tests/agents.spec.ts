import { test, expect } from '@playwright/test';

test.describe('Agents Page', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the API responses
    await page.route('**/api/auth/apps*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 2,
          app_id: 'e7ef8f19-794a-4927-8976-c7c805bc9cb4',
          name: 'Test Agent',
          description: 'A test agent',
          type: 'agent',
          created_at: '2025-03-20T22:37:01.868679',
          is_active: true,
        }]),
      });
    });

    await page.route('**/api/auth/keys*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 2,
          name: 'Test Key',
          app_id: 2,
          created_at: '2025-03-20T22:37:40.818814',
          last_used_at: null,
          is_active: true,
        }]),
      });
    });

    // Navigate to the Agents page
    await page.goto('/agents');
  });

  test('displays agents list', async ({ page }) => {
    // Check if the page title is displayed
    await expect(page.getByRole('heading', { name: 'Agents' })).toBeVisible();

    // Check if the "Register New Agent" button is displayed
    await expect(page.getByRole('button', { name: 'Register New Agent' })).toBeVisible();

    // Check if the table headers are displayed
    const expectedHeaders = ['Name', 'Description', 'Status', 'Created', 'API Key', 'Actions'];
    for (const header of expectedHeaders) {
      await expect(page.locator('th', { hasText: header })).toBeVisible();
    }

    // Get the first row cells
    const row = page.locator('tbody tr').first();
    
    // Check if the test agent is displayed with correct data
    await expect(row.locator('td').nth(0)).toHaveText('Test Agent');
    await expect(row.locator('td').nth(1)).toHaveText('A test agent');
    
    // Check status badge
    const statusCell = row.locator('td').nth(2);
    await expect(statusCell.locator('span')).toHaveText('Active');
    
    // Check created date
    await expect(row.locator('td').nth(3)).toHaveText('Mar 20, 2025');

    // Check API key badge
    const keyCell = row.locator('td').nth(4);
    await expect(keyCell.locator('span')).toHaveText('Active');

    // Check action buttons
    const actionsCell = row.locator('td').nth(5);
    await expect(actionsCell.getByRole('button', { name: 'Edit' })).toBeVisible();
    await expect(actionsCell.getByRole('button', { name: 'Delete' })).toBeVisible();
  });
}); 