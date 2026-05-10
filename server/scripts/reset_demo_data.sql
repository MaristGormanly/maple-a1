-- reset_demo_data.sql
-- Wipes all rubrics, assignments, submissions, and evaluation results.
-- Preserves users and style_guide_chunks.
-- Run: psql $DATABASE_URL -f server/scripts/reset_demo_data.sql

TRUNCATE evaluation_results, submissions, assignments, rubrics;
