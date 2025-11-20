-- Migration: Composer Slice 2 - Keyword Pipeline Tables
-- Created: 2025-11-20
-- Description: Creates tables for managing keyword pools, groups, and user overrides
--              Implements the Keyword Pipeline (Raw → Cleaned → Grouped) workflow

-- ============================================================================
-- Table: composer_keyword_pools
-- ============================================================================
-- Purpose: Stores keyword pools for body and title optimization
-- Scope: Per project or per SKU group within a project
-- Pipeline: raw_keywords → cleaned_keywords → grouped (via composer_keyword_groups)

CREATE TABLE IF NOT EXISTS composer_keyword_pools (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES composer_organizations(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES composer_projects(id) ON DELETE CASCADE,
    group_id uuid NULL REFERENCES composer_sku_groups(id) ON DELETE CASCADE,

    -- Pool configuration
    pool_type text NOT NULL CHECK (pool_type IN ('body', 'titles')),
    status text NOT NULL DEFAULT 'empty' CHECK (status IN ('empty', 'uploaded', 'cleaned', 'grouped')),

    -- Raw keywords (user upload)
    raw_keywords jsonb NOT NULL DEFAULT '[]'::jsonb,
    raw_keywords_url text NULL,

    -- Cleaned keywords (after AI processing)
    cleaned_keywords jsonb NOT NULL DEFAULT '[]'::jsonb,
    removed_keywords jsonb NOT NULL DEFAULT '[]'::jsonb,
    clean_settings jsonb NOT NULL DEFAULT '{}'::jsonb,
    cleaned_at timestamptz NULL,

    -- Grouping metadata
    grouped_at timestamptz NULL,
    grouping_config jsonb NOT NULL DEFAULT '{}'::jsonb,
    approved_at timestamptz NULL,

    -- Audit
    created_at timestamptz NOT NULL DEFAULT now(),

    -- Constraints
    CONSTRAINT composer_keyword_pools_scope_check
        CHECK (
            (group_id IS NULL) OR
            (group_id IS NOT NULL AND pool_type = 'body')
        )
);

-- Indexes for composer_keyword_pools
CREATE INDEX idx_composer_keyword_pools_org_project_type
    ON composer_keyword_pools(organization_id, project_id, pool_type);

CREATE INDEX idx_composer_keyword_pools_org_project_group
    ON composer_keyword_pools(organization_id, project_id, group_id);

CREATE INDEX idx_composer_keyword_pools_status
    ON composer_keyword_pools(organization_id, status);

-- RLS for composer_keyword_pools
ALTER TABLE composer_keyword_pools ENABLE ROW LEVEL SECURITY;

CREATE POLICY composer_keyword_pools_select_policy ON composer_keyword_pools
    FOR SELECT
    USING (organization_id = current_org_id());

CREATE POLICY composer_keyword_pools_insert_policy ON composer_keyword_pools
    FOR INSERT
    WITH CHECK (organization_id = current_org_id());

CREATE POLICY composer_keyword_pools_update_policy ON composer_keyword_pools
    FOR UPDATE
    USING (organization_id = current_org_id())
    WITH CHECK (organization_id = current_org_id());

CREATE POLICY composer_keyword_pools_delete_policy ON composer_keyword_pools
    FOR DELETE
    USING (organization_id = current_org_id());

-- ============================================================================
-- Table: composer_keyword_groups
-- ============================================================================
-- Purpose: AI-generated semantic groups of keywords from a pool
-- Structure: Each group has an index, optional label, and array of phrases

CREATE TABLE IF NOT EXISTS composer_keyword_groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES composer_organizations(id) ON DELETE CASCADE,
    keyword_pool_id uuid NOT NULL REFERENCES composer_keyword_pools(id) ON DELETE CASCADE,

    -- Group identity
    group_index integer NOT NULL,
    label text NULL,

    -- Group content
    phrases jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,

    -- Audit
    created_at timestamptz NOT NULL DEFAULT now(),

    -- Ensure unique group_index per pool
    CONSTRAINT composer_keyword_groups_unique_index
        UNIQUE (keyword_pool_id, group_index)
);

-- Indexes for composer_keyword_groups
CREATE INDEX idx_composer_keyword_groups_org_pool_index
    ON composer_keyword_groups(organization_id, keyword_pool_id, group_index);

CREATE INDEX idx_composer_keyword_groups_pool
    ON composer_keyword_groups(keyword_pool_id);

-- RLS for composer_keyword_groups
ALTER TABLE composer_keyword_groups ENABLE ROW LEVEL SECURITY;

