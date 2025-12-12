-- Add format_preferences column to scribe_projects for storing output formatting options
-- (e.g., ALL CAPS bullet headers, paragraph breaks in description)

alter table public.scribe_projects
  add column if not exists format_preferences jsonb default null;

comment on column public.scribe_projects.format_preferences is 'JSON object storing output format preferences like {bulletCapsHeaders: true, descriptionParagraphs: true}';
