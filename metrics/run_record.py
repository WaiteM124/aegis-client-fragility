"""Build and validate versioned JSON run records for metrics.run_all.

Records capture one structural-fragility run for later analysis. They do
not store forecasts, probabilities, or a blended fragility score.

Schema versions
---------------
- ``run_record.v1`` — original shape (still loadable into DuckDB).
- ``run_record.v2`` — adds required ``client_id`` for per-client packs.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from metrics.contracts import Scenario
from metrics.graph_loader import load_graph
from metrics.thresholds import THRESHOLDS

SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"
SCHEMA_PATH_V1 = SCHEMAS_DIR / "run_record.v1.json"
SCHEMA_PATH_V2 = SCHEMAS_DIR / "run_record.v2.json"
# Back-compat alias used by older tests / docs.
SCHEMA_PATH = SCHEMA_PATH_V1
SCHEMA_VERSION_V1 = "run_record.v1"
SCHEMA_VERSION_V2 = "run_record.v2"
SCHEMA_VERSION = SCHEMA_VERSION_V1

# Align with pyproject.toml [project].version until a dedicated metrics
# package version is split out.
PACKAGE_VERSION = "0.1.0"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).resolve().parents[1],
            text=True,
        )
        commit = out.strip()
        return commit or None
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def load_schema(version: str = SCHEMA_VERSION_V1) -> dict[str, Any]:
    if version == SCHEMA_VERSION_V2:
        path = SCHEMA_PATH_V2
    elif version == SCHEMA_VERSION_V1:
        path = SCHEMA_PATH_V1
    else:
        raise ValueError(f"unknown run record schema version: {version!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_run_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate against v1 or v2 schema; raise on failure; return record."""
    import jsonschema

    version = record.get("schema_version")
    if version == SCHEMA_VERSION_V2:
        schema = load_schema(SCHEMA_VERSION_V2)
    elif version == SCHEMA_VERSION_V1:
        schema = load_schema(SCHEMA_VERSION_V1)
    else:
        # Try v1 then v2 for clearer errors on missing schema_version.
        schema = load_schema(SCHEMA_VERSION_V1)
    jsonschema.validate(
        instance=record,
        schema=schema,
        format_checker=jsonschema.FormatChecker(),
    )
    return record


def build_run_record(
    graph_path: str | Path,
    *,
    scenario: Scenario | None = None,
    stress_ladder: bool | list[float] | None = None,
    survival_floor: float | None = None,
    run_id: str | None = None,
    ts_utc: datetime | None = None,
    client_id: str | None = None,
    method_tag: str | None = None,
) -> dict[str, Any]:
    """Run all metrics and assemble a schema-validatable run record.

    When ``client_id`` is set, emits ``run_record.v2``; otherwise ``v1``.
    ``method_tag`` is recorded on v2 when set (locked backtest maps).
    """
    # Local import avoids a circular dependency with metrics.run_all.
    from metrics.run_all import run_all

    path = Path(graph_path)
    graph = load_graph(path)
    scenario = scenario or Scenario()

    if stress_ladder is True:
        scenario = scenario.model_copy(update={"run_stress_ladder": True})
    elif isinstance(stress_ladder, list):
        scenario = scenario.model_copy(
            update={"run_stress_ladder": True, "stress_ladder": list(stress_ladder)}
        )

    if survival_floor is not None:
        scenario = scenario.model_copy(update={"survival_floor": survival_floor})

    grouped = run_all(graph, scenario)
    metric_rows: list[dict[str, Any]] = []
    for _group, results in grouped.items():
        for r in results:
            metric_rows.append(
                {
                    "metric": r.metric,
                    "version": r.version,
                    "value": float(r.value),
                    "status": r.status.value,
                    "drivers": list(r.drivers),
                }
            )

    # Effective probe settings as recorded (not forecasts).
    floor = scenario.survival_floor
    if floor is None:
        floor = graph.graph.get("survival_floor")
    if floor is None:
        ruin_line = graph.graph.get("ruin_line") or {}
        if isinstance(ruin_line, dict):
            floor = ruin_line.get("survival_floor")
    if floor is None:
        floor = THRESHOLDS.ruin.survival_floor

    if scenario.stress_ladder is not None:
        probe_ladder: bool | list[float] = list(scenario.stress_ladder)
    else:
        probe_ladder = bool(scenario.run_stress_ladder)

    ts = ts_utc or datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    else:
        ts = ts.astimezone(UTC)

    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION_V2 if client_id else SCHEMA_VERSION_V1,
        "run_id": run_id or str(uuid.uuid4()),
        "ts_utc": ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "graph_name": str(graph.graph.get("name") or path.stem),
        "graph_sha256": _sha256_file(path),
        "git_commit": _git_commit(),
        "package_version": PACKAGE_VERSION,
        "probe": {
            "stress_ladder": probe_ladder,
            "survival_floor": float(floor) if floor is not None else None,
        },
        "metrics": metric_rows,
    }
    if client_id is not None:
        record["client_id"] = client_id
    if method_tag is not None:
        if client_id is None:
            raise ValueError("method_tag requires client_id (run_record.v2)")
        record["method_tag"] = method_tag
    return record


def write_run_record(record: dict[str, Any], out_path: str | Path) -> Path:
    validate_run_record(record)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
