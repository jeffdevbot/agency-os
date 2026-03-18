-- =====================================================================
-- MIGRATION: WBR report snapshots
-- Purpose:
--   Store canonical WBR digest snapshots for reproducible downstream
--   use (Claw summaries, email drafts, audit trail).
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.wbr_report_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE RESTRICT,
  snapshot_kind text NOT NULL
    CHECK (snapshot_kind IN ('weekly_email', 'manual', 'claw_request')),
  week_count integer NOT NULL,
  week_ending date,
  window_start date NOT NULL,
  window_end date NOT NULL,
  source_run_at timestamptz NOT NULL DEFAULT now(),
  digest_version text NOT NULL,
  digest jsonb NOT NULL,
  raw_report jsonb,
  created_by uuid REFERENCES public.profiles(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.wbr_report_snapshots
  IS 'Canonical WBR digest snapshots used for email drafting, Claw summaries, and audit.';

COMMENT ON COLUMN public.wbr_report_snapshots.digest
  IS 'Compact, prompt-friendly digest (wbr_digest_v1 or later).';

COMMENT ON COLUMN public.wbr_report_snapshots.raw_report
  IS 'Optional full section payloads for debugging or rehydration.';

CREATE INDEX IF NOT EXISTS idx_wbr_report_snapshots_profile_created
  ON public.wbr_report_snapshots(profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wbr_report_snapshots_profile_week_ending
  ON public.wbr_report_snapshots(profile_id, week_ending DESC);

ALTER TABLE public.wbr_report_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR snapshots"
  ON public.wbr_report_snapshots;
CREATE POLICY "Admins can view WBR snapshots"
  ON public.wbr_report_snapshots FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR snapshots"
  ON public.wbr_report_snapshots;
CREATE POLICY "Admins can manage WBR snapshots"
  ON public.wbr_report_snapshots FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));
