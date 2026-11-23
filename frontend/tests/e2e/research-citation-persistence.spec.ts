import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.fixture';
import path from 'path';
import fs from 'fs';

/**
 * Real Research Citation Persistence Across Reload & Navigation E2E.
 *
 * Validates:
 * 1. Document upload and ingestion into project workspace.
 * 2. Grounded research query processing and citation extraction.
 * 3. Structured payload persistence into the relational messages database.
 * 4. Provenance display via interactive citation [1] badge.
 * 5. Citation persistence across hard browser reload (page.reload()).
 * 6. Citation persistence across cross-route navigation (/projects -> /chat).
 *
 * Note: This deterministic test verifies citation lifecycle and UI/database persistence
 * using the hermetic test pipeline. Live NVIDIA NIM cloud inference verification is
 * governed separately and requires production API keys.
 */
test.describe('Real Research Citation Persistence Across Reload & Navigation', () => {
  let projectId: number;

  test.beforeEach(async ({ page, request }) => {
    await loginAs(page, 'member');

    const cookies = await page.context().cookies();
    const accessCookie = cookies.find((c) => c.name === 'access_token');

    // Create a dedicated project for research persistence tests
    const createResp = await request.post('http://127.0.0.1:8001/projects', {
      headers: {
        Cookie: `access_token=${accessCookie?.value}`,
        'X-Orchestra-Request': 'true',
      },
      data: {
        name: `Citation Persistence Space ${Date.now()}`,
        description: 'Testing citation persistence across browser reload and session restoration',
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

  test('citations survive database persistence, page reload, and cross-route navigation', async ({
    page,
  }) => {
    await page.goto('/chat');
    await expect(page.getByRole('heading', { name: 'Orchestra Autonomous Assistant' })).toBeVisible({ timeout: 25000 });

    // 1. Submit research query
    const input = page.getByRole('textbox');
    await input.fill('Explain the Transformer attention mechanism and self-attention.');
    await page.getByRole('button', { name: 'Send' }).click();

    // 2. Wait for response and verify citation section renders
    await expect(page.locator('.prose, [data-testid="message-content"]').first()).toBeVisible({ timeout: 35000 });
    await expect(page.getByText(/Verified Citations/i)).toBeVisible({ timeout: 20000 });

    // 3. Inspect citation [1] badge
    const citationBtn = page.getByRole('button', { name: /\[1\]/ }).first();
    await expect(citationBtn).toBeVisible({ timeout: 10000 });
    await citationBtn.click();

    // 4. Verify popover provenance card
    await expect(page.getByText(/sample_research\.md/i).first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/Page 1|p\.1/i).first()).toBeVisible({ timeout: 10000 });

    // 5. Hard browser reload
    await page.reload();
    await expect(page).toHaveURL(/.*chat/);

    // 6. Verify citations are restored from database history after reload
    await expect(page.getByText(/Verified Citations/i)).toBeVisible({ timeout: 20000 });
    const restoredCitationBtn = page.getByRole('button', { name: /\[1\]/ }).first();
    await expect(restoredCitationBtn).toBeVisible({ timeout: 10000 });

    // 7. Click badge again to verify full provenance restored
    await restoredCitationBtn.click();
    await expect(page.getByText(/sample_research\.md/i).first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/Page 1|p\.1/i).first()).toBeVisible({ timeout: 10000 });

    // 8. Cross-route navigation to /projects and back to /chat
    await page.goto('/projects');
    await expect(page.getByRole('heading', { name: 'Project Workspaces' })).toBeVisible({ timeout: 20000 });

    await page.goto('/chat');
    await expect(page.getByText(/Verified Citations/i)).toBeVisible({ timeout: 20000 });
    await expect(page.getByRole('button', { name: /\[1\]/ }).first()).toBeVisible({ timeout: 10000 });
  });
});
