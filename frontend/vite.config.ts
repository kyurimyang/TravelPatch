import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // The repo-root .env holds every key (backend ones too). Only the two values below are public
  // by design (the anon key is guarded by RLS) and are copied into the browser bundle by name.
  // Never add SUPABASE_SERVICE_ROLE_KEY or any API key here.
  const env = loadEnv(mode, '..', '')
  return {
    plugins: [react()],
    define: {
      'import.meta.env.VITE_SUPABASE_URL': JSON.stringify(env.SUPABASE_URL ?? ''),
      'import.meta.env.VITE_SUPABASE_ANON_KEY': JSON.stringify(env.SUPABASE_ANON_KEY ?? ''),
      'import.meta.env.VITE_ADMIN_EMAILS': JSON.stringify(env.ADMIN_EMAILS ?? ''),
    },
    server: {
      // Dev only: the browser calls /api/..., Vite forwards it to the FastAPI server
      // (uvicorn app.main:app) without the /api prefix. Deployed, frontend/vercel.json does the same.
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  }
})
