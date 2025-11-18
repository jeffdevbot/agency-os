-- Update Composer default organization fallback to match production data.
insert into public.composer_organizations (id, name, plan)
values ('e9368435-9a8b-4b52-b610-7b3531b30412'::uuid, 'Default Composer Org', 'internal')
on conflict (id) do nothing;

create or replace function public.current_org_id()
returns uuid
language sql
stable
as $$
  select coalesce(
    nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'organization_id', '')::uuid,
    nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'org_id', '')::uuid,
    'e9368435-9a8b-4b52-b610-7b3531b30412'::uuid
  );
$$;
