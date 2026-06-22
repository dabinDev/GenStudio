import { fileURLToPath, URL } from 'node:url';

import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

const apiTarget = process.env.VITE_ADMIN_API_TARGET || 'http://127.0.0.1:8000';

export default defineConfig({
  base: '/admin/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5174,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 1024,
    rollupOptions: {
      output: {
        manualChunks(rawId) {
          const id = rawId.replace(/\\/g, '/');
          if (!id.includes('node_modules')) {
            return undefined;
          }
          if (id.includes('/echarts/') || id.includes('/zrender/')) {
            return 'admin-charts';
          }
          if (id.includes('/element-plus/') || id.includes('/@element-plus/')) {
            return 'admin-ui';
          }
          if (id.includes('/vue') || id.includes('/pinia/') || id.includes('/vue-router/')) {
            return 'admin-vue';
          }
          if (id.includes('/gsap/')) {
            return 'admin-motion';
          }
          return 'admin-vendor';
        },
      },
    },
  },
});
