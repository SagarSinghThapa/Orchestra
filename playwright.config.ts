import { defineConfig, devices } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const pythonExec =
  process.env.PYTHON_EXEC ||
  (fs.existsSync('D:/orchest/.venv/Scripts/python.exe')
    ? 'D:/orchest/.venv/Scripts/python.exe'
    : 'python');

const dbPath = path.resolve(__dirname, './test-results/orchestra_e2e.db').replace(/\\/g, '/');

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45000,
  expect: {
    timeout: 10000,
  },
  use: {
    baseURL: 'http://127.0.0.1:3001',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  outputDir: './test-results/playwright-artifacts',
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  globalSetup: path.resolve(__dirname, './tests/e2e/fixtures/global-setup.ts'),
  webServer: [
    {
      command: `"${pythonExec}" -m uvicorn app.main:app --host 127.0.0.1 --port 8001`,
      cwd: path.resolve(__dirname, './backend'),
      url: 'http://127.0.0.1:8001/health',
      reuseExistingServer: false,
      timeout: 90000,
      env: {
        ENVIRONMENT: 'test',
        DATABASE_URL: `sqlite:///${dbPath}`,
        JWT_SECRET: 'test-jwt-secret-key-for-e2e-testing-minimum-32-chars-long',
        RATE_LIMIT_BACKEND: 'memory',
        RATE_LIMIT_ENABLED: 'true',
        RATE_LIMIT_AUTH_LIMIT: '100',
        RATE_LIMIT_READ_LIMIT: '500',
        RATE_LIMIT_AI_LIMIT: '100',
        RATE_LIMIT_SEARCH_LIMIT: '100',
        RATE_LIMIT_UPLOAD_LIMIT: '100',
        RATE_LIMIT_EVAL_LIMIT: '100',
        METRICS_ENABLED: 'false',
        OTEL_ENABLED: 'false',
        LANGSMITH_TRACING: 'false',
        COOKIE_SECURE: 'false',
        CORS_ALLOWED_ORIGINS: '["http://127.0.0.1:3001","http://localhost:3001"]',
        WORKSPACE_BASE_DIR: path.resolve(__dirname, './test-results/workspaces').replace(/\\/g, '/'),
        LLM_PROVIDER: 'test',
        EMBEDDING_PROVIDER: 'test',
        QDRANT_URL: ':memory:',
      },
    },
    {
      command: 'npm run dev -- --port 3001',
      cwd: path.resolve(__dirname, './frontend'),
      url: 'http://127.0.0.1:3001',
      reuseExistingServer: false,
      timeout: 90000,
      env: {
        NEXT_PUBLIC_API_URL: 'http://127.0.0.1:8001',
        PORT: '3001',
      },
    },
  ],
});
