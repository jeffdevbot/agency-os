-- =====================================================================
-- MIGRATION: Monthly P&L Phase 1 foundation
-- Purpose:
--   Create all tables for the backfill-first Monthly P&L system:
--   profiles, imports, import months, raw rows, ledger entries,
--   mapping rules, and COGS monthly. Plus storage bucket and
--   default US mapping rules.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) P&L profiles — one per client + marketplace
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.monthly_pnl_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id uuid NOT NULL REFERENCES public.agency_clients(id) ON DELETE RESTRICT,
  marketplace_code text NOT NULL,
  currency_code text NOT NULL DEFAULT 'USD',
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'active', 'archived')),
  notes text,
  created_by uuid REFERENCES public.profiles(id),
  updated_by uuid REFERENCES public.profiles(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_profiles_client_marketplace
  ON public.monthly_pnl_profiles(client_id, marketplace_code);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_profiles_status
  ON public.monthly_pnl_profiles(status);

DROP TRIGGER IF EXISTS update_monthly_pnl_profiles_updated_at ON public.monthly_pnl_profiles;
CREATE TRIGGER update_monthly_pnl_profiles_updated_at
  BEFORE UPDATE ON public.monthly_pnl_profiles
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.monthly_pnl_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view P&L profiles" ON public.monthly_pnl_profiles;
CREATE POLICY "Admins can view P&L profiles"
  ON public.monthly_pnl_profiles FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage P&L profiles" ON public.monthly_pnl_profiles;
CREATE POLICY "Admins can manage P&L profiles"
  ON public.monthly_pnl_profiles FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 2) P&L imports — tracks uploaded files or automated source pulls
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.monthly_pnl_imports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.monthly_pnl_profiles(id) ON DELETE CASCADE,
  source_type text NOT NULL
    CHECK (source_type IN ('amazon_transaction_upload', 'windsor_settlement', 'cogs_upload')),
  period_start date,
  period_end date,
  source_filename text,
  storage_path text,
  source_file_sha256 text,
  import_scope text
    CHECK (import_scope IN ('single_month', 'multi_month', 'full_year')),
  supersedes_import_id uuid REFERENCES public.monthly_pnl_imports(id) ON DELETE SET NULL,
  import_status text NOT NULL DEFAULT 'pending'
    CHECK (import_status IN ('pending', 'running', 'success', 'error')),
  row_count integer NOT NULL DEFAULT 0 CHECK (row_count >= 0),
  error_message text,
  raw_meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  initiated_by uuid REFERENCES public.profiles(id),
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Only block duplicate SHA when a prior import is still active (success/running).
-- Errored or pending imports do NOT block retry of the same file.
CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_imports_profile_source_sha256
  ON public.monthly_pnl_imports(profile_id, source_type, source_file_sha256)
  WHERE source_file_sha256 IS NOT NULL AND import_status IN ('success', 'running');

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_imports_profile_source_period
  ON public.monthly_pnl_imports(profile_id, source_type, period_start, period_end);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_imports_profile_status
  ON public.monthly_pnl_imports(profile_id, import_status);

DROP TRIGGER IF EXISTS update_monthly_pnl_imports_updated_at ON public.monthly_pnl_imports;
CREATE TRIGGER update_monthly_pnl_imports_updated_at
  BEFORE UPDATE ON public.monthly_pnl_imports
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.monthly_pnl_imports ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view P&L imports" ON public.monthly_pnl_imports;
CREATE POLICY "Admins can view P&L imports"
  ON public.monthly_pnl_imports FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage P&L imports" ON public.monthly_pnl_imports;
