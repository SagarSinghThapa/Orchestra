import { test, expect } from '@playwright/test';
import { loginAs, TEST_USERS } from './fixtures/auth.fixture';

test.describe('Authentication & Session Security E2E', () => {
  test('unauthenticated navigation to protected route redirects to login', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForURL((url) => url.pathname === '/login');
    await expect(page.getByRole('heading', { name: /Sign in to Orchestra/i })).toBeVisible();
  });

  test('login flow sets httpOnly cookie and displays user profile in header', async ({ page }) => {
    await page.goto('/login');
    await page.getByPlaceholder('you@domain.com').fill(TEST_USERS.member.email);
    await page.getByPlaceholder('At least 8 characters...').fill(TEST_USERS.member.password);
    await page.locator('button[type="submit"]').click();

    await page.waitForURL('**/dashboard');
    await expect(page.getByText(TEST_USERS.member.email)).toBeVisible();
    await expect(page.getByText(/member/i).first()).toBeVisible();

    // Verify httpOnly cookie in browser context
    const cookies = await page.context().cookies();
    const accessCookie = cookies.find((c) => c.name === 'access_token');
    expect(accessCookie).toBeDefined();
    expect(accessCookie?.httpOnly).toBe(true);

    // Inviolable token privacy: zero tokens stored in localStorage or sessionStorage
    const localToken = await page.evaluate(() => localStorage.getItem('access_token'));
    const sessionToken = await page.evaluate(() => sessionStorage.getItem('access_token'));
    expect(localToken).toBeNull();
    expect(sessionToken).toBeNull();
  });

  test('session profile restores on browser reload without re-authenticating', async ({ page }) => {
    await loginAs(page, 'admin');
    await expect(page.getByText(TEST_USERS.admin.email)).toBeVisible();
    await expect(page.getByText(/admin/i).first()).toBeVisible();

    // Reload page
    await page.reload();
    await expect(page).toHaveURL(/.*dashboard/);
    await expect(page.getByText(TEST_USERS.admin.email)).toBeVisible();
    await expect(page.getByText(/admin/i).first()).toBeVisible();
  });

  test('sign out clears session and redirects to login', async ({ page }) => {
    await loginAs(page, 'viewer');
    await expect(page.getByText(TEST_USERS.viewer.email)).toBeVisible();

    // Click Sign out button
    await page.getByRole('button', { name: 'Sign out' }).click();
    await page.waitForURL((url) => url.pathname === '/login');
    await expect(page.getByRole('heading', { name: /Sign in to Orchestra/i })).toBeVisible();

    // Verify navigating back to protected route redirects to login
    await page.goto('/dashboard');
    await page.waitForURL((url) => url.pathname === '/login');
  });

  test('registration flow creates member account and logs in', async ({ page }) => {
    const randomEmail = `newuser_${Date.now()}@orchestra.io`;
    await page.goto('/login');

    // Switch to Create Account mode
    await page.getByRole('button', { name: 'Create Account' }).click();
    await expect(page.getByRole('heading', { name: /Create an account/i })).toBeVisible();

    await page.getByPlaceholder('you@domain.com').fill(randomEmail);
    await page.getByPlaceholder('At least 8 characters...').fill('SecurePassword123!');
    await page.getByRole('button', { name: 'Register' }).click();

    await page.waitForURL('**/dashboard');
    await expect(page.getByText(randomEmail)).toBeVisible();
    await expect(page.getByText(/member/i).first()).toBeVisible();
  });
});
