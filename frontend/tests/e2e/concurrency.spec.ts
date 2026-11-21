import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.fixture';

test.describe('Concurrency & Single-Flight Token Refresh E2E', () => {
  test('single-flight refresh: concurrent 401 requests coalesce into exactly one refresh call', async ({
    page,
    context,
  }) => {
    // 1. Log in to establish valid session cookies (lands on /dashboard)
    await loginAs(page, 'member');

    // Wait for dashboard to settle
    await page.waitForLoadState('networkidle');

    // 2. Corrupt access_token cookie to trigger 401 on next calls while keeping refresh_token intact
    const cookies = await context.cookies();
    const accessCookie = cookies.find((c) => c.name === 'access_token');
    if (accessCookie) {
      await context.addCookies([
        {
          name: 'access_token',
          value: 'invalid_expired_token_for_single_flight_test',
          domain: accessCookie.domain,
          path: accessCookie.path,
          httpOnly: accessCookie.httpOnly,
          secure: accessCookie.secure,
          sameSite: accessCookie.sameSite,
        },
      ]);
    }

    // 3. Count outgoing network calls to /auth/refresh
    let refreshCallCount = 0;
    page.on('request', (req) => {
      if (req.url().includes('/auth/refresh')) {
        refreshCallCount++;
      }
    });

    // 4. Dispatch 5 simultaneous API requests through window.api adapter in browser context
    const results = await page.evaluate(async () => {
      const api = (window as unknown as { api: { get: (path: string) => Promise<unknown> } }).api;
      const calls = Array.from({ length: 5 }, () =>
        api.get('/auth/me').then(
          (res) => ({ ok: true, data: res }),
          (err) => ({ ok: false, error: String(err) })
        )
      );
      return Promise.all(calls);
    });

    // 5. Invariant verification:
    // Exactly one refresh call was executed over the wire
    expect(refreshCallCount).toBe(1);

    // All 5 concurrent requests recovered cleanly and succeeded with user payload
    for (const res of results) {
      expect(res.ok).toBe(true);
      if ('data' in res) {
        expect((res.data as { email?: string })?.email).toBe('member@orchestra.io');
      }
    }
  });
});