CREATE POLICY "Admins can manage P&L imports"
  ON public.monthly_pnl_imports FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 3) P&L import months — month-level slices for atomic activation
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.monthly_pnl_import_months (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.monthly_pnl_profiles(id) ON DELETE CASCADE,
  import_id uuid NOT NULL REFERENCES public.monthly_pnl_imports(id) ON DELETE CASCADE,
  source_type text NOT NULL
    CHECK (source_type IN ('amazon_transaction_upload', 'windsor_settlement', 'cogs_upload')),
  entry_month date NOT NULL,
  import_status text NOT NULL DEFAULT 'pending'
    CHECK (import_status IN ('pending', 'running', 'success', 'error')),
  is_active boolean NOT NULL DEFAULT false,
  supersedes_import_month_id uuid REFERENCES public.monthly_pnl_import_months(id) ON DELETE SET NULL,
  raw_row_count integer NOT NULL DEFAULT 0 CHECK (raw_row_count >= 0),
  ledger_row_count integer NOT NULL DEFAULT 0 CHECK (ledger_row_count >= 0),
  mapped_amount numeric(18, 2) NOT NULL DEFAULT 0,
  unmapped_amount numeric(18, 2) NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_import_months_import_month
  ON public.monthly_pnl_import_months(import_id, entry_month);

CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_import_months_active
  ON public.monthly_pnl_import_months(profile_id, source_type, entry_month)
  WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_import_months_profile_source_month_status
  ON public.monthly_pnl_import_months(profile_id, source_type, entry_month, import_status);

DROP TRIGGER IF EXISTS update_monthly_pnl_import_months_updated_at ON public.monthly_pnl_import_months;
CREATE TRIGGER update_monthly_pnl_import_months_updated_at
  BEFORE UPDATE ON public.monthly_pnl_import_months
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.monthly_pnl_import_months ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view P&L import months" ON public.monthly_pnl_import_months;
CREATE POLICY "Admins can view P&L import months"
  ON public.monthly_pnl_import_months FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage P&L import months" ON public.monthly_pnl_import_months;
CREATE POLICY "Admins can manage P&L import months"
  ON public.monthly_pnl_import_months FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 4) P&L raw rows — audit/debugging store of parsed source rows
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.monthly_pnl_raw_rows (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  import_id uuid NOT NULL REFERENCES public.monthly_pnl_imports(id) ON DELETE CASCADE,
  profile_id uuid NOT NULL REFERENCES public.monthly_pnl_profiles(id) ON DELETE CASCADE,
  import_month_id uuid REFERENCES public.monthly_pnl_import_months(id) ON DELETE SET NULL,
  source_type text NOT NULL
    CHECK (source_type IN ('amazon_transaction_upload', 'windsor_settlement', 'cogs_upload')),
  row_index integer NOT NULL CHECK (row_index >= 0),
  posted_at timestamptz,
  order_id text,
  sku text,
  raw_type text,
  raw_description text,
  release_at timestamptz,
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_raw_rows_import_row_index
  ON public.monthly_pnl_raw_rows(import_id, row_index);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_raw_rows_profile_import
  ON public.monthly_pnl_raw_rows(profile_id, import_id);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_raw_rows_import_posted
  ON public.monthly_pnl_raw_rows(import_id, posted_at);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_raw_rows_import_release
  ON public.monthly_pnl_raw_rows(import_id, release_at);

DROP TRIGGER IF EXISTS update_monthly_pnl_raw_rows_updated_at ON public.monthly_pnl_raw_rows;
CREATE TRIGGER update_monthly_pnl_raw_rows_updated_at
  BEFORE UPDATE ON public.monthly_pnl_raw_rows
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.monthly_pnl_raw_rows ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view P&L raw rows" ON public.monthly_pnl_raw_rows;
CREATE POLICY "Admins can view P&L raw rows"
  ON public.monthly_pnl_raw_rows FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage P&L raw rows" ON public.monthly_pnl_raw_rows;
CREATE POLICY "Admins can manage P&L raw rows"
  ON public.monthly_pnl_raw_rows FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 5) P&L mapping rules — deterministic raw→bucket mapping
--    (created before ledger_entries which references it)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.monthly_pnl_mapping_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid REFERENCES public.monthly_pnl_profiles(id) ON DELETE CASCADE,
  marketplace_code text NOT NULL DEFAULT 'US',
  source_type text NOT NULL
    CHECK (source_type IN ('amazon_transaction_upload', 'windsor_settlement')),
  match_spec jsonb NOT NULL DEFAULT '{}'::jsonb,
  match_operator text NOT NULL DEFAULT 'exact_fields'
    CHECK (match_operator IN ('exact_fields', 'contains', 'starts_with', 'regex')),
  target_bucket text NOT NULL,
  priority integer NOT NULL DEFAULT 100,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_mapping_rules_source_marketplace
  ON public.monthly_pnl_mapping_rules(source_type, marketplace_code, active, priority);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_mapping_rules_profile
  ON public.monthly_pnl_mapping_rules(profile_id)
  WHERE profile_id IS NOT NULL;

-- Global seed rules are unique per (marketplace, source_type, match_spec, match_operator)
-- when profile_id IS NULL.  This lets the seed INSERTs use ON CONFLICT DO NOTHING.
CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_mapping_rules_global_seed
  ON public.monthly_pnl_mapping_rules(marketplace_code, source_type, match_spec, match_operator)
  WHERE profile_id IS NULL;

DROP TRIGGER IF EXISTS update_monthly_pnl_mapping_rules_updated_at ON public.monthly_pnl_mapping_rules;
CREATE TRIGGER update_monthly_pnl_mapping_rules_updated_at
  BEFORE UPDATE ON public.monthly_pnl_mapping_rules
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.monthly_pnl_mapping_rules ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view P&L mapping rules" ON public.monthly_pnl_mapping_rules;
CREATE POLICY "Admins can view P&L mapping rules"
  ON public.monthly_pnl_mapping_rules FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage P&L mapping rules" ON public.monthly_pnl_mapping_rules;
