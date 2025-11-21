-- Migration: Add updated_at column to composer_keyword_pools for optimistic locking
-- Created: 2025-11-21
-- Purpose: Fix race condition in concurrent keyword uploads

-- Add updated_at column if it doesn't exist
ALTER TABLE composer_keyword_pools
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Create or replace the trigger function to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing trigger if it exists (idempotent)
DROP TRIGGER IF EXISTS update_composer_keyword_pools_updated_at ON composer_keyword_pools;

-- Create trigger to automatically update updated_at on every UPDATE
CREATE TRIGGER update_composer_keyword_pools_updated_at
BEFORE UPDATE ON composer_keyword_pools
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Backfill updated_at for existing rows (set to created_at if NULL)
UPDATE composer_keyword_pools
SET updated_at = created_at
WHERE updated_at IS NULL;

-- Add comment explaining the purpose
COMMENT ON COLUMN composer_keyword_pools.updated_at IS 'Timestamp for optimistic locking - prevents lost updates in concurrent keyword uploads';
