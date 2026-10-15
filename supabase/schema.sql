-- Starting schema for the planned PostgreSQL/Supabase production data adapter.
create extension if not exists pgcrypto;
create extension if not exists vector;
create table if not exists public.analyses (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  payload jsonb not null, created_at timestamptz not null default now()
);
create table if not exists public.roadmap_tasks (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  task_index integer not null, payload jsonb not null, updated_at timestamptz not null default now(), unique(user_id,task_index)
);
create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  filename text not null, created_at timestamptz not null default now()
);
create table if not exists public.document_chunks (
  id uuid primary key default gen_random_uuid(), document_id uuid not null references public.documents(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade, chunk_index integer not null, content text not null,
  embedding vector(1536), created_at timestamptz not null default now()
);
create index if not exists document_chunks_user_id_idx on public.document_chunks(user_id);
create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  payload jsonb not null, created_at timestamptz not null default now()
);
create table if not exists public.interviews (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  payload jsonb not null, created_at timestamptz not null default now()
);
alter table public.analyses enable row level security;
alter table public.roadmap_tasks enable row level security;
alter table public.documents enable row level security;
alter table public.document_chunks enable row level security;
alter table public.conversations enable row level security;
alter table public.interviews enable row level security;
create policy "own analyses" on public.analyses for all using (auth.uid()=user_id) with check (auth.uid()=user_id);
create policy "own roadmap" on public.roadmap_tasks for all using (auth.uid()=user_id) with check (auth.uid()=user_id);
create policy "own documents" on public.documents for all using (auth.uid()=user_id) with check (auth.uid()=user_id);
create policy "own chunks" on public.document_chunks for all using (auth.uid()=user_id) with check (auth.uid()=user_id);
create policy "own conversations" on public.conversations for all using (auth.uid()=user_id) with check (auth.uid()=user_id);
create policy "own interviews" on public.interviews for all using (auth.uid()=user_id) with check (auth.uid()=user_id);
