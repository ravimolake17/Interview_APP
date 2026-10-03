import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: '/proctoring/',
  plugins: [react()],
  build: {
    outDir: '../../backend/agent5_static/dist',
    emptyOutDir: true,
    sourcemap: true,
    target: 'es2022',
  },
  server: {
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8030',
      '/health': 'http://127.0.0.1:8030',
      '/ready': 'http://127.0.0.1:8030',
      '/ws': {
        target: 'ws://127.0.0.1:8030',
        ws: true,
      },
    },
  },
})
