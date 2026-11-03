import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API runs on 8010 locally (8000 is often taken); docker-compose sets http://api:8000.
const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8010'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: { '/api': apiTarget, '/media': apiTarget },
    // Docker on Windows does not forward file events into the container.
    watch: process.env.VITE_USE_POLLING === 'true' ? { usePolling: true, interval: 300 } : undefined,
  },
})
