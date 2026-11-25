-- status_changes.sql
-- Metrics whose status changed between a client's two most recent runs.
-- Change the client: edit WHERE r.client_id = 'chillco' below.
-- Needs at least two runs for that client; otherwise returns no rows.
-- Tables: runs, metric_results (see metrics/store/migrations/).
-- How to run: see docs/metrics-run-queries.md (DuckDB UI catalog aegis_runs, or python duckdb).

WITH ranked AS (
  SELECT
    r.run_id,
    r.client_id,
    r.ts_utc,
    ROW_NUMBER() OVER (PARTITION BY r.client_id ORDER BY r.ts_utc DESC) AS rn
  FROM runs r
  WHERE r.client_id = 'chillco'  -- change client here
),
pair AS (
  SELECT
    c.client_id,
    p.run_id AS previous_run_id,
    p.ts_utc AS previous_ts,
    c.run_id AS current_run_id,
    c.ts_utc AS current_ts
  FROM ranked c
  JOIN ranked p
    ON c.client_id = p.client_id
   AND c.rn = 1
   AND p.rn = 2
)
SELECT
  pair.client_id,
  pair.previous_run_id,
  pair.previous_ts,
  pair.current_run_id,
  pair.current_ts,
  cur.metric,
  prev.status AS previous_status,
  prev.value AS previous_value,
  cur.status AS current_status,
  cur.value AS current_value
FROM pair
JOIN metric_results cur ON cur.run_id = pair.current_run_id
JOIN metric_results prev
  ON prev.run_id = pair.previous_run_id
 AND prev.metric = cur.metric
WHERE cur.status <> prev.status
ORDER BY cur.metric;
