import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  root: './frontend',
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  build: {
    outDir: '../dist'
  },
});
