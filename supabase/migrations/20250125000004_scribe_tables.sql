-- Scribe core tables and RLS
-- Create tables
create table if not exists public.scribe_projects (
  id uuid primary key default gen_random_uuid(),
  created_by uuid not null references public.profiles(id) on delete cascade,
  name text not null,
  marketplaces text[] not null default '{}',
  category text,
  sub_category text,
  brand_tone_default text,
  target_audience_default text,
  words_to_avoid_default text[] not null default '{}',
  supplied_content_default text,
  keywords_mode text not null default 'per_project',
  questions_mode text not null default 'per_project',
  topics_mode text not null default 'per_project',
  status text not null default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.scribe_skus (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.scribe_projects(id) on delete cascade,
  sku_code text not null,
  asin text,
  product_name text,
  brand_tone_override text,
  target_audience_override text,
  words_to_avoid_override text[] not null default '{}',
  supplied_content_override text,
  sort_order int,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.scribe_variant_attributes (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.scribe_projects(id) on delete cascade,
  name text not null,
  slug text not null,
  sort_order int,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.scribe_sku_variant_values (
  id uuid primary key default gen_random_uuid(),
  sku_id uuid not null references public.scribe_skus(id) on delete cascade,
  attribute_id uuid not null references public.scribe_variant_attributes(id) on delete cascade,
  value text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (sku_id, attribute_id)
);

create table if not exists public.scribe_keywords (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.scribe_projects(id) on delete cascade,
  sku_id uuid references public.scribe_skus(id) on delete cascade,
  keyword text not null,
  source text,
  priority int,
  created_at timestamptz not null default now()
);

create table if not exists public.scribe_customer_questions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.scribe_projects(id) on delete cascade,
  sku_id uuid references public.scribe_skus(id) on delete cascade,
  question text not null,
  source text,
  created_at timestamptz not null default now()
);

create table if not exists public.scribe_topics (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.scribe_projects(id) on delete cascade,
  sku_id uuid references public.scribe_skus(id) on delete cascade,
  topic_index smallint not null,
  title text not null,
  description text,
  generated_by text,
  approved boolean not null default false,
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.scribe_generated_content (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.scribe_projects(id) on delete cascade,
  sku_id uuid not null references public.scribe_skus(id) on delete cascade,
  version int not null default 1,
  title text,
  bullets jsonb,
  description text,
  backend_keywords text,
  model_used text,
  prompt_version text,
  approved boolean not null default false,
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.scribe_generation_jobs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.scribe_projects(id) on delete cascade,
  job_type text not null,
  status text not null default 'queued',
  payload jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

-- Indexes
create index if not exists idx_scribe_projects_created_by on public.scribe_projects(created_by);
create index if not exists idx_scribe_skus_project on public.scribe_skus(project_id);
create index if not exists idx_scribe_variant_attributes_project on public.scribe_variant_attributes(project_id);
create index if not exists idx_scribe_sku_variant_values_sku on public.scribe_sku_variant_values(sku_id);
create index if not exists idx_scribe_keywords_project on public.scribe_keywords(project_id);
create index if not exists idx_scribe_keywords_sku on public.scribe_keywords(sku_id);
create index if not exists idx_scribe_customer_questions_project on public.scribe_customer_questions(project_id);
create index if not exists idx_scribe_customer_questions_sku on public.scribe_customer_questions(sku_id);
create index if not exists idx_scribe_topics_project on public.scribe_topics(project_id);
create index if not exists idx_scribe_topics_sku on public.scribe_topics(sku_id);
create index if not exists idx_scribe_generated_content_project on public.scribe_generated_content(project_id);
create index if not exists idx_scribe_generated_content_sku on public.scribe_generated_content(sku_id);
create index if not exists idx_scribe_generation_jobs_project on public.scribe_generation_jobs(project_id);

-- Enable RLS
alter table public.scribe_projects enable row level security;
alter table public.scribe_skus enable row level security;
alter table public.scribe_variant_attributes enable row level security;
alter table public.scribe_sku_variant_values enable row level security;
alter table public.scribe_keywords enable row level security;
alter table public.scribe_customer_questions enable row level security;
alter table public.scribe_topics enable row level security;
alter table public.scribe_generated_content enable row level security;
alter table public.scribe_generation_jobs enable row level security;

-- Projects policies (owner-only)
drop policy if exists scribe_projects_select on public.scribe_projects;
create policy scribe_projects_select on public.scribe_projects
  for select using (created_by = auth.uid());

drop policy if exists scribe_projects_write on public.scribe_projects;
create policy scribe_projects_write on public.scribe_projects
  for all using (created_by = auth.uid())
  with check (created_by = auth.uid() and status != 'archived');

-- Helper: owner check and archived guard reused via subqueries
-- SKUs
drop policy if exists scribe_skus_select on public.scribe_skus;
create policy scribe_skus_select on public.scribe_skus
  for select using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  );

drop policy if exists scribe_skus_write on public.scribe_skus;
create policy scribe_skus_write on public.scribe_skus
  for all using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  )
  with check (
    project_id in (select id from public.scribe_projects where created_by = auth.uid() and status != 'archived')
  );

-- Variant attributes
drop policy if exists scribe_variant_attributes_select on public.scribe_variant_attributes;
create policy scribe_variant_attributes_select on public.scribe_variant_attributes
  for select using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  );

drop policy if exists scribe_variant_attributes_write on public.scribe_variant_attributes;
create policy scribe_variant_attributes_write on public.scribe_variant_attributes
  for all using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  )
  with check (
    project_id in (select id from public.scribe_projects where created_by = auth.uid() and status != 'archived')
  );

