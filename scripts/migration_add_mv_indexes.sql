-- scripts/migration_add_mv_indexes.sql
-- Run once to add unique indexes to materialized views for concurrent refresh support.
-- This allows REFRESH MATERIALIZED VIEW CONCURRENTLY to work without blocking.

-- Add index to mv_remote_trends (if not already present)
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_remote_trends ON mv_remote_trends(week, remote_type);

-- Add index to mv_city_hiring (if not already present)
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_city_hiring ON mv_city_hiring(location, role_category);
