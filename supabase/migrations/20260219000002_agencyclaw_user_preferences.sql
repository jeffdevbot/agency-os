-- =====================================================================
-- MIGRATION: AgencyClaw User Preferences (C10E)
-- Purpose:
--   Actor-scoped durable preference store for AgencyClaw.
--   One row per profile_id. Stores default_client_id and a JSONB
--   bag for future extensibility.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Table
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agencyclaw_user_preferences (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  default_client_id uuid REFERENCES public.agency_clients(id) ON DELETE SET NULL,
  preferences jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (profile_id)
);

-- ---------------------------------------------------------------------
-- 2) Index
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_user_prefs_profile
  ON public.agencyclaw_user_preferences(profile_id);

-- ---------------------------------------------------------------------
-- 3) updated_at trigger
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS update_agencyclaw_user_preferences_updated_at ON public.agencyclaw_user_preferences;
CREATE TRIGGER update_agencyclaw_user_preferences_updated_at
  BEFORE UPDATE ON public.agencyclaw_user_preferences
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ---------------------------------------------------------------------
-- 4) RLS + policies
-- ---------------------------------------------------------------------
ALTER TABLE public.agencyclaw_user_preferences ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users manage own preferences" ON public.agencyclaw_user_preferences;
CREATE POLICY "Users manage own preferences"
  ON public.agencyclaw_user_preferences FOR ALL TO authenticated
  USING (profile_id = auth.uid())
  WITH CHECK (profile_id = auth.uid());

DROP POLICY IF EXISTS "Authenticated users can view own preferences" ON public.agencyclaw_user_preferences;
CREATE POLICY "Authenticated users can view own preferences"
  ON public.agencyclaw_user_preferences FOR SELECT TO authenticated
  USING (profile_id = auth.uid());
