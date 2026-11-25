-- Aegis local run-record store (DuckDB) — migration 002
-- Add client_id for per-client packs. v1 records load with NULL client_id.

ALTER TABLE runs ADD COLUMN IF NOT EXISTS client_id VARCHAR;
