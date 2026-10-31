import { execSync } from 'child_process';
import path from 'path';
import fs from 'fs';

export default async function globalSetup() {
  const repoRoot = path.resolve(__dirname, '../../..');
  const bootstrapScript = path.resolve(__dirname, 'bootstrap_test_db.py');

  const pythonExec =
    process.env.PYTHON_EXEC ||
    (fs.existsSync('D:/orchest/.venv/Scripts/python.exe')
      ? 'D:/orchest/.venv/Scripts/python.exe'
      : 'python');

  console.log(`[Global Setup] Bootstrapping isolated E2E test database with ${pythonExec}...`);
  execSync(`"${pythonExec}" "${bootstrapScript}"`, {
    cwd: repoRoot,
    stdio: 'inherit',
    env: {
      ...process.env,
      ENVIRONMENT: 'test',
    },
  });
  console.log('[Global Setup] Database ready.');
}

