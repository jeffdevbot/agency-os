-- AgencyClaw debug validation queries
-- Run in Supabase SQL editor when testing /api/slack/debug/chat.

-- ------------------------------------------------------------------
-- 0) Table presence and row counts
-- ------------------------------------------------------------------
select 'agency_clients' as table_name, count(*) as rows from public.agency_clients
union all
select 'brands', count(*) from public.brands
union all
select 'playbook_sops', count(*) from public.playbook_sops
union all
select 'playbook_slack_sessions', count(*) from public.playbook_slack_sessions
union all
select 'agent_runs', count(*) from public.agent_runs
union all
select 'agent_messages', count(*) from public.agent_messages
union all
select 'agent_skill_events', count(*) from public.agent_skill_events
order by table_name;

-- ------------------------------------------------------------------
-- 1) Client + brand ClickUp mapping sanity checks
-- Edit the filter terms below as needed.
-- ------------------------------------------------------------------
with params as (
  select
    'test'::text as client_like,
    'test'::text as brand_like
)
select
  c.id as client_id,
  c.name as client_name,
  b.id as brand_id,
  b.name as brand_name,
  b.clickup_space_id,
  b.clickup_list_id,
  case when b.clickup_space_id is null then true else false end as missing_space,
  case when b.clickup_list_id is null then true else false end as missing_list
from public.agency_clients c
left join public.brands b on b.client_id = c.id
cross join params p
where lower(c.name) like ('%' || p.client_like || '%')
   or lower(coalesce(b.name, '')) like ('%' || p.brand_like || '%')
order by c.name, b.name;

-- ------------------------------------------------------------------
-- 2) SOP coverage and freshness checks
-- ------------------------------------------------------------------
select
  category,
  name,
  last_synced_at,
  char_length(coalesce(content_md, '')) as content_chars
from public.playbook_sops
order by category nulls last, name;

-- Find SOPs likely relevant to coupon/promotions.
select
  id,
  category,
  name,
  left(coalesce(content_md, ''), 240) as snippet
from public.playbook_sops
where lower(coalesce(name, '')) like '%coupon%'
   or lower(coalesce(name, '')) like '%promotion%'
   or lower(coalesce(content_md, '')) like '%coupon%'
   or lower(coalesce(content_md, '')) like '%promotion%'
order by last_synced_at desc nulls last;

-- ------------------------------------------------------------------
-- 3) Debug user session and run trace checks
-- ------------------------------------------------------------------
with params as (
  select 'U_DEBUG_TERMINAL'::text as debug_user
)
select
  s.id as session_id,
  s.slack_user_id,
  s.profile_id,
  s.active_client_id,
  s.last_message_at,
  s.created_at
from public.playbook_slack_sessions s
cross join params p
where s.slack_user_id = p.debug_user
order by s.last_message_at desc
limit 10;

-- Latest runs for debug user.
with params as (
  select 'U_DEBUG_TERMINAL'::text as debug_user
)
select
  r.id as run_id,
  r.parent_run_id,
  r.trace_id,
  r.run_type,
  r.status,
  r.started_at,
  r.completed_at,
  (
    select count(*)
    from public.agent_skill_events e
    where e.run_id = r.id
  ) as skill_event_count
from public.agent_runs r
join public.playbook_slack_sessions s on s.id = r.session_id
cross join params p
where s.slack_user_id = p.debug_user
order by r.started_at desc
limit 25;

-- ------------------------------------------------------------------
-- 4) Inspect one recent run in detail
-- Replace <RUN_ID> with a UUID from query (3).
-- ------------------------------------------------------------------
-- select role, created_at, content, summary
-- from public.agent_messages
-- where run_id = '<RUN_ID>'::uuid
-- order by created_at asc;

-- select event_type, skill_id, created_at, payload_summary, payload
-- from public.agent_skill_events
-- where run_id = '<RUN_ID>'::uuid
-- order by created_at asc;

-- ------------------------------------------------------------------
-- 5) Assignment context (optional)
-- ------------------------------------------------------------------
select
  c.name as client_name,
  b.name as brand_name,
  ar.slug as role_slug,
  p.full_name as assignee_name,
  p.slack_user_id as assignee_slack_user_id
from public.client_assignments ca
join public.agency_clients c on c.id = ca.client_id
left join public.brands b on b.id = ca.brand_id
join public.agency_roles ar on ar.id = ca.role_id
join public.profiles p on p.id = ca.team_member_id
order by c.name, b.name nulls first, ar.slug, p.full_name;
