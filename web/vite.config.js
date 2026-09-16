import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2022',
  },
  server: {
    port: 5173,
    open: true,
  },
  worker: {
    // Worker clasico (iife) en produccion: MediaPipe usa importScripts() nativo
    // para cargar su WASM. En dev Vite sirve el worker como modulo y se aplica
    // un shim (ver gesture.worker.js).
    format: 'iife',
  },
});
