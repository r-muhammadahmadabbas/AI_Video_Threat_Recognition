import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/cameras': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/incidents': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/zones': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/rules': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/evidence': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/users': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/audit': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})