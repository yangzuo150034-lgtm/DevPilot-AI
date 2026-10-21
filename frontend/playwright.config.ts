import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 45000,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure' },
  webServer: [
    {
      command:
        process.platform === 'win32'
          ? '..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8000'
          : '../.venv/bin/python -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/v1/health',
      reuseExistingServer: !process.env.CI,
      env: {
        DEVPILOT_DATA_DIR: '../.data/e2e',
        DEVPILOT_API_TOKEN: '',
        DEVPILOT_SANDBOX_ENABLED: 'false',
        DEVPILOT_DATABASE_URL: '',
        DEVPILOT_CHECKPOINT_URL: '',
        DEVPILOT_QDRANT_URL: '',
        DEVPILOT_EMBEDDING_PROVIDER: 'hash',
        DEVPILOT_EXECUTION_BACKEND: 'thread',
        DEVPILOT_OPENAI_API_KEY: '',
      },
    },
    { command: 'npm run dev', url: 'http://127.0.0.1:5173', reuseExistingServer: !process.env.CI },
  ],
})
