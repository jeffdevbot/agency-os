-- =====================================================================
-- MIGRATION: WBR imports and mappings (v2 foundation)
-- Purpose:
--   Add Pacvue import tracking, listing import tracking, canonical child
--   ASIN catalog, and mapping tables that bind campaigns and ASINs to the
--   shared WBR row tree.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Pacvue import batches
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wbr_pacvue_import_batches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  source_filename text,
  import_status text NOT NULL DEFAULT 'running'
    CHECK (import_status IN ('running', 'success', 'error')),
  rows_read integer NOT NULL DEFAULT 0 CHECK (rows_read >= 0),
  rows_loaded integer NOT NULL DEFAULT 0 CHECK (rows_loaded >= 0),
  error_message text,
  initiated_by uuid REFERENCES public.profiles(id),
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wbr_pacvue_import_batches_profile_created
  ON public.wbr_pacvue_import_batches(profile_id, created_at DESC);

DROP TRIGGER IF EXISTS update_wbr_pacvue_import_batches_updated_at ON public.wbr_pacvue_import_batches;
CREATE TRIGGER update_wbr_pacvue_import_batches_updated_at
  BEFORE UPDATE ON public.wbr_pacvue_import_batches
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_pacvue_import_batches ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR Pacvue import batches" ON public.wbr_pacvue_import_batches;
CREATE POLICY "Admins can view WBR Pacvue import batches"
  ON public.wbr_pacvue_import_batches FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR Pacvue import batches" ON public.wbr_pacvue_import_batches;
CREATE POLICY "Admins can manage WBR Pacvue import batches"
  ON public.wbr_pacvue_import_batches FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 2) Pacvue campaign mapping snapshot/history
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wbr_pacvue_campaign_map (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  import_batch_id uuid NOT NULL REFERENCES public.wbr_pacvue_import_batches(id) ON DELETE CASCADE,
  campaign_name text NOT NULL,
  raw_tag text NOT NULL,
  row_id uuid NOT NULL REFERENCES public.wbr_rows(id) ON DELETE CASCADE,
  leaf_row_label text NOT NULL,
  goal_code text,
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wbr_pacvue_campaign_map_profile_campaign_active
  ON public.wbr_pacvue_campaign_map(profile_id, campaign_name)
  WHERE active = true;

CREATE INDEX IF NOT EXISTS idx_wbr_pacvue_campaign_map_profile_row
  ON public.wbr_pacvue_campaign_map(profile_id, row_id);

CREATE INDEX IF NOT EXISTS idx_wbr_pacvue_campaign_map_profile_leaf_label
  ON public.wbr_pacvue_campaign_map(profile_id, leaf_row_label);

CREATE INDEX IF NOT EXISTS idx_wbr_pacvue_campaign_map_profile_goal_code
  ON public.wbr_pacvue_campaign_map(profile_id, goal_code)
  WHERE goal_code IS NOT NULL;

DROP TRIGGER IF EXISTS update_wbr_pacvue_campaign_map_updated_at ON public.wbr_pacvue_campaign_map;
CREATE TRIGGER update_wbr_pacvue_campaign_map_updated_at
  BEFORE UPDATE ON public.wbr_pacvue_campaign_map
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_pacvue_campaign_map ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR Pacvue campaign map" ON public.wbr_pacvue_campaign_map;
CREATE POLICY "Admins can view WBR Pacvue campaign map"
  ON public.wbr_pacvue_campaign_map FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR Pacvue campaign map" ON public.wbr_pacvue_campaign_map;
CREATE POLICY "Admins can manage WBR Pacvue campaign map"
  ON public.wbr_pacvue_campaign_map FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 3) Listing import batches
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wbr_listing_import_batches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  source_filename text,
  import_status text NOT NULL DEFAULT 'running'
    CHECK (import_status IN ('running', 'success', 'error')),
  rows_read integer NOT NULL DEFAULT 0 CHECK (rows_read >= 0),
  rows_loaded integer NOT NULL DEFAULT 0 CHECK (rows_loaded >= 0),
  error_message text,
  initiated_by uuid REFERENCES public.profiles(id),
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_wbr_listing_import_batches_profile_created
  ON public.wbr_listing_import_batches(profile_id, created_at DESC);

DROP TRIGGER IF EXISTS update_wbr_listing_import_batches_updated_at ON public.wbr_listing_import_batches;
CREATE TRIGGER update_wbr_listing_import_batches_updated_at
  BEFORE UPDATE ON public.wbr_listing_import_batches
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_listing_import_batches ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR listing import batches" ON public.wbr_listing_import_batches;
CREATE POLICY "Admins can view WBR listing import batches"
  ON public.wbr_listing_import_batches FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR listing import batches" ON public.wbr_listing_import_batches;
