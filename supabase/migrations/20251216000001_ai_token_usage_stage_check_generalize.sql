-- Migration: Generalize ai_token_usage.stage constraint beyond Scribe
-- Created: 2025-12-16
-- Purpose:
--   The `ai_token_usage` table was originally created for Scribe, where `stage`
--   is a fixed set (`stage_a|stage_b|stage_c`). Now that multiple tools write to
--   this table (e.g. Debrief), non-Scribe tools need to record their own stage
--   values (e.g. `extract`, `summarize`) without being blocked by the Scribe-only
--   check constraint.
--
-- Behavior after this migration:
--   - For tool='scribe': stage must be NULL or one of stage_a|stage_b|stage_c
--   - For other tools: stage may be any text (or NULL)

ALTER TABLE public.ai_token_usage
  DROP CONSTRAINT IF EXISTS scribe_usage_logs_stage_check;

ALTER TABLE public.ai_token_usage
  DROP CONSTRAINT IF EXISTS ai_token_usage_stage_check;

ALTER TABLE public.ai_token_usage
  ADD CONSTRAINT ai_token_usage_stage_check
  CHECK (
    stage IS NULL
    OR tool <> 'scribe'
    OR stage = ANY (ARRAY['stage_a'::text, 'stage_b'::text, 'stage_c'::text])
  );

