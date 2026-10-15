# AI Career Launchpad

A career preparation MVP built with Next.js and FastAPI. The AI features call the configured Nexus OpenAI-compatible API from the backend; credentials never enter browser code.

## Features

- Responsive career dashboard and landing workspace with honest empty states.
- PDF/TXT resume and job-description assessment, validated against a Pydantic schema.
- Career mentor with recent prompt context.
- Resume-driven learning plan with completion tracking.
- Role and mode specific mock interview questions and structured answer feedback.
- PDF/TXT study document ingestion, overlapping chunks, per-user keyword retrieval, source excerpts, and grounded AI answers. This MVP does not generate embeddings; it explicitly reports keyword retrieval.
- Server endpoints for dashboard data and roadmap updates.

## Requirements and local setup

Node.js 18+ and Python 3.10+.

1. In the repository root, run `npm install`.
2. In `backend`, create `.env` from `.env.example`. Set `NEXUS_API_KEY` and `NEXUS_MODEL` to values enabled for your Nexus account. The model name is not assumed or checked against an account at startup.
3. Install and start the API:

   ```powershell
   cd backend
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```

4. In another terminal, from the repository root run `npm run dev` and open http://localhost:3000.

AI requests return a clear 503 if `NEXUS_API_KEY` or `NEXUS_MODEL` is missing. Configure these before using analysis, mentor, interview, or grounded answer generation. `NEXUS_BASE_URL` defaults to `https://nexusapi.navigatelabs.ai`.

## Environment variables

`backend/.env` uses `NEXUS_API_KEY`, `NEXUS_BASE_URL`, `NEXUS_MODEL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `DATABASE_URL`, `FRONTEND_ORIGIN`, `MAX_UPLOAD_MB`, and `APP_REQUIRE_AUTH`. Authentication is required by default. Only set `APP_REQUIRE_AUTH=false` for isolated local development without sign-in. The data adapter is SQLite. Do not put provider keys in `NEXT_PUBLIC_*` variables.

The frontend uses `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`), and optional `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` for its email/password sign-in and sign-up panel. Supabase anon keys are intended for browser use; keep the service-role key out of the frontend.

## Persistence and authentication limits

The implemented MVP persists to SQLite, with records partitioned by a server-verified Supabase user ID when backend `SUPABASE_URL` and `SUPABASE_ANON_KEY` are configured. The browser blocks all workspace features until email/password sign-in succeeds. Supabase Auth must have email/password enabled. The API also rejects feature requests without a valid bearer token. SQLite files on serverless Vercel are ephemeral; use a persistent backend host and managed PostgreSQL for durable production data (the supplied schema is a starting point).

## Checks

Run `npm run build` for the frontend production build. The API can be checked with `python -m compileall backend` and `python -m unittest discover -s backend/tests -v`. API docs appear at http://localhost:8000/docs while running.

Automated tests use mocked provider calls; no real Nexus account is available in this repository, so real provider compatibility remains unverified.

## Supabase setup

1. Create a Supabase project.
2. In SQL Editor, run `supabase/schema.sql`. It creates user-owned tables and enables row-level security. Keep user and file data private.
3. Enable email/password in Supabase Auth. For local signup confirmations, set **Site URL** to your local frontend (usually `http://localhost:3000`) and add both `http://localhost:3000` and `http://localhost:3001` to allowed redirect URLs. The sign-up form redirects to the actual frontend origin. Set matching backend `SUPABASE_URL`/`SUPABASE_ANON_KEY` and frontend `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY`; the sign-in panel sends bearer tokens to the API, which verifies them with Supabase Auth.
4. Before production, replace the SQLite data adapter with PostgreSQL/Supabase storage operations. The MVP is deliberately fail-closed when `APP_ENV=production` and auth is not configured.

## Deployment

### Vercel frontend

1. Import the repository in Vercel, set the project root to the repository root, and deploy with the default Next.js build (`npm run build`).
2. Set `NEXT_PUBLIC_API_URL` to the deployed FastAPI origin, then redeploy.
3. Configure the backend CORS `FRONTEND_ORIGIN` to the exact Vercel site origin.

### FastAPI backend

The API uses multipart uploads, synchronous SQLite, temporary PDF extraction, and a 45-second AI call timeout. It is not configured for Vercel serverless persistence/runtime. Deploy on a small persistent Python host (for example Render or Railway) with `uvicorn main:app --host 0.0.0.0 --port $PORT`, and set secrets there. For multi-user production, complete the documented auth/Postgres migration first. No deployment has been performed from this repository.

## Current limitations

- Supabase Auth credentials are required to use the app by default. `APP_REQUIRE_AUTH=false` is an explicit local-only test bypass.
- SQLite local persistence only; no durable serverless or multi-instance data store.
- RAG retrieval uses per-user keyword matching, not vector embeddings.
- Nexus model access and model-specific structured JSON support require validation with your account.
- The optional MCP integration and speech-to-text are not included.
