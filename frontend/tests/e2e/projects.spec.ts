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
});