CREATE POLICY "Admins can manage WBR listing import batches"
  ON public.wbr_listing_import_batches FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 4) Canonical child ASIN catalog per WBR profile
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wbr_profile_child_asins (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  listing_batch_id uuid REFERENCES public.wbr_listing_import_batches(id) ON DELETE SET NULL,
  parent_asin text,
  child_asin text NOT NULL,
  parent_sku text,
  child_sku text,
  fnsku text,
  upc text,
  category text,
  parent_title text,
  child_product_name text,
  source_item_style text,
  size text,
  fulfillment_method text,
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wbr_profile_child_asins_profile_child_active
  ON public.wbr_profile_child_asins(profile_id, child_asin)
  WHERE active = true;

CREATE INDEX IF NOT EXISTS idx_wbr_profile_child_asins_profile_style
  ON public.wbr_profile_child_asins(profile_id, source_item_style);

CREATE INDEX IF NOT EXISTS idx_wbr_profile_child_asins_profile_parent_asin
  ON public.wbr_profile_child_asins(profile_id, parent_asin)
  WHERE parent_asin IS NOT NULL;

DROP TRIGGER IF EXISTS update_wbr_profile_child_asins_updated_at ON public.wbr_profile_child_asins;
CREATE TRIGGER update_wbr_profile_child_asins_updated_at
  BEFORE UPDATE ON public.wbr_profile_child_asins
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_profile_child_asins ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR profile child ASINs" ON public.wbr_profile_child_asins;
CREATE POLICY "Admins can view WBR profile child ASINs"
  ON public.wbr_profile_child_asins FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR profile child ASINs" ON public.wbr_profile_child_asins;
CREATE POLICY "Admins can manage WBR profile child ASINs"
  ON public.wbr_profile_child_asins FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 5) ASIN -> row mapping
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.wbr_asin_row_map (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.wbr_profiles(id) ON DELETE CASCADE,
  child_asin text NOT NULL,
  row_id uuid NOT NULL REFERENCES public.wbr_rows(id) ON DELETE CASCADE,
  mapping_source text NOT NULL DEFAULT 'manual'
    CHECK (mapping_source IN ('manual', 'imported', 'suggested')),
  active boolean NOT NULL DEFAULT true,
  created_by uuid REFERENCES public.profiles(id),
  updated_by uuid REFERENCES public.profiles(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wbr_asin_row_map_profile_child_active
  ON public.wbr_asin_row_map(profile_id, child_asin)
  WHERE active = true;

CREATE INDEX IF NOT EXISTS idx_wbr_asin_row_map_profile_row
  ON public.wbr_asin_row_map(profile_id, row_id);

DROP TRIGGER IF EXISTS update_wbr_asin_row_map_updated_at ON public.wbr_asin_row_map;
CREATE TRIGGER update_wbr_asin_row_map_updated_at
  BEFORE UPDATE ON public.wbr_asin_row_map
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.wbr_asin_row_map ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view WBR ASIN row map" ON public.wbr_asin_row_map;
CREATE POLICY "Admins can view WBR ASIN row map"
  ON public.wbr_asin_row_map FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage WBR ASIN row map" ON public.wbr_asin_row_map;
CREATE POLICY "Admins can manage WBR ASIN row map"
  ON public.wbr_asin_row_map FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 6) Mapping integrity helpers
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.wbr_validate_pacvue_campaign_map()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_batch_profile_id uuid;
  v_row_profile_id uuid;
  v_row_kind text;
BEGIN
  SELECT profile_id
  INTO v_batch_profile_id
  FROM public.wbr_pacvue_import_batches
  WHERE id = NEW.import_batch_id;

  IF v_batch_profile_id IS NULL THEN
    RAISE EXCEPTION 'Pacvue import batch % was not found', NEW.import_batch_id;
  END IF;

  IF v_batch_profile_id <> NEW.profile_id THEN
    RAISE EXCEPTION 'Pacvue campaign map must use an import batch from the same WBR profile';
  END IF;

  SELECT profile_id, row_kind
  INTO v_row_profile_id, v_row_kind
  FROM public.wbr_rows
  WHERE id = NEW.row_id;

  IF v_row_profile_id IS NULL THEN
    RAISE EXCEPTION 'Referenced WBR row % was not found', NEW.row_id;
  END IF;

  IF v_row_profile_id <> NEW.profile_id THEN
    RAISE EXCEPTION 'Pacvue campaign map row must belong to the same WBR profile';
  END IF;

  IF v_row_kind <> 'leaf' THEN
    RAISE EXCEPTION 'Pacvue campaign map row_id must reference a leaf row';
  END IF;

  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.wbr_validate_asin_row_map()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_row_profile_id uuid;
  v_row_kind text;
  v_has_catalog_entry boolean;
BEGIN
  SELECT profile_id, row_kind
  INTO v_row_profile_id, v_row_kind
  FROM public.wbr_rows
  WHERE id = NEW.row_id;

  IF v_row_profile_id IS NULL THEN
    RAISE EXCEPTION 'Referenced WBR row % was not found', NEW.row_id;
  END IF;

  IF v_row_profile_id <> NEW.profile_id THEN
    RAISE EXCEPTION 'ASIN row map row must belong to the same WBR profile';
  END IF;

  IF v_row_kind <> 'leaf' THEN
    RAISE EXCEPTION 'ASIN row map row_id must reference a leaf row';
  END IF;

  SELECT EXISTS (
    SELECT 1
    FROM public.wbr_profile_child_asins a
    WHERE a.profile_id = NEW.profile_id
      AND a.child_asin = NEW.child_asin
      AND (a.active = true OR NEW.active = false)
  )
  INTO v_has_catalog_entry;

  IF NOT v_has_catalog_entry THEN
    RAISE EXCEPTION 'ASIN row map child_asin % must exist in the WBR profile child ASIN catalog', NEW.child_asin;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS validate_wbr_pacvue_campaign_map ON public.wbr_pacvue_campaign_map;
CREATE TRIGGER validate_wbr_pacvue_campaign_map
  BEFORE INSERT OR UPDATE ON public.wbr_pacvue_campaign_map
  FOR EACH ROW EXECUTE FUNCTION public.wbr_validate_pacvue_campaign_map();

DROP TRIGGER IF EXISTS validate_wbr_asin_row_map ON public.wbr_asin_row_map;
CREATE TRIGGER validate_wbr_asin_row_map
  BEFORE INSERT OR UPDATE ON public.wbr_asin_row_map
  FOR EACH ROW EXECUTE FUNCTION public.wbr_validate_asin_row_map();
