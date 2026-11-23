import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.fixture';

test.describe('CSRF & CORS Cross-Layer Security E2E', () => {
  test('direct cookie-authenticated mutation without X-Orchestra-Request fails with HTTP 403', async ({
    page,
    request,
  }) => {
    // 1. Authenticate via standard UI flow
    await loginAs(page, 'member');

    // 2. Extract access_token cookie from browser context
    const cookies = await page.context().cookies();
    const accessCookie = cookies.find((c) => c.name === 'access_token');
    expect(accessCookie).toBeDefined();

    // 3. Dispatch direct mutating request using cookie but omitting X-Orchestra-Request header
    const response = await request.post('http://127.0.0.1:8001/projects', {
      headers: {
        Cookie: `access_token=${accessCookie?.value}`,
        // Intentionally omit X-Orchestra-Request header
      },
      data: {
        name: 'Malicious CSRF Project',
        description: 'Should be rejected',
      },
    });

    expect(response.status()).toBe(403);
    const body = await response.json();
    expect(body.detail).toContain('CSRF protection header');
  });

  test('cookie-authenticated mutation with X-Orchestra-Request header succeeds with HTTP 201', async ({
    page,
    request,
  }) => {
    await loginAs(page, 'member');

    const cookies = await page.context().cookies();
    const accessCookie = cookies.find((c) => c.name === 'access_token');
    expect(accessCookie).toBeDefined();

    const response = await request.post('http://127.0.0.1:8001/projects', {
      headers: {
        Cookie: `access_token=${accessCookie?.value}`,
        'X-Orchestra-Request': 'true',
      },
      data: {
        name: `Valid Project ${Date.now()}`,
        description: 'Created with valid CSRF header',
      },
    });

    expect(response.status()).toBe(201);
    const body = await response.json();
    expect(body.name).toContain('Valid Project');
    expect(body.id).toBeDefined();
  });

  test('CORS preflight responds with allowed origin and exposed headers', async ({ request }) => {
    const response = await request.fetch('http://127.0.0.1:8001/projects', {
      method: 'OPTIONS',
      headers: {
        Origin: 'http://127.0.0.1:3001',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'X-Orchestra-Request,Content-Type',
      },
    });

    expect(response.status()).toBe(200);
    const allowOrigin = response.headers()['access-control-allow-origin'];
    expect(allowOrigin).toBe('http://127.0.0.1:3001');
    const allowCredentials = response.headers()['access-control-allow-credentials'];
    expect(allowCredentials).toBe('true');
  });
});
