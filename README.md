# AI Career Launchpad

Next.js frontend with a FastAPI backend for resume analysis, career mentoring, interview practice, and study document Q&A. AI credentials and resume contents stay on the backend.

## Local development

Requirements: Node.js 18+ and Python 3.10+.

1. Install frontend packages from the repository root with `npm install`.
2. In `backend`, copy `.env.example` to `.env`; set the Nexus credentials and Supabase project URL/anon key.
3. Install/start the backend:

   ```powershell
   cd backend
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

4. Set root `.env.local` from `.env.example`, then run `npm run dev` from the repository root.

SQLite is the local default. The backend also supports PostgreSQL using `DATABASE_URL`; install dependencies from `backend/requirements.txt` after updating it.

## Supabase database

Supabase provides both email/password authentication and managed PostgreSQL. Run `supabase/schema.sql` in the Supabase SQL Editor to create the app tables and row-level security policies. If you previously ran the older schema that created `roadmap_tasks` and `document_chunks`, run `supabase/migrate_legacy_schema.sql` instead; it keeps existing records while adapting the tables to the backend. The backend creates the current tables at startup too.

Use the Supabase **Postgres connection string** for backend `DATABASE_URL` (Project Settings → Database → Connect). For the Vercel serverless backend, choose the **Transaction pooler**. Replace the password placeholder and URL-encode special characters in the password. Never expose this URL or database password in frontend variables.

The backend verifies each bearer token with Supabase Auth and scopes every database query by the verified Supabase user ID. Keep `APP_REQUIRE_AUTH=true`. `SUPABASE_URL` and `SUPABASE_ANON_KEY` are used by the backend to validate sessions. The frontend uses `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` for sign-in; the anon key is intended for browser use. Never use a service-role key in the frontend.

## Deploy

### Vercel backend

Deploy the backend as a **separate Vercel project** from this same Git repository:

1. In Vercel, choose **Add New → Project**, import the repository already used by the frontend, and set **Root Directory** to `backend`.
2. Vercel detects the FastAPI app through `backend/index.py`. Keep the Python requirements in `backend/requirements.txt`; no Uvicorn start command is needed for Vercel Functions.
3. Add backend-only environment variables in this Vercel project: `NEXUS_API_KEY`, `NEXUS_BASE_URL`, `NEXUS_MODEL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `DATABASE_URL`, `FRONTEND_ORIGIN`, `APP_REQUIRE_AUTH=true`, and `MAX_UPLOAD_MB=4`.
4. Set `FRONTEND_ORIGIN` to the exact deployed frontend origin, for example `https://your-project.vercel.app` (no trailing slash). Add custom frontend domains as comma-separated origins. `DATABASE_URL` must use Supabase's Transaction pooler; never use the local SQLite URL in production.
5. Deploy. Check the backend's `/health` endpoint; it should report `database: postgresql`, AI configured, and Supabase auth mode.

### Vercel frontend

In the existing frontend Vercel project, set `NEXT_PUBLIC_API_URL` to the new backend project's URL (no trailing slash), plus `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. Redeploy the frontend. In Supabase Authentication URL settings, set Site URL to the frontend origin and add it (and any custom frontend domain) to allowed redirect URLs.

The API uses Vercel's Python runtime as a serverless FastAPI function. Keep `MAX_UPLOAD_MB` at 4 or lower because Vercel Functions have a 4.5 MB request body limit. For local development, SQLite remains the default and the upload limit can be overridden in `backend/.env`.

## Notes

- Uploaded PDF/TXT files are read in memory; extracted document chunks are stored in PostgreSQL.
- The API currently uses per-user keyword retrieval for study documents, not vector embeddings.
- Provider access/model support depends on the Nexus account configuration.
