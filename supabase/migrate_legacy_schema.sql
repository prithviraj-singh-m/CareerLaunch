-- Run this only if you previously ran the older schema.sql that created
-- roadmap_tasks, JSONB payload columns, and document_chunks.
begin;

do $$ begin
  if to_regclass('public.roadmap') is null and to_regclass('public.roadmap_tasks') is not null then
    alter table public.roadmap_tasks rename to roadmap;
  end if;
end $$;

-- Drop old auth/document foreign keys so IDs can be stored as text consistently
-- by the API, which independently verifies the Supabase access token.
do $$ declare item record; begin
  for item in
    select conrelid::regclass as tbl, conname
    from pg_constraint
    where contype='f'
      and conrelid in ('public.analyses'::regclass, 'public.roadmap'::regclass,
                       'public.documents'::regclass, 'public.conversations'::regclass,
                       'public.interviews'::regclass, to_regclass('public.document_chunks'))
  loop
    execute format('alter table %s drop constraint %I', item.tbl, item.conname);
  end loop;
end $$;

alter table public.analyses alter column id drop default;
alter table public.analyses alter column id type text using id::text;
alter table public.analyses alter column id set default gen_random_uuid()::text;
alter table public.analyses alter column user_id type text using user_id::text;
alter table public.analyses alter column payload type text using payload::text;
alter table public.roadmap alter column id drop default;
alter table public.roadmap alter column id type text using id::text;
alter table public.roadmap alter column id set default gen_random_uuid()::text;
alter table public.roadmap alter column user_id type text using user_id::text;
alter table public.roadmap alter column payload type text using payload::text;
alter table public.documents alter column id drop default;
alter table public.documents alter column id type text using id::text;
alter table public.documents alter column id set default gen_random_uuid()::text;
alter table public.documents alter column user_id type text using user_id::text;
alter table public.conversations alter column id drop default;
alter table public.conversations alter column id type text using id::text;
alter table public.conversations alter column id set default gen_random_uuid()::text;
alter table public.conversations alter column user_id type text using user_id::text;
alter table public.conversations alter column payload type text using payload::text;
alter table public.interviews alter column id drop default;
alter table public.interviews alter column id type text using id::text;
alter table public.interviews alter column id set default gen_random_uuid()::text;
alter table public.interviews alter column user_id type text using user_id::text;
alter table public.interviews alter column payload type text using payload::text;

alter table public.documents add column if not exists chunks text not null default '[]';
do $$ begin
  if to_regclass('public.document_chunks') is not null then
    update public.documents d set chunks = coalesce((
      select json_agg(dc.content order by dc.chunk_index)::text
      from public.document_chunks dc where dc.document_id::text=d.id
    ), '[]')
    where exists (select 1 from public.document_chunks dc where dc.document_id::text=d.id);
  end if;
end $$;

create unique index if not exists roadmap_user_task_unique on public.roadmap(user_id, task_index);

-- Recreate policies with text comparisons after the user_id type changes.
drop policy if exists "own analyses" on public.analyses;
drop policy if exists analyses_owner_access on public.analyses;
drop policy if exists "own roadmap" on public.roadmap;
drop policy if exists roadmap_owner_access on public.roadmap;
drop policy if exists "own documents" on public.documents;
drop policy if exists documents_owner_access on public.documents;
drop policy if exists "own conversations" on public.conversations;
drop policy if exists conversations_owner_access on public.conversations;
drop policy if exists "own interviews" on public.interviews;
drop policy if exists interviews_owner_access on public.interviews;

do $$ begin create policy analyses_owner_access on public.analyses for all using (auth.uid()::text=user_id) with check (auth.uid()::text=user_id); end $$;
do $$ begin create policy roadmap_owner_access on public.roadmap for all using (auth.uid()::text=user_id) with check (auth.uid()::text=user_id); end $$;
do $$ begin create policy documents_owner_access on public.documents for all using (auth.uid()::text=user_id) with check (auth.uid()::text=user_id); end $$;
do $$ begin create policy conversations_owner_access on public.conversations for all using (auth.uid()::text=user_id) with check (auth.uid()::text=user_id); end $$;
do $$ begin create policy interviews_owner_access on public.interviews for all using (auth.uid()::text=user_id) with check (auth.uid()::text=user_id); end $$;

commit;
