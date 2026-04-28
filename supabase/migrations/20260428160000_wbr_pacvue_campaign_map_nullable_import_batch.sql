-- =====================================================================
-- MIGRATION: Allow manual entries in wbr_pacvue_campaign_map
--
-- Manual mappings created from the admin sync UI need to live in the
-- same table as Pacvue-imported mappings, but they have no associated
-- import batch. Drop the NOT NULL on import_batch_id and update the
-- validator trigger to skip batch lookup when the column is NULL.
--
-- The FK to wbr_pacvue_import_batches stays as ON DELETE CASCADE; that
-- only affects rows tied to a batch. Manual rows (NULL import_batch_id)
-- are unaffected by batch deletes, which is the desired behavior.
-- =====================================================================

ALTER TABLE public.wbr_pacvue_campaign_map
  ALTER COLUMN import_batch_id DROP NOT NULL;

CREATE OR REPLACE FUNCTION public.wbr_validate_pacvue_campaign_map()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
DECLARE
  v_batch_profile_id uuid;
  v_row_profile_id uuid;
  v_row_kind text;
BEGIN
  IF NEW.import_batch_id IS NOT NULL THEN
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
$function$;