-- Variant values
drop policy if exists scribe_sku_variant_values_select on public.scribe_sku_variant_values;
create policy scribe_sku_variant_values_select on public.scribe_sku_variant_values
  for select using (
    exists (
      select 1 from public.scribe_skus s
      join public.scribe_projects p on p.id = s.project_id
      where s.id = scribe_sku_variant_values.sku_id
        and p.created_by = auth.uid()
    )
  );

drop policy if exists scribe_sku_variant_values_write on public.scribe_sku_variant_values;
create policy scribe_sku_variant_values_write on public.scribe_sku_variant_values
  for all using (
    exists (
      select 1 from public.scribe_skus s
      join public.scribe_projects p on p.id = s.project_id
      where s.id = scribe_sku_variant_values.sku_id
        and p.created_by = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.scribe_skus s
      join public.scribe_projects p on p.id = s.project_id
      where s.id = scribe_sku_variant_values.sku_id
        and p.created_by = auth.uid()
        and p.status != 'archived'
    )
  );

-- Keywords
drop policy if exists scribe_keywords_select on public.scribe_keywords;
create policy scribe_keywords_select on public.scribe_keywords
  for select using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  );

drop policy if exists scribe_keywords_write on public.scribe_keywords;
create policy scribe_keywords_write on public.scribe_keywords
  for all using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  )
  with check (
    project_id in (select id from public.scribe_projects where created_by = auth.uid() and status != 'archived')
  );

-- Customer questions
drop policy if exists scribe_questions_select on public.scribe_customer_questions;
create policy scribe_questions_select on public.scribe_customer_questions
  for select using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  );

drop policy if exists scribe_questions_write on public.scribe_customer_questions;
create policy scribe_questions_write on public.scribe_customer_questions
  for all using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  )
  with check (
    project_id in (select id from public.scribe_projects where created_by = auth.uid() and status != 'archived')
  );

-- Topics
drop policy if exists scribe_topics_select on public.scribe_topics;
create policy scribe_topics_select on public.scribe_topics
  for select using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  );

drop policy if exists scribe_topics_write on public.scribe_topics;
create policy scribe_topics_write on public.scribe_topics
  for all using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  )
  with check (
    project_id in (select id from public.scribe_projects where created_by = auth.uid() and status != 'archived')
  );

-- Generated content
drop policy if exists scribe_generated_content_select on public.scribe_generated_content;
create policy scribe_generated_content_select on public.scribe_generated_content
  for select using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  );

drop policy if exists scribe_generated_content_write on public.scribe_generated_content;
create policy scribe_generated_content_write on public.scribe_generated_content
  for all using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  )
  with check (
    project_id in (select id from public.scribe_projects where created_by = auth.uid() and status != 'archived')
  );

-- Generation jobs
drop policy if exists scribe_generation_jobs_select on public.scribe_generation_jobs;
create policy scribe_generation_jobs_select on public.scribe_generation_jobs
  for select using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  );

drop policy if exists scribe_generation_jobs_write on public.scribe_generation_jobs;
create policy scribe_generation_jobs_write on public.scribe_generation_jobs
  for all using (
    project_id in (select id from public.scribe_projects where created_by = auth.uid())
  )
  with check (
    project_id in (select id from public.scribe_projects where created_by = auth.uid() and status != 'archived')
  );