CREATE POLICY "Admins can manage P&L mapping rules"
  ON public.monthly_pnl_mapping_rules FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 6) P&L ledger entries — canonical normalized rows for the report
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.monthly_pnl_ledger_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.monthly_pnl_profiles(id) ON DELETE CASCADE,
  import_id uuid NOT NULL REFERENCES public.monthly_pnl_imports(id) ON DELETE CASCADE,
  import_month_id uuid REFERENCES public.monthly_pnl_import_months(id) ON DELETE SET NULL,
  entry_month date NOT NULL,
  posted_at timestamptz,
  order_id text,
  sku text,
  source_type text NOT NULL
    CHECK (source_type IN ('amazon_transaction_upload', 'windsor_settlement', 'cogs_upload')),
  source_subtype text,
  raw_type text,
  raw_description text,
  ledger_bucket text NOT NULL,
  amount numeric(18, 2) NOT NULL,
  currency_code text NOT NULL DEFAULT 'USD',
  is_mapped boolean NOT NULL DEFAULT false,
  mapping_rule_id uuid REFERENCES public.monthly_pnl_mapping_rules(id) ON DELETE SET NULL,
  source_row_index integer,
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Dedupe key: prefer source-row-based uniqueness. One raw row + bucket
-- should produce exactly one ledger entry per import.
CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_ledger_entries_import_row_bucket
  ON public.monthly_pnl_ledger_entries(import_id, source_row_index, ledger_bucket)
  WHERE source_row_index IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_ledger_profile_month_bucket
  ON public.monthly_pnl_ledger_entries(profile_id, entry_month, ledger_bucket);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_ledger_profile_month_mapped
  ON public.monthly_pnl_ledger_entries(profile_id, entry_month, is_mapped);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_ledger_profile_source_month
  ON public.monthly_pnl_ledger_entries(profile_id, source_type, entry_month);

DROP TRIGGER IF EXISTS update_monthly_pnl_ledger_entries_updated_at ON public.monthly_pnl_ledger_entries;
CREATE TRIGGER update_monthly_pnl_ledger_entries_updated_at
  BEFORE UPDATE ON public.monthly_pnl_ledger_entries
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.monthly_pnl_ledger_entries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view P&L ledger entries" ON public.monthly_pnl_ledger_entries;
CREATE POLICY "Admins can view P&L ledger entries"
  ON public.monthly_pnl_ledger_entries FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage P&L ledger entries" ON public.monthly_pnl_ledger_entries;
CREATE POLICY "Admins can manage P&L ledger entries"
  ON public.monthly_pnl_ledger_entries FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 7) P&L COGS monthly — optional cost-of-goods source
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.monthly_pnl_cogs_monthly (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.monthly_pnl_profiles(id) ON DELETE CASCADE,
  entry_month date NOT NULL,
  sku text,
  asin text,
  amount numeric(18, 2) NOT NULL,
  currency_code text NOT NULL DEFAULT 'USD',
  source_import_id uuid REFERENCES public.monthly_pnl_imports(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_cogs_profile_month_sku_asin
  ON public.monthly_pnl_cogs_monthly(profile_id, entry_month, COALESCE(sku, ''), COALESCE(asin, ''));

DROP TRIGGER IF EXISTS update_monthly_pnl_cogs_monthly_updated_at ON public.monthly_pnl_cogs_monthly;
CREATE TRIGGER update_monthly_pnl_cogs_monthly_updated_at
  BEFORE UPDATE ON public.monthly_pnl_cogs_monthly
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.monthly_pnl_cogs_monthly ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view P&L COGS" ON public.monthly_pnl_cogs_monthly;
CREATE POLICY "Admins can view P&L COGS"
  ON public.monthly_pnl_cogs_monthly FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage P&L COGS" ON public.monthly_pnl_cogs_monthly;
CREATE POLICY "Admins can manage P&L COGS"
  ON public.monthly_pnl_cogs_monthly FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 8) Supabase Storage bucket for finance/reporting imports
-- ---------------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public)
VALUES ('monthly-pnl-imports', 'monthly-pnl-imports', false)
ON CONFLICT (id) DO NOTHING;

-- Admin-only storage policies
DROP POLICY IF EXISTS "Admins can upload P&L files" ON storage.objects;
CREATE POLICY "Admins can upload P&L files"
  ON storage.objects FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'monthly-pnl-imports'
    AND EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true)
  );

