"""Ruin: whether any rung of the stress ladder crosses a point of no return.

Formula
-------
Using the same stress ladder as convexity (δ ∈ {0.10, 0.20, 0.50}):

    F₀ = deliverable inbound flow to the client
    F(δ) = deliverable flow after structural stress at intensity δ

Survival floor resolution (first match wins):

    1. ``scenario.survival_floor`` (also set by CLI ``--survival-floor``)
    2. graph YAML / ``graph.graph["survival_floor"]`` (client-level override)
    3. ``thresholds.ruin.survival_floor`` (documented default **0.5**)

Ruin iff any δ in the ladder satisfies:

    F(δ) < floor × F₀     when F₀ > 0
    or F₀ ≤ 0             (no deliverable baseline)

Strict inequality: remaining exactly equal to the floor is not ruin.
A 60% loss (remaining 40%) triggers at floor 0.5; a 40% loss does not.

Value = 1.0 if ruin, else 0.0.

Meaning
-------
Ruin is a hard structural red flag: under the stress ladder, deliverable
flow falls below the client's survival floor (point of no return). The
default floor is half of baseline because a client is usually finished
well before total loss. This is not a probability of ruin — it flags that
the graph's flow accounting admits a below-floor state at a listed stress
intensity.

Status
------
  red    if ruin
  green  otherwise

``run_all`` forces the Convexity group to red whenever ruin is red.
"""

from __future__ import annotations

import argparse

import networkx as nx

from metrics.contracts import MetricResult, Scenario, Status
from metrics.graph_loader import apply_edge_shock, apply_node_shock
from metrics.stress import ensure_flow, stress_ladder_losses
from metrics.thresholds import STRESS_LADDER, THRESHOLDS, Thresholds

METRIC = "ruin"
VERSION = "1.1.0"


def resolve_survival_floor(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
) -> float:
    """Resolve survival floor: scenario → graph YAML → thresholds default."""
    thresholds = thresholds or THRESHOLDS
    if scenario is not None and scenario.survival_floor is not None:
        return float(scenario.survival_floor)
    graph_floor = graph.graph.get("survival_floor")
    if graph_floor is not None:
        return float(graph_floor)
    return float(thresholds.ruin.survival_floor)


def compute(
    graph: nx.DiGraph,
    scenario: Scenario | None = None,
    thresholds: Thresholds | None = None,
    ladder: tuple[float, ...] = STRESS_LADDER,
) -> MetricResult:
    thresholds = thresholds or THRESHOLDS
    floor = resolve_survival_floor(graph, scenario, thresholds)

    g = graph
    if scenario is not None:
        for ns in scenario.node_shocks:
            if ns.node_id in g:
                g = apply_node_shock(g, ns.node_id, ns.intensity)
        for es in scenario.edge_shocks:
            if g.has_edge(es.source, es.target):
                g = apply_edge_shock(g, es.source, es.target, es.intensity)

    g = ensure_flow(g)
    f0, remaining, losses = stress_ladder_losses(g, ladder)

    crossed: list[str] = []
    if f0 <= 0:
        crossed = [f"delta={d}" for d in ladder]
    else:
        threshold_flow = floor * f0
        for delta, f in remaining.items():
            if f < threshold_flow:
                crossed.append(f"delta={delta}")

    is_ruin = len(crossed) > 0
    return MetricResult(
        metric=METRIC,
        version=VERSION,
        value=1.0 if is_ruin else 0.0,
        status=Status.RED if is_ruin else Status.GREEN,
        drivers=crossed if is_ruin else [],
        inputs={
            "F0": f0,
            "remaining": {str(k): v for k, v in remaining.items()},
            "losses": {str(k): v for k, v in losses.items()},
            "survival_floor": floor,
            "threshold_flow": floor * f0 if f0 > 0 else 0.0,
            "crossed_rungs": crossed,
        },
        meaning=(
            ("RUIN: a stress-ladder rung fell below the survival floor. ")
            if is_ruin
            else "No ladder rung fell below the survival floor. "
        )
        + f"Floor={floor:.2f} of baseline. Hard structural flag — not a probability of ruin.",
        unit="flag",
    )


def main(argv: list[str] | None = None) -> None:
    from metrics.cli_utils import add_common_args, load_graph_and_scenario

    parser = argparse.ArgumentParser(description="Detect structural ruin on the stress ladder.")
    add_common_args(parser)
    parser.add_argument(
        "--survival-floor",
        type=float,
        default=None,
        metavar="FRAC",
        help=(
            "Ruin when remaining flow < FRAC × baseline F0 at any ladder rung. "
            "Overrides graph YAML and the default (0.5 in metrics.thresholds)."
        ),
    )
    args = parser.parse_args(argv)
    graph, scenario = load_graph_and_scenario(args)
    if args.survival_floor is not None:
        scenario = scenario.model_copy(update={"survival_floor": args.survival_floor})
    print(compute(graph, scenario).format_readable())


if __name__ == "__main__":
    main()
