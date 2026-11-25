-- Aegis local run-record store (DuckDB) — migration 001
-- Same logical record shape as metrics/schemas/run_record.v1.json.
-- No blended score column. Per-metric rows only.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR PRIMARY KEY,
    ts_utc TIMESTAMPTZ NOT NULL,
    graph_name VARCHAR NOT NULL,
    graph_sha256 VARCHAR NOT NULL,
    git_commit VARCHAR,
    package_version VARCHAR NOT NULL,
    stress_ladder JSON NOT NULL,
    survival_floor DOUBLE
);

CREATE TABLE IF NOT EXISTS metric_results (
    run_id VARCHAR NOT NULL,
    metric VARCHAR NOT NULL,
    metric_version VARCHAR NOT NULL,
    value DOUBLE NOT NULL,
    status VARCHAR NOT NULL,
    drivers JSON NOT NULL,
    PRIMARY KEY (run_id, metric),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
