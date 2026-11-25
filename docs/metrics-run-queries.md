# Example queries over local metrics run records

Aegis stores structural-fragility runs in DuckDB (`data/aegis_runs.duckdb` by
default). Records are validated `run_record.v1` JSON — per-metric values and
statuses only. No blended score. These queries are examples for local analysis;
they are not forecasts.

```bash
# Write + load a run
PYTHONPATH=. python -m metrics.run_all --graph metrics/examples/chillco.yaml \
  --stress-ladder --store

# Open the DB
python -c "import duckdb; print(duckdb.connect('data/aegis_runs.duckdb').execute('SHOW TABLES').fetchall())"
```

## Latest run per graph

```sql
SELECT r.graph_name, r.run_id, r.ts_utc, r.package_version, r.git_commit
FROM runs r
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY r.graph_name ORDER BY r.ts_utc DESC
) = 1
ORDER BY r.graph_name;
```

## Status changes for a graph across metric versions

```sql
SELECT
  r.ts_utc,
  r.graph_name,
  m.metric,
  m.metric_version,
  m.status,
  m.value
FROM runs r
JOIN metric_results m USING (run_id)
WHERE r.graph_name = 'hidden_shared_subtier'
  AND m.metric = 'optionality'
ORDER BY r.ts_utc, m.metric_version;
```

## All graphs with a RED single point of failure (latest run each)

```sql
WITH latest AS (
  SELECT *
  FROM runs
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY graph_name ORDER BY ts_utc DESC
  ) = 1
)
SELECT
  l.graph_name,
  l.ts_utc,
  m.value AS spof_count,
  m.drivers
FROM latest l
JOIN metric_results m ON m.run_id = l.run_id
WHERE m.metric = 'single_points_of_failure'
  AND m.status = 'red'
ORDER BY l.graph_name;
```

## Probe settings for runs where ruin left NOT_TESTED

```sql
SELECT r.graph_name, r.ts_utc, r.stress_ladder, r.survival_floor, m.status
FROM runs r
JOIN metric_results m USING (run_id)
WHERE m.metric = 'ruin'
  AND m.status = 'not_tested'
ORDER BY r.ts_utc DESC;
```
