import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.fixture';
import path from 'path';
import fs from 'fs';

test.describe('Developer Intelligence Preview-Apply & Hash Guarding E2E', () => {
  let projectId: number;
  let workspaceDir: string;

  test.beforeEach(async ({ page, request }) => {
    await loginAs(page, 'member');

    const cookies = await page.context().cookies();
    const accessCookie = cookies.find((c) => c.name === 'access_token');

    // Create a fresh test project
    const createResp = await request.post('http://127.0.0.1:8001/projects', {
      headers: {
        Cookie: `access_token=${accessCookie?.value}`,
        'X-Orchestra-Request': 'true',
      },
      data: {
        name: `Dev Project ${Date.now()}`,
        description: 'Testing two-stage preview apply workflow',
      },
    });

    expect(createResp.status()).toBe(201);
    const proj = await createResp.json();
    projectId = proj.id;

    await page.evaluate((id) => {
      localStorage.setItem('orchestra_selected_project_id', id.toString());
    }, projectId);

    // Setup isolated project workspace with sample repo fixtures
    workspaceDir = path.resolve(__dirname, `../../test-results/workspaces/project_${projectId}`);
    fs.mkdirSync(workspaceDir, { recursive: true });

    const fixtureDir = path.resolve(__dirname, 'fixtures/workspaces/sample_repo');
    fs.copyFileSync(path.join(fixtureDir, 'config.json'), path.join(workspaceDir, 'config.json'));
    fs.copyFileSync(path.join(fixtureDir, 'fibonacci.py'), path.join(workspaceDir, 'fibonacci.py'));
  });

  test('generates diff preview for config.json with non-python AST skip badge and unchanged disk file', async ({
    page,
  }) => {
    await page.goto('/developer/coding');
    await expect(page.getByRole('heading', { name: 'Autonomous Coding Assistant' })).toBeVisible();

    const originalDiskContent = fs.readFileSync(path.join(workspaceDir, 'config.json'), 'utf-8');

    // Fill task prompt and target files
    await page.getByPlaceholder('Describe the feature, bugfix, or refactor to implement across the workspace...').fill(
      'Update workspace configuration settings and debug mode.'
    );
    await page.getByPlaceholder('e.g. app/main.py, tests/test_main.py').fill('config.json');

    // Click Generate Proposal (Preview)
    await page.getByRole('button', { name: 'Generate Proposal (Preview)' }).click();

    // Verify UnifiedDiffViewer renders diff
    await expect(page.getByText('Synthesized Proposal Review')).toBeVisible({ timeout: 30000 });
    await expect(page.getByText(/AST: Skipped \(non-python\)/i)).toBeVisible();

    // Verify disk content was not changed during preview
    const currentDiskContent = fs.readFileSync(path.join(workspaceDir, 'config.json'), 'utf-8');
    expect(currentDiskContent).toBe(originalDiskContent);
  });

  test('detects syntax error on python target and disables Apply to Workspace button', async ({
    page,
  }) => {
    await page.goto('/developer/coding');
    await expect(page.getByRole('heading', { name: 'Autonomous Coding Assistant' })).toBeVisible();

    // Request proposal on python target where canned mock produces invalid python syntax
    await page.getByPlaceholder('Describe the feature, bugfix, or refactor to implement across the workspace...').fill(
      'Refactor fibonacci computation to use matrix exponentiation.'
    );
    await page.getByPlaceholder('e.g. app/main.py, tests/test_main.py').fill('fibonacci.py');

    await page.getByRole('button', { name: 'Generate Proposal (Preview)' }).click();

    // Verify proposal review appears
    await expect(page.getByText('Synthesized Proposal Review')).toBeVisible({ timeout: 30000 });

    // Verify AST failure warning banner
    await expect(
      page.getByText('Cannot apply changes: one or more files failed AST validation.')
    ).toBeVisible();

    // Verify Apply to Workspace button is disabled
    const applyBtn = page.getByRole('button', { name: 'Apply to Workspace' });
    await expect(applyBtn).toBeDisabled();
  });

  test('successfully applies modifications to disk and modifies workspace file', async ({
    page,
  }) => {
    await page.goto('/developer/coding');
    await expect(page.getByRole('heading', { name: 'Autonomous Coding Assistant' })).toBeVisible();

    const initialContent = fs.readFileSync(path.join(workspaceDir, 'config.json'), 'utf-8');

    await page.getByPlaceholder('Describe the feature, bugfix, or refactor to implement across the workspace...').fill(
      'Update project name in config.json.'
    );
    await page.getByPlaceholder('e.g. app/main.py, tests/test_main.py').fill('config.json');

    await page.getByRole('button', { name: 'Generate Proposal (Preview)' }).click();
    await expect(page.getByText('Synthesized Proposal Review')).toBeVisible({ timeout: 30000 });

    // Click Apply to Workspace
    const applyBtn = page.getByRole('button', { name: 'Apply to Workspace' });
    await expect(applyBtn).toBeEnabled();
    await applyBtn.click();

    // Verify confirmation modal
    await expect(page.getByRole('heading', { name: /Confirm Code Application/i })).toBeVisible();
    await page.getByRole('button', { name: 'Yes, Write to Disk' }).click();

    // Verify applied banner
    await expect(page.getByText('Changes Applied Successfully to Disk')).toBeVisible({ timeout: 15000 });

    // Verify disk was modified
    const updatedContent = fs.readFileSync(path.join(workspaceDir, 'config.json'), 'utf-8');
    expect(updatedContent).not.toBe(initialContent);
  });

  test('rejects stale patch with HTTP 409 conflict when file is modified concurrently on disk', async ({
    page,
  }) => {
    await page.goto('/developer/coding');
    await expect(page.getByRole('heading', { name: 'Autonomous Coding Assistant' })).toBeVisible();

    await page.getByPlaceholder('Describe the feature, bugfix, or refactor to implement across the workspace...').fill(
      'Modify config.json settings.'
    );
    await page.getByPlaceholder('e.g. app/main.py, tests/test_main.py').fill('config.json');

    // 1. Generate preview
    await page.getByRole('button', { name: 'Generate Proposal (Preview)' }).click();
    await expect(page.getByText('Synthesized Proposal Review')).toBeVisible({ timeout: 30000 });

    // 2. Concurrent out-of-band disk modification changing base hash
    fs.writeFileSync(
      path.join(workspaceDir, 'config.json'),
      JSON.stringify({ mutated_by: 'concurrent_actor' }, null, 2)
    );

    // 3. Attempt to apply proposal
    const applyBtn = page.getByRole('button', { name: 'Apply to Workspace' });
    await expect(applyBtn).toBeEnabled();
    await applyBtn.click();

    await expect(page.getByRole('heading', { name: /Confirm Code Application/i })).toBeVisible();
    await page.getByRole('button', { name: 'Yes, Write to Disk' }).click();

    // Verify conflict error message is displayed
    await expect(
      page.getByText(/Workspace files were modified concurrently|Base hashes no longer match/i)
    ).toBeVisible({ timeout: 15000 });
  });
});

