## Ecomlabs Tools Frontend

This package hosts the Next.js application that powers the Ecomlabs Tools dashboard and login. It uses Supabase + Google OAuth for authentication and is deployed to Render as the `frontend-web` service.

### Local development

1. Copy `.env.example` to `.env.local` and fill in the Supabase + backend values:
   ```bash
   cp .env.example .env.local
   ```
2. Install dependencies and start the dev server:
   ```bash
   npm install
   npm run dev
   ```
3. Navigate to [http://localhost:3000](http://localhost:3000). Authentication will only work if the Supabase project allows `http://localhost:3000` as an OAuth redirect URL (Auth → Settings → URLs).

### Environment variables

| Variable | Description |
| --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL (https://*.supabase.co). |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public anon key used by the browser client. |
| `NEXT_PUBLIC_BACKEND_URL` | FastAPI backend base URL (local: http://localhost:8000; prod: Render `backend-core`). |

### Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Starts Next.js locally on port 3000. |
| `npm run build` | Production build (used by Render). |
| `npm start` | Serves the production build. |
