-- =====================================================================
-- MIGRATION: Add aliases column to playbook_sops
-- Purpose:
--   Enable natural language lookups for SOPs. The aliases array stores
--   alternative names that users/AI might use to refer to an SOP.
--   Example: ngram SOP has aliases ["n-gram", "keyword research", "negative keywords"]
-- =====================================================================

-- Add aliases column for natural language matching
ALTER TABLE public.playbook_sops
ADD COLUMN IF NOT EXISTS aliases text[] DEFAULT '{}';

-- Create GIN index for efficient array containment queries
-- Allows: SELECT * FROM playbook_sops WHERE 'keyword research' = ANY(aliases)
CREATE INDEX IF NOT EXISTS idx_playbook_sops_aliases
  ON public.playbook_sops USING GIN (aliases);

-- Add comment explaining the column
COMMENT ON COLUMN public.playbook_sops.aliases IS
  'Alternative names for this SOP (lowercase). Used for natural language lookup. Example: {"n-gram", "keyword research", "negative keywords"}';
