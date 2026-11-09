import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.fixture';
import path from 'path';
import fs from 'fs';

test.describe('Knowledge Ingestion & Document Pipeline E2E', () => {
  let projectId: number;
  const projectTitle = `Research Workspace ${Date.now()}`;

  test.beforeEach(async ({ page, request }) => {
    await loginAs(page, 'member');

    // Ensure we have an active project for document uploads
    const cookies = await page.context().cookies();
    const accessCookie = cookies.find((c) => c.name === 'access_token');

    // Create a fresh test project via API if needed
    const createResp = await request.post('http://127.0.0.1:8001/projects', {
      headers: {
        Cookie: `access_token=${accessCookie?.value}`,
        'X-Orchestra-Request': 'true',
      },
      data: {
        name: `${projectTitle}_${Date.now()}`,
        description: 'E2E Document pipeline isolation workspace',
      },
    });

    if (createResp.status() === 201) {
      const proj = await createResp.json();
      projectId = proj.id;
      // Set active project in local storage
      await page.evaluate((id) => {
        localStorage.setItem('orchestra_selected_project_id', id.toString());
      }, projectId);
    }
  });

  test('successfully uploads Markdown, PlainText, and PDF documents and verifies indexed status', async ({
    page,
  }) => {
    await page.goto('/documents');
    await expect(page.getByRole('heading', { name: 'Knowledge Ingestion' })).toBeVisible();

    const mdPath = path.resolve(__dirname, 'fixtures/documents/sample_research.md');
    const txtPath = path.resolve(__dirname, 'fixtures/documents/sample_research.txt');
    const pdfPath = path.resolve(__dirname, 'fixtures/documents/sample_research.pdf');

    // 1. Upload Markdown fixture
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: /Upload Document|Select Document to Ingest/i }).first().click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(mdPath);

    // Verify row appears with sample_research.md
    await expect(page.getByText('sample_research.md')).toBeVisible({ timeout: 15000 });
    // Verify status reaches 'Indexed'
    await expect(page.getByText('Indexed').first()).toBeVisible({ timeout: 20000 });

    // 2. Upload PlainText fixture
    const fileChooserPromise2 = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: 'Upload Document' }).click();
    const fileChooser2 = await fileChooserPromise2;
    await fileChooser2.setFiles(txtPath);
    await expect(page.getByText('sample_research.txt')).toBeVisible({ timeout: 15000 });

    // 3. Upload PDF fixture
    const fileChooserPromise3 = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: 'Upload Document' }).click();
    const fileChooser3 = await fileChooserPromise3;
    await fileChooser3.setFiles(pdfPath);
    await expect(page.getByText('sample_research.pdf')).toBeVisible({ timeout: 15000 });

    // 4. Verify table headers exist
    await expect(page.getByRole('columnheader', { name: 'Filename' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Size' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Status' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Chunks' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Uploaded' })).toBeVisible();
  });

  test('deletes document with confirmation and removes it from UI', async ({ page }) => {
    await page.goto('/documents');
    await expect(page.getByRole('heading', { name: 'Knowledge Ingestion' })).toBeVisible();

    const txtPath = path.resolve(__dirname, 'fixtures/documents/sample_research.txt');

    // Upload txt fixture
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: /Upload Document|Select Document to Ingest/i }).first().click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(txtPath);

    await expect(page.getByText('sample_research.txt')).toBeVisible({ timeout: 15000 });

    // Set dialog handler to accept deletion confirm
    page.once('dialog', (dialog) => dialog.accept());

    // Click delete on the row
    const deleteBtn = page.getByRole('button', { name: 'Delete' }).first();
    await deleteBtn.click();

    // Verify row disappears
    await expect(page.getByText('sample_research.txt')).not.toBeVisible({ timeout: 10000 });
  });

  test('rejects unsupported file extensions with error banner', async ({ page }) => {
    await page.goto('/documents');
    await expect(page.getByRole('heading', { name: 'Knowledge Ingestion' })).toBeVisible();

    const badFilePath = path.resolve(__dirname, '../../../test-results/exploit.exe');
    fs.writeFileSync(badFilePath, 'MZ_dummy_binary_payload');

    try {
      const fileChooserPromise = page.waitForEvent('filechooser');
      await page.getByRole('button', { name: /Upload Document|Select Document to Ingest/i }).first().click();
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles(badFilePath);

      // Verify client-side rejection banner
      await expect(page.getByText(/Unsupported file type '.exe'/i)).toBeVisible();
    } finally {
      if (fs.existsSync(badFilePath)) fs.unlinkSync(badFilePath);
    }
  });

  test('rejects oversized files exceeding 10MB limit with clear warning', async ({ page }) => {
    await page.goto('/documents');
    await expect(page.getByRole('heading', { name: 'Knowledge Ingestion' })).toBeVisible();

    const oversizedPath = path.resolve(__dirname, '../../../test-results/oversized.txt');
    // Create 10.5MB file
    const buffer = Buffer.alloc(10.5 * 1024 * 1024, 'a');
    fs.writeFileSync(oversizedPath, buffer);

    try {
      const fileChooserPromise = page.waitForEvent('filechooser');
      await page.getByRole('button', { name: /Upload Document|Select Document to Ingest/i }).first().click();
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles(oversizedPath);

      // Verify client-side size rejection banner
      await expect(page.getByText(/exceeds maximum limit of 10MB/i)).toBeVisible();
    } finally {
      if (fs.existsSync(oversizedPath)) fs.unlinkSync(oversizedPath);
    }
  });
});

