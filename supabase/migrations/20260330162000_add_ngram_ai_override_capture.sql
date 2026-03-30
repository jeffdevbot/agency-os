-- =====================================================================
-- MIGRATION: N-Gram AI prompt version + override capture
-- Purpose:
--   Persist the exact prompt version used for Step 3 preview runs and
--   capture silent diffs between AI-prefilled workbooks and analyst-reviewed
--   submissions for later calibration analysis.
-- =====================================================================

ALTER TABLE public.ngram_ai_preview_runs
  ADD COLUMN IF NOT EXISTS prompt_version text;

COMMENT ON COLUMN public.ngram_ai_preview_runs.prompt_version
  IS 'Version identifier for the Step 3 N-Gram AI prompt used to generate the preview run.';

UPDATE public.ngram_ai_preview_runs
SET prompt_version = nullif(preview_payload->>'prompt_version', '')
WHERE prompt_version IS NULL;

CREATE TABLE IF NOT EXISTS public.ngram_ai_override_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  preview_run_id uuid NOT NULL REFERENCES public.ngram_ai_preview_runs(id) ON DELETE RESTRICT,
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE RESTRICT,
  collected_by_auth_user_id uuid,
  source_filename text,
  model text,
  prompt_version text,
  override_payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.ngram_ai_override_runs
  IS 'Persisted AI-vs-analyst override captures from reviewed N-Gram workbooks.';

COMMENT ON COLUMN public.ngram_ai_override_runs.override_payload
  IS 'Structured diff payload comparing saved AI preview decisions against the reviewed workbook submission.';

CREATE INDEX IF NOT EXISTS idx_ngram_ai_override_runs_preview_created
  ON public.ngram_ai_override_runs(preview_run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ngram_ai_override_runs_profile_created
  ON public.ngram_ai_override_runs(profile_id, created_at DESC);

ALTER TABLE public.ngram_ai_override_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view ngram ai override runs"
  ON public.ngram_ai_override_runs;
CREATE POLICY "Admins can view ngram ai override runs"
  ON public.ngram_ai_override_runs FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage ngram ai override runs"
  ON public.ngram_ai_override_runs;
CREATE POLICY "Admins can manage ngram ai override runs"
  ON public.ngram_ai_override_runs FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));
