import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.fixture';
import path from 'path';
import fs from 'fs';

test.describe('Grounded Research & Citation Verification E2E', () => {
  let projectId: number;

  test.beforeEach(async ({ page, request }) => {
    await loginAs(page, 'member');

    const cookies = await page.context().cookies();
    const accessCookie = cookies.find((c) => c.name === 'access_token');

    // Create a dedicated project for research tests
    const createResp = await request.post('http://127.0.0.1:8001/projects', {
      headers: {
        Cookie: `access_token=${accessCookie?.value}`,
        'X-Orchestra-Request': 'true',
      },
      data: {
        name: `Research Space ${Date.now()}`,
        description: 'Testing grounded RAG and citations',
      },
    });

    expect(createResp.status()).toBe(201);
    const proj = await createResp.json();
    projectId = proj.id;

    await page.evaluate((id) => {
      localStorage.setItem('orchestra_selected_project_id', id.toString());
    }, projectId);

    // Upload research fixture document to project via API
    const mdPath = path.resolve(__dirname, 'fixtures/documents/sample_research.md');
    const fileBuffer = fs.readFileSync(mdPath);

    const formData = new FormData();
    const blob = new Blob([fileBuffer], { type: 'text/markdown' });
    formData.append('file', blob, 'sample_research.md');

    const uploadResp = await request.post(`http://127.0.0.1:8001/projects/${projectId}/documents`, {
      headers: {
        Cookie: `access_token=${accessCookie?.value}`,
        'X-Orchestra-Request': 'true',
      },
      multipart: {
        file: {
          name: 'sample_research.md',
          mimeType: 'text/markdown',
          buffer: fileBuffer,
        },
      },
    });

    expect(uploadResp.status()).toBe(201);
  });

  test('submits research query, renders answer with inline citation and clickable details card', async ({
    page,
  }) => {
    await page.goto('/chat');
    await expect(page.getByRole('heading', { name: 'Orchestra Autonomous Assistant' })).toBeVisible();

    // Type and send research query
    const input = page.getByRole('textbox');
    await input.fill('Explain the Transformer attention mechanism and self-attention.');
    await page.getByRole('button', { name: 'Send' }).click();

    // Wait for orchestrator response
    await expect(page.getByText(/Routing through LangGraph/i)).toBeVisible({ timeout: 5000 }).catch(() => {});
    await expect(page.locator('.prose, [data-testid="message-content"]').first()).toBeVisible({ timeout: 30000 });

    // Verify citation section renders
    await expect(page.getByText(/Verified Citations/i)).toBeVisible({ timeout: 15000 });

    // Click citation [1] badge
    const citationBtn = page.getByRole('button', { name: /\[1\]/ }).first();
    await expect(citationBtn).toBeVisible();
    await citationBtn.click();

    // Verify citation popover card details
    await expect(page.getByText(/sample_research\.md/i).first()).toBeVisible();
    await expect(page.getByText(/Page 1|p\.1/i).first()).toBeVisible();
    await expect(page.getByText(/Score:/i)).toBeVisible();
  });

  test('submits unrepresented query and verifies Insufficient Verified Evidence banner', async ({
    page,
  }) => {
    await page.goto('/chat');
    await expect(page.getByRole('heading', { name: 'Orchestra Autonomous Assistant' })).toBeVisible();

    const input = page.getByRole('textbox');
    await input.fill('What were the trading volumes of Japanese rice markets in 1730?');
    await page.getByRole('button', { name: 'Send' }).click();

    // Verify Insufficient Verified Evidence banner appears
    await expect(page.getByText('Insufficient Verified Evidence')).toBeVisible({ timeout: 30000 });
    await expect(
      page.getByText('Available indexed documents lacked sufficient verified evidence')
    ).toBeVisible();
  });
});

