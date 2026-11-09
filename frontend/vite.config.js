import { defineConfig } from 'vite';

// The frontend never talks to anything but the local backend, via this proxy.
export default defineConfig({
  // MapLibre GL 6 ships its web worker as a separate module; pre-bundling would break its URL.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
