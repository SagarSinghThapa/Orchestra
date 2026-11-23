import { execSync } from 'child_process';
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
    path.resolve(__dirname, '../../../../.venv'),
    path.resolve(__dirname, '../../../../../.venv'),
    path.resolve(__dirname, '../../../.venv'),
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

export default async function globalSetup() {
  const repoRoot = path.resolve(__dirname, '../../../..');
  const bootstrapScript = path.resolve(__dirname, 'bootstrap_test_db.py');
  const pythonExec = getPythonExecutable();

  const dbPath = path.resolve(repoRoot, 'test-results/orchestra_e2e.db').replace(/\\/g, '/');

  console.log(`[Global Setup] Bootstrapping isolated E2E test database with ${pythonExec}...`);
  execSync(`"${pythonExec}" "${bootstrapScript}"`, {
    cwd: repoRoot,
    stdio: 'inherit',
    env: {
      ...process.env,
      ENVIRONMENT: 'test',
      DATABASE_URL: `sqlite:///${dbPath}`,
    },
  });
  console.log('[Global Setup] Database ready.');
}
