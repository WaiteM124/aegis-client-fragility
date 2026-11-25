"""Local DuckDB store for metrics run records.

Append-only load of validated ``run_record.v1`` JSON files. Idempotent on
``run_id``. Analytics later may move to BigQuery with the same record
schema (see ADR-017); this package is the local path.

Public API: ``load``, ``DEFAULT_DB_PATH``, ``migrate``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from metrics.run_record import validate_run_record

DEFAULT_DB_PATH = Path("data/aegis_runs.duckdb")
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

__all__ = ["DEFAULT_DB_PATH", "load", "migrate"]


def _connect(db_path: Path):
    import duckdb

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def _split_sql(sql: str) -> list[str]:
    """Split SQL on ';' after dropping full-line `--` comments."""
    cleaned_lines: list[str] = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    return [part.strip() for part in cleaned.split(";") if part.strip()]


def _applied_versions(con) -> set[int]:
    row = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_name = 'schema_migrations'"
    ).fetchone()
    if not row or row[0] == 0:
        return set()
    rows = con.execute("SELECT version FROM schema_migrations").fetchall()
    return {int(r[0]) for r in rows}


def migrate(con) -> None:
    """Apply versioned SQL migrations in order (idempotent)."""
    applied = _applied_versions(con)
    paths = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for path in paths:
        try:
            version = int(path.name.split("_", 1)[0])
        except ValueError as exc:
            raise ValueError(f"migration filename must start with digits: {path.name}") from exc
        if version in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        for statement in _split_sql(sql):
            con.execute(statement)
        con.execute(
            "INSERT INTO schema_migrations (version) VALUES (?) "
            "ON CONFLICT (version) DO NOTHING",
            [version],
        )


def _run_exists(con, run_id: str) -> bool:
    row = con.execute("SELECT 1 FROM runs WHERE run_id = ? LIMIT 1", [run_id]).fetchone()
    return row is not None


def _insert_record(con, record: dict[str, Any]) -> None:
    probe = record["probe"]
    con.execute(
        """
        INSERT INTO runs (
            run_id, ts_utc, graph_name, graph_sha256, git_commit,
            package_version, stress_ladder, survival_floor
        ) VALUES (?, ?, ?, ?, ?, ?, ?::JSON, ?)
        """,
        [
            record["run_id"],
            record["ts_utc"],
            record["graph_name"],
            record["graph_sha256"],
            record.get("git_commit"),
            record["package_version"],
            json.dumps(probe["stress_ladder"]),
            probe.get("survival_floor"),
        ],
    )
    for m in record["metrics"]:
        con.execute(
            """
            INSERT INTO metric_results (
                run_id, metric, metric_version, value, status, drivers
            ) VALUES (?, ?, ?, ?, ?, ?::JSON)
            """,
            [
                record["run_id"],
                m["metric"],
                m["version"],
                float(m["value"]),
                m["status"],
                json.dumps(list(m["drivers"])),
            ],
        )


def load(
    paths: list[str | Path],
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Validate and append run-record JSON files into DuckDB.

    Returns the number of newly inserted runs. Existing ``run_id`` rows are
    skipped (idempotent). Each file must validate against run_record.v1.
    """
    con = _connect(Path(db_path))
    try:
        migrate(con)
        inserted = 0
        for raw_path in paths:
            path = Path(raw_path)
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"{path}: run record must be a JSON object")
            record = validate_run_record(data)
            if _run_exists(con, record["run_id"]):
                continue
            _insert_record(con, record)
            inserted += 1
        return inserted
    finally:
        con.close()
