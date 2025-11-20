-- Ensure highlight_attributes column exists as JSONB array for key attribute emphasis.
alter table public.composer_projects
add column if not exists highlight_attributes jsonb;

alter table public.composer_projects
alter column highlight_attributes drop default;

alter table public.composer_projects
alter column highlight_attributes type jsonb using coalesce(to_jsonb(highlight_attributes), '[]'::jsonb);

alter table public.composer_projects
alter column highlight_attributes set default '[]'::jsonb;
