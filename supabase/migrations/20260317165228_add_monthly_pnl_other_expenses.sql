-- Add manual Monthly P&L other-expense rows and per-profile visibility toggles.

-- ---------------------------------------------------------------------
-- 1) Manual monthly expense values
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.monthly_pnl_manual_expenses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.monthly_pnl_profiles(id) ON DELETE CASCADE,
  entry_month date NOT NULL,
  expense_key text NOT NULL CHECK (expense_key IN ('fbm_fulfillment_fees', 'agency_fees')),
  amount numeric(18, 2) NOT NULL CHECK (amount >= 0),
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_manual_expenses_profile_month_key
  ON public.monthly_pnl_manual_expenses(profile_id, entry_month, expense_key);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_manual_expenses_profile_month
  ON public.monthly_pnl_manual_expenses(profile_id, entry_month);

DROP TRIGGER IF EXISTS update_monthly_pnl_manual_expenses_updated_at
  ON public.monthly_pnl_manual_expenses;
CREATE TRIGGER update_monthly_pnl_manual_expenses_updated_at
  BEFORE UPDATE ON public.monthly_pnl_manual_expenses
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.monthly_pnl_manual_expenses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view P&L manual expenses"
  ON public.monthly_pnl_manual_expenses;
CREATE POLICY "Admins can view P&L manual expenses"
  ON public.monthly_pnl_manual_expenses FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage P&L manual expenses"
  ON public.monthly_pnl_manual_expenses;
CREATE POLICY "Admins can manage P&L manual expenses"
  ON public.monthly_pnl_manual_expenses FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

-- ---------------------------------------------------------------------
-- 2) Per-profile visibility toggles for manual expense rows
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.monthly_pnl_manual_expense_settings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid NOT NULL REFERENCES public.monthly_pnl_profiles(id) ON DELETE CASCADE,
  expense_key text NOT NULL CHECK (expense_key IN ('fbm_fulfillment_fees', 'agency_fees')),
  is_enabled boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_pnl_manual_expense_settings_profile_key
  ON public.monthly_pnl_manual_expense_settings(profile_id, expense_key);

CREATE INDEX IF NOT EXISTS idx_monthly_pnl_manual_expense_settings_profile
  ON public.monthly_pnl_manual_expense_settings(profile_id);

DROP TRIGGER IF EXISTS update_monthly_pnl_manual_expense_settings_updated_at
  ON public.monthly_pnl_manual_expense_settings;
CREATE TRIGGER update_monthly_pnl_manual_expense_settings_updated_at
  BEFORE UPDATE ON public.monthly_pnl_manual_expense_settings
  FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.monthly_pnl_manual_expense_settings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins can view P&L manual expense settings"
  ON public.monthly_pnl_manual_expense_settings;
CREATE POLICY "Admins can view P&L manual expense settings"
  ON public.monthly_pnl_manual_expense_settings FOR SELECT TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));

DROP POLICY IF EXISTS "Admins can manage P&L manual expense settings"
  ON public.monthly_pnl_manual_expense_settings;
CREATE POLICY "Admins can manage P&L manual expense settings"
  ON public.monthly_pnl_manual_expense_settings FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true))
  WITH CHECK (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = true));
