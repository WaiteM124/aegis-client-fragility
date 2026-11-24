"""Run every structural-fragility metric and print grouped results.

Groups
------
  Concentration — HHI, monoculture
  Contagion     — single points of failure, cascade depth
  Convexity     — convexity, ruin
  Optionality   — optionality, slack

Each group shows the status of its **worst** metric (red > amber > green).
Ruin forces the Convexity group (and the ruin line) to red.

No weighted or blended single score is produced. Averaging would hide
danger and the units differ across metrics.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

import networkx as nx

from metrics import cascade_depth, convexity, hhi, monoculture, optionality, ruin, slack
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

_RANK = {Status.GREEN: 0, Status.AMBER: 1, Status.RED: 2}


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
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    if args.survival_floor is not None:
        scenario = scenario.model_copy(update={"survival_floor": args.survival_floor})
    print(format_grouped(run_all(graph, scenario)))


if __name__ == "__main__":
    main()
