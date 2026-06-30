import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev'de backend FastAPI (127.0.0.1:8000) proxy'lenir; böylece tarayıcıda CORS
// gerekmez. API çağrıları göreli yollarla yapılır (örn. fetch('/datasets/upload')).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/datasets': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
