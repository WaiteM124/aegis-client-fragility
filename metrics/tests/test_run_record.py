"""Run-record schema, --out JSON, and DuckDB store round-trips."""

from __future__ import annotations

import json

import pytest

from metrics.run_record import (
    PACKAGE_VERSION,
    SCHEMA_PATH,
    build_run_record,
    validate_run_record,
)
from metrics.store import DEFAULT_DB_PATH
from metrics.store import load as store_load


def test_schema_file_exists():
    assert SCHEMA_PATH.is_file()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$id"].endswith("run_record.v1.json")
    assert "run_id" in schema["required"]
    from metrics.run_record import SCHEMA_PATH_V2

    assert SCHEMA_PATH_V2.is_file()
    v2 = json.loads(SCHEMA_PATH_V2.read_text(encoding="utf-8"))
    assert "client_id" in v2["required"]


def test_build_and_validate_run_record(tmp_path, examples_dir):
    graph_path = examples_dir / "hidden_shared_subtier.yaml"
    record = build_run_record(
        graph_path=graph_path,
        stress_ladder=True,
        survival_floor=0.5,
    )
    validate_run_record(record)
    assert record["schema_version"] == "run_record.v1"
    assert record["graph_name"] == "hidden_shared_subtier"
    assert len(record["graph_sha256"]) == 64
    assert record["package_version"] == PACKAGE_VERSION
    assert "metrics" in record and len(record["metrics"]) >= 8
    for m in record["metrics"]:
        assert {"metric", "version", "value", "status", "drivers"} <= set(m)
    assert record["probe"]["stress_ladder"] is True
    assert record["probe"]["survival_floor"] == 0.5


def test_invalid_record_rejected():
    with pytest.raises(Exception):
        validate_run_record({"run_id": "x"})  # missing required fields


def test_run_all_out_writes_json(tmp_path, examples_dir):
    from metrics.run_all import main

    out = tmp_path / "run.json"
    main(
        [
            "--graph",
            str(examples_dir / "one_route.yaml"),
            "--stress-ladder",
            "--out",
            str(out),
        ]
    )
    assert out.is_file()
    record = json.loads(out.read_text(encoding="utf-8"))
    validate_run_record(record)


def test_duckdb_round_trip_idempotent(tmp_path, examples_dir):
    graph_path = examples_dir / "one_route.yaml"
    record = build_run_record(graph_path=graph_path, stress_ladder=True)
    validate_run_record(record)
    assert record["schema_version"] == "run_record.v1"
    assert "client_id" not in record
    json_path = tmp_path / "rec.json"
    json_path.write_text(json.dumps(record), encoding="utf-8")

    db = tmp_path / "test_runs.duckdb"
    n1 = store_load([json_path], db_path=db)
    assert n1 == 1
    n2 = store_load([json_path], db_path=db)
    assert n2 == 0  # duplicate run_id ignored

    import duckdb

    con = duckdb.connect(str(db))
    runs = con.execute("SELECT run_id, graph_name, client_id FROM runs").fetchall()
    assert len(runs) == 1
    assert runs[0][0] == record["run_id"]
    assert runs[0][2] is None  # v1 loads with NULL client_id
    metrics = con.execute(
        "SELECT COUNT(*) FROM metric_results WHERE run_id = ?", [record["run_id"]]
    ).fetchone()[0]
    assert metrics == len(record["metrics"])
    con.close()


def test_duckdb_loads_v1_and_v2(tmp_path, examples_dir):
    graph_path = examples_dir / "one_route.yaml"
    v1 = build_run_record(graph_path=graph_path, stress_ladder=True)
    v2 = build_run_record(
        graph_path=graph_path, stress_ladder=True, client_id="chillco"
    )
    validate_run_record(v1)
    validate_run_record(v2)
    p1 = tmp_path / "v1.json"
    p2 = tmp_path / "v2.json"
    p1.write_text(json.dumps(v1), encoding="utf-8")
    p2.write_text(json.dumps(v2), encoding="utf-8")
    db = tmp_path / "both.duckdb"
    assert store_load([p1, p2], db_path=db) == 2

    import duckdb

    con = duckdb.connect(str(db))
    rows = {
        r[0]: r[1]
        for r in con.execute("SELECT run_id, client_id FROM runs").fetchall()
    }
    assert rows[v1["run_id"]] is None
    assert rows[v2["run_id"]] == "chillco"
    con.close()


def test_duckdb_rejects_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"run_id": "only"}), encoding="utf-8")
    db = tmp_path / "bad.duckdb"
    with pytest.raises(Exception):
        store_load([bad], db_path=db)


def test_default_db_path_is_gitignored():
    # Documented default; actual file may not exist yet.
    assert DEFAULT_DB_PATH.name == "aegis_runs.duckdb"
    assert "data" in DEFAULT_DB_PATH.parts
