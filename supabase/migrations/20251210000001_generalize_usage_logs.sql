-- Migration: Generalize usage logs for AdScope and other tools
-- Created: 2025-12-10
-- Purpose: Rename scribe_usage_logs to ai_token_usage and make project_id nullable

-- 1. Rename the table
ALTER TABLE IF EXISTS public.scribe_usage_logs RENAME TO ai_token_usage;

-- 2. Rename the indexes (convention)
ALTER INDEX IF EXISTS idx_scribe_usage_logs_project RENAME TO idx_ai_token_usage_project;
ALTER INDEX IF EXISTS idx_scribe_usage_logs_user RENAME TO idx_ai_token_usage_user;
ALTER INDEX IF EXISTS idx_scribe_usage_logs_job RENAME TO idx_ai_token_usage_job;

-- 3. Make project_id nullable
-- 3. Make project_id nullable and add meta column
ALTER TABLE public.ai_token_usage ALTER COLUMN project_id DROP NOT NULL;
ALTER TABLE public.ai_token_usage ADD COLUMN IF NOT EXISTS meta jsonb DEFAULT '{}'::jsonb;

-- 4. Update Policies

-- Drop old policies (names might vary, so we drop if exists)
DROP POLICY IF EXISTS scribe_usage_logs_select ON public.ai_token_usage;
DROP POLICY IF EXISTS scribe_usage_logs_insert ON public.ai_token_usage;

-- Create new generalized policies
-- SELECT: Users can see their own logs (regardless of project)
CREATE POLICY ai_token_usage_select ON public.ai_token_usage
  FOR SELECT USING (
    user_id = auth.uid()
  );

-- INSERT: Users can insert logs for themselves
CREATE POLICY ai_token_usage_insert ON public.ai_token_usage
  FOR INSERT WITH CHECK (
    user_id = auth.uid()
  );