DROP POLICY IF EXISTS "Admins can read P&L files" ON storage.objects;
CREATE POLICY "Admins can read P&L files"
  ON storage.objects FOR SELECT TO authenticated
  USING (
    bucket_id = 'monthly-pnl-imports'
    AND EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true)
  );

-- ---------------------------------------------------------------------
-- 9) Seed default US mapping rules for amazon_transaction_upload
-- ---------------------------------------------------------------------
-- Direct column mappings: each column in the CSV maps to a ledger bucket.
-- These rules use match_operator = 'exact_fields' with match_spec
-- containing the mapping from source CSV column to ledger bucket.
-- For transaction uploads, the column-based expansion happens in code,
-- but type/description-based mapping rules catch special rows.

-- Advertising: Service Fee / Cost of Advertising
INSERT INTO public.monthly_pnl_mapping_rules
  (marketplace_code, source_type, match_spec, match_operator, target_bucket, priority)
VALUES
  ('US', 'amazon_transaction_upload',
   '{"type": "Service Fee", "description": "Cost of Advertising"}',
   'exact_fields', 'advertising', 10)
ON CONFLICT DO NOTHING;

-- Subscription: Service Fee / Subscription
INSERT INTO public.monthly_pnl_mapping_rules
  (marketplace_code, source_type, match_spec, match_operator, target_bucket, priority)
VALUES
  ('US', 'amazon_transaction_upload',
   '{"type": "Service Fee", "description": "Subscription"}',
   'exact_fields', 'subscription_fees', 10)
ON CONFLICT DO NOTHING;

-- Inbound placement: Service Fee / FBA Inbound Placement Service Fee
INSERT INTO public.monthly_pnl_mapping_rules
  (marketplace_code, source_type, match_spec, match_operator, target_bucket, priority)
VALUES
  ('US', 'amazon_transaction_upload',
   '{"type": "Service Fee", "description": "FBA Inbound Placement Service Fee"}',
   'exact_fields', 'inbound_placement_and_defect_fees', 10)
ON CONFLICT DO NOTHING;

-- FBA storage fee
INSERT INTO public.monthly_pnl_mapping_rules
  (marketplace_code, source_type, match_spec, match_operator, target_bucket, priority)
VALUES
  ('US', 'amazon_transaction_upload',
   '{"type": "FBA Inventory Fee", "description": "FBA storage fee"}',
   'exact_fields', 'fba_monthly_storage_fees', 10)
ON CONFLICT DO NOTHING;

-- FBA long-term storage fee
INSERT INTO public.monthly_pnl_mapping_rules
  (marketplace_code, source_type, match_spec, match_operator, target_bucket, priority)
VALUES
  ('US', 'amazon_transaction_upload',
   '{"type": "FBA Inventory Fee", "description": "FBA Long-Term Storage Fee"}',
   'exact_fields', 'fba_long_term_storage_fees', 10)
ON CONFLICT DO NOTHING;

-- FBA removal order: disposal
INSERT INTO public.monthly_pnl_mapping_rules
  (marketplace_code, source_type, match_spec, match_operator, target_bucket, priority)
VALUES
  ('US', 'amazon_transaction_upload',
   '{"type": "FBA Inventory Fee"}',
   'exact_fields', 'fba_removal_order_fees', 50)
ON CONFLICT DO NOTHING;

-- Adjustment / FBA Inventory Reimbursement
INSERT INTO public.monthly_pnl_mapping_rules
  (marketplace_code, source_type, match_spec, match_operator, target_bucket, priority)
VALUES
  ('US', 'amazon_transaction_upload',
   '{"type": "Adjustment"}',
   'exact_fields', 'fba_inventory_credit', 50)
ON CONFLICT DO NOTHING;

-- Transfer rows → non-P&L
INSERT INTO public.monthly_pnl_mapping_rules
  (marketplace_code, source_type, match_spec, match_operator, target_bucket, priority)
VALUES
  ('US', 'amazon_transaction_upload',
   '{"type": "Transfer"}',
   'exact_fields', 'non_pnl_transfer', 10)
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------
-- 10) RPC: atomic month-slice activation
--     Deactivates old active slice and activates the new one in a
--     single transaction so the report never sees a blank month.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.pnl_activate_month_slice(
  p_profile_id uuid,
  p_source_type text,
  p_entry_month date,
  p_import_month_id uuid
) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  -- Deactivate any existing active slice for this profile/source/month
  UPDATE public.monthly_pnl_import_months
     SET is_active = false, updated_at = now()
   WHERE profile_id = p_profile_id
     AND source_type = p_source_type
     AND entry_month = p_entry_month
     AND is_active = true
     AND id != p_import_month_id;

  -- Activate the new slice
  UPDATE public.monthly_pnl_import_months
     SET is_active = true, updated_at = now()
   WHERE id = p_import_month_id;
END;
$$;
