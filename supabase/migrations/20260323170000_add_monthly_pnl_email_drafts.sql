-- Monthly P&L email draft persistence.

CREATE TABLE IF NOT EXISTS public.monthly_pnl_email_drafts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id uuid NOT NULL REFERENCES public.agency_clients(id) ON DELETE RESTRICT,
  report_month date NOT NULL,
  draft_kind text NOT NULL CHECK (draft_kind IN ('monthly_pnl_highlights_email')),
  prompt_version text NOT NULL,
  comparison_mode_requested text NOT NULL,
  comparison_mode_used text NOT NULL,
  marketplace_scope text NOT NULL,
  profile_ids jsonb NOT NULL,
  brief_payload jsonb NOT NULL,
  subject text NOT NULL,
  body text NOT NULL,
  model text,
  created_by uuid REFERENCES public.profiles(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_email_drafts_client_created
  ON public.monthly_pnl_email_drafts(client_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_email_drafts_client_month
  ON public.monthly_pnl_email_drafts(client_id, report_month DESC);

ALTER TABLE public.monthly_pnl_email_drafts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "monthly_pnl_email_drafts_admin_all" ON public.monthly_pnl_email_drafts;

CREATE POLICY "monthly_pnl_email_drafts_admin_all" ON public.monthly_pnl_email_drafts
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles
      WHERE profiles.id = auth.uid()
        AND profiles.is_admin = true
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.profiles
      WHERE profiles.id = auth.uid()
        AND profiles.is_admin = true
    )
  );
