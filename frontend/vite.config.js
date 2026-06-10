import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;

          if (id.includes('react') || id.includes('react-dom')) {
            return 'react-vendor';
          }

          if (id.includes('i18next') || id.includes('react-i18next')) {
            return 'i18n-vendor';
          }

          if (id.includes('recharts') || id.includes('d3-')) {
            return 'chart-vendor';
          }

          if (id.includes('lucide-react')) {
            return 'icons-vendor';
          }

          return 'vendor';
        },
      },
    },
  },
  server: {
    host: '127.0.0.1',
    port: 3000,
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/burnin': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/stream': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8001',
        ws: true,
      },
    },
  },
});
