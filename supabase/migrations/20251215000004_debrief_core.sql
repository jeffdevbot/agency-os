-- =====================================================================
-- MIGRATION: Debrief Core Tables (Meeting Notes + Extracted Tasks)
-- Purpose:
--   Store Google Meet/Gemini notes and extracted tasks for review.
-- Notes:
--   - ClickUp task creation is deferred; tasks remain in Debrief until Phase 4.
--   - RLS: authenticated users can read; only admins can write.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Enums
-- ---------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'meeting_note_status') then
    create type meeting_note_status as enum ('pending', 'processing', 'ready', 'processed', 'dismissed', 'failed');
  end if;

  if not exists (select 1 from pg_type where typname = 'extracted_task_status') then
    create type extracted_task_status as enum ('pending', 'approved', 'rejected', 'created', 'failed');
  end if;
end;
$$;

-- ---------------------------------------------------------------------
-- 2) debrief_meeting_notes
-- ---------------------------------------------------------------------
create table if not exists public.debrief_meeting_notes (
  id uuid primary key default gen_random_uuid(),
  google_doc_id text unique not null,
  google_doc_url text not null,
  title text not null,
  meeting_date timestamptz,
  owner_email text not null,
  raw_content text,
  summary_content text,
  suggested_client_id uuid references public.agency_clients(id),
  status meeting_note_status not null default 'pending',
  extraction_error text,
  dismissed_by uuid references public.profiles(id),
  dismissed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_meeting_notes_status on public.debrief_meeting_notes(status);
create index if not exists idx_meeting_notes_owner on public.debrief_meeting_notes(owner_email);
create index if not exists idx_meeting_notes_date on public.debrief_meeting_notes(meeting_date desc);

drop trigger if exists update_debrief_meeting_notes_updated_at on public.debrief_meeting_notes;
create trigger update_debrief_meeting_notes_updated_at
  before update on public.debrief_meeting_notes
  for each row execute function public.update_updated_at_column();

alter table public.debrief_meeting_notes enable row level security;

drop policy if exists "Authenticated users can view meeting notes" on public.debrief_meeting_notes;
create policy "Authenticated users can view meeting notes"
  on public.debrief_meeting_notes for select to authenticated using (true);

drop policy if exists "Only admins can manage meeting notes" on public.debrief_meeting_notes;
create policy "Only admins can manage meeting notes"
  on public.debrief_meeting_notes for all to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true))
  with check (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));

-- ---------------------------------------------------------------------
-- 3) debrief_extracted_tasks
-- ---------------------------------------------------------------------
create table if not exists public.debrief_extracted_tasks (
  id uuid primary key default gen_random_uuid(),
  meeting_note_id uuid not null references public.debrief_meeting_notes(id) on delete cascade,
  raw_text text not null,
  title text not null,
  description text,
  suggested_brand_id uuid references public.brands(id),
  suggested_assignee_id uuid references public.profiles(id),
  task_type text,
  status extracted_task_status not null default 'pending',
  clickup_task_id text,
  clickup_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_extracted_tasks_meeting on public.debrief_extracted_tasks(meeting_note_id);
create index if not exists idx_extracted_tasks_status on public.debrief_extracted_tasks(status);
create index if not exists idx_extracted_tasks_brand on public.debrief_extracted_tasks(suggested_brand_id);
create index if not exists idx_extracted_tasks_assignee on public.debrief_extracted_tasks(suggested_assignee_id);

drop trigger if exists update_debrief_extracted_tasks_updated_at on public.debrief_extracted_tasks;
create trigger update_debrief_extracted_tasks_updated_at
  before update on public.debrief_extracted_tasks
  for each row execute function public.update_updated_at_column();

alter table public.debrief_extracted_tasks enable row level security;

drop policy if exists "Authenticated users can view extracted tasks" on public.debrief_extracted_tasks;
create policy "Authenticated users can view extracted tasks"
  on public.debrief_extracted_tasks for select to authenticated using (true);

drop policy if exists "Only admins can manage extracted tasks" on public.debrief_extracted_tasks;
create policy "Only admins can manage extracted tasks"
  on public.debrief_extracted_tasks for all to authenticated
  using (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true))
  with check (exists (select 1 from public.profiles where id = auth.uid() and is_admin = true));

