-- =====================================================================
-- MIGRATION: Playbook/Vara Tables (Slack Bot Sessions + SOP Cache)
-- Purpose:
--   Create tables for the Vara Slack bot:
--   1. playbook_slack_sessions - Conversation state with 30-min timeout
--   2. playbook_sops - Cached SOP content from ClickUp Docs
-- Notes:
--   - Bot uses SUPABASE_SERVICE_ROLE_KEY (bypasses RLS)
--   - Existing columns already in place: profiles.slack_user_id,
--     profiles.clickup_user_id, brands.clickup_space_id, brands.clickup_list_id
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) playbook_slack_sessions - Slack conversation state
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.playbook_slack_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slack_user_id text NOT NULL,
  profile_id uuid REFERENCES public.profiles(id),
  active_client_id uuid REFERENCES public.agency_clients(id),
  context jsonb DEFAULT '{}'::jsonb,
  last_message_at timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now()
);

-- Index for fast lookup by Slack user (primary access pattern)
CREATE INDEX IF NOT EXISTS idx_playbook_sessions_slack_user
  ON public.playbook_slack_sessions(slack_user_id);

-- Index for cleanup queries (sessions older than 30 min)
CREATE INDEX IF NOT EXISTS idx_playbook_sessions_last_message
  ON public.playbook_slack_sessions(last_message_at);

-- RLS: Bot uses service role key, but add policies for admin access
ALTER TABLE public.playbook_slack_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view all sessions" ON public.playbook_slack_sessions;
CREATE POLICY "Admins can view all sessions"
  ON public.playbook_slack_sessions FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage sessions" ON public.playbook_slack_sessions;
CREATE POLICY "Admins can manage sessions"
  ON public.playbook_slack_sessions FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 2) playbook_sops - Cached SOP content from ClickUp Docs
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.playbook_sops (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clickup_doc_id text NOT NULL,
  clickup_page_id text NOT NULL,
  name text NOT NULL,
  content_md text,
  category text,  -- 'ngram', 'weekly', 'monthly', 'account_health', etc.
  last_synced_at timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now(),

  UNIQUE(clickup_doc_id, clickup_page_id)
);

-- Index for lookup by category (common access pattern)
CREATE INDEX IF NOT EXISTS idx_playbook_sops_category
  ON public.playbook_sops(category);

-- RLS: Read-only for authenticated, write for admins/service role
ALTER TABLE public.playbook_sops ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can view SOPs" ON public.playbook_sops;
CREATE POLICY "Authenticated users can view SOPs"
  ON public.playbook_sops FOR SELECT TO authenticated
  USING (true);

DROP POLICY IF EXISTS "Admins can manage SOPs" ON public.playbook_sops;
CREATE POLICY "Admins can manage SOPs"
  ON public.playbook_sops FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 3) Helper function to clean up stale sessions (optional cron job)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.cleanup_stale_playbook_sessions()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  deleted_count integer;
BEGIN
  DELETE FROM public.playbook_slack_sessions
  WHERE last_message_at < now() - interval '30 minutes';

  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$;

-- Grant execute to service role (for scheduled cleanup)
GRANT EXECUTE ON FUNCTION public.cleanup_stale_playbook_sessions() TO service_role;
