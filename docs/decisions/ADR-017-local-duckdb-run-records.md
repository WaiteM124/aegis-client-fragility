# ADR-017: Local DuckDB for metrics run records; BigQuery later

**Date:** 2026-11-25

## Context

Structural-fragility runs need to be stored and compared over time (metric
version changes, graph edits, probe settings). A durable analytics warehouse is
not chosen yet. Operators still need a local, zero-cloud path that matches the
versioned JSON run-record contract (`run_record.v1`).

## Decision

1. **Record first.** Every `metrics.run_all` run can emit one JSON object
   validated against `metrics/schemas/run_record.v1.json` (`--out PATH`).
   Fields include `run_id`, UTC timestamp, graph name, graph SHA-256, git
   commit when available, package version, probe settings, and per-metric
   version / value / status / drivers. No blended score field.
2. **Local store now.** `metrics.store.load` appends validated records into a
   DuckDB file (default `data/aegis_runs.duckdb`, gitignored). Schema lives in
   versioned SQL migrations under `metrics/store/migrations/`. Idempotent on
   `run_id`. CLI `--store` writes the record and loads it in one step.
3. **Same schema later.** When a cloud warehouse is needed, load the same
   `run_record.v1` documents into BigQuery (or equivalent) without changing the
   metric maths or inventing a second record shape.

## Status

Accepted

## Consequences

- `duckdb` and `jsonschema` are required for the metrics local path.
- Analysis starts with saved SQL in `docs/queries/` (see `docs/metrics-run-queries.md`).
- CI does not need a shared database; tests use a temporary DuckDB file.
- Choosing BigQuery later is an import/pipeline concern, not a metrics redesign.

## Alternatives rejected

- **SQLite only.** Fine for OLTP-style local use; DuckDB is a better fit for
  analytical queries over many run records and nested JSON drivers.
- **Database before a versioned record.** Would freeze storage before the
  exchange format; record-first keeps adapters replaceable.
- **Skipping local store until BigQuery.** Blocks offline iteration and
  portfolio demos that must run without cloud credentials.
