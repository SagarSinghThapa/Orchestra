import { defineConfig, devices } from '@playwright/test';
import path from 'path';
import fs from 'fs';

function getPythonExecutable(): string {
  if (process.env.PYTHON_EXEC) {
    return process.env.PYTHON_EXEC;
  }
  if (process.env.VIRTUAL_ENV) {
    const venvPython =
      process.platform === 'win32'
        ? path.join(process.env.VIRTUAL_ENV, 'Scripts', 'python.exe')
        : path.join(process.env.VIRTUAL_ENV, 'bin', 'python');
    if (fs.existsSync(venvPython)) return venvPython;
  }
  const candidateRelativeDirs = [
    path.resolve(__dirname, '../.venv'),
    path.resolve(__dirname, '../../.venv'),
    path.resolve(__dirname, './.venv'),
  ];
  for (const dir of candidateRelativeDirs) {
    const candidate =
      process.platform === 'win32'
        ? path.join(dir, 'Scripts', 'python.exe')
        : path.join(dir, 'bin', 'python');
    if (fs.existsSync(candidate)) return candidate;
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

const pythonExec = getPythonExecutable();
const repoRoot = path.resolve(__dirname, '..');
const dbPath = path.resolve(repoRoot, 'test-results/orchestra_e2e.db').replace(/\\/g, '/');

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
  outputDir: path.resolve(repoRoot, 'test-results/playwright-artifacts'),
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
      cwd: path.resolve(repoRoot, 'backend'),
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
        WORKSPACE_BASE_DIR: path.resolve(repoRoot, 'test-results/workspaces').replace(/\\/g, '/'),
        LLM_PROVIDER: 'test',
        EMBEDDING_PROVIDER: 'test',
        QDRANT_URL: ':memory:',
      },
    },
    {
      command: 'npm run dev:e2e',
      cwd: __dirname,
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
