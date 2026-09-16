import { defineConfig } from 'vite';

export default defineConfig({
    server: {
        port: 5173,
        open: true,
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            }
        }
    },
    build: {
        outDir: 'dist',
        minify: 'esbuild'
    }
});
