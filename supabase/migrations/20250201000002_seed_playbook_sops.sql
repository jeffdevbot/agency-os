-- =====================================================================
-- MIGRATION: Seed playbook_sops with all known SOPs
-- Purpose:
--   Insert SOP registry entries with doc_id, page_id, category, and aliases.
--   The sync job will fetch content from ClickUp and update content_md.
--
--   This makes SOP configuration database-driven instead of hardcoded in Python.
-- =====================================================================

-- Upsert all SOPs (uses unique constraint on clickup_doc_id, clickup_page_id)
-- Content will be populated by the sync job

-- ===========================================
-- Bi-Weekly PPC Optimizations (18m2dn-4417)
-- ===========================================

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4417', '18m2dn-1997', 'ngram',
  'NGram Optimization SOP',
  ARRAY['n-gram', 'ngram', 'n-gram research', 'ngram research', 'keyword research',
        'n-gram optimization', 'ngram optimization', 'search term analysis',
        'search term optimization', 'negative keyword', 'negative keywords']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4417', '18m2dn-1977', 'npat',
  'N-PAT Optimization SOP',
  ARRAY['n-pat', 'npat', 'negative pat', 'negative product targeting',
        'product targeting optimization', 'asin targeting', 'pat optimization']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

-- ===========================================
-- Weekly PPC Optimizations (18m2dn-4377)
-- ===========================================

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4377', '18m2dn-1777', 'hv_kw',
  'HV-KW Optimization SOP',
  ARRAY['hv-kw', 'hvkw', 'high volume keyword', 'high-volume keyword',
        'hv kw optimization', 'high volume kw']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4377', '18m2dn-1797', 'hv_pat',
  'HV-PAT Optimization SOP',
  ARRAY['hv-pat', 'hvpat', 'high volume pat', 'high-volume product targeting',
        'hv pat optimization']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4377', '18m2dn-1817', 'placement_bid',
  'Placement Bid Optimization SOP',
  ARRAY['placement bid', 'placement optimization', 'bid placement',
        'placement bid adjustment', 'top of search bid']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

-- ===========================================
-- Monthly PPC Optimizations (18m2dn-4397)
-- ===========================================

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4397', '18m2dn-1897', 'campaign_target',
  'Campaign Target Setting SOP',
  ARRAY['campaign target', 'target setting', 'campaign goals', 'acos target',
        'roas target', 'campaign target setting']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4397', '18m2dn-1917', 'pacvue_rules',
  'Pacvue Rules Master Update SOP',
  ARRAY['pacvue rules', 'rules master', 'pacvue automation', 'automation rules',
        'pacvue rules update', 'bid rules']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

-- ===========================================
-- Account Health & Hygiene (18m2dn-4457)
-- ===========================================

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4457', '18m2dn-2217', 'stranded_inventory',
  'Stranded Inventory SOP',
  ARRAY['stranded inventory', 'stranded', 'inventory stranded',
        'stranded stock', 'fix stranded inventory']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4457', '18m2dn-2237', 'product_compliance',
  'Product Compliance Requests SOP',
  ARRAY['product compliance', 'compliance request', 'compliance',
        'product compliance request', 'compliance review']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4457', '18m2dn-2257', 'policy_violations',
  'Policy Violations Review SOP',
  ARRAY['policy violations', 'policy violation', 'violations review',
        'account policy', 'policy review']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4457', '18m2dn-2277', 'search_suppressed',
  'Search Suppressed & At-Risk Listings SOP',
  ARRAY['search suppressed', 'suppressed listings', 'at-risk listings',
        'suppressed', 'listing suppression', 'fix suppressed']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

-- ===========================================
-- Standalone SOPs
-- ===========================================

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4477', '18m2dn-2357', 'fba_restock',
  'FBA Restock Request SOP',
  ARRAY['fba restock', 'restock', 'restock request', 'fba inventory',
        'inventory restock', 'send inventory']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4497', '18m2dn-2377', 'portfolio_budgets',
  'Portfolio Budgets Weekly SOP',
  ARRAY['portfolio budget', 'portfolio budgets', 'budget pacing',
        'budget review', 'weekly budget', 'ppc budget']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4517', '18m2dn-2417', 'price_discounts',
  'Price Discounts Promotion SOP',
  ARRAY['price discount', 'price discounts', 'discount promotion',
        'sale price', 'price promotion', 'run a sale']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

INSERT INTO public.playbook_sops (clickup_doc_id, clickup_page_id, category, name, aliases)
VALUES (
  '18m2dn-4537', '18m2dn-2437', 'coupons',
  'Coupons Promotion SOP',
  ARRAY['coupon', 'coupons', 'coupon promotion', 'create coupon',
        'amazon coupon', 'add coupon']
)
ON CONFLICT (clickup_doc_id, clickup_page_id)
DO UPDATE SET
  category = EXCLUDED.category,
  name = EXCLUDED.name,
  aliases = EXCLUDED.aliases;

-- ===========================================
-- Summary: 15 SOPs seeded
-- ===========================================
-- Run the sync job to populate content_md for each SOP:
--   POST /api/admin/sync-sops
