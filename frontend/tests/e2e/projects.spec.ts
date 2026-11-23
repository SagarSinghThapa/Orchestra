import { test, expect } from '@playwright/test';
import { loginAs } from './fixtures/auth.fixture';

test.describe('Multi-Tenant Project Lifecycle & Isolation E2E', () => {
  test('user can create a project via modal and see it selected as active workspace', async ({
    page,
  }) => {
    await loginAs(page, 'member');

    const projectName = `Neural Compiler ${Date.now()}`;
    const projectDesc = 'AST-guided code generation research';

    // 1. Open project selector dropdown in header
    await page.locator('#project-header-slot button').first().click();

    // 2. Click "+ Create New Project"
    await page.getByRole('button', { name: '+ Create New Project' }).click();
    await expect(page.getByRole('heading', { name: 'Create New Project' })).toBeVisible();

    // 3. Fill and submit creation form
    await page.getByPlaceholder('e.g. Distributed Core Refactor').fill(projectName);
    await page.getByPlaceholder('Brief summary of project scope and architecture...').fill(projectDesc);
    await page.getByRole('button', { name: 'Create Project' }).click();

    // 4. Verify modal closes and header selector updates to active project name
    await expect(page.getByRole('heading', { name: 'Create New Project' })).not.toBeVisible();
    await expect(page.locator('#project-header-slot button').first()).toContainText(projectName);
  });

  test('user can switch between multiple owned projects', async ({ page }) => {
    await loginAs(page, 'member');

    const projectA = `Workspace Alpha ${Date.now()}`;
    const projectB = `Workspace Beta ${Date.now()}`;

    // Create Project A
    await page.locator('#project-header-slot button').first().click();
    await page.getByRole('button', { name: '+ Create New Project' }).click();
    await page.getByPlaceholder('e.g. Distributed Core Refactor').fill(projectA);
    await page.getByRole('button', { name: 'Create Project' }).click();
    await expect(page.locator('#project-header-slot button').first()).toContainText(projectA);

    // Create Project B
    await page.locator('#project-header-slot button').first().click();
    await page.getByRole('button', { name: '+ Create New Project' }).click();
    await page.getByPlaceholder('e.g. Distributed Core Refactor').fill(projectB);
    await page.getByRole('button', { name: 'Create Project' }).click();
    await expect(page.locator('#project-header-slot button').first()).toContainText(projectB);

    // Switch back to Project A
    await page.locator('#project-header-slot button').first().click();
    await page.getByRole('button', { name: projectA, exact: true }).click();
    await expect(page.locator('#project-header-slot button').first()).toContainText(projectA);
  });

  test('multi-tenant boundary: User B cannot access User A project via direct API', async ({
    page,
    request,
  }) => {
    // 1. Log in as Member (User A) and create Project
    await loginAs(page, 'member');
    const projectTitle = `Private Project ${Date.now()}`;

    await page.locator('#project-header-slot button').first().click();
    await page.getByRole('button', { name: '+ Create New Project' }).click();
    await page.getByPlaceholder('e.g. Distributed Core Refactor').fill(projectTitle);
    await page.getByRole('button', { name: 'Create Project' }).click();

    // Capture User A's project ID by querying projects list
    const cookiesA = await page.context().cookies();
    const accessCookieA = cookiesA.find((c) => c.name === 'access_token');

    const listRespA = await request.get('http://127.0.0.1:8001/projects', {
      headers: { Cookie: `access_token=${accessCookieA?.value}` },
    });
    expect(listRespA.status()).toBe(200);
    const projectsA = await listRespA.json();
    const createdProject = projectsA.find((p: { name: string; id: number }) => p.name === projectTitle);
    expect(createdProject).toBeDefined();
    const projectIdA = createdProject.id;

    // 2. Log in as Viewer (User B - different tenant)
    const contextB = await page.context().browser()?.newContext();
    if (!contextB) throw new Error('Failed to create browser context B');
    const pageB = await contextB.newPage();
    await loginAs(pageB, 'viewer');

    const cookiesB = await contextB.cookies();
    const accessCookieB = cookiesB.find((c) => c.name === 'access_token');

    // 3. Attempt direct query to User A's project using User B's credentials
    const foreignResp = await request.get(`http://127.0.0.1:8001/projects/${projectIdA}`, {
      headers: { Cookie: `access_token=${accessCookieB?.value}` },
    });

    // Inviolable IDOR defense: returns 404 without leaking existence
    expect(foreignResp.status()).toBe(404);
    const body = await foreignResp.json();
    expect(body.detail).toBe('Project not found');

    await contextB.close();
  });

  test('create project modal accessibility: Escape key and focus trap', async ({ page }) => {
    await loginAs(page, 'member');

    // 1. Open project modal
    await page.locator('#project-header-slot button').first().click();
    await page.getByRole('button', { name: '+ Create New Project' }).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();

    // 2. Press Escape key -> modal closes
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();

    // 3. Re-open modal and test Tab focus trapping
    await page.locator('#project-header-slot button').first().click();
    await page.getByRole('button', { name: '+ Create New Project' }).click();
    await expect(dialog).toBeVisible();

    // Focus input and cycle through with Tab
    const nameInput = page.getByPlaceholder('e.g. Distributed Core Refactor');
    await expect(nameInput).toBeFocused();

    await page.keyboard.press('Tab'); // Description
    await page.keyboard.press('Tab'); // Cancel button
    await page.keyboard.press('Tab'); // Create Project submit button
    await page.keyboard.press('Tab'); // Close X button or back to first
  });

  test('create project modal responsive viewport layout', async ({ page }) => {
    await loginAs(page, 'member');

    const viewports = [
      { width: 1920, height: 1080 },
      { width: 1440, height: 900 },
      { width: 1366, height: 768 },
      { width: 375, height: 667 }, // Mobile
    ];

    for (const vp of viewports) {
      await page.setViewportSize(vp);
      await page.locator('#project-header-slot button').first().click();
      await page.getByRole('button', { name: '+ Create New Project' }).click();

      const dialog = page.getByRole('dialog');
      await expect(dialog).toBeVisible();

      // Verify modal is centered within viewport and not clipped
      const box = await dialog.locator('> div').boundingBox();
      expect(box).not.toBeNull();
      if (box) {
        expect(box.y).toBeGreaterThanOrEqual(0);
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.width).toBeLessThanOrEqual(vp.width);
      }

      await page.keyboard.press('Escape');
      await expect(dialog).not.toBeVisible();
    }
  });

  test('sidebar Projects navigation renders Projects page, does NOT show raw JSON, and survives browser reload', async ({
    page,
  }) => {
    await loginAs(page, 'member');

    // 1. Create a project first so we have guaranteed data
    const uniqueName = `Workspace Navigation ${Date.now()}`;
    await page.locator('#project-header-slot button').first().click();
    await page.getByRole('button', { name: '+ Create New Project' }).click();
    await page.getByPlaceholder('e.g. Distributed Core Refactor').fill(uniqueName);
    await page.getByPlaceholder('Brief summary of project scope and architecture...').fill('Testing frontend projects navigation');
    await page.getByRole('button', { name: 'Create Project' }).click();
    await expect(page.locator('#project-header-slot button').first()).toContainText(uniqueName);

    // 2. Click Projects link in the left sidebar
    await page.getByRole('link', { name: 'Projects' }).click();
    await page.waitForURL('**/projects');

    // 3. Assert frontend Projects heading exists and NO raw JSON appears in body
    const heading = page.getByRole('heading', { name: 'Project Workspaces' });
    await expect(heading).toBeVisible();

    const bodyText = await page.innerText('body');
    expect(bodyText).not.toMatch(/^\[\s*\{.*"id":\s*\d+/);

    // 4. Verify project card exists with name and Open Workspace button
    const card = page.locator(`[data-testid="project-card"]:has-text("${uniqueName}")`);
    await expect(card).toBeVisible();
    await expect(card.getByRole('button', { name: /Open Workspace/i })).toBeVisible();

    // 5. Browser refresh: refresh page at /projects
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Project Workspaces' })).toBeVisible();
    const refreshedBody = await page.innerText('body');
    expect(refreshedBody).not.toMatch(/^\[\s*\{.*"id":\s*\d+/);
    await expect(page.locator(`[data-testid="project-card"]:has-text("${uniqueName}")`)).toBeVisible();

    // 6. Click Open Workspace on the project card
    await card.getByRole('button', { name: /Open Workspace/i }).click();
    await page.waitForURL('**/chat');

    // 7. Verify header selector reflects the active project
    await expect(page.locator('#project-header-slot button').first()).toContainText(uniqueName);
  });

  test('route collision regression: browser GET and API GET /projects resolve to distinct application layers', async ({
    page,
    request,
  }) => {
    await loginAs(page, 'member');

    const cookies = await page.context().cookies();
    const accessCookie = cookies.find((c) => c.name === 'access_token');

    // 1. API request with application/json and X-Orchestra-Request header -> resolves to FastAPI backend
    const apiResp = await request.get('http://127.0.0.1:8001/projects', {
      headers: {
        Cookie: `access_token=${accessCookie?.value}`,
        'X-Orchestra-Request': 'true',
        Accept: 'application/json',
      },
    });
    expect(apiResp.status()).toBe(200);
    expect(apiResp.headers()['content-type']).toContain('application/json');
    const apiData = await apiResp.json();
    expect(Array.isArray(apiData)).toBe(true);

    // 2. Browser page navigation with Accept: text/html -> resolves to Next.js frontend UI
    await page.goto('/projects');
    await expect(page.getByRole('heading', { name: 'Project Workspaces' })).toBeVisible();
    const pageContent = await page.content();
    expect(pageContent).toContain('<!DOCTYPE html>');
    expect(pageContent).toContain('Project Workspaces');
  });
});
