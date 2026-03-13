-- Cleanup script for Composer Slice 2 tables
-- Run this FIRST if you need to start fresh

-- Drop tables in reverse dependency order (overrides -> groups -> pools)
DROP TABLE IF EXISTS composer_keyword_group_overrides CASCADE;
DROP TABLE IF EXISTS composer_keyword_groups CASCADE;
DROP TABLE IF EXISTS composer_keyword_pools CASCADE;
