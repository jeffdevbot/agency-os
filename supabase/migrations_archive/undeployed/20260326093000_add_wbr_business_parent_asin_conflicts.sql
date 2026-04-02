-- Archived on 2026-04-02.
-- This migration is not present in the live Supabase migration ledger for the
-- current production database, and the target table does not exist live.
-- Keep the historical SQL here, but do not treat it as part of the active
-- canonical migration sequence.

create table if not exists public.wbr_business_parent_asin_conflicts (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references public.wbr_profiles(id) on delete cascade,
  sync_run_id uuid not null references public.wbr_sync_runs(id) on delete cascade,
  report_date date not null,
  child_asin text not null,
  stored_parent_asin text,
  distinct_parent_asins jsonb not null default '[]'::jsonb,
  source_row_count integer not null default 0,
  first_detected_date date not null,
  last_detected_date date not null,
  overlap_day_count integer not null default 1,
  source_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint wbr_business_parent_asin_conflicts_unique_day
    unique (profile_id, report_date, child_asin)
);

comment on table public.wbr_business_parent_asin_conflicts is
  'QA records for Windsor business facts where the same child ASIN appears under conflicting parent ASINs on the same date.';

comment on column public.wbr_business_parent_asin_conflicts.stored_parent_asin is
  'The parent ASIN retained on the aggregated business fact row for backward compatibility.';

comment on column public.wbr_business_parent_asin_conflicts.distinct_parent_asins is
  'All distinct non-empty parent ASIN values observed in the raw Windsor rows for this child ASIN on this date.';

comment on column public.wbr_business_parent_asin_conflicts.first_detected_date is
  'Earliest report_date on which this profile + child_asin has been observed with a conflicting parent ASIN condition.';

comment on column public.wbr_business_parent_asin_conflicts.last_detected_date is
  'Latest report_date on which this profile + child_asin has been observed with a conflicting parent ASIN condition.';

comment on column public.wbr_business_parent_asin_conflicts.overlap_day_count is
  'Number of distinct report dates recorded so far for this profile + child_asin conflict sequence.';

create index if not exists idx_wbr_business_parent_conflicts_profile_child
  on public.wbr_business_parent_asin_conflicts (profile_id, child_asin, report_date desc);

drop trigger if exists update_wbr_business_parent_conflicts_updated_at
  on public.wbr_business_parent_asin_conflicts;
create trigger update_wbr_business_parent_conflicts_updated_at
  before update on public.wbr_business_parent_asin_conflicts
  for each row execute function public.set_current_timestamp_updated_at();

alter table public.wbr_business_parent_asin_conflicts enable row level security;

drop policy if exists "Admins can view WBR business parent conflicts"
  on public.wbr_business_parent_asin_conflicts;
create policy "Admins can view WBR business parent conflicts"
  on public.wbr_business_parent_asin_conflicts for select to authenticated
  using (public.is_admin(auth.uid()));

drop policy if exists "Admins can manage WBR business parent conflicts"
  on public.wbr_business_parent_asin_conflicts;
create policy "Admins can manage WBR business parent conflicts"
  on public.wbr_business_parent_asin_conflicts for all to authenticated
  using (public.is_admin(auth.uid()))
  with check (public.is_admin(auth.uid()));
