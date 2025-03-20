import { test, expect } from '@playwright/test';

test.describe('Tool Providers Page', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the API responses
    await page.route('**/api/auth/apps*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 1,
          app_id: '59da877a-a426-4142-bff7-95d1fb603958',
          name: 'Test Tool Provider',
          description: 'A test tool provider',
          type: 'tool_provider',
          created_at: '2025-03-20T22:36:25.220499',
          is_active: true,
        }]),
      });
    });

    await page.route('**/api/auth/keys*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 1,
          name: 'Test Key',
          app_id: 1,
          created_at: '2025-03-20T22:37:40.060812',
          last_used_at: null,
          is_active: true,
        }]),
      });
    });

    // Navigate to the Tool Providers page
    await page.goto('/tool-providers');
  });

  test('displays tool providers list', async ({ page }) => {
    // Check if the page title is displayed
    await expect(page.getByRole('heading', { name: 'Tool Providers' })).toBeVisible();

    // Check if the "Register New Provider" button is displayed
    await expect(page.getByRole('button', { name: 'Register New Provider' })).toBeVisible();

    // Check if the table headers are displayed
    const expectedHeaders = ['Name', 'Description', 'Status', 'Created', 'API Key', 'Actions'];
    for (const header of expectedHeaders) {
      await expect(page.locator('th', { hasText: header })).toBeVisible();
    }

    // Get the first row cells
    const row = page.locator('tbody tr').first();
    
    // Check if the test tool provider is displayed with correct data
    await expect(row.locator('td').nth(0)).toHaveText('Test Tool Provider');
    await expect(row.locator('td').nth(1)).toHaveText('A test tool provider');
    
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