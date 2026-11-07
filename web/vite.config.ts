/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv, searchForWorkspaceRoot } from 'vite'

// The avatar parts catalog is shared with the API (repo-root shared/); Docker mounts it at /shared.
const sharedDir = fileURLToPath(new URL('../shared', import.meta.url))

export default defineConfig(({ mode }) => {
  // API_PROXY_TARGET comes from the shell or the repo-root .env (docker-compose sets http://api:8000).
  const env = loadEnv(mode, fileURLToPath(new URL('..', import.meta.url)), '')
  const apiTarget = env.API_PROXY_TARGET || 'http://localhost:8010'

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
        '@shared': sharedDir,
      },
    },
    server: {
      port: 5173,
      proxy: { '/api': apiTarget, '/media': apiTarget },
      // Docker on Windows does not forward file events into the container.
      watch: env.VITE_USE_POLLING === 'true' ? { usePolling: true, interval: 300 } : undefined,
      fs: { allow: [searchForWorkspaceRoot(process.cwd()), sharedDir] },
    },
    test: {
      include: ['src/**/*.test.ts'],
      environment: 'node',
    },
  }
})
