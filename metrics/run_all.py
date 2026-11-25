"""Run every structural-fragility metric and print grouped results.

Groups
------
  Concentration — HHI, monoculture
  Contagion     — single points of failure, cascade depth
  Convexity     — convexity, ruin, distance_to_ruin
  Optionality   — optionality, slack

Each group shows the status of its **worst** metric
(red > amber > not_tested > green). Ruin forces the Convexity group
(and the ruin line) to red. NOT_TESTED is never counted as a pass.

No weighted or blended single score is produced. Averaging would hide
danger and the units differ across metrics.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

import networkx as nx

from metrics import (
    cascade_depth,
    convexity,
    distance_to_ruin,
    hhi,
    monoculture,
    optionality,
    ruin,
    slack,
)
from metrics import single_points_of_failure as spof
from metrics.cli_utils import add_common_args, load_graph_and_scenario
from metrics.contracts import MetricResult, Scenario, Status

GROUPS: list[tuple[str, list[tuple[str, Callable[..., MetricResult]]]]] = [
    (
        "Concentration",
        [
            ("HHI", hhi.compute),
            ("Monoculture", monoculture.compute),
        ],
    ),
    (
        "Contagion",
        [
            ("Single points of failure", spof.compute),
            ("Cascade depth", cascade_depth.compute),
        ],
    ),
    (
        "Convexity",
        [
            ("Convexity", convexity.compute),
            ("Ruin", ruin.compute),
            ("Distance to ruin", distance_to_ruin.compute),
        ],
    ),
    (
        "Optionality",
        [
            ("Optionality", optionality.compute),
            ("Slack", slack.compute),
        ],
    ),
]

# NOT_TESTED outranks GREEN so an untested probe cannot look like a pass.
_RANK = {
    Status.GREEN: 0,
    Status.NOT_TESTED: 1,
    Status.AMBER: 2,
    Status.RED: 3,
}


def worst_status(results: list[MetricResult], *, ruin_forces_red: bool = False) -> Status:
    status = Status.GREEN
    for r in results:
        if _RANK[r.status] > _RANK[status]:
            status = r.status
        if ruin_forces_red and r.metric == "ruin" and r.status == Status.RED:
            return Status.RED
    return status


def run_all(graph: nx.DiGraph, scenario: Scenario | None = None) -> dict[str, list[MetricResult]]:
    scenario = scenario or Scenario()
    out: dict[str, list[MetricResult]] = {}
    for group_name, metrics in GROUPS:
        out[group_name] = [fn(graph, scenario) for _label, fn in metrics]
    return out


def format_grouped(results: dict[str, list[MetricResult]]) -> str:
    lines: list[str] = []
    lines.append("Aegis structural-fragility metrics")
    lines.append("No forecast — structural weaknesses only. No blended score.")
    lines.append("")
    for group_name, _ in GROUPS:
        group_results = results[group_name]
        force = group_name == "Convexity"
        group_status = worst_status(group_results, ruin_forces_red=force)
        lines.append(f"=== {group_name}  [{group_status.value.upper()}] ===")
        for r in group_results:
            lines.append(
                f"  - {r.metric:24s}  value={r.value:<12}  status={r.status.value.upper()}"
            )
            if r.drivers:
                lines.append(f"      drivers: {', '.join(r.drivers)}")
            if r.status == Status.NOT_TESTED and r.meaning:
                # Surface the not-tested reason plainly
                reason = r.inputs.get("reason") if r.inputs else None
                if reason:
                    lines.append(f"      reason: {reason}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run all Aegis structural-fragility metrics (no blended score)."
    )
    add_common_args(parser)
    parser.add_argument(
        "--survival-floor",
        type=float,
        default=None,
        metavar="FRAC",
        help=(
            "Ruin when remaining flow < FRAC × baseline at any ladder rung. "
            "Overrides graph YAML and the default (0.5)."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write one JSON run record (run_record.v1) to PATH.",
    )
    parser.add_argument(
        "--store",
        nargs="?",
        const="data/aegis_runs.duckdb",
        default=None,
        metavar="DB",
        help=(
            "Write a run record and load it into local DuckDB (default "
            "data/aegis_runs.duckdb). Implies a temp JSON if --out is omitted."
        ),
    )
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    # --stress-ladder is on common args and already folded into scenario
    if args.survival_floor is not None:
        scenario = scenario.model_copy(update={"survival_floor": args.survival_floor})

    results = run_all(graph, scenario)
    print(format_grouped(results))

    if args.out is None and args.store is None:
        return

    from metrics.run_record import build_run_record, write_run_record
    from metrics.store import load as store_load

    stress: bool | list[float]
    if scenario.stress_ladder is not None:
        stress = list(scenario.stress_ladder)
    else:
        stress = bool(scenario.run_stress_ladder)

    record = build_run_record(
        graph_path=args.graph,
        scenario=scenario,
        stress_ladder=stress if stress else False,
        survival_floor=scenario.survival_floor,
    )

    out_path = args.out
    if out_path is None and args.store is not None:
        # Persist alongside the DB so --store alone still leaves a JSON artifact.
        out_path = Path(args.store).with_suffix(".last_run.json")
    assert out_path is not None
    write_run_record(record, out_path)

    if args.store is not None:
        inserted = store_load([out_path], db_path=Path(args.store))
        print(f"run record → {out_path} (stored={inserted} new row(s) in {args.store})")
    else:
        print(f"run record → {out_path}")


if __name__ == "__main__":
    main()
