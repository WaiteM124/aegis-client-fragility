# Example queries over local metrics run records

Aegis stores structural-fragility runs in DuckDB (`data/aegis_runs.duckdb` by
default). Records are validated `run_record.v1` or `run_record.v2` JSON —
per-metric values and statuses only. v2 adds `client_id`. No blended score.
These queries are for local analysis; they are not forecasts.

## Populate the store

Run at least twice when you want compare / status-change queries to have data:

```bash
PYTHONPATH=. python -m metrics.run_all --client chillco --stress-ladder --store
PYTHONPATH=. python -m metrics.run_all --client chillco --stress-ladder --store
```

Default path: `data/aegis_runs.duckdb` (gitignored). Schema:
`metrics/store/migrations/` (`runs`, `metric_results`).

## Open the DuckDB UI

Connecting to the file (or attaching it) exposes the catalog as `aegis_runs`.
Then paste a query from `docs/queries/`.

```python
import duckdb

con = duckdb.connect("data/aegis_runs.duckdb")  # catalog name: aegis_runs
con.execute("CALL start_ui()")  # opens the local UI; paste SQL from docs/queries/
```

Or attach from a fresh session:

```python
import duckdb

con = duckdb.connect()
con.execute("ATTACH 'data/aegis_runs.duckdb' AS aegis_runs")
con.execute("USE aegis_runs")
con.execute("CALL start_ui()")
```

Without the UI, run the same SQL via `con.execute(...)` / `con.sql(...)`.

## Saved queries (`docs/queries/`)

| File | Purpose |
|---|---|
| [compare_runs.sql](queries/compare_runs.sql) | `PIVOT`: one row per metric, columns per run (value + status), ordered/labeled by `ts_utc`. Default client `chillco`. |
| [latest_run.sql](queries/latest_run.sql) | All metrics (with `drivers`) for the latest run of a client. |
| [status_changes.sql](queries/status_changes.sql) | Metrics whose `status` changed between a client's two most recent runs. |
| [cleanup_untagged.sql](queries/cleanup_untagged.sql) | **Destructive:** delete `runs` with `client_id IS NULL` and their `metric_results`. |

Each file starts with a comment on what it does and how to change the client
filter. Edit `WHERE … client_id = 'chillco'` as needed.

## Ad-hoc snippets

### Latest run per client / graph

```sql
SELECT r.client_id, r.graph_name, r.run_id, r.ts_utc, r.package_version, r.git_commit
FROM runs r
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY coalesce(r.client_id, ''), r.graph_name ORDER BY r.ts_utc DESC
) = 1
ORDER BY r.client_id, r.graph_name;
```

### Status history for one metric on a graph

```sql
SELECT
  r.ts_utc,
  r.client_id,
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

### Graphs with a RED single point of failure (latest run each)

```sql
WITH latest AS (
  SELECT *
  FROM runs
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY coalesce(client_id, ''), graph_name ORDER BY ts_utc DESC
  ) = 1
)
SELECT
  l.client_id,
  l.graph_name,
  l.ts_utc,
  m.value AS spof_count,
  m.drivers
FROM latest l
JOIN metric_results m ON m.run_id = l.run_id
WHERE m.metric = 'single_points_of_failure'
  AND m.status = 'red'
ORDER BY l.client_id, l.graph_name;
```

### Probe settings where ruin is NOT_TESTED

```sql
SELECT r.client_id, r.graph_name, r.ts_utc, r.stress_ladder, r.survival_floor, m.status
FROM runs r
JOIN metric_results m USING (run_id)
WHERE m.metric = 'ruin'
  AND m.status = 'not_tested'
ORDER BY r.ts_utc DESC;
```
