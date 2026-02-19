-- =====================================================================
-- MIGRATION: ClickUp Space Registry (C6A)
-- Purpose:
--   Registry of ClickUp spaces with classification and brand mapping.
--   Synced from ClickUp API, supports brand-scoped routing.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Table
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.clickup_space_registry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  space_id text UNIQUE NOT NULL,
  team_id text NOT NULL,
  name text NOT NULL,
  classification text NOT NULL DEFAULT 'unknown'
    CHECK (classification IN ('brand_scoped', 'shared_service', 'unknown')),
  brand_id uuid REFERENCES public.brands(id) ON DELETE SET NULL,
  active boolean NOT NULL DEFAULT true,
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  last_synced_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 2) Indexes
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_space_registry_classification_active
  ON public.clickup_space_registry(classification, active);

CREATE INDEX IF NOT EXISTS idx_space_registry_brand_id
  ON public.clickup_space_registry(brand_id)
  WHERE brand_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_space_registry_active_synced
  ON public.clickup_space_registry(active, last_synced_at DESC);

-- ---------------------------------------------------------------------
-- 3) updated_at trigger
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS update_clickup_space_registry_updated_at ON public.clickup_space_registry;
CREATE TRIGGER update_clickup_space_registry_updated_at
  BEFORE UPDATE ON public.clickup_space_registry
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ---------------------------------------------------------------------
-- 4) RLS + policies
-- ---------------------------------------------------------------------
ALTER TABLE public.clickup_space_registry ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Only admins can manage space registry" ON public.clickup_space_registry;
CREATE POLICY "Only admins can manage space registry"
  ON public.clickup_space_registry FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Authenticated users can view space registry" ON public.clickup_space_registry;
CREATE POLICY "Authenticated users can view space registry"
  ON public.clickup_space_registry FOR SELECT TO authenticated
  USING (true);
