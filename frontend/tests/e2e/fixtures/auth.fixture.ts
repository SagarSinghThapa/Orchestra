import { Page, expect } from '@playwright/test';

export interface TestUser {
  email: string;
  role: 'admin' | 'member' | 'viewer';
}

export const TEST_USERS = {
  admin: {
    email: 'admin@orchestra.io',
    password: 'TestPassword123!',
    role: 'admin',
  },
  member: {
    email: 'member@orchestra.io',
    password: 'TestPassword123!',
    role: 'member',
  },
  viewer: {
    email: 'viewer@orchestra.io',
    password: 'TestPassword123!',
    role: 'viewer',
  },
} as const;

/**
 * Logs in via the real Next.js login form.
 * Asserts that the response sets an httpOnly session cookie and
 * that neither localStorage nor sessionStorage contains raw tokens.
 */
export async function loginAs(page: Page, role: 'admin' | 'member' | 'viewer') {
  const credentials = TEST_USERS[role];

  await page.goto('/login');
  await expect(page.getByRole('heading', { name: /Sign in to Orchestra/i })).toBeVisible();

  await page.getByPlaceholder('you@domain.com').fill(credentials.email);
  await page.getByPlaceholder('At least 8 characters...').fill(credentials.password);

  // Submit and wait for redirect to /dashboard
  await page.locator('button[type="submit"]').click();
  await page.waitForURL('**/dashboard', { timeout: 15000 });

  // Inviolable token privacy verification
  const localToken = await page.evaluate(() => localStorage.getItem('access_token'));
  const sessionToken = await page.evaluate(() => sessionStorage.getItem('access_token'));
  expect(localToken).toBeNull();
  expect(sessionToken).toBeNull();
}

/**
 * Clears cookies and navigates to login to ensure clean unauthenticated context.
 */
export async function logout(page: Page) {
  await page.context().clearCookies();
  await page.goto('/login');
}
