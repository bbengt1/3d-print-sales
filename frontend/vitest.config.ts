import path from 'path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  define: {
    __APP_BUILD_ID__: JSON.stringify('vitest'),
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
});
