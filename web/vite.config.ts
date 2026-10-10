import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The production bundle is served by the loopback FastAPI process on port 8513.
// During development the Vite server proxies same-origin /api/* to it.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': `${import.meta.dirname}/src` },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    // The bridge allow-lists the 5173 Host/Origin for this development proxy.
    proxy: { '/api': { target: 'http://127.0.0.1:8513', changeOrigin: false } },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
  },
})
