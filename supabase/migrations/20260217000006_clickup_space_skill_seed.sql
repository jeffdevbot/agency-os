-- =====================================================================
-- MIGRATION: Seed ClickUp space sync/classification skills
-- Purpose:
--   Add newly documented ClickUp space skills to skill_catalog.
-- Notes:
--   - Existing rows are preserved (ON CONFLICT DO NOTHING).
--   - Seeded disabled until implementation is complete.
-- =====================================================================

INSERT INTO public.skill_catalog (
  id,
  name,
  description,
  owner_service,
  implemented_in_code,
  enabled_default
)
VALUES
  (
    'cc_clickup_space_sync',
    'ClickUp Space Sync',
    'Sync ClickUp spaces into local registry for routing and classification.',
    'orchestrator',
    false,
    false
  ),
  (
    'cc_clickup_space_list',
    'ClickUp Space List',
    'List ClickUp spaces with classification and brand mapping status.',
    'orchestrator',
    false,
    false
  ),
  (
    'cc_clickup_space_classify',
    'ClickUp Space Classify',
    'Set classification for a ClickUp space (brand_scoped/shared_service/unknown).',
    'orchestrator',
    false,
    false
  ),
  (
    'cc_clickup_space_brand_map',
    'ClickUp Space Brand Map',
    'Map or unmap a brand_scoped ClickUp space to a brand.',
    'orchestrator',
    false,
    false
  )
ON CONFLICT (id) DO NOTHING;

