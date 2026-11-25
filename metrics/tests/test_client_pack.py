"""Client pack schemas, cut-off guard, confidential guard, --client / --lock."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from metrics.client_pack import (
    CLIENTS_ROOT,
    BacktestCutOffError,
    ConfidentialPayloadError,
    LockExistsError,
    assert_no_confidential_payloads,
    check_backtest_cut_off,
    list_model_paths,
    load_client,
    load_sources_manifest,
    lock_map,
    validate_client,
    validate_sources_manifest,
)
from metrics.run_record import SCHEMA_VERSION_V2, build_run_record, validate_run_record


def test_client_and_sources_schemas_validate_chillco_and_carillion():
    chillco = load_client("chillco")
    assert chillco["kind"] == "example"
    assert chillco["data_classification"] == "example"
    assert "made-up" in (chillco.get("notes") or "").lower() or "EXAMPLE" in chillco["display_name"]

    carillion = load_client("carillion")
    assert carillion["kind"] == "backtest"
    assert carillion["data_classification"] == "public"
    assert carillion["cut_off_date"] == "2017-03-01"

    for cid in ("chillco", "carillion"):
        validate_sources_manifest(load_sources_manifest(cid))


def test_invalid_client_yaml_rejected():
    with pytest.raises(Exception):
        validate_client({"id": "x"})  # missing required fields


def test_backtest_requires_cut_off_date():
    with pytest.raises(Exception):
        validate_client(
            {
                "id": "x",
                "display_name": "X",
                "kind": "backtest",
                "data_classification": "public",
            }
        )


def test_backtest_cut_off_rejects_late_source():
    client = {
        "id": "carillion",
        "display_name": "Carillion",
        "kind": "backtest",
        "data_classification": "public",
        "cut_off_date": "2017-03-01",
    }
    validate_client(client)
    manifest = {
        "schema_version": "sources_manifest.v1",
        "sources": [
            {
                "id": "late",
                "title": "After cut-off",
                "publisher": "Example",
                "publication_date": "2017-03-02",
                "url": "https://example.com/late",
            }
        ],
    }
    validate_sources_manifest(manifest)
    with pytest.raises(BacktestCutOffError):
        check_backtest_cut_off(client, manifest)


def test_backtest_cut_off_allows_on_or_before():
    client = load_client("carillion")
    manifest = {
        "schema_version": "sources_manifest.v1",
        "sources": [
            {
                "id": "ok",
                "title": "On cut-off",
                "publisher": "Example",
                "publication_date": "2017-03-01",
                "url": "https://example.com/ok",
            }
        ],
    }
    validate_sources_manifest(manifest)
    check_backtest_cut_off(client, manifest)  # does not raise


def test_chillco_model_lives_under_clients():
    models = list_model_paths("chillco")
    assert len(models) == 1
    assert models[0].name == "chillco.yaml"
    assert "clients" in models[0].parts
    assert not (Path("metrics/examples/chillco.yaml")).exists()


def test_carillion_has_no_model_numbers():
    assert list_model_paths("carillion") == []
    model_dir = CLIENTS_ROOT / "carillion" / "model"
    assert model_dir.is_dir()
    for p in model_dir.iterdir():
        assert p.name.startswith(".") or p.name == ".gitkeep"


def test_confidential_guard_flags_tracked_payload(tmp_path, monkeypatch):
    # Build a fake clients tree with a confidential pack and a tracked file.
    clients = tmp_path / "clients"
    conf = clients / "secretco"
    (conf / "sources").mkdir(parents=True)
    (conf / "model").mkdir()
    (conf / "client.yaml").write_text(
        yaml.dump(
            {
                "id": "secretco",
                "display_name": "Secret Co",
                "kind": "live",
                "data_classification": "confidential",
            }
        ),
        encoding="utf-8",
    )
    payload = conf / "model" / "graph.yaml"
    payload.write_text("name: secret\nnodes: []\nedges: []\n", encoding="utf-8")

    # Simulate git ls-files returning the payload path.
    def fake_tracked(rel_prefix: str, *, repo_root: Path):
        if "secretco/model" in rel_prefix.replace("\\", "/"):
            return [Path("clients/secretco/model/graph.yaml")]
        return []

    monkeypatch.setattr(
        "metrics.client_pack._tracked_paths_under",
        fake_tracked,
    )
    with pytest.raises(ConfidentialPayloadError):
        assert_no_confidential_payloads(root=clients)


def test_confidential_guard_ok_for_repo_clients():
    # chillco / carillion are not confidential; should pass.
    assert_no_confidential_payloads()


def test_lock_map_writes_date_stamped_and_refuses_overwrite(tmp_path):
    clients = tmp_path / "clients"
    cid = "chillco"
    pack = clients / cid
    (pack / "maps").mkdir(parents=True)
    (pack / "client.yaml").write_text(
        yaml.dump(
            {
                "id": cid,
                "display_name": "ChillCo",
                "kind": "example",
                "data_classification": "example",
            }
        ),
        encoding="utf-8",
    )
    record = {
        "schema_version": "run_record.v2",
        "run_id": "r1",
        "ts_utc": "2026-11-25T10:00:00.000Z",
        "client_id": cid,
        "graph_name": "chillco",
        "graph_sha256": "a" * 64,
        "git_commit": None,
        "package_version": "0.1.0",
        "probe": {"stress_ladder": True, "survival_floor": 0.5},
        "metrics": [
            {
                "metric": "hhi",
                "version": "1",
                "value": 0.1,
                "status": "green",
                "drivers": [],
            }
        ],
    }
    validate_run_record(record)
    rec_path = tmp_path / "run.json"
    rec_path.write_text(json.dumps(record), encoding="utf-8")
    stamp = datetime(2026, 11, 25, 12, 0, 0, tzinfo=UTC)
    a, b = lock_map(
        client_id=cid,
        record_path=rec_path,
        output_text="hello\n",
        stamp=stamp,
        root=clients,
    )
    assert a.exists() and b.exists()
    assert "2026-11-25T120000Z" in a.name
    with pytest.raises(LockExistsError):
        lock_map(
            client_id=cid,
            record_path=rec_path,
            output_text="hello\n",
            stamp=stamp,
            root=clients,
        )


def test_run_all_client_writes_v2_record_to_runs(tmp_path, monkeypatch):
    from metrics.run_all import main

    # Redirect client runs dir via writing into real chillco runs (gitignored).
    # Use --out under tmp and --client chillco; also verify schema v2.
    out = tmp_path / "forced.json"
    db = tmp_path / "runs.duckdb"
    main(
        [
            "--client",
            "chillco",
            "--stress-ladder",
            "--out",
            str(out),
            "--store",
            str(db),
        ]
    )
    assert out.is_file()
    record = json.loads(out.read_text(encoding="utf-8"))
    validate_run_record(record)
    assert record["schema_version"] == SCHEMA_VERSION_V2
    assert record["client_id"] == "chillco"

    import duckdb

    con = duckdb.connect(str(db))
    row = con.execute(
        "SELECT client_id, graph_name FROM runs WHERE run_id = ?",
        [record["run_id"]],
    ).fetchone()
    assert row is not None
    assert row[0] == "chillco"
    con.close()


def test_build_run_record_v2_with_client_id():
    graph = CLIENTS_ROOT / "chillco" / "model" / "chillco.yaml"
    record = build_run_record(
        graph_path=graph,
        client_id="chillco",
        stress_ladder=True,
    )
    validate_run_record(record)
    assert record["schema_version"] == SCHEMA_VERSION_V2
    assert record["client_id"] == "chillco"
