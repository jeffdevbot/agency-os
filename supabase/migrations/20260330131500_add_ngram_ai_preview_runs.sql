-- =====================================================================
-- MIGRATION: N-Gram AI preview runs
-- Purpose:
--   Persist the exact Step 3 AI preview payload for auditability and
--   follow-up tuning, instead of relying only on aggregate token logs.
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.ngram_ai_preview_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE RESTRICT,
  requested_by_auth_user_id uuid,
  ad_product text NOT NULL,
  date_from date NOT NULL,
  date_to date NOT NULL,
  spend_threshold numeric(12,2) NOT NULL CHECK (spend_threshold >= 0),
  respect_legacy_exclusions boolean NOT NULL DEFAULT true,
  model text,
  prompt_tokens integer NOT NULL DEFAULT 0 CHECK (prompt_tokens >= 0),
  completion_tokens integer NOT NULL DEFAULT 0 CHECK (completion_tokens >= 0),
  total_tokens integer NOT NULL DEFAULT 0 CHECK (total_tokens >= 0),
  preview_payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.ngram_ai_preview_runs
  IS 'Persisted N-Gram 2 Step 3 AI preview payloads for audit and tuning.';

COMMENT ON COLUMN public.ngram_ai_preview_runs.requested_by_auth_user_id
  IS 'Supabase auth.users id from the requesting session.';

COMMENT ON COLUMN public.ngram_ai_preview_runs.preview_payload
  IS 'Exact preview response payload returned to the UI, including warnings and campaign evaluations.';

CREATE INDEX IF NOT EXISTS idx_ngram_ai_preview_runs_profile_created
  ON public.ngram_ai_preview_runs(profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ngram_ai_preview_runs_user_created
  ON public.ngram_ai_preview_runs(requested_by_auth_user_id, created_at DESC);

ALTER TABLE public.ngram_ai_preview_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view ngram ai preview runs"
  ON public.ngram_ai_preview_runs;
CREATE POLICY "Admins can view ngram ai preview runs"
  ON public.ngram_ai_preview_runs FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage ngram ai preview runs"
  ON public.ngram_ai_preview_runs;
CREATE POLICY "Admins can manage ngram ai preview runs"
  ON public.ngram_ai_preview_runs FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));
