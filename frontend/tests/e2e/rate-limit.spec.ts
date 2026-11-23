import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.fixture';

test.describe('Rate Limiting Enforcement & Cooldown UX E2E', () => {
  let projectId: number;

  test.beforeEach(async ({ page, request }) => {
    await loginAs(page, 'member');

    const cookies = await page.context().cookies();
    const accessCookie = cookies.find((c) => c.name === 'access_token');

    // Create a project for test isolation
    const createResp = await request.post('http://127.0.0.1:8001/projects', {
      headers: {
        Cookie: `access_token=${accessCookie?.value}`,
        'X-Orchestra-Request': 'true',
      },
      data: {
        name: `Throttle Space ${Date.now()}`,
        description: 'Rate limit testing workspace',
      },
    });

    expect(createResp.status()).toBe(201);
    const proj = await createResp.json();
    projectId = proj.id;

    await page.evaluate((id) => {
      localStorage.setItem('orchestra_selected_project_id', id.toString());
    }, projectId);
  });

  test('HTTP 429 response includes Retry-After header, X-Request-ID, and structured error body', async ({
    page,
  }) => {
    // Intercept a route to simulate 429 rate limit enforcement with valid CORS credentials headers
    await page.route(`**/projects/${projectId}/rate-limit-test`, async (route) => {
      await route.fulfill({
        status: 429,
        contentType: 'application/json',
        headers: {
          'Access-Control-Allow-Origin': 'http://127.0.0.1:3001',
          'Access-Control-Allow-Credentials': 'true',
          'Access-Control-Expose-Headers': 'Retry-After, X-Request-ID',
          'Retry-After': '5',
          'X-Request-ID': 'req-rate-limit-test-12345',
        },
        body: JSON.stringify({
          detail: 'Rate limit exceeded. Quota exhausted for route class.',
          error_category: 'rate_limited',
        }),
      });
    });

    // Invoke through window.api adapter and inspect caught ApiError
    const result = await page.evaluate(async (pid) => {
      const api = (window as unknown as {
        api: { get: (path: string) => Promise<unknown> };
      }).api;

      try {
        await api.get(`http://127.0.0.1:8001/projects/${pid}/rate-limit-test`);
        return { success: true };
      } catch (err: unknown) {
        const error = err as {
          status?: number;
          message?: string;
          retryAfter?: number;
          requestId?: string;
        };
        return {
          success: false,
          status: error.status,
          message: error.message,
          retryAfter: error.retryAfter,
          requestId: error.requestId,
        };
      }
    }, projectId);

    expect(result.success).toBe(false);
    expect(result.status).toBe(429);
    expect(result.retryAfter).toBe(5);
    expect(result.requestId).toBe('req-rate-limit-test-12345');
    expect(result.message).toContain('Rate limit exceeded');
  });

  test('UI gracefully handles 429 error and displays non-blocking cooldown feedback without loop', async ({
    page,
  }) => {
    // Navigate to chat
    await page.goto('/chat');
    await expect(page.getByRole('heading', { name: 'Orchestra Autonomous Assistant' })).toBeVisible();

    // Intercept chat orchestration call to return 429 with Retry-After: 3
    await page.route(/\/projects\/[^/]+\/orchestrate/, async (route) => {
      await route.fulfill({
        status: 429,
        contentType: 'application/json',
        headers: {
          'Access-Control-Allow-Origin': 'http://127.0.0.1:3001',
          'Access-Control-Allow-Credentials': 'true',
          'Access-Control-Expose-Headers': 'Retry-After, X-Request-ID',
          'Retry-After': '3',
          'X-Request-ID': 'req-chat-throttled-6789',
        },
        body: JSON.stringify({
          detail: 'Too many research queries. Please wait 3 seconds.',
          error_category: 'rate_limited',
        }),
      });
    });

    // Send a message in chat
    const input = page.getByRole('textbox');
    await input.fill('Trigger throttle test');
    await page.getByRole('button', { name: 'Send' }).click();

    // Verify error toast or banner is displayed with rate limit feedback
    await expect(
      page.getByText(/Too many research queries|Please wait 3 seconds/i)
    ).toBeVisible({ timeout: 10000 });

    // Verify user can input new query and send button becomes active (not locked in error state)
    await input.fill('New query after cooldown');
    const sendBtn = page.getByRole('button', { name: 'Send' });
    await expect(sendBtn).toBeEnabled();
  });
});
