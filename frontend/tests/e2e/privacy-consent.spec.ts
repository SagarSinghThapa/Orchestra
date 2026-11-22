import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.fixture';

test.describe('Privacy, Cookie Consent & Public Policy Architecture E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Clear storage and cookies for clean initial context
    await page.context().clearCookies();
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());
    await page.reload();
  });

  test('first-time visitor sees cookie consent banner and can acknowledge', async ({ page }) => {
    await page.goto('/login');

    const banner = page.locator('aside[aria-label="Cookie and Privacy Consent"]');
    await expect(banner).toBeVisible();
    await expect(banner.getByText(/Privacy & Cookie Notice/i)).toBeVisible();

    // Acknowledge essential storage
    const ackBtn = banner.getByRole('button', { name: /acknowledge & continue/i });
    await ackBtn.click();

    // Banner dismisses immediately
    await expect(banner).not.toBeVisible();

    // Persisted in localStorage
    const stored = await page.evaluate(() => {
      const raw = localStorage.getItem('orchestra_cookie_consent_v1');
      return raw ? JSON.parse(raw) : null;
    });

    expect(stored).not.toBeNull();
    expect(stored.version).toBe(1);
    expect(stored.consentGiven).toBe(true);
    expect(stored.categories.essential).toBe(true);
    expect(stored.categories.analytics).toBe(false);

    // Survives page refresh without reappearing
    await page.reload();
    await expect(page.locator('aside[aria-label="Cookie and Privacy Consent"]')).not.toBeVisible();
  });

  test('unauthenticated public access to /privacy and /cookies without login redirect', async ({ page }) => {
    // 1. Visit /privacy unauthenticated
    await page.goto('/privacy');
    await expect(page).toHaveURL(/\/privacy$/);
    await expect(page.getByRole('heading', { name: /Privacy Policy/i, level: 1 })).toBeVisible();
    await expect(page.getByText(/\[DRAFT — PENDING OWNER REVIEW\]/i)).toBeVisible();

    // 2. Visit /cookies unauthenticated
    await page.goto('/cookies');
    await expect(page).toHaveURL(/\/cookies$/);
    await expect(page.getByRole('heading', { name: /Cookie Policy/i, level: 1 })).toBeVisible();
    await expect(page.getByText(/First-Party Cookies Deployed by Orchestra/i)).toBeVisible();
    await expect(page.getByText('access_token')).toBeVisible();
    await expect(page.getByText('refresh_token')).toBeVisible();
    await expect(page.getByText('csrf_token')).toBeVisible();
  });

  test('protected workspace routes strictly redirect unauthenticated visitors to login', async ({ page }) => {
    // /settings must redirect
    await page.goto('/settings');
    await page.waitForURL((url) => url.pathname === '/login');
    expect(page.url()).toContain('redirect=%2Fsettings');

    // /chat must redirect
    await page.goto('/chat');
    await page.waitForURL((url) => url.pathname === '/login');
    expect(page.url()).toContain('redirect=%2Fchat');

    // /projects must redirect
    await page.goto('/projects');
    await page.waitForURL((url) => url.pathname === '/login');
    expect(page.url()).toContain('redirect=%2Fprojects');
  });

  test('cookie preferences modal can be opened from /cookies and customized', async ({ page }) => {
    await page.goto('/cookies');

    const openPrefsBtn = page.getByRole('button', { name: /open cookie preferences/i });
    await openPrefsBtn.click();

    const dialog = page.getByRole('dialog', { name: /privacy & cookie preferences/i });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText(/Strictly Necessary Cookies & Storage/i)).toBeVisible();
    await expect(dialog.getByText(/Always Active/i)).toBeVisible();

    // Toggle optional analytics switch
    const analyticsSwitch = dialog.getByRole('switch', { name: /toggle optional analytics/i });
    await expect(analyticsSwitch).toHaveAttribute('aria-checked', 'false');

    await analyticsSwitch.click();
    await expect(analyticsSwitch).toHaveAttribute('aria-checked', 'true');

    // Save preferences
    await dialog.getByRole('button', { name: /save preferences/i }).click();
    await expect(dialog).not.toBeVisible();

    // Verify localStorage update
    const consent = await page.evaluate(() => {
      const raw = localStorage.getItem('orchestra_cookie_consent_v1');
      return raw ? JSON.parse(raw) : null;
    });
    expect(consent?.categories?.analytics).toBe(true);
  });

  test('authenticated user can view and manage privacy preferences from /settings', async ({ page }) => {
    await loginAs(page, 'member');

    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: /Platform Settings/i })).toBeVisible();

    const privacyCard = page.locator('div', { hasText: 'Privacy & Data Preferences' }).first();
    await expect(privacyCard).toBeVisible();
    await expect(privacyCard.getByText(/Essential Authentication & CSRF Cookies/i)).toBeVisible();

    const manageBtn = page.getByRole('button', { name: /manage cookie preferences/i });
    await manageBtn.click();

    const dialog = page.getByRole('dialog', { name: /privacy & cookie preferences/i });
    await expect(dialog).toBeVisible();

    // Dismiss with cancel
    await dialog.getByRole('button', { name: /cancel/i }).click();
    await expect(dialog).not.toBeVisible();
  });

  test('zero tokens or credentials in localStorage across all privacy actions', async ({ page }) => {
    await page.goto('/login');

    // Acknowledge consent
    const ackBtn = page.locator('aside[aria-label="Cookie and Privacy Consent"]').getByRole('button', { name: /acknowledge & continue/i });
    if (await ackBtn.isVisible()) {
      await ackBtn.click();
    }

    // Inspect localStorage keys and values
    const storageDump = await page.evaluate(() => {
      const dump: Record<string, string> = {};
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key) {
          dump[key] = localStorage.getItem(key) || '';
        }
      }
      return dump;
    });

    for (const [key, val] of Object.entries(storageDump)) {
      expect(key.toLowerCase()).not.toContain('token');
      expect(key.toLowerCase()).not.toContain('secret');
      expect(key.toLowerCase()).not.toContain('jwt');
      expect(val.toLowerCase()).not.toContain('bearer');
      expect(val.toLowerCase()).not.toContain('eyj'); // JWT signature prefix
    }
  });
});
