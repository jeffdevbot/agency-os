-- =====================================================================
-- MIGRATION: WBR profiles and rows (v2 foundation)
-- Purpose:
--   Create the marketplace-specific WBR profile root object and the
--   shared row tree used across business and ads sections.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) WBR profiles
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wbr_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id uuid NOT NULL REFERENCES public.agency_clients(id) ON DELETE RESTRICT,
  marketplace_code text NOT NULL,
  display_name text NOT NULL,
  week_start_day text NOT NULL
    CHECK (week_start_day IN ('sunday', 'monday')),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'active', 'paused', 'archived')),
  windsor_account_id text,
  amazon_ads_profile_id text,
  amazon_ads_account_id text,
  backfill_start_date date,
  daily_rewrite_days integer NOT NULL DEFAULT 14
    CHECK (daily_rewrite_days >= 1 AND daily_rewrite_days <= 60),
  created_by uuid REFERENCES public.profiles(id),
  updated_by uuid REFERENCES public.profiles(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wbr_profiles_client_marketplace
  ON public.wbr_profiles(client_id, marketplace_code);

CREATE INDEX IF NOT EXISTS idx_wbr_profiles_status
  ON public.wbr_profiles(status);

DROP TRIGGER IF EXISTS update_wbr_profiles_updated_at ON public.wbr_profiles;
CREATE TRIGGER update_wbr_profiles_updated_at
  BEFORE UPDATE ON public.wbr_profiles
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR profiles" ON public.wbr_profiles;
CREATE POLICY "Admins can view WBR profiles"
  ON public.wbr_profiles FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR profiles" ON public.wbr_profiles;
CREATE POLICY "Admins can manage WBR profiles"
  ON public.wbr_profiles FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 2) WBR rows
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wbr_rows (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  row_label text NOT NULL,
  row_kind text NOT NULL
    CHECK (row_kind IN ('parent', 'leaf')),
  parent_row_id uuid REFERENCES public.wbr_rows(id) ON DELETE SET NULL,
  sort_order integer NOT NULL DEFAULT 0,
  active boolean NOT NULL DEFAULT true,
  created_by uuid REFERENCES public.profiles(id),
  updated_by uuid REFERENCES public.profiles(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wbr_rows_profile_kind_label_active
  ON public.wbr_rows(profile_id, row_kind, row_label)
  WHERE active = true;

CREATE INDEX IF NOT EXISTS idx_wbr_rows_profile_parent_sort
  ON public.wbr_rows(profile_id, parent_row_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_wbr_rows_profile_kind_sort
  ON public.wbr_rows(profile_id, row_kind, sort_order);

-- ---------------------------------------------------------------------
-- 3) Row hierarchy validation helper
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.wbr_validate_row_hierarchy()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_parent_profile_id uuid;
  v_parent_row_kind text;
BEGIN
  IF NEW.row_kind = 'parent' AND NEW.parent_row_id IS NOT NULL THEN
    RAISE EXCEPTION 'Parent rows cannot have a parent_row_id in WBR v1';
  END IF;

  IF NEW.parent_row_id IS NULL THEN
    IF NEW.row_kind = 'leaf' AND EXISTS (
      SELECT 1
      FROM public.wbr_rows child
      WHERE child.parent_row_id = NEW.id
        AND child.id <> NEW.id
    ) THEN
      RAISE EXCEPTION 'Leaf rows cannot have child rows in WBR v1';
    END IF;

    RETURN NEW;
  END IF;

  IF NEW.parent_row_id = NEW.id THEN
    RAISE EXCEPTION 'WBR rows cannot parent themselves';
  END IF;

  IF NEW.row_kind <> 'leaf' THEN
    RAISE EXCEPTION 'Only leaf rows may reference parent_row_id in WBR v1';
  END IF;

  SELECT profile_id, row_kind
  INTO v_parent_profile_id, v_parent_row_kind
  FROM public.wbr_rows
  WHERE id = NEW.parent_row_id;

  IF v_parent_profile_id IS NULL THEN
    RAISE EXCEPTION 'Parent WBR row % was not found', NEW.parent_row_id;
  END IF;

  IF v_parent_profile_id <> NEW.profile_id THEN
    RAISE EXCEPTION 'Parent WBR row must belong to the same WBR profile';
  END IF;

  IF v_parent_row_kind <> 'parent' THEN
    RAISE EXCEPTION 'parent_row_id must reference a row with row_kind = parent';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS validate_wbr_rows_hierarchy ON public.wbr_rows;
CREATE TRIGGER validate_wbr_rows_hierarchy
  BEFORE INSERT OR UPDATE ON public.wbr_rows
  FOR EACH ROW EXECUTE FUNCTION public.wbr_validate_row_hierarchy();

DROP TRIGGER IF EXISTS update_wbr_rows_updated_at ON public.wbr_rows;
CREATE TRIGGER update_wbr_rows_updated_at
  BEFORE UPDATE ON public.wbr_rows
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_rows ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR rows" ON public.wbr_rows;
CREATE POLICY "Admins can view WBR rows"
  ON public.wbr_rows FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR rows" ON public.wbr_rows;
CREATE POLICY "Admins can manage WBR rows"
  ON public.wbr_rows FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));
