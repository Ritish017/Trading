import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig } from 'vite';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      port: 5174,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8001',
          changeOrigin: true,
          configure: (proxy, _options) => {
            proxy.on('error', (_err, _req, _res) => {
              // swallow proxy errors cleanly during server reload
            });
          },
        },
        '/ws': {
          target: 'ws://127.0.0.1:8001',
          ws: true,
          configure: (proxy, _options) => {
            proxy.on('error', (_err, _req, _res) => {
              // swallow ws errors cleanly
            });
          },
        },
      },
      hmr: process.env.DISABLE_HMR !== 'true',
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
  };
});
