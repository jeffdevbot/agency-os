-- Ensure attribute_preferences column exists on scribe_skus (idempotent)
alter table public.scribe_skus
  add column if not exists attribute_preferences jsonb;
