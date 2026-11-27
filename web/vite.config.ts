import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// mode=mock: 内置假后端，打成单个 HTML，可直接双击打开验收
// 其它模式: 正常构建，静态资源输出到 dist/，由 Python 后端托管或独立部署
export default defineConfig(({ mode }) => ({
  base: './',
  plugins: [react(), ...(mode === 'mock' ? [viteSingleFile()] : [])],
  define: { __MOCK__: JSON.stringify(mode === 'mock') },
  build: {
    outDir: mode === 'mock' ? 'dist-mock' : 'dist',
    assetsInlineLimit: mode === 'mock' ? 100_000_000 : 4096,
    chunkSizeWarningLimit: 1500,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8787',
      '/login': 'http://127.0.0.1:8787',
      '/logout': 'http://127.0.0.1:8787',
      '/healthz': 'http://127.0.0.1:8787',
    },
  },
}))
