-- =====================================================================
-- MIGRATION: Command Center Assignment Slot Uniqueness
-- Purpose:
--   Enforce the org-chart model: one assignee per role slot per scope.
--   - client scope (brand_id IS NULL): unique (client_id, role_id)
--   - brand scope  (brand_id IS NOT NULL): unique (client_id, brand_id, role_id)
-- Notes:
--   This matches Command Center PRD drag/drop "replace existing assignment" behavior.
-- =====================================================================

do $$
begin
  if exists (
    select 1
    from public.client_assignments
    where brand_id is null
    group by client_id, role_id
    having count(*) > 1
  ) then
    raise exception 'Duplicate client-scope role assignments exist; cleanup required before adding uniqueness (client_id, role_id).';
  end if;

  if exists (
    select 1
    from public.client_assignments
    where brand_id is not null
    group by client_id, brand_id, role_id
    having count(*) > 1
  ) then
    raise exception 'Duplicate brand-scope role assignments exist; cleanup required before adding uniqueness (client_id, brand_id, role_id).';
  end if;
end;
$$;

drop index if exists idx_assignments_unique_brand_scope;
drop index if exists idx_assignments_unique_client_scope;

create unique index if not exists idx_assignments_unique_brand_role_scope
  on public.client_assignments (client_id, brand_id, role_id)
  where brand_id is not null;

create unique index if not exists idx_assignments_unique_client_role_scope
  on public.client_assignments (client_id, role_id)
  where brand_id is null;

