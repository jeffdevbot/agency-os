-- =====================================================================
-- MIGRATION: Harden WBR Section 3 sync constraints
-- Purpose:
--   1) Replace any existing source_type CHECK on public.wbr_sync_runs
--      without relying on the original auto-generated constraint name.
--   2) Enforce source_type alignment for Section 3 fact tables via
--      sync_run_id validator triggers, matching the Section 1/2 pattern.
-- =====================================================================

DO $$
DECLARE
  v_constraint_name text;
BEGIN
  FOR v_constraint_name IN
    SELECT c.conname
    FROM pg_constraint c
    JOIN pg_attribute a
      ON a.attrelid = c.conrelid
     AND a.attnum = ANY (c.conkey)
    WHERE c.conrelid = 'public.wbr_sync_runs'::regclass
      AND c.contype = 'c'
      AND a.attname = 'source_type'
  LOOP
    EXECUTE format(
      'ALTER TABLE public.wbr_sync_runs DROP CONSTRAINT %I',
      v_constraint_name
    );
  END LOOP;
END
$$;

ALTER TABLE public.wbr_sync_runs
  ADD CONSTRAINT wbr_sync_runs_source_type_check
  CHECK (
    source_type IN (
      'windsor_business',
      'windsor_inventory',
      'windsor_returns',
      'amazon_ads',
      'pacvue_import',
      'listing_import'
    )
  );

CREATE OR REPLACE FUNCTION public.wbr_validate_inventory_sync_run()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_run_profile_id uuid;
  v_run_source_type text;
BEGIN
  IF NEW.sync_run_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT profile_id, source_type
  INTO v_run_profile_id, v_run_source_type
  FROM public.wbr_sync_runs
  WHERE id = NEW.sync_run_id;

  IF v_run_profile_id IS NULL THEN
    RAISE EXCEPTION 'WBR sync run % was not found', NEW.sync_run_id;
  END IF;

  IF v_run_profile_id <> NEW.profile_id THEN
    RAISE EXCEPTION 'Inventory fact sync_run_id must belong to the same WBR profile';
  END IF;

  IF v_run_source_type <> 'windsor_inventory' THEN
    RAISE EXCEPTION 'Inventory fact sync_run_id must reference source_type = windsor_inventory';
  END IF;

  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.wbr_validate_returns_sync_run()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_run_profile_id uuid;
  v_run_source_type text;
BEGIN
  IF NEW.sync_run_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT profile_id, source_type
  INTO v_run_profile_id, v_run_source_type
  FROM public.wbr_sync_runs
  WHERE id = NEW.sync_run_id;

  IF v_run_profile_id IS NULL THEN
    RAISE EXCEPTION 'WBR sync run % was not found', NEW.sync_run_id;
  END IF;

  IF v_run_profile_id <> NEW.profile_id THEN
    RAISE EXCEPTION 'Returns fact sync_run_id must belong to the same WBR profile';
  END IF;

  IF v_run_source_type <> 'windsor_returns' THEN
    RAISE EXCEPTION 'Returns fact sync_run_id must reference source_type = windsor_returns';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS validate_wbr_inventory_sync_run
  ON public.wbr_inventory_asin_snapshots;
CREATE TRIGGER validate_wbr_inventory_sync_run
  BEFORE INSERT OR UPDATE ON public.wbr_inventory_asin_snapshots
  FOR EACH ROW EXECUTE FUNCTION public.wbr_validate_inventory_sync_run();

DROP TRIGGER IF EXISTS validate_wbr_returns_sync_run
  ON public.wbr_returns_asin_daily;
CREATE TRIGGER validate_wbr_returns_sync_run
  BEFORE INSERT OR UPDATE ON public.wbr_returns_asin_daily
  FOR EACH ROW EXECUTE FUNCTION public.wbr_validate_returns_sync_run();
