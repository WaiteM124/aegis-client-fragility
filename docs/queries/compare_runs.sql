-- compare_runs.sql
-- Pivot metric value and status across stored runs for one client.
-- One row per metric; one (value, status) column pair per run.
-- Run columns are labeled and ordered by runs.ts_utc (ISO timestamp + run_id).
-- Change the client: edit WHERE r.client_id = 'chillco' below.
-- Tables: runs, metric_results (see metrics/store/migrations/).
-- How to run: see docs/metrics-run-queries.md (DuckDB UI catalog aegis_runs, or python duckdb).

WITH base AS (
  SELECT
    m.metric,
    strftime(r.ts_utc, '%Y-%m-%dT%H:%M:%SZ') || ' ' || r.run_id AS run_label,
    m.value,
    m.status
  FROM runs r
  JOIN metric_results m USING (run_id)
  WHERE r.client_id = 'chillco'  -- change client here
)
PIVOT base
ON run_label
USING first(value) AS value, first(status) AS status
GROUP BY metric
ORDER BY metric;
