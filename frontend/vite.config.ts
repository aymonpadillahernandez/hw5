import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dashboard calls the FastAPI backend directly at http://localhost:8000 (see src/api.ts); the backend allows
// this origin (http://localhost:5173) through CORS.
export default defineConfig({
  plugins: [react()],
  server: { host: 'localhost', port: 5173, strictPort: true },
})
