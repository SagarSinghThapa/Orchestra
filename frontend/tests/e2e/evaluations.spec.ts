import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.fixture';

test.describe('Evaluations Benchmarking Dashboard E2E', () => {
  let projectId: number;

  test.beforeEach(async ({ page, request }) => {
    await loginAs(page, 'admin');

    const cookies = await page.context().cookies();
    const accessCookie = cookies.find((c) => c.name === 'access_token');

    const createResp = await request.post('http://127.0.0.1:8001/projects', {
      headers: {
        Cookie: `access_token=${accessCookie?.value}`,
        'X-Orchestra-Request': 'true',
      },
      data: {
        name: `Eval Space ${Date.now()}`,
        description: 'Testing evaluation benchmarking dashboard',
      },
    });

    expect(createResp.status()).toBe(201);
    const proj = await createResp.json();
    projectId = proj.id;

    await page.evaluate((id) => {
      localStorage.setItem('orchestra_selected_project_id', id.toString());
    }, projectId);
  });

  test('runs deterministic benchmark suite, verifies metric cards, inspects run cases, and sets baseline', async ({
    page,
  }) => {
    await page.goto('/evaluations');
    await expect(page.getByRole('heading', { name: 'Model & Agent Evaluations' })).toBeVisible();

    // 1. Verify Metric Cards headers are present
    await expect(page.getByText('RAG Faithfulness', { exact: true })).toBeVisible();
    await expect(page.getByText('Citation Precision', { exact: true })).toBeVisible();
    await expect(page.getByText('Coding AST Validity', { exact: true })).toBeVisible();
    await expect(page.getByText('P95 Latency', { exact: true })).toBeVisible();

    // 2. Open Run Benchmark Modal
    const runBtn = page.getByRole('button', { name: /Run Benchmark/i }).first();
    await expect(runBtn).toBeVisible();
    await runBtn.click();

    await expect(page.getByRole('heading', { name: 'Execute Benchmark Suite' })).toBeVisible();

    // Click Launch Benchmark
    const startBtn = page.getByRole('button', { name: 'Launch Benchmark' });
    await expect(startBtn).toBeVisible();
    await startBtn.click();

    // 3. Wait for evaluation execution to complete and inspector modal to open automatically
    await expect(page.getByRole('heading', { name: /Run Inspection:/i })).toBeVisible({
      timeout: 45000,
    });

    // Verify test case breakdown is rendered
    await expect(page.getByText(/Case-by-Case Execution Results/i)).toBeVisible();

    // Close inspector modal
    await page.getByRole('button', { name: '✕' }).click();
    await expect(page.getByRole('heading', { name: /Run Inspection:/i })).not.toBeVisible();

    // 4. Verify run appears in RunsTable with 'Completed' status badge
    await expect(page.getByText('Completed').first()).toBeVisible();

    // 5. Baseline designation
    const baselineBtn = page.getByRole('button', { name: /Set Baseline/i }).first();
    if (await baselineBtn.isVisible()) {
      await baselineBtn.click();
      await expect(page.getByText(/Active Baseline/i).first()).toBeVisible({ timeout: 10000 });
    }
  });
});