CREATE POLICY composer_keyword_groups_select_policy ON composer_keyword_groups
    FOR SELECT
    USING (organization_id = current_org_id());

CREATE POLICY composer_keyword_groups_insert_policy ON composer_keyword_groups
    FOR INSERT
    WITH CHECK (organization_id = current_org_id());

CREATE POLICY composer_keyword_groups_update_policy ON composer_keyword_groups
    FOR UPDATE
    USING (organization_id = current_org_id())
    WITH CHECK (organization_id = current_org_id());

CREATE POLICY composer_keyword_groups_delete_policy ON composer_keyword_groups
    FOR DELETE
    USING (organization_id = current_org_id());

-- ============================================================================
-- Table: composer_keyword_group_overrides
-- ============================================================================
-- Purpose: User manual adjustments to AI-generated keyword groupings
-- Actions: move (phrase to different group), remove (from grouping), add (new phrase)

CREATE TABLE IF NOT EXISTS composer_keyword_group_overrides (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES composer_organizations(id) ON DELETE CASCADE,
    keyword_pool_id uuid NOT NULL REFERENCES composer_keyword_pools(id) ON DELETE CASCADE,
    source_group_id uuid NULL REFERENCES composer_keyword_groups(id) ON DELETE CASCADE,

    -- Override details
    phrase text NOT NULL,
    action text NOT NULL CHECK (action IN ('move', 'remove', 'add')),

    -- Target for 'move' action
    target_group_label text NULL,
    target_group_index integer NULL,

    -- Audit
    created_at timestamptz NOT NULL DEFAULT now(),

    -- Validation: move action requires target
    CONSTRAINT composer_keyword_overrides_move_check
        CHECK (
            (action = 'move' AND (target_group_label IS NOT NULL OR target_group_index IS NOT NULL)) OR
            (action != 'move')
        )
);

-- Indexes for composer_keyword_group_overrides
CREATE INDEX idx_composer_keyword_overrides_org_pool_created
    ON composer_keyword_group_overrides(organization_id, keyword_pool_id, created_at);

CREATE INDEX idx_composer_keyword_overrides_pool
    ON composer_keyword_group_overrides(keyword_pool_id);

CREATE INDEX idx_composer_keyword_overrides_source_group
    ON composer_keyword_group_overrides(source_group_id)
    WHERE source_group_id IS NOT NULL;

-- RLS for composer_keyword_group_overrides
ALTER TABLE composer_keyword_group_overrides ENABLE ROW LEVEL SECURITY;

CREATE POLICY composer_keyword_overrides_select_policy ON composer_keyword_group_overrides
    FOR SELECT
    USING (organization_id = current_org_id());

CREATE POLICY composer_keyword_overrides_insert_policy ON composer_keyword_group_overrides
    FOR INSERT
    WITH CHECK (organization_id = current_org_id());

CREATE POLICY composer_keyword_overrides_update_policy ON composer_keyword_group_overrides
    FOR UPDATE
    USING (organization_id = current_org_id())
    WITH CHECK (organization_id = current_org_id());

CREATE POLICY composer_keyword_overrides_delete_policy ON composer_keyword_group_overrides
    FOR DELETE
    USING (organization_id = current_org_id());

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE composer_keyword_pools IS
    'Keyword pools for body and title optimization. Implements pipeline: raw → cleaned → grouped.';

COMMENT ON COLUMN composer_keyword_pools.pool_type IS
    'Type of keywords: body (general product keywords) or titles (brand/specific keywords)';

COMMENT ON COLUMN composer_keyword_pools.status IS
    'Pipeline status: empty → uploaded → cleaned → grouped';

COMMENT ON COLUMN composer_keyword_pools.group_id IS
    'Optional: scope pool to specific SKU group. Only valid for body pools.';

COMMENT ON TABLE composer_keyword_groups IS
    'AI-generated semantic groups from a keyword pool. Each group has index, label, and phrases.';

COMMENT ON TABLE composer_keyword_group_overrides IS
    'User manual adjustments to keyword groupings. Supports move, remove, and add actions.';

-- ============================================================================
-- Validation Queries (not executed, for reference)
-- ============================================================================

-- Verify tables exist:
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public' AND table_name LIKE 'composer_keyword%';

-- Verify RLS is enabled:
-- SELECT tablename, rowsecurity FROM pg_tables
-- WHERE schemaname = 'public' AND tablename LIKE 'composer_keyword%';

-- Verify policies exist:
-- SELECT schemaname, tablename, policyname FROM pg_policies
-- WHERE tablename LIKE 'composer_keyword%';
