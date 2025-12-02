-- Add locale column to scribe_projects with allowed set
alter table public.scribe_projects
  add column if not exists locale text not null default 'en-US';

update public.scribe_projects
  set locale = 'en-US'
  where locale is null;

alter table public.scribe_projects
  drop constraint if exists scribe_projects_locale_check;

alter table public.scribe_projects
  add constraint scribe_projects_locale_check
  check (locale in (
    'en-US','en-CA','en-GB','en-AU',
    'fr-CA','fr-FR',
    'es-MX','es-ES',
    'de-DE',
    'it-IT',
    'pt-BR',
    'nl-NL'
  ));

comment on column public.scribe_projects.locale is 'BCP 47 locale code for generation (e.g., en-US, fr-CA)';
