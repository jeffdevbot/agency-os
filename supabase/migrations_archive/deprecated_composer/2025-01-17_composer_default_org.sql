-- Seed default Composer organization for internal use.
insert into public.composer_organizations (id, name, plan)
values ('6c5b1e9d-5656-4ad4-a2dd-96d64c97f4ef'::uuid, 'Ecomlabs', 'internal')
on conflict (id) do nothing;

-- Fallback org helper. Remove fallback once JWTs include org_id for multi-tenant SaaS.
create or replace function public.current_org_id()
returns uuid
language sql
stable
as $$
  select coalesce(
    nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'organization_id', '')::uuid,
    nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'org_id', '')::uuid,
    '6c5b1e9d-5656-4ad4-a2dd-96d64c97f4ef'::uuid
  );
$$;
