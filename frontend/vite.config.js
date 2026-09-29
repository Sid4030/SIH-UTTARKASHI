import { defineConfig } from 'vite';

export default defineConfig({
    server: {
        port: 5173,
        open: true,
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                timeout: 3600000,
                proxyTimeout: 3600000,
            },
            '/hazard-score': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                timeout: 3600000,
                proxyTimeout: 3600000,
            },
            '/assess-habitations': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                timeout: 3600000,
                proxyTimeout: 3600000,
            },
            '/relocation-plan': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                timeout: 3600000,
                proxyTimeout: 3600000,
            }
        }
    },
    build: {
        outDir: 'dist',
        minify: 'esbuild'
    }
});
