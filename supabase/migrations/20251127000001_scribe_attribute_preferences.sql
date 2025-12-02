-- Migration: Add attribute_preferences to scribe_skus
-- Date: 2025-11-27
-- Purpose: Store per-SKU attribute usage preferences for Stage C copy generation

-- Add attribute_preferences column to scribe_skus
ALTER TABLE scribe_skus
ADD COLUMN IF NOT EXISTS attribute_preferences jsonb;

-- Add comment explaining the column structure
COMMENT ON COLUMN scribe_skus.attribute_preferences IS
'Attribute usage preferences for copy generation. Shape: { mode?: "auto"|"overrides", rules?: Record<string, { sections: ("title"|"bullets"|"description"|"backend_keywords")[] }> }. Defaults to auto mode when null.';
