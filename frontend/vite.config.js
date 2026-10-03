import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Cloudflare Tunnel can reach this dev server. Candidate email links are
    // NOT built here — set FRONTEND_URL in backend/.env to the public tunnel URL.
    allowedHosts: ['.trycloudflare.com', '.loca.lt', '.ngrok-free.app', '.ngrok.io'],
    proxy: {
      '/api': {
        target: 'http://localhost:8030',
        changeOrigin: true,
      },
      '/screening-files': {
        target: 'http://localhost:8030',
        changeOrigin: true,
      },
      '/extract': {
        target: 'http://localhost:8030',
        changeOrigin: true,
      },
      '/api/jd': {
        target: 'http://localhost:8030',
        changeOrigin: true,
      },
      '/proctoring': {
        target: 'http://localhost:8030',
        changeOrigin: true,
      },
      '/monitor': {
        target: 'http://localhost:8030',
        changeOrigin: true,
      },
      '/ready': {
        target: 'http://localhost:8030',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8030',
        ws: true,
      },
    },
  },
});
