-- latest_run.sql
-- All metrics for the latest run of a client, including drivers when stored.
-- Change the client: edit WHERE r.client_id = 'chillco' below.
-- To see every client: remove the WHERE line (keeps PARTITION BY client_id).
-- Tables: runs, metric_results (see metrics/store/migrations/).
-- How to run: see docs/metrics-run-queries.md (DuckDB UI catalog aegis_runs, or python duckdb).

WITH latest AS (
  SELECT *
  FROM runs r
  WHERE r.client_id = 'chillco'  -- change client here; remove WHERE for all clients
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY r.client_id ORDER BY r.ts_utc DESC
  ) = 1
)
SELECT
  l.client_id,
  l.run_id,
  l.ts_utc,
  l.graph_name,
  l.package_version,
  m.metric,
  m.metric_version,
  m.value,
  m.status,
  m.drivers
FROM latest l
JOIN metric_results m USING (run_id)
ORDER BY l.client_id, m.metric;
