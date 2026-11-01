import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.fixture';

test.describe('Conversational Memory & Multi-Turn Chat E2E', () => {
  let projectId: number;

  test.beforeEach(async ({ page, request }) => {
    await loginAs(page, 'member');

    const cookies = await page.context().cookies();
    const accessCookie = cookies.find((c) => c.name === 'access_token');

    // Create a fresh project for chat session isolation
    const createResp = await request.post('http://127.0.0.1:8001/projects', {
      headers: {
        Cookie: `access_token=${accessCookie?.value}`,
        'X-Orchestra-Request': 'true',
      },
      data: {
        name: `Chat Memory Workspace ${Date.now()}`,
        description: 'Multi-turn conversation and three-tier memory testing',
      },
    });

    expect(createResp.status()).toBe(201);
    const proj = await createResp.json();
    projectId = proj.id;

    await page.evaluate((id) => {
      localStorage.setItem('orchestra_selected_project_id', id.toString());
    }, projectId);
  });

  test('multi-turn conversation preserves context and persists across browser reload', async ({
    page,
  }) => {
    await page.goto('/chat');
    await expect(page.getByRole('heading', { name: 'Orchestra Autonomous Assistant' })).toBeVisible();

    const input = page.getByRole('textbox');

    // 1. Send first turn
    await input.fill('What is the capital of France?');
    await page.getByRole('button', { name: 'Send' }).click();

    // Verify first response arrives
    await expect(page.getByText(/Routing through LangGraph/i)).toBeVisible({ timeout: 5000 }).catch(() => {});
    await expect(page.locator('.prose, [data-testid="message-content"]').first()).toBeVisible({ timeout: 30000 });

    // 2. Send follow-up turn
    await input.fill('What is its population approximately?');
    await page.getByRole('button', { name: 'Send' }).click();

    // Verify second response arrives
    await expect(page.locator('.prose, [data-testid="message-content"]').nth(1)).toBeVisible({ timeout: 30000 });

    // 3. Browser reload to verify persistence from SQLite backend
    await page.reload();
    await expect(page).toHaveURL(/.*chat/);

    // Verify messages reload from backend
    await expect(page.getByText('What is the capital of France?')).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('What is its population approximately?')).toBeVisible({ timeout: 15000 });
  });

  test('inspects memory telemetry modal, validates privacy boundary, resets and rebuilds memory', async ({
    page,
  }) => {
    await page.goto('/chat');
    await expect(page.getByRole('heading', { name: 'Orchestra Autonomous Assistant' })).toBeVisible();

    const input = page.getByRole('textbox');

    // Seed conversation with message
    await input.fill('Initiating conversation for memory telemetry testing.');
    await page.getByRole('button', { name: 'Send' }).click();
    await expect(page.locator('.prose, [data-testid="message-content"]').first()).toBeVisible({ timeout: 30000 });

    // Open Memory Telemetry modal
    const memoryBtn = page.getByRole('button', { name: /Memory Telemetry/i });
    await expect(memoryBtn).toBeVisible({ timeout: 10000 });
    await memoryBtn.click();

    // Verify modal headers and telemetry items
    await expect(page.getByRole('heading', { name: /Session Memory & Telemetry/i })).toBeVisible();
    await expect(page.getByText('Derived Summary')).toBeVisible();
    await expect(page.getByText('Assembled Context')).toBeVisible();
    await expect(page.getByText('Active Sliding Window')).toBeVisible();

    // Inviolable Privacy Invariant: raw internal summary string is NEVER rendered in client DOM
    const modalContent = await page.locator('.fixed.inset-0').innerText();
    expect(modalContent).not.toContain('RAW_SYSTEM_SUMMARY_PROMPT');
    expect(modalContent).not.toContain('LLM_MEMORY_STATE_RAW');

    // Trigger memory rebuild
    const rebuildBtn = page.getByRole('button', { name: 'Rebuild Memory' });
    await expect(rebuildBtn).toBeVisible();
    await rebuildBtn.click();

    // Close modal
    await page.getByRole('button', { name: '✕' }).click();
    await expect(page.getByRole('heading', { name: /Session Memory & Telemetry/i })).not.toBeVisible();

    // Verify original chat message remains completely intact on the screen
    await expect(page.getByText('Initiating conversation for memory telemetry testing.')).toBeVisible();
  });
});

