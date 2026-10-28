-- Tables used by backend/main.py. The API verifies each Supabase access token
-- and includes the verified user ID in every data query.
create table if not exists public.analyses (
  id text primary key,
  user_id text not null,
  payload text not null,
  created_at timestamptz not null default now()
);
create table if not exists public.roadmap (
  user_id text not null,
  task_index integer not null,
  payload text not null,
  primary key (user_id, task_index)
);
create table if not exists public.documents (
  id text primary key,
  user_id text not null,
  filename text not null,
  chunks text not null,
  created_at timestamptz not null default now()
);
create table if not exists public.conversations (
  id text primary key,
  user_id text not null,
  payload text not null,
  created_at timestamptz not null default now()
);
create table if not exists public.interviews (
  id text primary key,
  user_id text not null,
  payload text not null,
  created_at timestamptz not null default now()
);

alter table public.analyses enable row level security;
alter table public.roadmap enable row level security;
alter table public.documents enable row level security;
alter table public.conversations enable row level security;
alter table public.interviews enable row level security;

do $$ begin
  create policy analyses_owner_access on public.analyses for all
    using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
exception when duplicate_object then null; end $$;
do $$ begin
  create policy roadmap_owner_access on public.roadmap for all
    using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
exception when duplicate_object then null; end $$;
do $$ begin
  create policy documents_owner_access on public.documents for all
    using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
exception when duplicate_object then null; end $$;
do $$ begin
  create policy conversations_owner_access on public.conversations for all
    using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
exception when duplicate_object then null; end $$;
do $$ begin
  create policy interviews_owner_access on public.interviews for all
    using (auth.uid()::text = user_id) with check (auth.uid()::text = user_id);
exception when duplicate_object then null; end $$;
