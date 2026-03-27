-- =====================================================================
-- MIGRATION: STR keyword dimension fields
-- Purpose:
--   Preserve Amazon-native search-term keyword semantics that were
--   flattened away in the initial schema.  Adds keyword_id, keyword,
--   keyword_type, and targeting so ingest can store the full Amazon Ads
--   spSearchTerm row without discarding meaning.
--
--   Also rebuilds the unique index to include keyword_id.  The old index
--   treated (profile, date, campaign, search_term, match_type) as the
--   natural key, but in the Amazon report the same search_term/match_type
--   can appear for multiple keywords in the same campaign — those rows are
--   legitimately distinct.  Adding keyword_id to the index (COALESCE to
--   '' for auto-targeting rows that have no keyword) preserves that
--   distinction.
--
-- Migration is safe on an empty or pre-populated table because the new
--   index is MORE permissive than the old one (more rows can coexist).
--   The ingestion layer uses a delete-and-reinsert window strategy so
--   existing rows are replaced on the next sync run.
-- =====================================================================

-- Add new columns (nullable — old rows have no keyword context)
ALTER TABLE public.search_term_daily_facts
  ADD COLUMN IF NOT EXISTS keyword_id   text,
  ADD COLUMN IF NOT EXISTS keyword      text,
  ADD COLUMN IF NOT EXISTS keyword_type text,
  ADD COLUMN IF NOT EXISTS targeting    text;

COMMENT ON COLUMN public.search_term_daily_facts.keyword_id
  IS 'Amazon Ads keyword ID (keywordId). Null for auto-targeting rows.';
COMMENT ON COLUMN public.search_term_daily_facts.keyword
  IS 'Keyword text as entered in the Amazon Ads console (keyword/keywordText). Null for auto-targeting.';
COMMENT ON COLUMN public.search_term_daily_facts.keyword_type
  IS 'Amazon Ads keywordType: BROAD, PHRASE, EXACT, or AUTO for auto-targeting rows.';
COMMENT ON COLUMN public.search_term_daily_facts.targeting
  IS 'Amazon Ads targeting expression (targeting/targetingExpression). Present for auto-targeting rows.';

-- Rebuild the unique index to include keyword_id and targeting.
--
-- keyword_id: the same search term can be triggered by multiple distinct
--   keywords in the same campaign — those rows are legitimately different.
--   COALESCE(keyword_id, '') keeps auto-targeting rows (no keyword) comparable.
--
-- targeting: for auto-targeting rows (keyword_id IS NULL), the targeting
--   expression is the identity dimension.  Two auto-targeting rows with the
--   same search_term but different targeting expressions are distinct in the
--   Amazon report and must be stored as separate rows.
--   COALESCE(targeting, '') keeps keyword-targeted rows (no targeting) comparable.
DROP INDEX IF EXISTS uq_search_term_daily_facts_profile_day_type_campaign_term_match;

CREATE UNIQUE INDEX IF NOT EXISTS uq_str_facts_profile_day_type_campaign_keyword_term_match
  ON public.search_term_daily_facts(
    profile_id,
    report_date,
    campaign_type,
    COALESCE(campaign_id,  ''),
    campaign_name,
    COALESCE(keyword_id,   ''),
    COALESCE(targeting,    ''),
    search_term,
    COALESCE(match_type,   '')
  );
