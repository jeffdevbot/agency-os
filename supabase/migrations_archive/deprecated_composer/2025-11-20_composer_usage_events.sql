-- Migration: Create composer_usage_events table for AI/LLM usage tracking
-- Created: 2025-11-20
-- Purpose: Log all AI operations for cost tracking and analytics across Composer workflow

-- Create the table
CREATE TABLE IF NOT EXISTS composer_usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES composer_organizations(id) ON DELETE CASCADE,
    project_id UUID REFERENCES composer_projects(id) ON DELETE CASCADE,
    job_id UUID REFERENCES composer_jobs(id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK (action IN (
        'keyword_grouping',
        'theme_suggestion',
        'sample_generate',
        'bulk_generate',
        'backend_keywords',
        'locale_generate',
        'keyword_clean',
        'ai_lab'
    )),
    model TEXT NOT NULL,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    tokens_total INTEGER NOT NULL DEFAULT 0,
    cost_usd NUMERIC(10,6),
    duration_ms INTEGER,
    meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create indexes for common query patterns
CREATE INDEX idx_composer_usage_events_org_created
    ON composer_usage_events(organization_id, created_at DESC);

CREATE INDEX idx_composer_usage_events_org_project_created
    ON composer_usage_events(organization_id, project_id, created_at DESC);

CREATE INDEX idx_composer_usage_events_org_action_created
    ON composer_usage_events(organization_id, action, created_at DESC);

CREATE INDEX idx_composer_usage_events_org_model_created
    ON composer_usage_events(organization_id, model, created_at DESC);

-- Enable Row Level Security
ALTER TABLE composer_usage_events ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can read usage events for their organization
CREATE POLICY "Users can read usage events for their organization"
    ON composer_usage_events
    FOR SELECT
    TO authenticated
    USING (
        organization_id = (auth.jwt() ->> 'organization_id')::uuid
    );

-- RLS Policy: Authenticated users can insert usage events for their organization
CREATE POLICY "Users can insert usage events for their organization"
    ON composer_usage_events
    FOR INSERT
    TO authenticated
    WITH CHECK (
        organization_id = (auth.jwt() ->> 'organization_id')::uuid
    );

-- Add comment on table
COMMENT ON TABLE composer_usage_events IS 'Tracks all AI/LLM operations for cost tracking and analytics across Composer workflow';

-- Add comments on key columns
COMMENT ON COLUMN composer_usage_events.action IS 'Type of AI operation performed';
COMMENT ON COLUMN composer_usage_events.model IS 'AI model identifier (e.g., gpt-5.1-nano, gpt-4.1-mini-high)';
COMMENT ON COLUMN composer_usage_events.meta IS 'Flexible JSONB storage for operation-specific metadata (pool_type, pool_id, keyword_count, basis, etc.)';
COMMENT ON COLUMN composer_usage_events.cost_usd IS 'Calculated cost in USD with 6 decimal precision';
