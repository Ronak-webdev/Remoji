import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist', // Standard vite output, FastAPI mounts static from frontend/dist
  },
  server: {
    port: 5173,
    strictPort: true,
    hmr: {
      protocol: 'ws',
      host: 'localhost',
      port: 5173,
    },
    proxy: {
      '/upload': 'http://localhost:7860',
      '/status': 'http://localhost:7860',
      '/export': 'http://localhost:7860'
    }
  },
})

