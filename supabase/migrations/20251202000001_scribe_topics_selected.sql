-- Add selected column to scribe_topics for Stage B topic selection
-- This replaces the approval-based model with a simpler selection model for Scribe Lite

alter table public.scribe_topics
add column if not exists selected boolean not null default false;

-- Add index for efficient querying of selected topics
create index if not exists idx_scribe_topics_selected
on public.scribe_topics(sku_id, selected)
where selected = true;

-- Add comment for clarity
comment on column public.scribe_topics.selected is
'Indicates if this topic was selected by the user in Stage B (Scribe Lite uses selection instead of approval)';
