"""Saved analytical SQL under docs/queries/ must stay executable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from metrics.run_record import build_run_record, validate_run_record
from metrics.store import load as store_load

QUERIES_DIR = Path(__file__).resolve().parents[2] / "docs" / "queries"

NON_DESTRUCTIVE = (
    "compare_runs.sql",
    "latest_run.sql",
    "status_changes.sql",
)

DESTRUCTIVE = "cleanup_untagged.sql"


def _strip_full_line_comments(sql: str) -> str:
    lines: list[str] = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


@pytest.fixture
def two_chillco_runs_db(tmp_path: Path, examples_dir: Path) -> Path:
    """Temp DuckDB with two chillco runs so compare / status queries have data."""
    graph_path = examples_dir / "one_route.yaml"
    paths: list[Path] = []
    for i in range(2):
        record = build_run_record(
            graph_path=graph_path,
            stress_ladder=True,
            client_id="chillco",
        )
        validate_run_record(record)
        # Flip one status on the second run so status_changes.sql can return a row.
        if i == 1:
            for m in record["metrics"]:
                if m["metric"] == "hhi":
                    m["status"] = "red" if m["status"] != "red" else "amber"
                    break
            validate_run_record(record)
        path = tmp_path / f"chillco_run_{i}.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        paths.append(path)

    db = tmp_path / "aegis_runs.duckdb"
    assert store_load(paths, db_path=db) == 2
    return db


def test_saved_query_files_exist():
    assert QUERIES_DIR.is_dir()
    for name in (*NON_DESTRUCTIVE, DESTRUCTIVE):
        path = QUERIES_DIR / name
        assert path.is_file(), f"missing {path}"
        text = path.read_text(encoding="utf-8")
        assert text.lstrip().startswith("--"), f"{name} should start with a header comment"
        assert "client" in text.lower()


def test_cleanup_untagged_is_marked_destructive():
    text = (QUERIES_DIR / DESTRUCTIVE).read_text(encoding="utf-8")
    assert "DESTRUCTIVE" in text
    assert "DELETE FROM metric_results" in text
    assert "DELETE FROM runs" in text
    assert "client_id IS NULL" in text


@pytest.mark.parametrize("filename", NON_DESTRUCTIVE)
def test_non_destructive_saved_queries_execute(two_chillco_runs_db: Path, filename: str):
    import duckdb

    sql_path = QUERIES_DIR / filename
    sql = _strip_full_line_comments(sql_path.read_text(encoding="utf-8"))
    assert sql, f"{filename} has no executable SQL after stripping comments"
    assert "DELETE" not in sql.upper()

    con = duckdb.connect(str(two_chillco_runs_db))
    try:
        rows = con.execute(sql).fetchall()
        if filename == "latest_run.sql":
            assert rows, "latest_run should return metric rows"
            # drivers column is last in the SELECT list
            assert rows[0][-1] is not None
        if filename == "compare_runs.sql":
            assert rows, "compare_runs should return one row per metric"
        if filename == "status_changes.sql":
            assert any(r[5] == "hhi" for r in rows), "expected hhi status flip"
    finally:
        con.close()
