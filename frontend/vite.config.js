import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development, /api requests are proxied to the FastAPI backend.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: { '/api': process.env.VITE_API_URL || 'http://localhost:8000' },
  },
})
