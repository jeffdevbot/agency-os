-- WBR email draft persistence.
-- Stores generated client-facing weekly email drafts across multiple marketplaces.

CREATE TABLE IF NOT EXISTS public.wbr_email_drafts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id uuid NOT NULL REFERENCES public.agency_clients(id) ON DELETE RESTRICT,
  snapshot_group_key text NOT NULL,
  draft_kind text NOT NULL CHECK (draft_kind IN ('weekly_client_email')),
  prompt_version text NOT NULL,
  marketplace_scope text NOT NULL,
  snapshot_ids jsonb NOT NULL,
  subject text NOT NULL,
  body text NOT NULL,
  model text,
  created_by uuid REFERENCES public.profiles(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wbr_email_drafts_client_created
  ON public.wbr_email_drafts(client_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wbr_email_drafts_group_key
  ON public.wbr_email_drafts(snapshot_group_key);

-- Admin-only RLS (consistent with other WBR tables).
ALTER TABLE public.wbr_email_drafts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "wbr_email_drafts_admin_all" ON public.wbr_email_drafts;

CREATE POLICY "wbr_email_drafts_admin_all" ON public.wbr_email_drafts
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
