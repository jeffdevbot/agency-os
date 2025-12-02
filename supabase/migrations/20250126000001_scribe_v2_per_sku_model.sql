-- Scribe v2.0: Per-SKU Model Migration
-- Removes shared defaults/overrides, makes sku_id NOT NULL, adds usage telemetry

-- 1. Remove old shared default columns from scribe_projects
ALTER TABLE public.scribe_projects DROP COLUMN IF EXISTS brand_tone_default;
ALTER TABLE public.scribe_projects DROP COLUMN IF EXISTS target_audience_default;
ALTER TABLE public.scribe_projects DROP COLUMN IF EXISTS words_to_avoid_default;
ALTER TABLE public.scribe_projects DROP COLUMN IF EXISTS supplied_content_default;
ALTER TABLE public.scribe_projects DROP COLUMN IF EXISTS keywords_mode;
ALTER TABLE public.scribe_projects DROP COLUMN IF EXISTS questions_mode;
ALTER TABLE public.scribe_projects DROP COLUMN IF EXISTS topics_mode;

-- 2. Rename override columns in scribe_skus to remove _override suffix
DO $$
BEGIN
  -- Only rename if the column exists (for idempotency)
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'scribe_skus' AND column_name = 'brand_tone_override') THEN
    ALTER TABLE public.scribe_skus RENAME COLUMN brand_tone_override TO brand_tone;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'scribe_skus' AND column_name = 'target_audience_override') THEN
    ALTER TABLE public.scribe_skus RENAME COLUMN target_audience_override TO target_audience;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'scribe_skus' AND column_name = 'words_to_avoid_override') THEN
    ALTER TABLE public.scribe_skus RENAME COLUMN words_to_avoid_override TO words_to_avoid;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'scribe_skus' AND column_name = 'supplied_content_override') THEN
    ALTER TABLE public.scribe_skus RENAME COLUMN supplied_content_override TO supplied_content;
  END IF;
END $$;

-- 3. Make sku_id NOT NULL in keywords, questions, and topics
-- First, delete any orphaned records with NULL sku_id (should not exist, but safety check)
DELETE FROM public.scribe_keywords WHERE sku_id IS NULL;
DELETE FROM public.scribe_customer_questions WHERE sku_id IS NULL;
DELETE FROM public.scribe_topics WHERE sku_id IS NULL;

-- Now make sku_id NOT NULL
ALTER TABLE public.scribe_keywords ALTER COLUMN sku_id SET NOT NULL;
ALTER TABLE public.scribe_customer_questions ALTER COLUMN sku_id SET NOT NULL;
ALTER TABLE public.scribe_topics ALTER COLUMN sku_id SET NOT NULL;

-- 4. Create scribe_usage_logs table for token usage telemetry
CREATE TABLE IF NOT EXISTS public.scribe_usage_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tool text NOT NULL,
  project_id uuid NOT NULL REFERENCES public.scribe_projects(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  job_id uuid REFERENCES public.scribe_generation_jobs(id) ON DELETE SET NULL,
  sku_id uuid REFERENCES public.scribe_skus(id) ON DELETE SET NULL,
  prompt_tokens int,
  completion_tokens int,
  total_tokens int,
  model text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Index for usage logs
CREATE INDEX IF NOT EXISTS idx_scribe_usage_logs_project ON public.scribe_usage_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_scribe_usage_logs_user ON public.scribe_usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_scribe_usage_logs_job ON public.scribe_usage_logs(job_id);

-- Enable RLS on usage logs
ALTER TABLE public.scribe_usage_logs ENABLE ROW LEVEL SECURITY;

-- Usage logs policies (owner-only)
DROP POLICY IF EXISTS scribe_usage_logs_select ON public.scribe_usage_logs;
CREATE POLICY scribe_usage_logs_select ON public.scribe_usage_logs
  FOR SELECT USING (
    project_id IN (SELECT id FROM public.scribe_projects WHERE created_by = auth.uid())
  );

DROP POLICY IF EXISTS scribe_usage_logs_insert ON public.scribe_usage_logs;
CREATE POLICY scribe_usage_logs_insert ON public.scribe_usage_logs
  FOR INSERT WITH CHECK (
    project_id IN (SELECT id FROM public.scribe_projects WHERE created_by = auth.uid())
  );
