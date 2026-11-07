import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.fixture';

test.describe('Error Recovery, Request ID Surfacing & Chat Retry E2E', () => {
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
        name: `Recovery Test Space ${Date.now()}`,
        description: 'Testing error banners, request IDs, and message retries',
      },
    });

    expect(createResp.status()).toBe(201);
    const proj = await createResp.json();
    projectId = proj.id;

    await page.evaluate((id) => {
      localStorage.setItem('orchestra_selected_project_id', id.toString());
    }, projectId);
  });

  test('surfaces correlation Request ID on error and guarantees zero stack traces in DOM', async ({
    page,
  }) => {
    await page.goto('/chat');
    await expect(page.getByRole('heading', { name: 'Orchestra Autonomous Assistant' })).toBeVisible();

    const simulatedRequestId = 'req_e2e_recovery_test_98765';

    // Intercept orchestration call with a 500 error containing correlation request ID
    await page.route(/\/projects\/[^/]+\/orchestrate/, async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        headers: {
          'Access-Control-Allow-Origin': 'http://127.0.0.1:3001',
          'Access-Control-Allow-Credentials': 'true',
          'Access-Control-Expose-Headers': 'X-Request-ID',
          'X-Request-ID': simulatedRequestId,
        },
        body: JSON.stringify({
          detail: `Upstream service failure. Reference ID: ${simulatedRequestId}`,
          error_category: 'upstream_error',
        }),
      });
    });

    const input = page.getByRole('textbox');
    await input.fill('Trigger error surfacing check');
    await page.getByRole('button', { name: 'Send' }).click();

    // 1. Verify error banner surfaces the Request ID
    await expect(page.getByText(simulatedRequestId)).toBeVisible({ timeout: 10000 });

    // 2. Information disclosure audit: assert DOM contains zero Python stack traces or internal paths
    const bodyText = await page.innerText('body');
    expect(bodyText).not.toContain('Traceback (most recent call last)');
    expect(bodyText).not.toContain('site-packages');
    expect(bodyText).not.toContain('.py", line');
    expect(bodyText).not.toContain('SELECT ');
    expect(bodyText).not.toContain('password_hash');
  });

  test('failed chat message allows one-click inline retry that recovers successfully', async ({
    page,
  }) => {
    await page.goto('/chat');
    await expect(page.getByRole('heading', { name: 'Orchestra Autonomous Assistant' })).toBeVisible();

    let failFirstCall = true;

    // Route that fails the first time, then succeeds on retry
    await page.route(/\/projects\/[^/]+\/orchestrate/, async (route) => {
      if (failFirstCall) {
        failFirstCall = false;
        await route.fulfill({
          status: 502,
          contentType: 'application/json',
          headers: {
            'Access-Control-Allow-Origin': 'http://127.0.0.1:3001',
            'Access-Control-Allow-Credentials': 'true',
          },
          body: JSON.stringify({
            detail: 'Temporary upstream gateway timeout. Please retry.',
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          headers: {
            'Access-Control-Allow-Origin': 'http://127.0.0.1:3001',
            'Access-Control-Allow-Credentials': 'true',
          },
          body: JSON.stringify({
            session_id: 1,
            intent: 'direct_qa',
            answer: 'Recovered response after inline retry successfully generated.',
            execution_trace: ['intent_classified', 'direct_qa_executed'],
            metadata: { duration_ms: 15 },
          }),
        });
      }
    });

    // 1. Send query
    const input = page.getByRole('textbox');
    await input.fill('Compute distributed consensus status');
    await page.getByRole('button', { name: 'Send' }).click();

    // 2. Verify error banner and Retry button appear on the failed message bubble
    await expect(page.getByText('Temporary upstream gateway timeout')).toBeVisible({ timeout: 10000 });
    const retryBtn = page.getByRole('button', { name: 'Retry' });
    await expect(retryBtn).toBeVisible();

    // 3. Click Retry
    await retryBtn.click();

    // 4. Verify message completes and recovered answer is rendered without page reload
    await expect(
      page.getByText('Recovered response after inline retry successfully generated.')
    ).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('Temporary upstream gateway timeout')).not.toBeVisible();
  });
});
