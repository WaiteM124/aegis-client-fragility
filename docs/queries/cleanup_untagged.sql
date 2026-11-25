-- cleanup_untagged.sql
-- DESTRUCTIVE: permanently deletes runs with client_id IS NULL and their
-- metric_results rows. There is no client filter — only untagged (NULL) runs.
-- v1 records load with client_id NULL; prefer tagging via --client / v2.
-- Preview first:
--   SELECT run_id, ts_utc, graph_name FROM runs WHERE client_id IS NULL;
--   SELECT COUNT(*) FROM metric_results
--   WHERE run_id IN (SELECT run_id FROM runs WHERE client_id IS NULL);
-- How to run: see docs/metrics-run-queries.md. Do not run in CI.

-- Child rows first (FK from metric_results.run_id → runs.run_id).
DELETE FROM metric_results
WHERE run_id IN (SELECT run_id FROM runs WHERE client_id IS NULL);

DELETE FROM runs
WHERE client_id IS NULL;
