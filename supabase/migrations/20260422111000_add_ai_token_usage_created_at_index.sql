-- Speed up Command Center token reporting scans by time window.
CREATE INDEX IF NOT EXISTS idx_ai_token_usage_created_at
  ON public.ai_token_usage (created_at DESC);
